"""
benchmark/internal_runner.py
=============================
Runs the full benchmark using the Flask test client (no live server needed).
Much faster than e2e_runner.py — completes all 598 scenarios in ~60s.

Usage:
    python benchmark/internal_runner.py
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app

ROOT          = os.path.dirname(os.path.dirname(__file__))
SCENARIOS_PATH = os.path.join(ROOT, "benchmark", "data", "synthetic_scenarios.json")
RESULTS_PATH   = os.path.join(ROOT, "benchmark", "reports", "run_results.json")
FIXES_PATH     = os.path.join(ROOT, "benchmark", "reports", "actionable_fixes.json")

OOS_PHRASES = [
    "outside what i can help",
    "programming tutor",
    "i'm a programming tutor",
    "not within my scope",
    "outside my scope",
]

def _is_oos(text):
    t = text.lower()
    return any(p in t for p in OOS_PHRASES)

def _check_turn(turn_spec, response):
    expect    = turn_spec.get("expect", {})
    resp_text = response.get("text", response.get("response", ""))
    intent    = response.get("intent", "")
    language  = response.get("language", "unspecified")
    failures  = []

    if "is_oos" in expect:
        actual_oos = _is_oos(resp_text) or response.get("is_out_of_scope", False)
        if expect["is_oos"] and not actual_oos:
            failures.append(f"OOS_GUARDRAIL_FAILURE: expected OOS, got non-OOS. intent='{intent}' text='{resp_text[:100]}'")
        elif not expect["is_oos"] and actual_oos:
            failures.append(f"OOS_GUARDRAIL_FAILURE: expected in-scope, got OOS. text='{resp_text[:100]}'")

    if "intent_in" in expect and intent not in expect["intent_in"]:
        failures.append(f"BACKEND_LOGIC_ERROR: intent '{intent}' not in {expect['intent_in']}")

    if "language" in expect:
        if language != expect["language"] and language != "unspecified":
            failures.append(f"BACKEND_LOGIC_ERROR: language '{language}' != '{expect['language']}'")

    if "language_in" in expect and language not in expect["language_in"]:
        failures.append(f"BACKEND_LOGIC_ERROR: language '{language}' not in {expect['language_in']}")

    if expect.get("has_code") is True and "```" not in resp_text:
        failures.append(f"KB_OR_TEMPLATE_GAP: no code block in response. intent='{intent}' text='{resp_text[:100]}'")

    for phrase in expect.get("response_contains", []):
        if phrase.lower() not in resp_text.lower():
            failures.append(f"BACKEND_LOGIC_ERROR: missing phrase '{phrase}' in response")

    for phrase in expect.get("must_not_contain", []):
        if phrase.lower() in resp_text.lower():
            failures.append(f"OOS_GUARDRAIL_FAILURE: OOS response contains code phrase '{phrase}'")

    required = ["response", "intent", "language", "confidence", "suggestions", "session_id"]
    for k in required:
        if k not in response:
            failures.append(f"FRONTEND_JS_CONTRACT_MISMATCH: missing key '{k}'")

    if not resp_text.strip():
        failures.append("BACKEND_LOGIC_ERROR: empty response")

    return len(failures) == 0, failures

def _classify(msg):
    if "OOS_GUARDRAIL"        in msg: return "OOS_GUARDRAIL_FAILURE"
    if "FRONTEND_JS_CONTRACT" in msg: return "FRONTEND_JS_CONTRACT_MISMATCH"
    if "KB_OR_TEMPLATE"       in msg: return "KB_OR_TEMPLATE_GAP"
    if "CONTEXT_MEMORY"       in msg: return "CONTEXT_MEMORY_DROP"
    return "BACKEND_LOGIC_ERROR"

def run_all(scenarios, client):
    total  = len(scenarios)
    passed = failed = 0
    results  = []
    all_fixes = []

    print(f"Running {total} scenarios …")
    t0 = time.time()

    for i, scenario in enumerate(scenarios, 1):
        sid       = None
        ui_lang   = scenario.get("ui_language", "auto")
        turn_res  = []
        scen_pass = True

        for turn_spec in scenario["turns"]:
            payload = {
                "message":    turn_spec["message"],
                "language":   ui_lang,
                "session_id": sid,
            }
            resp = client.post("/api/chat",
                               data=json.dumps(payload),
                               content_type="application/json")
            d    = resp.get_json() or {}
            if not sid:
                sid = d.get("session_id")

            ok, failures = _check_turn(turn_spec, d)
            if not ok:
                scen_pass = False

            turn_res.append({
                "turn":         turn_spec["turn"],
                "message":      turn_spec["message"],
                "passed":       ok,
                "failures":     failures,
                "intent":       d.get("intent","?"),
                "language":     d.get("language","?"),
                "text_preview": (d.get("text") or d.get("response",""))[:150],
            })

        if scen_pass:
            passed += 1
            if i % 50 == 0:
                print(f"  [{i:04d}/{total}] {passed} passed so far …")
        else:
            failed += 1
            fail_turns = [t for t in turn_res if not t["passed"]]
            print(f"  [{i:04d}/{total}] FAIL  {scenario['id']}  ({len(fail_turns)} turn(s))")
            for t in fail_turns:
                for f_msg in t["failures"]:
                    all_fixes.append({
                        "scenario_id": scenario["id"],
                        "category":    scenario["category"],
                        "turn":        t["turn"],
                        "message":     t["message"],
                        "failure":     f_msg,
                        "root_cause":  _classify(f_msg),
                        "intent":      t["intent"],
                        "language":    t["language"],
                        "text_preview":t["text_preview"],
                    })

        results.append({
            "scenario_id":  scenario["id"],
            "category":     scenario["category"],
            "description":  scenario["description"],
            "passed":       scen_pass,
            "turn_results": turn_res,
        })

    elapsed    = time.time() - t0
    pass_rate  = 100.0 * passed / total if total else 0
    print(f"\n{'='*60}")
    print(f"Pass rate : {passed}/{total}  ({pass_rate:.1f}%)   [{elapsed:.0f}s]")
    print(f"{'='*60}\n")
    return results, all_fixes, {"total":total,"passed":passed,"failed":failed,"pass_rate":round(pass_rate,2)}

def main():
    with open(SCENARIOS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    scenarios = data["scenarios"]

    app    = create_app()
    client = app.test_client()
    client.get("/")   # warm up / create cookie

    results, fixes, summary = run_all(scenarios, client)

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results, "failures": fixes}, f, indent=2, ensure_ascii=False)

    fix_out = {"metadata":{"total_failures":len(fixes),"pass_rate":summary["pass_rate"]}, "fixes":fixes, "patch_plan":[]}
    with open(FIXES_PATH, "w", encoding="utf-8") as f:
        json.dump(fix_out, f, indent=2, ensure_ascii=False)

    print(f"Results       → {RESULTS_PATH}")
    print(f"Fixes         → {FIXES_PATH}")
    return summary["failed"]

if __name__ == "__main__":
    sys.exit(main())
