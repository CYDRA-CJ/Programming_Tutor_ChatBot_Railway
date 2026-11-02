"""
benchmark/failure_diagnostics.py
=================================
Reads benchmark/reports/actionable_fixes.json and produces:
  1. A human-readable console report grouped by root-cause category.
  2. A prioritised patch plan: which backend/frontend files need changes and why.

Root-cause categories (from e2e_runner.py):
  BACKEND_LOGIC_ERROR          — routing, intent, language, or topic mismatch
  OOS_GUARDRAIL_FAILURE        — OOS not detected OR valid query falsely blocked
  CONTEXT_MEMORY_DROP          — session state lost across turns
  KB_OR_TEMPLATE_GAP           — missing KB record / code example / template
  FRONTEND_JS_CONTRACT_MISMATCH — JSON key missing or wrong type

Usage:
    python benchmark/failure_diagnostics.py [--fixes benchmark/reports/actionable_fixes.json]
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

ROOT       = os.path.dirname(os.path.dirname(__file__))
FIXES_PATH = os.path.join(ROOT, "benchmark", "reports", "actionable_fixes.json")

# ── Root-cause → file ownership mapping ──────────────────────────────────────
OWNER_MAP = {
    "BACKEND_LOGIC_ERROR": [
        "app/routes/chat.py",
        "app/services/topic_resolver.py",
        "app/classifier/intent_classifier.py",
        "app/services/language_detector.py",
    ],
    "OOS_GUARDRAIL_FAILURE": [
        "app/services/scope_checker.py",
        "app/routes/chat.py",
        "app/services/response_formatter.py",
        "app/static/js/chat.js",
    ],
    "CONTEXT_MEMORY_DROP": [
        "app/conversation/context_manager.py",
        "app/routes/chat.py",
    ],
    "KB_OR_TEMPLATE_GAP": [
        "data/knowledge_base.json",
        "data/code_examples.json",
        "data/code_templates.json",
    ],
    "FRONTEND_JS_CONTRACT_MISMATCH": [
        "app/static/js/chat.js",
        "app/routes/chat.py",
    ],
}

SEVERITY_ORDER = [
    "OOS_GUARDRAIL_FAILURE",
    "CONTEXT_MEMORY_DROP",
    "BACKEND_LOGIC_ERROR",
    "KB_OR_TEMPLATE_GAP",
    "FRONTEND_JS_CONTRACT_MISMATCH",
]


def load_fixes(path: str) -> list:
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run e2e_runner.py first.")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fixes", [])


def analyse(fixes: list) -> dict:
    """Group failures by root-cause and scenario category."""
    by_root_cause  = defaultdict(list)
    by_category    = defaultdict(list)
    by_intent      = Counter()
    by_language    = Counter()

    for fix in fixes:
        rc = fix.get("root_cause", "BACKEND_LOGIC_ERROR")
        by_root_cause[rc].append(fix)
        by_category[fix.get("category", "?")].append(fix)
        if fix.get("intent"):
            by_intent[fix["intent"]] += 1
        if fix.get("language"):
            by_language[fix["language"]] += 1

    return {
        "by_root_cause": dict(by_root_cause),
        "by_category":   dict(by_category),
        "by_intent":     dict(by_intent),
        "by_language":   dict(by_language),
    }


def print_report(fixes: list, analysis: dict) -> None:
    total = len(fixes)
    print("=" * 70)
    print(f"FAILURE DIAGNOSTICS REPORT  —  {total} failures")
    print("=" * 70)

    if total == 0:
        print("\n✅ No failures. All scenarios passed.")
        return

    # ── Summary by root cause ─────────────────────────────────────────────────
    print("\n── FAILURES BY ROOT CAUSE ──────────────────────────────────────────")
    for rc in SEVERITY_ORDER:
        items = analysis["by_root_cause"].get(rc, [])
        if items:
            pct = 100.0 * len(items) / total
            print(f"  {rc:40s}: {len(items):4d}  ({pct:.1f}%)")

    # ── Summary by scenario category ─────────────────────────────────────────
    print("\n── FAILURES BY SCENARIO CATEGORY ───────────────────────────────────")
    for cat, items in sorted(analysis["by_category"].items(), key=lambda x: -len(x[1])):
        print(f"  {cat:35s}: {len(items):4d}")

    # ── Intent and language breakdown ─────────────────────────────────────────
    if analysis["by_intent"]:
        print("\n── MOST-FAILED INTENTS ─────────────────────────────────────────────")
        for intent, cnt in sorted(analysis["by_intent"].items(), key=lambda x: -x[1])[:10]:
            print(f"  {intent:30s}: {cnt}")

    # ── Detailed breakdown per root cause ─────────────────────────────────────
    print("\n── DETAILED FAILURES ───────────────────────────────────────────────")
    for rc in SEVERITY_ORDER:
        items = analysis["by_root_cause"].get(rc, [])
        if not items:
            continue
        print(f"\n  [{rc}]  ({len(items)} failures)")
        print(f"  Files to patch: {', '.join(OWNER_MAP.get(rc, ['?']))}")
        print()
        for item in items[:15]:   # show first 15 per category
            print(f"    Scenario : {item.get('scenario_id','?')}")
            print(f"    Turn     : {item.get('turn','?')}")
            print(f"    Message  : {item.get('message','?')[:70]}")
            print(f"    Failure  : {item.get('failure','?')[:120]}")
            if item.get("text_preview"):
                print(f"    Response : {item['text_preview'][:100]}")
            print()
        if len(items) > 15:
            print(f"    … and {len(items) - 15} more (see actionable_fixes.json for full list)\n")


def build_patch_plan(analysis: dict) -> list:
    """
    Produce a prioritised list of concrete file patches needed.
    Each entry describes what to check/change and in which file.
    """
    plan = []

    # OOS guardrail failures
    oos_failures = analysis["by_root_cause"].get("OOS_GUARDRAIL_FAILURE", [])
    if oos_failures:
        false_positives = [f for f in oos_failures if "falsely" in f.get("failure","").lower() or
                           "expected in-scope" in f.get("failure","").lower()]
        false_negatives = [f for f in oos_failures if "expected OOS" in f.get("failure","").lower() or
                           "not detected" in f.get("failure","").lower()]
        code_in_oos     = [f for f in oos_failures if "forbidden phrase" in f.get("failure","").lower()]

        if false_negatives:
            plan.append({
                "priority": 1,
                "file":     "app/services/scope_checker.py",
                "action":   "Expand OOS_SUBJECTS with phrases that the detector missed",
                "count":    len(false_negatives),
                "examples": [f["message"] for f in false_negatives[:5]],
            })
        if false_positives:
            plan.append({
                "priority": 1,
                "file":     "app/services/scope_checker.py",
                "action":   "Expand PROGRAMMING_SIGNALS so valid queries are not falsely blocked",
                "count":    len(false_positives),
                "examples": [f["message"] for f in false_positives[:5]],
            })
        if code_in_oos:
            plan.append({
                "priority": 1,
                "file":     "app/routes/chat.py",
                "action":   "OOS response contains real code — verify is_out_of_scope() fires before template engine",
                "count":    len(code_in_oos),
                "examples": [f["message"] for f in code_in_oos[:5]],
            })
        # OOS payload completeness
        plan.append({
            "priority": 1,
            "file":     "app/routes/chat.py",
            "action":   "Add is_out_of_scope:true, oos_image_url, suggested_topics to OOS response JSON",
            "count":    len(oos_failures),
            "examples": [],
        })
        plan.append({
            "priority": 2,
            "file":     "app/static/js/chat.js",
            "action":   "Render OOS card (image + message + suggested_topics chips) when r.is_out_of_scope===true",
            "count":    len(oos_failures),
            "examples": [],
        })

    # Context memory drops
    ctx_failures = analysis["by_root_cause"].get("CONTEXT_MEMORY_DROP", [])
    if ctx_failures:
        plan.append({
            "priority": 1,
            "file":     "app/conversation/context_manager.py",
            "action":   "Ensure record_answer() is preserved across OOS turns (already bypassed — verify ctx['last_answer'] not cleared)",
            "count":    len(ctx_failures),
            "examples": [f["message"] for f in ctx_failures[:5]],
        })

    # Backend logic errors
    be_failures = analysis["by_root_cause"].get("BACKEND_LOGIC_ERROR", [])
    if be_failures:
        # Deduplicate by scenario to find systemic patterns
        intent_failures = [f for f in be_failures if "intent" in f.get("failure","").lower()]
        lang_failures   = [f for f in be_failures if "language" in f.get("failure","").lower()]
        code_failures   = [f for f in be_failures if "code block" in f.get("failure","").lower()]
        if intent_failures:
            plan.append({
                "priority": 2,
                "file":     "app/routes/chat.py",
                "action":   "Fix intent routing (check _post_classify, CODE_REQUEST_PHRASES, SHOW_EXAMPLE_PHRASES)",
                "count":    len(intent_failures),
                "examples": [f["message"] for f in intent_failures[:5]],
            })
        if lang_failures:
            plan.append({
                "priority": 2,
                "file":     "app/services/language_detector.py",
                "action":   "Fix language detection for messages where the detected language is wrong",
                "count":    len(lang_failures),
                "examples": [f["message"] for f in lang_failures[:5]],
            })
        if code_failures:
            plan.append({
                "priority": 2,
                "file":     "app/knowledge/template_engine.py",
                "action":   "Generate/show code block for these queries — verify template exists and trigger_phrases match",
                "count":    len(code_failures),
                "examples": [f["message"] for f in code_failures[:5]],
            })

    # KB/template gaps
    kb_failures = analysis["by_root_cause"].get("KB_OR_TEMPLATE_GAP", [])
    if kb_failures:
        plan.append({
            "priority": 3,
            "file":     "data/code_templates.json or data/code_examples.json",
            "action":   "Add missing code blocks/templates for these generate_code / show_example queries",
            "count":    len(kb_failures),
            "examples": [f["message"] for f in kb_failures[:5]],
        })

    # Frontend JS contract mismatches
    js_failures = analysis["by_root_cause"].get("FRONTEND_JS_CONTRACT_MISMATCH", [])
    if js_failures:
        # Find which keys are missing
        missing_keys = Counter()
        for f in js_failures:
            failure_msg = f.get("failure", "")
            if "missing required key" in failure_msg:
                key = failure_msg.split("'")[1] if "'" in failure_msg else "?"
                missing_keys[key] += 1
        plan.append({
            "priority": 2,
            "file":     "app/routes/chat.py",
            "action":   f"Ensure response JSON always includes: {list(missing_keys.keys())}",
            "count":    len(js_failures),
            "examples": [],
        })

    plan.sort(key=lambda x: x["priority"])
    return plan


def print_patch_plan(plan: list) -> None:
    if not plan:
        return
    print("\n── PRIORITISED PATCH PLAN ──────────────────────────────────────────")
    for i, item in enumerate(plan, 1):
        print(f"\n  [{i}] Priority {item['priority']}  —  {item['file']}")
        print(f"      Action : {item['action']}")
        print(f"      Count  : {item['count']} failure(s)")
        if item.get("examples"):
            print(f"      Examples:")
            for ex in item["examples"][:3]:
                print(f"        - {ex[:80]}")


def main():
    parser = argparse.ArgumentParser(description="Analyse benchmark failures and produce a patch plan")
    parser.add_argument("--fixes", default=FIXES_PATH, help="Path to actionable_fixes.json")
    parser.add_argument("--json",  action="store_true",  help="Also print the patch plan as JSON")
    args = parser.parse_args()

    fixes    = load_fixes(args.fixes)
    analysis = analyse(fixes)
    print_report(fixes, analysis)
    plan     = build_patch_plan(analysis)
    print_patch_plan(plan)

    if args.json:
        print("\n── PATCH PLAN JSON ─────────────────────────────────────────────────")
        print(json.dumps(plan, indent=2))

    # Save updated fixes with patch plan appended
    with open(args.fixes, encoding="utf-8") as f:
        data = json.load(f)
    data["patch_plan"] = plan
    with open(args.fixes, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\nPatch plan saved → {args.fixes}")


if __name__ == "__main__":
    main()
