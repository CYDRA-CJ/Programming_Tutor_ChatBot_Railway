_PRIORITY = {
    "greeting":          0,
    "bot_capabilities":  1,
    "clarification":     2,
    "follow_up":         3,
    "explain_concept":   10,
    "show_syntax":       11,
    "show_example":      12,
    "generate_code":     13,
    "explain_code":      20,   # after generate_code / show_example
    "debug_code":        21,
    "predict_output":    22,
    "compare_concepts":  30,
    "request_quiz":      40,   # always last — test knowledge after teaching
}

# ── Intents that must run alone (no secondary tasks alongside them) ─────────
_SOLO_INTENTS = {"follow_up", "clarification", "greeting", "bot_capabilities"}

# ── Dependency rules: if intent A is present, intent B must come before it ──
_MUST_PRECEDE = {
    "explain_code": ["generate_code", "show_example"],
    "request_quiz": ["explain_concept", "compare_concepts", "show_example"],
}


def build_task_plan(intents, primary_intent):
    # Build an ordered list of tasks from the detected intents.
    # Returns a list of intent strings in execution order.

    if not intents:
        return [primary_intent]

    # Solo intents are handled alone.
    if primary_intent in _SOLO_INTENTS:
        return [primary_intent]

    # Remove duplicates and cap at 3.
    unique = list(dict.fromkeys([primary_intent] + [i for i in intents if i != primary_intent]))
    unique = unique[:3]

    # Apply dependency ordering: if explain_code is present without generate_code,
    # ensure generate_code or show_example comes first.
    for dependent, prereqs in _MUST_PRECEDE.items():
        if dependent in unique:
            has_prereq = any(p in unique for p in prereqs)
            if not has_prereq:
                # Remove the dependent — it has nothing to explain yet.
                unique = [i for i in unique if i != dependent]

    # Sort by priority.
    unique.sort(key=lambda x: _PRIORITY.get(x, 99))

    return unique if unique else [primary_intent]


def get_task_description(intent):
    # Return a human-readable description of what each intent task does.
    descriptions = {
        "greeting":          "Respond to the greeting",
        "bot_capabilities":  "Describe what the chatbot can teach",
        "explain_concept":   "Explain the concept",
        "show_syntax":       "Show the syntax",
        "show_example":      "Show a code example",
        "generate_code":     "Generate code",
        "explain_code":      "Explain the code",
        "debug_code":        "Help debug the issue",
        "predict_output":    "Predict the output",
        "compare_concepts":  "Compare the concepts",
        "request_quiz":      "Provide quiz questions",
        "follow_up":         "Continue from previous context",
        "clarification":     "Clarify the request",
    }
    return descriptions.get(intent, intent)
