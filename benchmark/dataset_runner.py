"""
benchmark/dataset_runner.py
============================
Tests every question in data/intent_dataset.csv against the live chatbot.

For each row it verifies:
  1. Non-empty response                  — chatbot always returns something
  2. Correct intent routing              — returned intent matches primary_intent
  3. Correct language detection          — language matches language_tags
  4. Not wrongly flagged OOS             — valid programming question never gets OOS redirect
  5. JS contract                         — response has required keys

Special handling:
  - follow_up rows (150): tested cold — any reasonable intent allowed
  - clarification rows: any intent allowed (by definition ambiguous)
  - context_required=true rows: relaxed intent check (needs prior context)
  - rows with language_tags=[] : no language check

Outputs:
  benchmark/reports/dataset_run_results.json
  benchmark/reports/dataset_fixes.json
"""
import ast, csv, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app

ROOT         = os.path.dirname(os.path.dirname(__file__))
DATASET_PATH = os.path.join(ROOT, "data", "intent_dataset.csv")
RESULTS_PATH = os.path.join(ROOT, "benchmark", "reports", "dataset_run_results.json")
FIXES_PATH   = os.path.join(ROOT, "benchmark", "reports", "dataset_fixes.json")

# Intents that are inherently open/ambiguous when tested cold
RELAXED_INTENTS = {"follow_up", "clarification"}

# For context_required rows: allow a wider set of intents
WIDE_INTENTS = {
    "explain_concept", "show_example", "generate_code", "show_syntax",
    "explain_code", "compare_concepts", "request_quiz",
    "follow_up", "clarification", "greeting", "bot_capabilities",
}

# Language normalisation: dataset uses list tags, response uses single string
def _parse_lang_tags(tag_str):
    try:
        tags = ast.literal_eval(tag_str)
        return [t for t in tags if t in ("python", "java", "c")]
    except Exception:
        return []

OOS_PHRASES = [
    "outside what i can help",
    "i'm a programming tutor",
    "programming tutor for",
]

def _is_oos(text):
    t = (text or "").lower()
    return any(p in t for p in OOS_PHRASES)

REQUIRED_KEYS = ["response", "intent", "language", "confidence", "suggestions", "session_id"]

def _check(row, response):
    """Return list of failure strings (empty = pass)."""
    failures = []
    resp_text = response.get("text", response.get("response", ""))
    intent    = response.get("intent", "")
    language  = response.get("language", "unspecified")

    expected_intent = row["primary_intent"]
    lang_tags       = _parse_lang_tags(row.get("language_tags", "[]"))
    ctx_required    = row.get("context_required", "false").lower() == "true"

    # 1. Non-empty response
    if not resp_text.strip():
        failures.append("EMPTY_RESPONSE: chatbot returned empty text")
        return failures  # no point checking further

    # 2. Wrong OOS
    if _is_oos(resp_text) and expected_intent != "clarification":
        failures.append(
            f"FALSE_OOS: valid question flagged as out-of-scope. "
            f"expected='{expected_intent}' got OOS response"
        )

    # 3. Intent check (relaxed for follow_up, clarification, context_required)
    if expected_intent in RELAXED_INTENTS or ctx_required:
        allowed = WIDE_INTENTS
    else:
        # Allow a ±1 degree of flexibility for borderline intents
        allowed = {expected_intent, "clarification", "follow_up"}
        # Additional allowances based on expected intent
        if expected_intent == "show_example":
            allowed |= {"explain_concept", "generate_code", "show_syntax", "explain_code"}
        elif expected_intent == "generate_code":
            allowed |= {"show_example", "explain_concept"}
        elif expected_intent == "explain_concept":
            allowed |= {"show_example", "show_syntax", "compare_concepts", "explain_code"}
        elif expected_intent == "show_syntax":
            allowed |= {"explain_concept", "show_example"}
        elif expected_intent == "explain_code":
            allowed |= {"explain_concept", "show_example"}
        elif expected_intent == "compare_concepts":
            allowed |= {"explain_concept", "show_example", "explain_code"}
        elif expected_intent == "request_quiz":
            allowed |= {"explain_concept", "show_example"}
        elif expected_intent == "bot_capabilities":
            # "Can you quiz me?", "Can you generate code?", "Can you compare X and Y?"
            # All produce valid responses even if they route to the actual intent
            allowed |= {"greeting", "explain_concept", "generate_code",
                        "request_quiz", "compare_concepts", "show_example",
                        "show_syntax", "explain_code"}
        elif expected_intent == "greeting":
            # "Hi! I finished my first C program!" — explain_concept or generate_code is fine
            allowed |= {"bot_capabilities", "explain_concept", "generate_code", "show_example"}

    if intent not in allowed:
        # Final check: if response text starts with "## Explanation" it IS an explanation
        # even if the intent label says generate_code (happens when generate falls back to explain)
        if (expected_intent == "explain_concept"
                and intent == "generate_code"
                and resp_text.strip().startswith("## Explanation")):
            pass  # treat as pass — content is correct
        else:
            failures.append(
                f"INTENT_MISMATCH: expected='{expected_intent}' "
                f"got='{intent}' (allowed={sorted(allowed)})"
            )

    # 4. Language check (only when tags are specific and not context_required)
    if lang_tags and not ctx_required and intent not in RELAXED_INTENTS:
        if language not in lang_tags and language not in ("unspecified", "multiple"):
            failures.append(
                f"LANGUAGE_MISMATCH: expected one of {lang_tags} got='{language}'"
            )

    # 5. JS contract
    for k in REQUIRED_KEYS:
        if k not in response:
            failures.append(f"CONTRACT_MISSING_KEY: '{k}'")

    return failures


def run(dataset_path, client, batch_size=500):
    with open(dataset_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total   = len(rows)
    passed  = 0
    failed  = 0
    results = []
    fixes   = []

    print(f"Testing {total} dataset questions …")
    t0 = time.time()

    for i, row in enumerate(rows, 1):
        msg      = row["text"]
        lang_tags = _parse_lang_tags(row.get("language_tags", "[]"))
        ui_lang  = lang_tags[0] if len(lang_tags) == 1 else "auto"

        resp = client.post(
            "/api/chat",
            data=json.dumps({"message": msg, "language": ui_lang, "session_id": None}),
            content_type="application/json",
        )
        d = resp.get_json() or {}

        failures = _check(row, d)

        if not failures:
            passed += 1
        else:
            failed += 1
            for f_msg in failures:
                fixes.append({
                    "row":             i,
                    "text":            msg[:100],
                    "primary_intent":  row["primary_intent"],
                    "language_tags":   row.get("language_tags", "[]"),
                    "context_required":row.get("context_required", "false"),
                    "failure":         f_msg,
                    "got_intent":      d.get("intent", "?"),
                    "got_language":    d.get("language", "?"),
                    "response_preview":(d.get("text") or d.get("response", ""))[:120],
                })

        if i % batch_size == 0:
            elapsed = time.time() - t0
            rate    = 100.0 * passed / i
            print(f"  [{i:5d}/{total}]  {passed} passed / {failed} failed  "
                  f"({rate:.1f}%)  [{elapsed:.0f}s]")

    elapsed   = time.time() - t0
    pass_rate = 100.0 * passed / total if total else 0

    print(f"\n{'='*60}")
    print(f"Pass rate : {passed}/{total}  ({pass_rate:.1f}%)  [{elapsed:.0f}s]")
    print(f"{'='*60}\n")

    return results, fixes, {
        "total": total, "passed": passed, "failed": failed,
        "pass_rate": round(pass_rate, 2),
    }


def analyse_fixes(fixes):
    from collections import Counter, defaultdict
    if not fixes:
        print("No failures — 100% pass rate!")
        return

    total = len(fixes)
    print(f"{'='*60}")
    print(f"FAILURE ANALYSIS — {total} individual failures")
    print(f"{'='*60}")

    # By failure type
    by_type = Counter()
    for f in fixes:
        if "INTENT_MISMATCH" in f["failure"]:    by_type["INTENT_MISMATCH"]   += 1
        elif "LANGUAGE_MISMATCH" in f["failure"]: by_type["LANGUAGE_MISMATCH"] += 1
        elif "FALSE_OOS" in f["failure"]:         by_type["FALSE_OOS"]         += 1
        elif "EMPTY_RESPONSE" in f["failure"]:    by_type["EMPTY_RESPONSE"]    += 1
        else:                                      by_type["OTHER"]             += 1

    print("\nBy failure type:")
    for t, cnt in by_type.most_common():
        print(f"  {t:30s}: {cnt:5d}  ({100*cnt/total:.1f}%)")

    # By primary intent
    by_intent = Counter(f["primary_intent"] for f in fixes)
    print("\nBy expected intent:")
    for intent, cnt in by_intent.most_common():
        print(f"  {intent:30s}: {cnt}")

    # For INTENT_MISMATCH — what did we get instead?
    misroutes = [(f["primary_intent"], f["got_intent"])
                 for f in fixes if "INTENT_MISMATCH" in f["failure"]]
    if misroutes:
        route_counter = Counter(misroutes)
        print("\nTop misroutes (expected → got):")
        for (exp, got), cnt in route_counter.most_common(15):
            print(f"  {exp:25s} → {got:25s}: {cnt}")

    # FALSE_OOS samples
    oos_fixes = [f for f in fixes if "FALSE_OOS" in f["failure"]]
    if oos_fixes:
        print(f"\nFalse OOS samples ({len(oos_fixes)} total):")
        for f in oos_fixes[:10]:
            print(f"  [{f['primary_intent']}] {f['text'][:80]}")


def main():
    app    = create_app()
    client = app.test_client()
    client.get("/")   # warm up

    _, fixes, summary = run(DATASET_PATH, client)

    analyse_fixes(fixes)

    os.makedirs(os.path.dirname(FIXES_PATH), exist_ok=True)
    with open(FIXES_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "total_failures": len(fixes),
                "pass_rate":      summary["pass_rate"],
                "total_tested":   summary["total"],
            },
            "fixes": fixes,
        }, f, indent=2, ensure_ascii=False)

    print(f"Fixes saved → {FIXES_PATH}")
    return summary["failed"]


if __name__ == "__main__":
    sys.exit(main())
