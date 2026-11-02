"""
benchmark/e2e_runner.py
=======================
Runs all synthetic scenarios against the live /api/chat endpoint.

Usage:
    python benchmark/e2e_runner.py [--url http://localhost:5000] [--scenario-file benchmark/data/synthetic_scenarios.json]

For each scenario it:
  1. Starts a fresh session (session_id = None on Turn 1).
  2. Posts each turn sequentially, carrying the session_id forward.
  3. Evaluates the response against the turn's `expect` dict.
  4. Records PASS / FAIL with structured diagnostics.

Outputs:
  benchmark/reports/run_results.json   — full results
  benchmark/reports/actionable_fixes.json — failures only (fed to failure_diagnostics.py)
  Console summary
"""

import argparse
import json
import os
import sys
import time
import requests

ROOT          = os.path.dirname(os.path.dirname(__file__))
SCENARIOS_PATH = os.path.join(ROOT, "benchmark", "data", "synthetic_scenarios.json")
RESULTS_PATH   = os.path.join(ROOT, "benchmark", "reports", "run_results.json")
FIXES_PATH     = os.path.join(ROOT, "benchmark", "reports", "actionable_fixes.json")
DEFAULT_URL    = "http://localhost:5000"

# OOS response fingerprints — we detect OOS by checking the response text
OOS_PHRASES = [
    "outside what i can help",
    "programming tutor",
    "i'm a programming tutor",
    "not within my scope",
    "can't help with that",
    "outside my scope",
    "not able to help with",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_oos_response(response_text: str) -> bool:
    t = response_text.lower()
    return any(phrase in t for phrase in OOS_PHRASES)


def _check_turn(turn_spec: dict, response: dict) -> tuple:
    """
    Evaluate a single turn response against its expect dict.
    Returns (passed: bool, failures: list[str])
    """
    expect   = turn_spec.get("expect", {})
    resp_text = response.get("text", response.get("response", ""))
    intent    = response.get("intent", "")
    language  = response.get("language", "unspecified")
    failures  = []

    # 1. OOS expectation
    if "is_oos" in expect:
        actual_oos = _is_oos_response(resp_text)
        if expect["is_oos"] and not actual_oos:
            failures.append(
                f"OOS_GUARDRAIL_FAILURE: expected OOS response but got non-OOS. "
                f"intent='{intent}', text_preview='{resp_text[:120]}'"
            )
        elif not expect["is_oos"] and actual_oos:
            failures.append(
                f"OOS_GUARDRAIL_FAILURE: expected in-scope response but got OOS redirect. "
                f"text_preview='{resp_text[:120]}'"
            )

    # 2. Intent check
    if "intent_in" in expect:
        allowed = expect["intent_in"]
        if intent not in allowed:
            failures.append(
                f"BACKEND_LOGIC_ERROR: intent '{intent}' not in allowed {allowed}"
            )

    # 3. Language check
    if "language" in expect:
        expected_lang = expect["language"]
        if language != expected_lang and language != "unspecified":
            failures.append(
                f"BACKEND_LOGIC_ERROR: language '{language}' != expected '{expected_lang}'"
            )
    if "language_in" in expect:
        allowed_langs = expect["language_in"]
        if language not in allowed_langs:
            failures.append(
                f"BACKEND_LOGIC_ERROR: language '{language}' not in allowed {allowed_langs}"
            )

    # 4. Code block presence
    if expect.get("has_code") is True:
        if "```" not in resp_text:
            failures.append(
                f"CODE_OR_TEMPLATE_GAP: expected code block (```) in response but none found. "
                f"intent='{intent}', text_preview='{resp_text[:120]}'"
            )

    # 5. Required phrases in response
    for phrase in expect.get("response_contains", []):
        if phrase.lower() not in resp_text.lower():
            failures.append(
                f"BACKEND_LOGIC_ERROR: response missing required phrase '{phrase}'. "
                f"text_preview='{resp_text[:120]}'"
            )

    # 6. Forbidden phrases (OOS response must not contain real code)
    for phrase in expect.get("must_not_contain", []):
        if phrase.lower() in resp_text.lower():
            failures.append(
                f"OOS_GUARDRAIL_FAILURE: OOS response contains forbidden phrase '{phrase}' — "
                f"chatbot may have generated real code for an OOS query. "
                f"text_preview='{resp_text[:120]}'"
            )

    # 7. JS/frontend contract — required keys in response JSON
    required_keys = ["response", "intent", "language", "confidence", "suggestions", "session_id"]
    for key in required_keys:
        if key not in response:
            failures.append(
                f"FRONTEND_JS_CONTRACT_MISMATCH: missing required key '{key}' in response JSON"
            )

    # 8. Non-empty response
    if not resp_text.strip():
        failures.append("BACKEND_LOGIC_ERROR: empty response text")

    return len(failures) == 0, failures


def _classify_failure(failure_msg: str) -> str:
    """Map a failure message to a root-cause category."""
    if "OOS_GUARDRAIL"         in failure_msg: return "OOS_GUARDRAIL_FAILURE"
    if "FRONTEND_JS_CONTRACT"  in failure_msg: return "FRONTEND_JS_CONTRACT_MISMATCH"
    if "CODE_OR_TEMPLATE"      in failure_msg: return "KB_OR_TEMPLATE_GAP"
    if "CONTEXT_MEMORY"        in failure_msg: return "CONTEXT_MEMORY_DROP"
    return "BACKEND_LOGIC_ERROR"


# ── Core runner ───────────────────────────────────────────────────────────────

def run_scenario(scenario: dict, base_url: str, delay: float = 0.1) -> dict:
    """
    Execute one scenario. Returns a result dict.
    """
    session_id = None
    turn_results = []
    last_valid_context = None  # tracks last in-scope turn for recovery check

    for turn_spec in scenario["turns"]:
        turn_name  = turn_spec["turn"]
        message    = turn_spec["message"]
        ui_lang    = scenario.get("ui_language", "auto")

        payload = {
            "message":    message,
            "language":   ui_lang,
            "session_id": session_id,
        }

        try:
            resp = requests.post(
                f"{base_url}/api/chat",
                json=payload,
                timeout=15,
            )
            if resp.status_code != 200:
                turn_results.append({
                    "turn":      turn_name,
                    "message":   message,
                    "passed":    False,
                    "failures":  [f"HTTP_{resp.status_code}: {resp.text[:200]}"],
                    "response":  {},
                })
                continue

            response = resp.json()
            # Carry session_id forward
            if response.get("session_id") and not session_id:
                session_id = response["session_id"]

            # Track context for recovery scenarios
            if turn_name == "valid_initial":
                last_valid_context = response

            # Context preservation check for recovery turns
            if turn_name == "scope_recovery" and turn_spec["expect"].get("context_preserved"):
                # The response must be non-OOS (checked by is_oos: False),
                # which implicitly confirms last_answer survived the OOS turn.
                # We add an explicit check: if response is OOS, context was lost.
                if _is_oos_response(response.get("text", response.get("response", ""))):
                    extra_failure = (
                        "CONTEXT_MEMORY_DROP: Turn 3 recovery query returned OOS response "
                        "— ctx['last_answer'] from Turn 1 was lost after the OOS Turn 2"
                    )
                    passed, failures = _check_turn(turn_spec, response)
                    failures.append(extra_failure)
                    passed = False
                    turn_results.append({
                        "turn":      turn_name,
                        "message":   message,
                        "passed":    passed,
                        "failures":  failures,
                        "response":  {k: response.get(k) for k in
                                      ("intent", "language", "topic", "confidence", "suggestions")},
                        "text_preview": response.get("text", response.get("response", ""))[:200],
                    })
                    if delay:
                        time.sleep(delay)
                    continue

            passed, failures = _check_turn(turn_spec, response)
            turn_results.append({
                "turn":      turn_name,
                "message":   message,
                "passed":    passed,
                "failures":  failures,
                "response":  {k: response.get(k) for k in
                              ("intent", "language", "topic", "confidence", "suggestions")},
                "text_preview": response.get("text", response.get("response", ""))[:200],
            })

        except requests.exceptions.ConnectionError:
            turn_results.append({
                "turn":     turn_name,
                "message":  message,
                "passed":   False,
                "failures": ["CONNECTION_ERROR: backend not reachable at " + base_url],
                "response": {},
            })
        except Exception as exc:
            turn_results.append({
                "turn":     turn_name,
                "message":  message,
                "passed":   False,
                "failures": [f"RUNNER_ERROR: {type(exc).__name__}: {exc}"],
                "response": {},
            })

        if delay:
            time.sleep(delay)

    scenario_passed = all(t["passed"] for t in turn_results)
    return {
        "scenario_id":   scenario["id"],
        "category":      scenario["category"],
        "description":   scenario["description"],
        "passed":        scenario_passed,
        "turn_results":  turn_results,
        "session_id":    session_id,
    }


def run_all(scenarios: list, base_url: str, delay: float = 0.05,
            categories: list = None) -> dict:
    """
    Run all (or a subset of) scenarios. Returns aggregated results.
    """
    if categories:
        scenarios = [s for s in scenarios if s["category"] in categories]

    total     = len(scenarios)
    passed    = 0
    failed    = 0
    results   = []
    failures  = []

    print(f"Running {total} scenarios against {base_url} …")
    for i, scenario in enumerate(scenarios, 1):
        result = run_scenario(scenario, base_url, delay=delay)
        results.append(result)

        if result["passed"]:
            passed += 1
            print(f"  [{i:04d}/{total}] PASS  {result['scenario_id']}")
        else:
            failed += 1
            fail_count = sum(1 for t in result["turn_results"] if not t["passed"])
            print(f"  [{i:04d}/{total}] FAIL  {result['scenario_id']}  ({fail_count} turn(s) failed)")
            # Collect actionable failures
            for t in result["turn_results"]:
                for f_msg in t.get("failures", []):
                    failures.append({
                        "scenario_id":    result["scenario_id"],
                        "category":       result["category"],
                        "turn":           t["turn"],
                        "message":        t["message"],
                        "failure":        f_msg,
                        "root_cause":     _classify_failure(f_msg),
                        "intent":         t.get("response", {}).get("intent", "?"),
                        "language":       t.get("response", {}).get("language", "?"),
                        "text_preview":   t.get("text_preview", ""),
                    })

    pass_rate = 100.0 * passed / total if total else 0.0
    summary   = {
        "total":     total,
        "passed":    passed,
        "failed":    failed,
        "pass_rate": round(pass_rate, 2),
    }
    print(f"\n{'='*60}")
    print(f"Pass rate: {passed}/{total}  ({pass_rate:.1f}%)")
    print(f"{'='*60}\n")

    return {
        "summary":  summary,
        "results":  results,
        "failures": failures,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="E2E benchmark runner for CodeTutor chatbot")
    parser.add_argument("--url",           default=DEFAULT_URL,    help="Base URL of the running Flask app")
    parser.add_argument("--scenarios",     default=SCENARIOS_PATH, help="Path to synthetic_scenarios.json")
    parser.add_argument("--delay",         default=0.05, type=float, help="Seconds between requests")
    parser.add_argument("--categories",    default=None, nargs="+",
                        choices=["in_scope_kb", "in_scope_example", "in_scope_template",
                                 "oos_direct", "oos_mid_drift", "oos_recovery"],
                        help="Only run these categories")
    args = parser.parse_args()

    if not os.path.exists(args.scenarios):
        print(f"ERROR: scenarios file not found: {args.scenarios}")
        print("Run:  python benchmark/scenario_generator.py  first")
        sys.exit(1)

    with open(args.scenarios, encoding="utf-8") as f:
        data = json.load(f)
    scenarios = data["scenarios"]

    run_data = run_all(scenarios, args.url, delay=args.delay, categories=args.categories)

    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

    # Write full results
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(run_data, f, indent=2, ensure_ascii=False)
    print(f"Full results → {RESULTS_PATH}")

    # Write actionable fixes
    fixes = {
        "metadata": {
            "total_failures": len(run_data["failures"]),
            "pass_rate":      run_data["summary"]["pass_rate"],
        },
        "fixes": run_data["failures"],
    }
    with open(FIXES_PATH, "w", encoding="utf-8") as f:
        json.dump(fixes, f, indent=2, ensure_ascii=False)
    print(f"Actionable fixes → {FIXES_PATH}")

    # Exit code: 0 = 100% pass, 1 = failures remain
    sys.exit(0 if run_data["summary"]["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
