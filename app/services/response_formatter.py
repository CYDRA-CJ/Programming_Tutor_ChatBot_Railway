LANGUAGE_LABELS = {
    "python":      "Python",
    "java":        "Java",
    "c":           "C",
    "multiple":    "Python, Java, and C",
    "unspecified": "programming",
}

INTENT_LABELS = {
    "explain_concept":   "Explanation",
    "show_syntax":       "Syntax",
    "show_example":      "Example",
    "generate_code":     "Generated Code",
    "explain_code":      "Code Explanation",
    "compare_concepts":  "Comparison",
    "request_quiz":      "Quiz",
    "greeting":          "",
    "bot_capabilities":  "What I Can Teach",
    "follow_up":         "",
    "clarification":     "",
}


def format_response(task_results):
    # Assemble the final response from a list of {intent, content} dicts.
    # task_results: [{"intent": str, "content": str}, ...]
    if not task_results:
        return fallback_response()

    # Single task — return content directly without a section header.
    if len(task_results) == 1:
        result = task_results[0]
        content = result.get("content", "")
        if not content:
            return fallback_response()
        return content

    # Multiple tasks — add section headers so the response is organised.
    parts = []
    for result in task_results:
        intent  = result.get("intent", "")
        content = result.get("content", "")
        if not content:
            continue
        label = INTENT_LABELS.get(intent, intent.replace("_", " ").title())
        if label:
            parts.append(f"## {label}")
            parts.append("")
        parts.append(content)
        parts.append("")
        parts.append("---")
        parts.append("")

    # Remove trailing separator.
    while parts and parts[-1] in ("", "---"):
        parts.pop()

    return "\n".join(parts) if parts else fallback_response()


def greeting_response(language="unspecified"):
    # Return a friendly greeting response.
    lang_label = LANGUAGE_LABELS.get(language, "programming")
    return (
        "Hello! I'm your Programming Language Tutor. 👋\n\n"
        "I can help you learn **Python**, **Java**, and **C** with:\n"
        "- Explanations of concepts and syntax\n"
        "- Code examples and generation\n"
        "- Quizzes to test your knowledge\n"
        "- Comparisons between languages\n\n"
        "What would you like to learn today?"
    )


def capabilities_response():
    # Return a description of what the chatbot can teach.
    return (
        "## What I Can Teach\n\n"
        "I support **Python**, **Java**, and **C**. Here is what I can help with:\n\n"
        "**Concepts & Syntax**\n"
        "- Variables, data types, operators\n"
        "- Conditions, loops, functions\n"
        "- Arrays, strings, collections\n"
        "- Classes and object-oriented programming\n"
        "- Modules, imports, header files\n"
        "- Error handling and exceptions\n"
        "- Recursion and scope\n\n"
        "**Code**\n"
        "- Show examples of any concept\n"
        "- Generate programs from templates\n"
        "- Explain code line by line\n\n"
        "**Practice**\n"
        "- Multiple-choice and identification quizzes\n"
        "- Compare concepts across languages\n\n"
        "**History**\n"
        "- Origins and history of Python, Java, and C\n\n"
        "*What topic would you like to start with?*"
    )


def fallback_response(reason="low_confidence"):
    # Return a clarification prompt when the intent is unclear.
    if reason == "unsupported_language":
        return (
            "I can only help with **Python**, **Java**, and **C**. "
            "I don't have information about other programming languages. "
            "Which of these three would you like to learn about?"
        )
    if reason == "out_of_scope":
        return (
            "I'm a programming tutor focused on Python, Java, and C. "
            "I can't help with that topic, but I'm happy to answer any "
            "programming question you have!"
        )
    # Default: low confidence / unclear intent.
    return (
        "I'm not sure I understood that. Could you rephrase your question?\n\n"
        "For example:\n"
        "- *Explain variables in Python*\n"
        "- *Show me a Java for loop example*\n"
        "- *Write a C program that reads two numbers and adds them*\n"
        "- *Quiz me on Python loops*\n"
        "- *Compare Python lists and Java arrays*"
    )


def out_of_scope_response():
    # Return a friendly redirect when the user asks about a non-programming topic.
    return (
        "I'm a programming tutor for **Python**, **Java**, and **C** — "
        "that topic is outside what I can help with.\n\n"
        "I'm ready for any programming question though! For example:\n"
        "- *Explain what a loop is*\n"
        "- *Show me a Python function example*\n"
        "- *Write a Java calculator program*\n"
        "- *Quiz me on C arrays*"
    )


def language_clarification_response(topic="that"):
    # Ask the user which language they want when it can't be determined.
    return (
        f"I can explain {topic} in **Python**, **Java**, or **C**. "
        "Which language would you like?"
    )


def follow_up_response(context_language, context_topic):
    # Inform the user we are continuing from previous context.
    lang  = LANGUAGE_LABELS.get(context_language, context_language)
    return f"Continuing with **{lang}** — {context_topic.replace('_', ' ')}."


def no_content_response(intent, language, topic):
    # Return a graceful message when no content was found.
    lang  = LANGUAGE_LABELS.get(language, language)
    topic_label = topic.replace("_", " ")
    return (
        f"I don't have specific content for **{topic_label}** in **{lang}** yet. "
        f"Try asking about a related topic or rephrasing your question."
    )


def gap_response(topic=None, language=None):
    # Return a GAP response: the request is programming-related but the required
    # knowledge, template, or capability is not available in this tutor's content.
    # Used instead of returning an unrelated fallback answer.
    parts = [
        "I don't have a lesson or program template for that specific request yet."
    ]
    suggestions = []
    if topic and topic != "programming_basics":
        topic_label = topic.replace("_", " ")
        suggestions.append(f"*Explain {topic_label}*")
    if language and language in ("python", "java", "c"):
        lang_label = LANGUAGE_LABELS[language]
        suggestions.append(f"*Show me a {lang_label} example*")
        suggestions.append(f"*Quiz me on {lang_label}*")
    if not suggestions:
        suggestions = [
            "*Explain loops in Python*",
            "*Write a Java calculator program*",
            "*Quiz me on C arrays*",
        ]
    parts.append(
        "I can help with Python, Java, and C — try one of these:\n"
        + "\n".join(f"- {s}" for s in suggestions[:3])
    )
    return "\n\n".join(parts)




# ── Small-talk and conversation responses ────────────────────────────────────

def thanks_response():
    """Respond when the user thanks the tutor."""
    return "You're welcome! 😊 I'm happy to help you learn Python, Java, and C."


def goodbye_response():
    """Respond when the user ends the conversation."""
    return "Goodbye! 👋 Keep practicing, and feel free to come back whenever you need help with Python, Java, or C."


def ack_response():
    """Acknowledge a short message such as 'ok' or 'got it'."""
    return "Got it! Let me know if you'd like to explore another programming topic."


def run_request_response(has_code=False):
    """Explain that this tutor does not execute programs."""
    if has_code:
        return (
            "I can't execute code directly, but I can help you trace it step by step, "
            "explain what it does, or check it for common issues. What would you like to do?"
        )
    return (
        "I can't run programs directly. Paste your code here and I can explain it, "
        "check for common issues, or help you work out its expected output."
    )


# ── Language selection and clarification responses ───────────────────────────

def unsupported_language_response(language):
    """Redirect requests for languages outside the tutor's supported set."""
    name = str(language).strip() or "that language"
    return (
        f"I don't currently support **{name}**. I can help with **Python**, "
        "**Java**, and **C**. Which of these would you like to use?"
    )


def language_set_response(language):
    """Confirm the language selected by the user."""
    label = LANGUAGE_LABELS.get(language, str(language).title())
    return (
        f"Great! We'll use **{label}**. What would you like to learn or build?"
    )


def assumed_language_note(language):
    """Tell the user when the tutor inferred a language from conversation context."""
    label = LANGUAGE_LABELS.get(language, "the current programming language")
    return (
        f"*I'm continuing in {label} based on our previous messages. "
        "Tell me if you'd prefer Python, Java, or C instead.*"
    )


def ask_for_code_response(action="explain"):
    """Ask the user to provide code needed for a code-related task."""
    prompts = {
        "explain": (
            "Please paste the code you'd like me to explain. I'll walk through "
            "what it does and clarify the important lines."
        ),
        "predict": (
            "Please paste the code whose output you want to predict. "
            "I'll trace it step by step where possible."
        ),
    }
    return prompts.get(action, prompts["explain"])


# ── Intent-choice responses ──────────────────────────────────────────────────

INTENT_CHOICE_TEXT = {
    "explain_concept": "Explain a concept",
    "show_syntax": "Show syntax",
    "show_example": "Show an example",
    "generate_code": "Generate code",
    "explain_code": "Explain code",
    "compare_concepts": "Compare concepts",
    "request_quiz": "Take a quiz",
    "greeting": "Greeting",
    "bot_capabilities": "Learn about the tutor's capabilities",
    "follow_up": "Continue a previous topic",
    "clarification": "Clarify the request",
}


def did_you_mean_response(intents):
    """Ask the user to clarify which detected intent they meant."""
    labels = [INTENT_CHOICE_TEXT[i] for i in intents if i in INTENT_CHOICE_TEXT]
    if len(labels) >= 2:
        choices = "\n".join(f"- {label}" for label in labels)
        return f"I'm not completely sure what you'd like to do. Did you mean one of these?\n\n{choices}"
    if len(labels) == 1:
        return f"Do you want me to **{labels[0].lower()}**? You can rephrase your request if you meant something else."
    return "I'm not sure what you meant. Could you rephrase your programming question?"