import random
import re

from app import get_quizzes
from app.conversation import followup_rules as fr

# Number of questions to return per quiz session by default.
DEFAULT_QUIZ_SIZE = 5

_LABELS = ["A", "B", "C", "D", "E", "F"]


# ── Selecting questions ──────────────────────────────────────────────────────

def get_quiz_questions(language, topic=None, count=DEFAULT_QUIZ_SIZE, shuffle=True):
    # Return a list of MC quiz questions filtered by language and optional topic.
    # Only multiple_choice questions are used — identification questions are excluded
    # since the quiz page is MC-only.
    quizzes = get_quizzes()
    if quizzes is None:
        return []

    # Multiple-choice only.
    pool = [q for q in quizzes if q.get("question_type") == "multiple_choice"]

    # Filter by language.
    if language and language not in ("unspecified", "multiple"):
        pool = [q for q in pool if q["language"] == language]

    # Further filter by topic if provided.
    if topic and topic != "programming_basics":
        topic_pool = [q for q in pool if q["topic"] == topic]
        # Fall back to full language pool if topic has no quizzes.
        if topic_pool:
            pool = topic_pool

    if not pool:
        return []

    if shuffle:
        pool = pool.copy()
        random.shuffle(pool)

    return pool[:count]


# ── Formatting (old API, unchanged) ──────────────────────────────────────────

def format_question(q, number=1, reveal_answer=False):
    # Format a single quiz question as a string.
    parts = []
    parts.append(f"**Question {number}:** {q['question']}")

    if q["question_type"] == "multiple_choice":
        options = q.get("options", [])
        for i, opt in enumerate(options):
            marker = ""
            if reveal_answer and i == q["correct_index"]:
                marker = " ✓"
            parts.append(f"  {_LABELS[i]}. {opt}{marker}")

    if reveal_answer:
        parts.append("")
        parts.append(f"**Answer:** {_get_answer_text(q)}")
        parts.append(f"**Explanation:** {q.get('explanation', '')}")

    return "\n".join(parts)


def _get_answer_text(q):
    # Return the correct answer as a readable string.
    if q["question_type"] == "multiple_choice":
        idx     = q.get("correct_index", 0)
        options = q.get("options", [])
        if 0 <= idx < len(options):
            return f"{_LABELS[idx]}. {options[idx]}"
    # Identification question.
    return q.get("options", ["?"])[0]


def check_answer(q, user_answer):
    # Check whether the user's answer is correct.
    # user_answer should be "A"/"B"/"C"/"D" for MC or the answer text for ident.
    # Returns (is_correct: bool, correct_answer: str, explanation: str).
    correct_text = _get_answer_text(q)
    explanation  = q.get("explanation", "")

    if q["question_type"] == "multiple_choice":
        idx = q.get("correct_index", 0)
        correct_label = _LABELS[idx] if idx < len(_LABELS) else "A"
        is_correct = user_answer.strip().upper().startswith(correct_label)
    else:
        # For identification, do a case-insensitive substring check.
        correct_raw = q.get("options", [""])[0].lower()
        ua = user_answer.strip().lower()
        # a very short reply ("a", "o") must not count as "contained in" the answer
        is_correct = bool(ua) and (correct_raw in ua or (len(ua) >= 3 and ua in correct_raw))

    return is_correct, correct_text, explanation


def format_quiz_session(questions):
    # Format a full quiz session as a single response string (old behaviour).
    if not questions:
        return "I don't have quiz questions for that topic yet. Try asking about a specific topic like loops, variables, or classes."

    parts = []
    parts.append(f"Here are {len(questions)} quiz question(s). Try to answer each one before checking!")
    parts.append("")

    for i, q in enumerate(questions, 1):
        parts.append(format_question(q, number=i, reveal_answer=False))
        parts.append("")

    parts.append("*Reply with your answers (e.g. '1. A, 2. C, 3. B') or say 'show answers' to reveal them.*")

    return "\n".join(parts)


# ── Quiz page payload (what chat.js's Quiz page expects) ─────────────────────

def quiz_page_payload(questions):
    # [{prompt, options[], answer(index), explanation}] — multiple-choice only.
    # Answer options are shuffled each time so the correct answer appears in a
    # random position, preventing students from pattern-matching by position.
    items = []
    for q in questions:
        if q.get("question_type") != "multiple_choice":
            continue
        options      = list(q.get("options", []))
        correct_text = options[q.get("correct_index", 0)]
        # Shuffle option order
        random.shuffle(options)
        new_correct_index = options.index(correct_text)
        items.append({
            "prompt":      q["question"],
            "options":     options,
            "answer":      new_correct_index,
            "explanation": q.get("explanation", ""),
        })
    return items


# ── Fill-in-the-blank exercises ───────────────────────────────────────────────

def get_fitb_questions(language, exercise_type="fill_in_blank", topic=None,
                       count=10, shuffle=True):
    # Return fill-in-the-blank questions filtered by language, exercise_type
    # ("fill_in_blank" or "fill_in_blank_mc"), and optionally topic.
    quizzes = get_quizzes()
    if quizzes is None:
        return []

    pool = [q for q in quizzes if q.get("question_type") == exercise_type]

    if language and language not in ("unspecified", "multiple"):
        pool = [q for q in pool if q["language"] == language]

    if topic:
        topic_pool = [q for q in pool if q["topic"] == topic]
        if topic_pool:
            pool = topic_pool

    if not pool:
        return []

    if shuffle:
        pool = pool.copy()
        random.shuffle(pool)

    return pool[:count]


def fitb_payload(questions):
    # Convert fill-in-the-blank question records to the payload the UI expects.
    #
    # Each item returned:
    #   {
    #     "question":    str   — instruction text
    #     "code":        str   — code snippet with ____ as the blank
    #     "answer":      str   — exact correct answer string
    #     "options":     list  — only present for fill_in_blank_mc (shuffled)
    #     "explanation": str
    #     "language":    str   — for syntax highlighting
    #     "type":        str   — "fill_in_blank" | "fill_in_blank_mc"
    #   }
    items = []
    for q in questions:
        qtype = q.get("question_type", "")
        if qtype not in ("fill_in_blank", "fill_in_blank_mc"):
            continue
        item = {
            "question":    q.get("question", ""),
            "code":        q.get("code", ""),
            "answer":      q.get("answer", ""),
            "explanation": q.get("explanation", ""),
            "language":    q.get("language", ""),
            "type":        qtype,
        }
        if qtype == "fill_in_blank_mc":
            # Shuffle options so the correct answer isn't always first
            opts = list(q.get("options", []))
            random.shuffle(opts)
            item["options"] = opts
        items.append(item)
    return items


def check_fitb_answer(correct_answer, user_answer):
    # Case-insensitive, whitespace-trimmed exact match.
    # Returns True if the user's answer matches the correct answer.
    return correct_answer.strip().lower() == user_answer.strip().lower()


# ── Conversational quiz ──────────────────────────────────────────────────────

_ANSWER_RE = re.compile(
    r"^\W*(?:(?:my |the )?answer(?: is)?|it'?s|its|i (?:think|choose|pick|say|guess)(?: it'?s| it is)?|option|choice|letter|maybe|"
    r"probably|(?:\d+|q\d+)\s*[.):-])?\s*[:\-]?\s*\(?([a-f])\)?[\s.!?)]*$",
    re.IGNORECASE,
)
_SKIP_RE  = re.compile(r"^\W*(skip|next|pass|i don'?t know|idk|dunno|no idea|show (?:me )?(?:the )?answers?|reveal|give up|what'?s the answer)\W*$", re.IGNORECASE)
_STOP_RE  = re.compile(r"^\W*(stop|quit|exit|end|cancel|enough|done)(?: the)?(?: quiz)?\W*$|^\W*(?:stop|quit|end|cancel) (?:the )?quiz\W*$", re.IGNORECASE)


_REQUEST_START = re.compile(
    r"^(?:explain|show|give|write|make|create|tell|what|how|why|when|where|who|can|could|please|help|compare|quiz|test|another)(?![\w-])",
    re.IGNORECASE,
)


def start_quiz(language, topic, count=DEFAULT_QUIZ_SIZE):
    # Build a quiz state dict for ctx["quiz"], or None if no questions exist.
    questions = get_quiz_questions(language, topic=topic, count=count)
    if not questions:
        return None
    return {
        "questions": questions,
        "index":     0,
        "score":     0,
        "total":     len(questions),
        "language":  language if language not in ("unspecified", "multiple") else None,
        "topic":     topic,
    }


def format_current_question(state):
    q = state["questions"][state["index"]]
    n, total = state["index"] + 1, state["total"]
    parts = [f"**Question {n} of {total}**", "", q["question"], ""]
    if q["question_type"] == "multiple_choice":
        for i, opt in enumerate(q.get("options", [])):
            parts.append(f"**{_LABELS[i]}.** {opt}")
        parts += ["", "*Tap a letter or type your answer.*"]
    else:
        parts.append("*Type your answer.*")
    return "\n".join(parts)


def quiz_chips(state):
    # Quick replies shown with the current question.
    if not state:
        return []
    q = state["questions"][state["index"]]
    chips = []
    if q["question_type"] == "multiple_choice":
        chips += _LABELS[: len(q.get("options", []))]
    chips += [fr.CHIP_SKIP, fr.CHIP_STOP_QUIZ]
    return chips


def quiz_intro(state):
    lang  = {"python": "Python", "java": "Java", "c": "C"}.get(state.get("language"), "programming")
    topic = state.get("topic") or ""
    topic = "" if topic == "programming_basics" else f" on **{topic.replace('_', ' ')}**"
    return f"Let's do a short **{lang}** quiz{topic} — {state['total']} questions, one at a time."


def parse_quiz_command(text, state):
    # Decide what the user's message means while a quiz is active.
    # Returns ("answer", value) / ("skip", None) / ("stop", None) / None.
    # None means "this is not about the quiz" (the message is handled normally).
    t = text.strip()
    if _STOP_RE.match(t):
        return ("stop", None)
    if _SKIP_RE.match(t) or t.lower() == fr.CHIP_SKIP.lower():
        return ("skip", None)

    q = state["questions"][state["index"]]
    if q["question_type"] == "multiple_choice":
        m = _ANSWER_RE.match(t)
        if m and ord(m.group(1).upper()) - 65 < len(q.get("options", [])):
            return ("answer", m.group(1).upper())
        # allow typing the option text itself
        low = t.lower().strip(" .!?")
        for i, opt in enumerate(q.get("options", [])):
            if low and low == str(opt).lower().strip():
                return ("answer", _LABELS[i])
        return None

    # identification question: short free text is the answer — unless it reads like
    # a request ("explain recursion", "show me an example"), which is handled normally.
    if len(t.split()) <= 6 and not t.endswith("?") and not _REQUEST_START.match(t) and not fr.match_smalltalk(t):
        return ("answer", t)
    return None


def is_stop_quiz(text):
    return bool(_STOP_RE.match(text.strip())) and "quiz" in text.lower()


def handle_quiz_turn(state, command, value):
    # Apply one quiz command. Returns (text, finished).
    q = state["questions"][state["index"]]
    parts = []

    if command == "stop":
        parts.append(f"Quiz stopped. You answered correctly {state['score']} of {state['index']} question(s) so far.")
        return "\n".join(parts), True

    if command == "skip":
        parts.append(f"No problem — the answer is **{_get_answer_text(q)}**.")
        if q.get("explanation"):
            parts.append(q["explanation"])
    else:
        ok, correct_text, explanation = check_answer(q, value)
        if ok:
            state["score"] += 1
            parts.append("✅ **Correct!**")
        else:
            parts.append(f"❌ **Not quite.** The correct answer is **{correct_text}**.")
        if explanation:
            parts.append("")
            parts.append(explanation)

    state["index"] += 1

    if state["index"] >= state["total"]:
        score, total = state["score"], state["total"]
        ratio = score / total if total else 0
        if ratio == 1:
            verdict = "Perfect score — excellent work! 🎉"
        elif ratio >= 0.6:
            verdict = "Nice work — you've got the main ideas."
        else:
            verdict = "Good effort — review the topic and try again, you'll improve quickly."
        parts += ["", "---", "", f"**Quiz complete!** You scored **{score} / {total}**.", verdict]
        return "\n".join(parts), True

    parts += ["", "---", "", format_current_question(state)]
    return "\n".join(parts), False
