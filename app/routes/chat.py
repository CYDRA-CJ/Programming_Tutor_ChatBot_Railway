import re

from flask import Blueprint, request, jsonify, render_template, session

from app import get_templates
from app.validators.input_validator    import validate, sanitise_response, get_error_response
from app.classifier.intent_classifier  import predict, is_multi_intent, predict_top_n, CONFIDENCE_THRESHOLD
from app.services.language_detector    import (
    detect_language, detect_all_languages, detect_unsupported_language, language_only_reply,
)
from app.services.topic_resolver       import (
    resolve_topic, is_specific_question, is_overview_question,
    get_activity_id, ACTIVITY_MAP,
)
from app.services.multi_intent_planner import build_task_plan
from app.services.response_formatter   import (
    format_response, greeting_response, capabilities_response,
    fallback_response, language_clarification_response, no_content_response,
    thanks_response, goodbye_response, ack_response, run_request_response,
    unsupported_language_response, language_set_response, ask_for_code_response,
    did_you_mean_response, assumed_language_note, out_of_scope_response,
    INTENT_CHOICE_TEXT,
)
from app.knowledge.knowledge_retriever import (
    get_record, get_record_by_alias, get_record_by_keywords, get_record_by_id,
    get_examples_by_topic, get_examples_by_language, get_example,
    format_record_response, format_example_response, format_example_full,
)
from app.knowledge.template_engine     import find_template, fill_template
from app.services.quiz_handler         import (
    get_quiz_questions, format_quiz_session, quiz_page_payload,
    start_quiz, format_current_question, quiz_chips, quiz_intro,
    parse_quiz_command, handle_quiz_turn, is_stop_quiz,
    get_fitb_questions, fitb_payload,
)
from app.services import code_helper
from app.services.scope_checker        import is_out_of_scope
from app.conversation import followup_rules as fr
from app.conversation.context_manager  import (
    get_context, save_context, clear_context, begin_turn,
    remember_language, active_language, set_pending, take_pending,
    mark_example_shown, record_answer,
)
from app.conversation.conversation_store import (
    init_db, new_session, session_exists, save_message, get_history,
    clear_history, get_title, get_sessions_for_user,
    claim_sessions, session_belongs_to_user,
    rename_session, pin_session, delete_session,
)

chat_bp = Blueprint("chat", __name__)

LOW_CONFIDENCE = CONFIDENCE_THRESHOLD       # one shared threshold
LANGS          = ("python", "java", "c")
LANG_LABEL     = {"python": "Python", "java": "Java", "c": "C"}
SOLO_INTENTS   = {"greeting", "bot_capabilities", "follow_up", "clarification"}

# Intents whose answer a follow-up can build on.
CONTENT_INTENTS = {
    "explain_concept", "show_syntax", "show_example", "generate_code",
    "explain_code", "compare_concepts",
}
# Intents that can be repeated in another language ("now in Java").
SWITCHABLE = {"explain_concept", "show_syntax", "show_example", "generate_code"}

# Phrases that mean "give me a code example to look at" — stay as show_example.
SHOW_EXAMPLE_PHRASES = [
    "give sample code", "give me sample code", "give a sample code",
    "show sample code", "show a sample code", "show me sample code",
    "give me an example", "show me an example", "show an example",
    "give example", "give me example", "show example",
    "example of", "example for", "example using",
    "code example of", "code example for",
]

# Phrases that mean the user wants new code generated.
CODE_REQUEST_PHRASES = [
    "make a sample code", "make a code", "make sample code",
    "write sample code", "write a sample code",
    "write a program", "write code", "write code for",
    "create a program", "create code", "make a program", "make program",
    "generate code", "generate a code", "generate program",
    "build a program", "build code",
    "basic code", "simple code",
    "make a basic", "make a simple", "make a calculator",
    "make a loop", "make a function", "make a class",
    "make a bank", "make a nested",
    "code for bank", "code for student", "code for library",
    "code for inventory", "code for payroll", "code for hospital",
]

STARTER_CHIPS = ["Explain Python loops", "Write a Java calculator program", "Quiz me on C pointers"]

_db_ready = False


# ══════════════════════════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════════════════════════

@chat_bp.before_app_request
def startup():
    # Create the tables once per process (not on every request).
    global _db_ready
    if not _db_ready:
        init_db()
        _db_ready = True


@chat_bp.route("/")
def index():
    return render_template("index.html")


def _owned():
    return list(session.get("owned", []))


def _resolve_session(data):
    # Decide which conversation this message belongs to.
    #  - the browser sends the session_id of the conversation it has open;
    #  - session_id = null means "New conversation" -> start a fresh one;
    #  - an old client that sends no session_id at all keeps using the cookie session.
    from app.routes.auth import current_user
    user    = current_user()
    user_id = user["id"] if user else None

    owned     = _owned()
    requested = data.get("session_id") if "session_id" in data else "__legacy__"

    if requested == "__legacy__":
        sid = session.get("session_id")
        if sid and session_exists(sid):
            if sid not in owned:
                owned.append(sid)
                session["owned"] = owned[-30:]
            return sid
    elif requested and session_exists(requested):
        # Accept if owned by cookie OR owned by the logged-in user in the DB.
        if requested in owned or (user_id and session_belongs_to_user(requested, user_id)):
            session["session_id"] = requested
            if requested not in owned:
                owned.append(requested)
                session["owned"] = owned[-30:]
            return requested

    sid = new_session(user_id=user_id)
    owned.append(sid)
    session["owned"]      = owned[-30:]
    session["session_id"] = sid
    return sid


@chat_bp.route("/api/chat", methods=["POST"])
def api_chat():
    return chat()


@chat_bp.route("/chat", methods=["POST"])
def chat():
    data       = request.get_json(silent=True) or {}
    session_id = _resolve_session(data)
    ui_lang    = data.get("language", "auto")
    quiz_page  = data.get("context") == "quiz"

    # 1. Validate.
    clean_msg, error = validate(data.get("message", ""))
    if error:
        msg = get_error_response(error)
        return jsonify({
            "response": msg, "text": msg, "reply": msg, "intent": "clarification",
            "language": "unspecified", "session_id": session_id, "suggestions": [],
        }), 200

    save_message(session_id, "user", clean_msg)

    # 2. Load context, run the turn, save context.
    ctx = get_context(session_id)
    if quiz_page:
        ctx["kind"] = "quiz"
    begin_turn(ctx)

    r = _process_turn(session_id, clean_msg, ctx, ui_lang, quiz_page)
    text = sanitise_response(r["text"])

    save_context(session_id, ctx)
    save_message(session_id, "assistant", text, intent=r["intent"],
                 language=r["language"], topic=r["topic"])

    out = {
        "response":         text,
        "text":             text,
        "reply":            text,
        "intent":           r["intent"],
        "language":         r["language"],
        "topic":            r["topic"],
        "confidence":       r["confidence"],
        "suggestions":      r["chips"][:4],
        "is_out_of_scope":  r.get("is_out_of_scope", False),
        "session_id":       session_id,
        "title":            get_title(session_id),
    }
    if r.get("is_out_of_scope"):
        out["oos_image_url"]    = "/static/images/out_of_scope_guide.svg"
        out["suggested_topics"] = r["chips"][:4]
    if r.get("quiz"):
        out["quiz"] = r["quiz"]
    return jsonify(out), 200


@chat_bp.route("/history", methods=["GET"])
def history():
    session_id = session.get("session_id")
    if not session_id:
        return jsonify({"history": []}), 200
    return jsonify({"history": get_history(session_id, limit=50)}), 200


@chat_bp.route("/api/quiz/topics", methods=["GET"])
def quiz_topics():
    # Return {language: [sorted topic slugs]} for topics that have ≥1 MC question.
    from collections import defaultdict
    from app import get_quizzes
    quizzes = get_quizzes() or []
    result = defaultdict(set)
    for q in quizzes:
        if q.get("question_type") == "multiple_choice":
            result[q["language"]].add(q["topic"])
    # Also add an "all" key with the union across all languages
    all_topics = set()
    for topics in result.values():
        all_topics |= topics
    return jsonify({
        "all":    sorted(all_topics),
        "python": sorted(result.get("python", [])),
        "java":   sorted(result.get("java",   [])),
        "c":      sorted(result.get("c",      [])),
    })


@chat_bp.route("/api/quiz/exercises", methods=["POST"])
def quiz_exercises():
    # Serve fill-in-the-blank exercise questions.
    # Always returns 10 items: 5 free-text + 5 MC, shuffled together.
    # Respects the language sent from the UI tab (python/java/c or empty for all).
    data     = request.get_json(silent=True) or {}
    language = data.get("language", "").strip() or None

    # Normalise language from UI values ("auto" → None)
    if language not in ("python", "java", "c"):
        language = None

    # Fetch 5 of each type then combine and shuffle
    free = get_fitb_questions(language, exercise_type="fill_in_blank",    count=5)
    mc   = get_fitb_questions(language, exercise_type="fill_in_blank_mc", count=5)

    import random as _r
    combined = fitb_payload(free) + fitb_payload(mc)
    _r.shuffle(combined)

    if not combined:
        return jsonify({"error": "No exercises found for that selection."}), 404
    return jsonify({"exercises": combined, "total": len(combined)})


@chat_bp.route("/clear", methods=["POST"])
def clear():
    session_id = session.get("session_id")
    if session_id and session_id in _owned():
        clear_history(session_id)
        clear_context(session_id)
    return jsonify({"status": "cleared"}), 200


@chat_bp.route("/api/sessions", methods=["GET"])
def api_sessions():
    # Logged-in users: return all their sessions (pinned first, newest-first).
    # Guests: always return empty — history is not saved for guests.
    from app.routes.auth import current_user
    user = current_user()
    if not user:
        return jsonify([]), 200

    rows = get_sessions_for_user(user["id"])
    out  = []
    for row in rows:
        sid   = row["session_id"]
        title = get_title(sid)
        if not title:
            continue
        out.append({
            "id":     sid,
            "title":  title,
            "pinned": bool(row["pinned"]),
            "kind":   get_context(sid).get("kind", "chat"),
        })
    return jsonify(out), 200


@chat_bp.route("/api/sessions/<sid>", methods=["GET"])
def api_session_messages(sid):
    from app.routes.auth import current_user
    user = current_user()
    owned_by_cookie = sid in _owned()
    owned_by_user   = user and session_belongs_to_user(sid, user["id"])
    if not owned_by_cookie and not owned_by_user:
        return jsonify({"error": "not found"}), 404
    if not session_exists(sid):
        return jsonify({"error": "not found"}), 404
    msgs = get_history(sid, limit=200)
    return jsonify([
        {"role": "user" if m["role"] == "user" else "bot", "text": m["content"],
         "intent": m.get("intent"), "language": m.get("language")}
        for m in msgs
    ]), 200


@chat_bp.route("/api/sessions/<sid>", methods=["PATCH"])
def api_session_update(sid):
    # Rename or pin/unpin a session.
    from app.routes.auth import current_user
    user = current_user()
    if not user or not session_belongs_to_user(sid, user["id"]):
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    if "title" in data:
        new_title = str(data["title"]).strip()[:60]
        rename_session(sid, new_title or None)
    if "pinned" in data:
        pin_session(sid, bool(data["pinned"]))
    return jsonify({"status": "ok"}), 200


@chat_bp.route("/api/sessions/<sid>", methods=["DELETE"])
def api_session_delete(sid):
    # Delete a session and all its messages.
    from app.routes.auth import current_user
    user = current_user()
    if not user or not session_belongs_to_user(sid, user["id"]):
        return jsonify({"error": "not found"}), 404
    delete_session(sid)
    # Remove from cookie-owned list too.
    owned = _owned()
    if sid in owned:
        owned.remove(sid)
        session["owned"] = owned
    return jsonify({"status": "deleted"}), 200


# ══════════════════════════════════════════════════════════════════════════════
#  Reply helpers
# ══════════════════════════════════════════════════════════════════════════════

def _reply(text, intent, language, topic, confidence=1.0, chips=None, quiz=None,
           is_oos=False):
    return {
        "text": text, "intent": intent, "language": language or "unspecified",
        "topic": topic or "programming_basics", "confidence": confidence,
        "chips": chips or [], "quiz": quiz, "is_out_of_scope": is_oos,
    }


def _other_languages(language):
    return [l for l in ("Python", "Java", "C") if l != LANG_LABEL.get(language)]


def _intent_chip(intent, language, topic):
    # A typed-message version of an intent, used for "Did you mean ...?" chips.
    t = (topic or "programming basics").replace("_", " ")
    lang = LANG_LABEL.get(language)
    return {
        "explain_concept":  f"Explain {t}" + (f" in {lang}" if lang else ""),
        "show_syntax":      f"Show the syntax of {t}" + (f" in {lang}" if lang else ""),
        "show_example":     f"Show me an example of {t}" + (f" in {lang}" if lang else ""),
        "generate_code":    f"Write a {lang or 'Python'} program",
        "request_quiz":     f"Quiz me on {t}",
        "compare_concepts": "Compare Python and Java",
        "explain_code":     "Explain this code",
    }.get(intent)


def _chips(ctx, intent, language, topic, trace):
    # Quick replies shown under a bot answer. Their wording matches
    # followup_rules.py so tapping a chip always does what it says.
    if trace.get("asked"):
        return ["Python", "Java", "C"]
    if trace.get("chips") is not None:
        return trace["chips"]
    if ctx.get("quiz"):
        return quiz_chips(ctx["quiz"])

    lang = LANG_LABEL.get(language)
    other = _other_languages(language)[0] if lang else None

    if intent in ("show_example", "generate_code"):
        chips = [fr.CHIP_EXPLAIN, fr.CHIP_ANOTHER]
        if other:
            chips.append(fr.chip_same_in(other))
        return chips
    if intent == "explain_concept":
        return [fr.CHIP_EXAMPLE, fr.CHIP_SIMPLER, fr.CHIP_QUIZ]
    if intent == "show_syntax":
        return [fr.CHIP_EXAMPLE, fr.CHIP_SIMPLER]
    if intent == "explain_code":
        return [fr.CHIP_ANOTHER, fr.CHIP_QUIZ]
    if intent == "compare_concepts":
        return [fr.CHIP_QUIZ, fr.CHIP_EXAMPLE]
    if intent in ("greeting", "bot_capabilities"):
        return STARTER_CHIPS
    return []


def _finish(ctx, intent, language, topic, src_text, content, trace, confidence=1.0, prefix="", suffix=""):
    # Turn an executed answer into a reply and update the context.
    asked = trace.get("asked")
    if ctx.get("quiz") and not trace.get("quiz_started"):
        suffix += "\n\n*Your quiz is still open — reply with an answer, or say \"stop quiz\".*"
        trace["chips"] = quiz_chips(ctx["quiz"])
    text  = f"{prefix}{content}{suffix}"
    if not asked and intent in CONTENT_INTENTS:
        record_answer(ctx, intent, language, topic, src_text, trace)
    if language in LANGS and not asked:
        remember_language(ctx, language)
    ctx["topic"]       = topic or ctx.get("topic")
    ctx["last_intent"] = intent
    return _reply(text, intent, language, topic, confidence, _chips(ctx, intent, language, topic, trace))


# ══════════════════════════════════════════════════════════════════════════════
#  The turn pipeline
# ══════════════════════════════════════════════════════════════════════════════

def _process_turn(sid, msg, ctx, ui_lang, quiz_page):
    language_ctx = ctx.get("language") or "unspecified"

    # 1. Quiz page (separate screen in the UI).
    if quiz_page:
        return _quiz_page_reply(msg, ctx, ui_lang)

    # 2. Active in-chat quiz: answers, skip, stop.
    if ctx.get("quiz"):
        cmd = parse_quiz_command(msg, ctx["quiz"])
        if cmd:
            return _quiz_turn(ctx, cmd)
        # Not an answer. The first stray message keeps the quiz open (with a reminder);
        # a second one means the user has moved on, so the quiz is closed.
        ctx["quiz"]["strays"] = ctx["quiz"].get("strays", 0) + 1
        if ctx["quiz"]["strays"] > 1:
            ctx["quiz"] = None

    # A bare answer letter while no quiz is running (e.g. an old chip). "C" is left alone: it is also a language.
    if not ctx.get("quiz") and re.fullmatch(r"[abdABD][.)]?", msg.strip()):
        return _reply("There's no quiz running right now. Want to start one?", "request_quiz",
                      language_ctx, ctx.get("topic"), chips=["Quiz me on Python", "Quiz me on Java", "Quiz me on C"])
    if not ctx.get("quiz") and is_stop_quiz(msg):
        return _reply("There's no quiz running right now. Want to start one?", "request_quiz",
                      language_ctx, ctx.get("topic"), chips=["Quiz me on Python", "Quiz me on Java", "Quiz me on C"])

    # 3. A language we do not teach.
    other = detect_unsupported_language(msg)
    if other:
        take_pending(ctx)
        return _reply(unsupported_language_response(other), "clarification",
                      "unspecified", ctx.get("topic"), chips=["Python", "Java", "C"])

    # 4. Small talk.
    talk = fr.match_smalltalk(msg)
    if talk:
        take_pending(ctx)
        if talk == "bye":
            ctx["quiz"] = None
            return _reply(goodbye_response(), "greeting", language_ctx, ctx.get("topic"))
        text = thanks_response() if talk == "thanks" else ack_response()
        return _reply(text, "greeting", language_ctx, ctx.get("topic"),
                      chips=_after_chat_chips(ctx))

    # 5. "Run my code" requests.
    if fr.is_run_request(msg) and not code_helper.looks_like_code(msg):
        has_code = bool((ctx.get("last_answer") or {}).get("code"))
        return _reply(run_request_response(has_code), "clarification", language_ctx, ctx.get("topic"),
                      chips=[fr.CHIP_EXPLAIN, fr.CHIP_OUTPUT] if has_code else [])

    # 6. The bot asked a question last turn (pending lives exactly one turn).
    r = _pending_turn(ctx, msg, ui_lang)
    if r:
        return r

    # 6.5 OOS check before follow-up — an OOS message must NEVER be treated as
    # a follow-up (e.g. "What movies should I watch?" after a valid Turn 1).
    # This check runs before follow-up detection so OOS always wins.
    if not code_helper.looks_like_code(msg) and is_out_of_scope(msg):
        last_lang  = ctx.get("language")
        last_topic = ctx.get("topic") or "programming_basics"
        lang_label = LANG_LABEL.get(last_lang, "Python")
        suggested  = [
            f"Explain {last_topic.replace('_', ' ')} in {lang_label}",
            f"Show me a {lang_label} example",
            f"Quiz me on {lang_label}",
            "What topics can you teach me?",
        ] if last_lang else STARTER_CHIPS + ["What topics can you teach me?"]
        return _reply(
            out_of_scope_response(), "clarification",
            language_ctx, ctx.get("topic"),
            chips=suggested[:4],
            is_oos=True,
        )

    # 7. Follow-up rules ("another example", "now in Java", "simpler", ...).
    r = _followup_turn(ctx, msg, ui_lang)
    if r:
        return r

    # 8. Normal pipeline.
    return _normal_turn(ctx, msg, ui_lang)


def _after_chat_chips(ctx):
    la = ctx.get("last_answer")
    if la and la.get("language") in LANGS:
        return [fr.CHIP_ANOTHER, fr.CHIP_QUIZ]
    return STARTER_CHIPS


# ── Quiz ─────────────────────────────────────────────────────────────────────

def _quiz_turn(ctx, cmd):
    state = ctx["quiz"]
    command, value = cmd
    text, finished = handle_quiz_turn(state, command, value)
    language = state.get("language") or ctx.get("language")
    topic    = state.get("topic")
    if finished:
        ctx["quiz"] = None
        chips = [fr.CHIP_QUIZ_AGAIN, fr.CHIP_EXAMPLE]
    else:
        state["strays"] = 0
        ctx["quiz"] = state
        chips = quiz_chips(state)
    ctx["last_intent"] = "request_quiz"
    return _reply(text, "request_quiz", language, topic, chips=chips)


def _quiz_page_reply(msg, ctx, ui_lang):
    # The Quiz page sends "Quiz me on <language> <topic>" and shows the
    # questions itself, so we return them as structured data.
    #
    # Sizing rules (Phase 3):
    #   • Specific topic selected → serve all available questions for that topic,
    #     capped at 10. No user-chosen count.
    #   • "All topics" (no topic_slug) → always 10 questions, randomly drawn
    #     from the full language pool.
    req_data   = request.get_json(silent=True) or {}
    topic_slug = req_data.get("quiz_topic", "").strip() or None

    language = ui_lang if ui_lang in LANGS else None
    if not language:
        lang, conf = detect_language(msg)
        language = lang if lang in LANGS else None

    if topic_slug:
        topic     = topic_slug   # use the dropdown slug directly
        quiz_count = 10          # cap; get_quiz_questions will return ≤ available
    else:
        topic, _ = resolve_topic(msg, language=language or "unspecified", context_topic=None)
        quiz_count = 10          # always 10 for "all topics"

    questions = get_quiz_questions(language, topic=topic, count=quiz_count)
    items = quiz_page_payload(questions)
    if not items:
        return _reply("I don't have quiz questions for that topic yet. Try a different topic or language.",
                      "request_quiz", language, topic)
    return _reply("Here is your quiz.", "request_quiz", language, topic, quiz=items)


# ── Pending question ("which language?") ─────────────────────────────────────

def _explicit_language(msg, ui_lang):
    if ui_lang in LANGS:
        return ui_lang
    lang, conf = detect_language(msg)
    return lang if conf == "high" and lang in LANGS else None


def _pending_turn(ctx, msg, ui_lang):
    pending = take_pending(ctx)
    if not pending or pending.get("type") != "language":
        return None
    lang = language_only_reply(msg) or _explicit_language(msg, ui_lang)
    if not lang:
        return None                      # user moved on; the question is dropped

    remember_language(ctx, lang)
    trace = {}
    topic = pending.get("topic") or "programming_basics"
    content = _execute_task(pending["intent"], pending["text"], lang, topic, ctx, trace,
                            opts={"activity_id": pending.get("activity_id")})
    return _finish(ctx, pending["intent"], lang, trace.get("topic", topic), pending["text"], content, trace)


# ── Follow-ups ───────────────────────────────────────────────────────────────

def _followup_turn(ctx, msg, ui_lang):
    fu = fr.detect_followup(msg)
    if not fu:
        return None

    la     = ctx.get("last_answer")
    action = fu["action"]

    # Nothing to follow up on yet.
    if not la:
        if action == "switch" and fu["strict"] and fu.get("language"):
            remember_language(ctx, fu["language"])
            lang = fu["language"]
            chips = [f"Explain loops in {LANG_LABEL[lang]}", f"Write a {LANG_LABEL[lang]} calculator program",
                     f"Quiz me on {LANG_LABEL[lang]}"]
            return _reply(language_set_response(lang), "follow_up", lang, ctx.get("topic"), chips=chips)
        return None

    # A message that names a NEW topic is a new request, not a follow-up.
    # (Cue-only messages such as "What's the output?" are "strict" and skip this check.)
    new_topic, tconf = resolve_topic(msg, language="unspecified", context_topic=None)
    topic_found = (not fu["strict"]) and tconf in ("high", "medium") and new_topic != la.get("topic")
    if topic_found and action in ("simpler", "explain_code", "switch"):
        return None

    topic_override = new_topic if (topic_found and action in ("another", "example", "more", "quiz", "generate")) else None
    explicit       = fu.get("language") or _explicit_language(msg, ui_lang)

    # Start from what was shown last, so a chain of follow-ups never loses the code/example.
    trace = {k: la.get(k) for k in ("record_id", "example_id", "template_id", "code", "code_language") if la.get(k)}
    intent, content = _do_followup_action(action, ctx, trace, explicit_lang=explicit, topic_override=topic_override)
    language = trace.get("language") or explicit or la.get("language") or "unspecified"
    topic    = trace.get("topic") or topic_override or la.get("topic")
    return _finish(ctx, intent, language, topic, la.get("text") or msg, content, trace)


def _guess_action(text):
    # For messages the classifier calls "follow_up" but no rule matched.
    t = text.lower()
    if re.search(r"\b(quiz|test|practice|practise)\b", t):
        return "quiz"
    if re.search(r"\b(another|different|more examples?|again)\b", t):
        return "another"
    if re.search(r"\b(same|redo|convert|translate|instead)\b", t) or re.search(r"\b(?:in|to|for|using) (python|java|c)\b", t):
        return "switch"
    if re.search(r"\b(explain|why|how|what)\b", t):
        return "why"
    return "more"


def _do_followup_action(action, ctx, trace, explicit_lang=None, topic_override=None):
    # Act on ctx["last_answer"]. Returns (intent_used, content).
    la        = ctx["last_answer"]
    language  = explicit_lang or la.get("language") or active_language(ctx) or "unspecified"
    topic     = topic_override or la.get("topic") or ctx.get("topic") or "programming_basics"
    src_text  = la.get("text") or ""
    trace["language"], trace["topic"] = language, topic

    if action == "switch":
        intent = la["intent"] if la["intent"] in SWITCHABLE else "show_example"
        content = _execute_task(intent, src_text, language, topic, ctx, trace)
        if not trace.get("asked") and intent != "show_example":      # examples bring their own intro
            content = f"Here's the same idea in **{LANG_LABEL.get(language, language)}**:\n\n{content}"
        return intent, content

    if action in ("another", "example"):
        content = _execute_task("show_example", src_text, language, topic, ctx, trace)
        return "show_example", content

    if action == "simpler":
        return "explain_concept", _simpler(la, trace)

    if action == "explain_code":
        return "explain_code", _execute_task("explain_code", src_text, language, topic, ctx, trace)

    if action in ("more", "why"):
        return "explain_concept", _more_about(la, language, topic, ctx, trace)

    if action == "quiz":
        return "request_quiz", _execute_task("request_quiz", src_text, language, topic, ctx, trace)

    if action == "generate":
        return "generate_code", _execute_task("generate_code", f"write a program for {topic.replace('_', ' ')} {src_text}",
                                              language, topic, ctx, trace)

    return "explain_concept", _more_about(la, language, topic, ctx, trace)


def _simpler(la, trace):
    # A shorter, beginner-level version of what was just said.
    rec = get_record_by_id(la["record_id"]) if la.get("record_id") else None
    if rec:
        trace["record_id"] = rec["id"]
        parts = ["Let me put that more simply:", "", rec.get("definition", "")]
        sentences = re.split(r"(?<=[.!?])\s+", (rec.get("explanation") or "").strip())
        if sentences and sentences[0]:
            parts += ["", " ".join(sentences[:2])]
        return "\n".join(parts).strip()

    ex = get_example(la["example_id"]) if la.get("example_id") else None
    if ex:
        trace["example_id"] = ex["id"]
        return f"In simple terms: {ex.get('explanation', ex.get('description', ''))}"

    if la.get("code"):
        trace["code"], trace["code_language"] = la["code"], la.get("code_language")
        tmpl = _template_by_id(la["template_id"]) if la.get("template_id") else None
        if tmpl and tmpl.get("explanation"):
            return f"In short: {tmpl['explanation']}\n\nWant it line by line? Tap *Explain this code*."
        expl = code_helper.explain_code(la["code"], la.get("code_language") or la.get("language"), limit=5)
        if expl:
            return expl + "\n\nTell me which line is confusing and I'll go deeper on just that one."

    return "Tell me which part is confusing and I'll explain just that part in plain words."


def _more_about(la, language, topic, ctx, trace):
    # Give NEW information about the last answer (not a repeat of it).
    rec = get_record_by_id(la["record_id"]) if la.get("record_id") else None
    if rec:
        trace["record_id"] = rec["id"]
        parts = []
        if rec.get("common_mistakes"):
            parts += ["**Common mistakes to avoid:**"] + [f"- {m}" for m in rec["common_mistakes"]] + [""]
        if rec.get("related_topics"):
            parts += [f"*Related topics: {', '.join(rec['related_topics'])}*", ""]
        if parts:
            ex_text = _execute_task("show_example", la.get("text") or "", language, topic, ctx, {}) \
                if language in LANGS else ""
            return "\n".join(parts).strip() + (f"\n\n**Here's it in action:**\n\n{ex_text}" if ex_text else "")

    ex = get_example(la["example_id"]) if la.get("example_id") else None
    code = la.get("code") or (ex or {}).get("code")
    if code:
        lang = la.get("code_language") or (ex or {}).get("language") or language
        expl = code_helper.explain_code(code, lang)
        if ex:
            trace["example_id"] = ex["id"]
        if expl:
            out = (ex or {}).get("output")
            return expl + (f"\n\n**Output:**\n```\n{out}\n```" if out else "")

    if language in LANGS:
        return _execute_task("show_example", la.get("text") or "", language, topic, ctx, trace)
    return "Ask me about a specific part and I'll go deeper — for example *Explain it simpler* or *Show me an example*."


# ── Normal pipeline ──────────────────────────────────────────────────────────

def _resolve_language(msg, primary, ctx, ui_lang):
    # Returns (language, confidence, assumed_from_context)
    #
    # Priority:
    #   1. UI tab explicitly set to python/java/c → use it, no text detection.
    #   2. Language explicitly named in the message text → use it.
    #   3. Multiple languages in text → "multiple".
    #   4. Global intents (greeting, bot_capabilities, compare) → "unspecified",
    #      never carry forward from context.
    #   5. Auto-detect mode → "unspecified". Do NOT carry forward the remembered
    #      language — general questions on Auto-detect get general answers.
    #      (Language memory only applies when a language tab is selected.)
    if ui_lang in LANGS:
        return ui_lang, "high", False
    lang, conf = detect_language(msg, context_language=None, intent=primary)
    if lang == "multiple":
        return "multiple", "high", False
    if lang in LANGS:
        return lang, "high", False
    if primary in ("greeting", "bot_capabilities", "compare_concepts"):
        return "unspecified", "low", False
    # Auto-detect mode: no language in text → return unspecified.
    # General questions get shared/general KB records.
    return "unspecified", "low", False


def _normal_turn(ctx, msg, ui_lang, greeting_prefix="", force_intent=None):
    trace = {}
    clf     = predict(msg)
    primary = force_intent or clf["intent"]
    conf    = clf["confidence"]

    code_present = code_helper.looks_like_code(msg)
    instruction, code = code_helper.extract_code(msg) if code_present else ("", None)

    # "Good afternoon! I need help understanding classes in Java."
    # The training data labels such messages "greeting", but they contain a real request:
    # if the part after the greeting names a topic or language, answer that request.
    if primary == "greeting" and not code_present and not force_intent:
        rest = fr.strip_greeting(msg)
        if len(rest.split()) >= 3:
            greeted = rest.lower() != msg.lower()
            r_topic, r_tconf = resolve_topic(rest, language="unspecified", context_topic=None)
            r_lang, _ = detect_language(rest)
            if r_tconf in ("high", "medium") or r_lang in LANGS:
                return _normal_turn(ctx, rest, ui_lang, greeting_prefix="Hello! " if greeted else "",
                                    force_intent="explain_concept")
            rest_clf = predict(rest)
            if rest_clf["intent"] not in SOLO_INTENTS and rest_clf["confidence"] >= LOW_CONFIDENCE:
                return _normal_turn(ctx, rest, ui_lang, greeting_prefix="Hello! " if greeted else "")

    primary = _post_classify(primary, msg, conf, code_present, instruction)

    # Out-of-scope: non-programming subject + no programming signal → redirect.
    # This runs after _post_classify so we respect any manual overrides, but
    # before language/topic resolution so we don't waste work on OOS messages.
    if not code_present and is_out_of_scope(msg):
        language_ctx = ctx.get("language") or "unspecified"
        # Build 3-4 in-scope starter suggestions relevant to the session
        last_lang  = ctx.get("language")
        last_topic = ctx.get("topic") or "programming_basics"
        lang_label = LANG_LABEL.get(last_lang, "Python")
        suggested  = [
            f"Explain {last_topic.replace('_', ' ')} in {lang_label}",
            f"Show me a {lang_label} example",
            f"Quiz me on {lang_label}",
            "What topics can you teach me?",
        ] if last_lang else STARTER_CHIPS + ["What topics can you teach me?"]
        return _reply(
            out_of_scope_response(), "clarification",
            language_ctx, ctx.get("topic"),
            chips=suggested[:4],
            is_oos=True,
        )

    # Language: named by the user > detected in pasted code > remembered.
    language, lang_conf, assumed = _resolve_language(msg, primary, ctx, ui_lang)
    if code_present:
        code_lang = code_helper.detect_code_language(code)
        if code_lang and lang_conf != "high":
            language, lang_conf, assumed = code_lang, "high", False
        trace.update({"pasted": True, "code": code, "code_language": language if language in LANGS else code_lang})

    topic, tconf = resolve_topic(msg, language=language, context_topic=ctx.get("topic"))
    trace["tconf"] = tconf

    # Unclear request -> keyword answer, or ask a short "did you mean" question.
    if primary == "clarification":
        intent, content = _clarify(msg, language, topic, ctx, trace, clf)
        return _finish(ctx, intent, language, topic, msg, content, trace, conf, prefix=greeting_prefix)

    # Several requests in one message?
    intents = (is_multi_intent(msg, result=clf)
               if (conf >= LOW_CONFIDENCE and not code_present and not force_intent) else [primary])
    # The compare rule demoted a false "compare_concepts" -> do not run the model's wrong guess as a second task.
    if clf["intent"] == "compare_concepts" and primary != "compare_concepts":
        intents = [i for i in intents if i != "compare_concepts"] or [primary]
    plan    = build_task_plan(intents, primary)

    results = []
    for intent in plan:
        content = _execute_task(intent, msg, language, topic, ctx, trace)
        if trace.get("asked"):
            results = [{"intent": intent, "content": content}]
            break
        if content:
            results.append({"intent": intent, "content": content})

    text = format_response(results) if results else fallback_response()

    # Say so when the language came from context rather than from the user.
    suffix = ""
    if (assumed and not trace.get("asked") and language in LANGS and not ctx.get("notice_shown")
            and (primary in CONTENT_INTENTS or primary == "request_quiz")):
        suffix = "\n\n" + assumed_language_note(language)
        ctx["notice_shown"] = True

    final_intent = next((r["intent"] for r in reversed(results) if r["intent"] in CONTENT_INTENTS), primary)
    return _finish(ctx, final_intent if results else primary, language, trace.get("topic", topic), msg, text, trace,
                   conf, prefix=greeting_prefix, suffix=suffix)


def _clarify(msg, language, topic, ctx, trace, clf):
    # The classifier is unsure. Try, in order:
    #   1. a knowledge-base answer found by keywords (works without a clear intent)
    #   2. re-explaining the last answer more simply
    #   3. a short "did you mean A or B?" question
    rec = get_record_by_keywords(msg, language)
    if rec:
        trace["record_id"] = rec["id"]
        return "explain_concept", format_record_response(rec)

    if ctx.get("last_answer"):
        intent, content = _do_followup_action("simpler", ctx, trace)
        return intent, content

    alts = [x["intent"] for x in predict_top_n(msg, 4, result=clf) if x["intent"] in INTENT_CHOICE_TEXT]
    # Only ask "did you mean ...?" when the model has SOME signal; for gibberish show examples instead.
    if len(alts) >= 2 and clf["confidence"] >= 0.20:
        trace["chips"] = [c for c in (_intent_chip(a, language, topic) for a in alts[:3]) if c]
        return "clarification", did_you_mean_response(alts)
    trace["chips"] = STARTER_CHIPS
    return "clarification", fallback_response()


# ══════════════════════════════════════════════════════════════════════════════
#  Post-classification rules
# ══════════════════════════════════════════════════════════════════════════════

_CONCEPT_PROTECTION = re.compile("|".join([
    r"\bwho (?:made|created|developed|invented|wrote|designed|is|was)\b",
    r"\bwhat (?:is|are) (?:the )?(?:python|java|jvm|jdk|jre|bytecode|venv|pip)\b",
    r"\bwhat (?:is|are) (?:the )?c(?:\s+(?:programming|language))?(?![\w+#])",
    r"\bhistory of\b", r"\b(?:when|where) was\b", r"\bwhy was (?:python|java|c)\b",
    r"\bwhat year\b", r"\btell me about\b",
    r"\bexplain (?:python|java|c programming|c language)\b(?!\s+(?:code|program|snippet|script))",
    r"\babout c language\b", r"\bintroduce c\b", r"\bc (?:overview|introduction)\b",
    r"\bdennis ritchie\b", r"\bb language\b", r"\bbcpl\b",
    r"\bvirtual environment\b", r"\bvenv\b", r"\bpip (?:install|freeze|list)\b",
    r"\brequirements\.txt\b", r"\bhow to (?:create a virtual|activate|deactivate|install packages)\b",
    r"\binfluence of\b", r"\bintroduction to\b", r"\bintro to\b",
    r"\bbeginners? guide\b", r"\boverview of\b",
]), re.IGNORECASE)

_LANG_WORD    = re.compile(r"\b(python|java|c)\b", re.IGNORECASE)
_COMPARE_CUES = re.compile(r"\b(compare|compared|comparison|vs\.?|versus|difference|differences|differ|differs|between|"
                           r"better|similar|similarities|same as|or)\b", re.IGNORECASE)


def _post_classify(intent, text, confidence, code_present=False, instruction=""):
    # Fix common misclassifications based on keyword rules.
    t = text.lower()

    # Pasted code: always route to explain_code (debug and predict_output removed).
    if code_present:
        if intent == "explain_code":
            return intent
        return "explain_code"

    # History / concept questions must stay explain_concept.
    if _CONCEPT_PROTECTION.search(t):
        return "explain_concept"

    # "make/write/create a program/code" -> generate_code (checked first).
    # "explain X program/system/using" — explanation of a program concept, not code generation.
    # Must run BEFORE CODE_REQUEST_PHRASES check to prevent "explain banking program" → generate_code.
    if re.search(r"^explain\b", t) and re.search(r"\b(?:program|system|application|using|ledger)\b", t):
        return "explain_concept"

    # "Can you give me an introduction to X" / "beginner-friendly introduction"
    if re.search(r"\b(?:introduction to|intro to|overview of|beginner.friendly)\b", t):
        return "explain_concept"

    if any(p in t for p in CODE_REQUEST_PHRASES):
        return "generate_code"

    # "give/show sample code" -> show_example (user wants to see, not generate).
    if any(p in t for p in SHOW_EXAMPLE_PHRASES):
        return "show_example"

    # "Can you explain X?" / "Can you show X?" — always educational, never bot_capabilities.
    if re.search(r"^can you (?:explain|tell|describe|show|help)", t):
        if any(p in t for p in CODE_REQUEST_PHRASES):
            return "generate_code"
        return "explain_concept"

    # "Explain X" with a known topic word — educational, not capabilities.
    if re.search(r"^explain\b", t) and not re.search(r"\b(what|which|how|topics?)\b", t):
        if any(p in t for p in CODE_REQUEST_PHRASES):
            return "generate_code"
        return "explain_concept"

    # "code for" -> generate_code only if it looks like a generation request.
    if "code for" in t and any(w in t for w in ["write", "make", "create", "build"]):
        return "generate_code"

    # Low confidence + code keywords + a language word -> generate_code.
    # (whole-word match: the old "c " test matched "basic " and "topic ")
    if confidence < 0.40 and any(p in t for p in ["code", "program", "write", "make"]) and _LANG_WORD.search(t):
        return "generate_code"

    # "compare_concepts" needs a comparison word; "Explain pointers in C" is a plain explanation.
    if intent == "compare_concepts" and not _COMPARE_CUES.search(t):
        return "explain_concept"

    # A bare language switch ("what about Java?", "now in C") -> follow_up.
    if fr.is_pure_language_message(t):
        return "follow_up"

    return intent


# ══════════════════════════════════════════════════════════════════════════════
#  Task executor
# ══════════════════════════════════════════════════════════════════════════════

def _ask_language(intent, text, topic, ctx, trace, activity_id=None, prompt=None):
    # Ask which language. The original request is remembered for ONE turn and
    # finished as soon as the user answers (typed or via the Python/Java/C chips).
    set_pending(ctx, type="language", intent=intent, text=text, topic=topic, activity_id=activity_id)
    trace["asked"] = True
    return prompt or language_clarification_response(topic.replace("_", " "))


_BARE_LANGUAGE_KEYWORDS = {"python", "java", "c", "python language", "java language", "c language", "the c language",
                           "python programming", "java programming", "c programming"}


def _only_language_keywords(rec, text):
    # True when the record matched ONLY because the text names the language itself.
    t = text.lower()
    hits = [k.lower() for k in rec.get("keywords", []) if k.lower() in t]
    return bool(hits) and all(h in _BARE_LANGUAGE_KEYWORDS for h in hits)


def _fmt_record(rec, trace, concise=False):
    trace["record_id"] = rec["id"]
    return format_record_response(rec, concise=concise)


def _example_groups(language, topic, text):
    # Candidate examples, best first: keyword record -> topic -> (only if empty) language.
    groups = []
    rec = get_record_by_keywords(text, language)
    if rec and rec.get("example_ids"):
        exs = [get_example(i) for i in rec["example_ids"]]
        groups.append([e for e in exs if e and e.get("language") == language])
    groups.append(get_examples_by_topic(topic, language))
    groups = [g for g in groups if g]
    if not groups:
        lang_ex = get_examples_by_language(language)
        if lang_ex:
            groups.append(lang_ex)
    return groups


def _pick_example(language, topic, text, ctx):
    # Returns (example, exhausted). Never repeats an example the user has seen,
    # until every example for the topic has been shown.
    shown  = set(ctx.get("shown_examples", []))
    groups = _example_groups(language, topic, text)
    for group in groups:
        for ex in group:
            if ex["id"] not in shown:
                return ex, False
    if groups:
        return groups[0][0], True
    return None, False


def _show_example(language, topic, text, ctx, trace):
    ex, exhausted = _pick_example(language, topic, text, ctx)
    if ex is None:
        rec = get_record(language, topic) or get_record_by_alias(text, language)
        if rec:
            return _fmt_record(rec, trace)
        return no_content_response("show_example", language, topic)
    trace["example_id"] = ex["id"]
    trace["code"], trace["code_language"] = ex.get("code"), ex.get("language")
    mark_example_shown(ctx, ex["id"])
    intro = ("That's every example I have on this topic, so here's the first one again:\n\n"
             if exhausted else f"Here's a **{LANG_LABEL.get(language, language)}** example — *{ex.get('title', '')}*:\n\n")
    return intro + format_example_response(ex)


def _generate(language, topic, text, trace):
    # Template trigger phrases start with the language name ("java simple calculator"),
    # so the language is added to the search text — otherwise a request whose language
    # arrived in a LATER message (after "which language?") would match the wrong template.
    tmpl = find_template(language, topic, f"{language} {text}")
    if tmpl is None:
        return None
    code, explanation, lang = fill_template(tmpl)
    if code is None:
        return None
    trace["template_id"] = tmpl["id"]
    trace["code"], trace["code_language"] = code, language
    parts = [f"```{lang or language}", code, "```"]
    if explanation:
        parts += ["", explanation]
    return "\n".join(parts)


def _template_by_id(template_id):
    for t in get_templates() or []:
        if t["id"] == template_id:
            return t
    return None


def _execute_task(intent, text, language, topic, ctx, trace, opts=None):
    # Execute a single task intent and return the response string.
    # `trace` collects what was shown (record / example / code) for ctx["last_answer"].
    opts = opts or {}

    # Several languages named at once: answer each (max two) separately.
    if language == "multiple" and intent in ("show_example", "generate_code", "show_syntax"):
        langs = [l for l in detect_all_languages(text) if l in LANGS][:2]
        parts = []
        for l in langs:
            sub = _execute_task(intent, text, l, topic, ctx, {}, opts)
            parts.append(f"### {LANG_LABEL[l]}\n\n{sub}")
        return "\n\n".join(parts) if parts else language_clarification_response(topic.replace("_", " "))

    # ── Greeting / capabilities ───────────────────────────────────────────────
    if intent == "greeting":
        return greeting_response(language)
    if intent == "bot_capabilities":
        return capabilities_response()

    # ── Follow-up the rules did not catch ─────────────────────────────────────
    if intent == "follow_up":
        la = ctx.get("last_answer")
        if la:
            fu = fr.detect_followup(text)
            action = fu["action"] if fu else _guess_action(text)
            explicit = _explicit_language(text, "auto")
            _, content = _do_followup_action(action, ctx, trace, explicit_lang=explicit)
            return content
        if language in LANGS:
            return language_set_response(language)
        return fallback_response()

    # ── Clarification ─────────────────────────────────────────────────────────
    if intent == "clarification":
        _, content = _clarify(text, language, topic, ctx, trace, predict(text))
        return content

    # ── Explain concept ───────────────────────────────────────────────────────
    if intent == "explain_concept":
        # Strategy 1: keyword match (shared records first when language unknown).
        rec = get_record_by_keywords(text, language)
        if rec and _only_language_keywords(rec, text):
            rec = None          # "what does eval() do in Python?" must not return Python's history

        # Strategy 2: topic -> alias -> shared.
        if rec is None:
            prefer_overview = is_overview_question(text)
            # Nothing matched and the topic is just the default: say so instead of guessing.
            if (trace.get("tconf") == "low" and topic == "programming_basics" and not prefer_overview
                    and not _CONCEPT_PROTECTION.search(text.lower())
                    and not get_record_by_alias(text, language)):
                lang = LANG_LABEL.get(language)
                trace["chips"] = [f"Explain variables{' in ' + lang if lang else ''}",
                                  f"Explain loops{' in ' + lang if lang else ''}",
                                  f"Explain functions{' in ' + lang if lang else ''}"]
                return ("I don't have a lesson on that specific point yet. I can explain the core topics — "
                        "variables, loops, functions, arrays, classes and more. Which would you like?")
            if language == "unspecified":
                rec = get_record("shared", topic) or get_record_by_alias(text, "unspecified")
                if rec is None:
                    return _ask_language(intent, text, topic, ctx, trace)
            else:
                rec = (get_record(language, topic, prefer_overview=prefer_overview)
                       or get_record_by_alias(text, language)
                       or get_record("shared", topic))
        if rec:
            concise = is_specific_question(text) and not rec.get("quick_facts")
            return _fmt_record(rec, trace, concise=concise)
        return no_content_response(intent, language, topic)

    # ── Show syntax ───────────────────────────────────────────────────────────
    if intent == "show_syntax":
        if language == "unspecified":
            return _ask_language(intent, text, topic, ctx, trace)
        rec = (get_record_by_keywords(text, language)
               or get_record(language, topic)
               or get_record_by_alias(text, language))
        if rec:
            ex = get_example(rec["syntax_example_id"]) if rec.get("syntax_example_id") else None
            if ex and ex.get("language") in (language, None):
                trace["record_id"], trace["example_id"] = rec["id"], ex["id"]
                trace["code"], trace["code_language"] = ex.get("code"), ex.get("language")
                mark_example_shown(ctx, ex["id"])
                return f"Here's the syntax for **{rec.get('title', topic.replace('_', ' '))}**:\n\n" + format_example_response(ex)
            return _fmt_record(rec, trace)
        return no_content_response(intent, language, topic)

    # ── Show example ──────────────────────────────────────────────────────────
    if intent == "show_example":
        if language == "unspecified":
            return _ask_language(intent, text, topic, ctx, trace)
        return _show_example(language, topic, text, ctx, trace)

    # ── Generate code ─────────────────────────────────────────────────────────
    if intent == "generate_code":
        activity_id = get_activity_id(text) or opts.get("activity_id")
        meta        = ACTIVITY_MAP.get(activity_id, {}) if activity_id else {}
        display     = meta.get("display")

        if language == "unspecified":
            prompt = (f"I can generate a **{display}** program for you.\n\n"
                      "Which programming language would you like? (Python, Java, or C)") if display else \
                     "Which programming language would you like the code in? (Python, Java, or C)"
            return _ask_language(intent, text, topic, ctx, trace, activity_id=activity_id, prompt=prompt)

        gen_topic = meta.get("topic", topic)
        trace["topic"] = gen_topic
        content = _generate(language, gen_topic, f"{display} {text}" if display else text, trace)
        if not content and display:
            content = _generate(language, gen_topic, display, trace)
        if content:
            lang = LANG_LABEL.get(language, language)
            intro = f"Here is a **{display}** program in **{lang}**:\n\n" if display else f"Here's a **{lang}** program for that:\n\n"
            return intro + content
        # Fall back to a static example for this topic.
        return _show_example(language, topic, text, ctx, trace)

    # ── Explain code ──────────────────────────────────────────────────────────
    if intent == "explain_code":
        if trace.get("pasted"):
            code, lang = trace["code"], trace.get("code_language") or language
            expl = code_helper.explain_code(code, lang if lang in LANGS else "python")
            if expl:
                return expl + "\n\nWant to know what it prints? Ask *What's the output?*"
            return "I couldn't break that code down automatically. Try pasting a few lines at a time, or tell me which line confuses you."

        la = ctx.get("last_answer") or {}
        if la.get("example_id"):
            ex = get_example(la["example_id"])
            if ex:
                trace["example_id"] = ex["id"]
                trace["code"], trace["code_language"] = ex.get("code"), ex.get("language")
                return "Here's how it works:\n\n" + format_example_full(ex)
        if la.get("code"):
            lang = la.get("code_language") or language
            expl = code_helper.explain_code(la["code"], lang if lang in LANGS else "python")
            trace["code"], trace["code_language"] = la["code"], lang
            tmpl = _template_by_id(la["template_id"]) if la.get("template_id") else None
            if tmpl:
                trace["template_id"] = tmpl["id"]
            head = (tmpl or {}).get("explanation", "")
            if expl or head:
                return ((head + "\n\n") if head else "") + (expl or "")
        if language in LANGS and topic != "programming_basics":
            examples = get_examples_by_topic(topic, language)
            if examples:
                trace["example_id"] = examples[0]["id"]
                return "Here's an example with its output and how it works:\n\n" + format_example_full(examples[0])
        trace["chips"] = []
        return ask_for_code_response("explain")

    # ── Compare concepts ──────────────────────────────────────────────────────
    if intent == "compare_concepts":
        rec = get_record("shared", topic)
        if rec:
            return _fmt_record(rec, trace)
        langs_detected = detect_all_languages(text)
        if len(langs_detected) >= 2 and langs_detected[0] != "unspecified":
            parts = []
            for lang in langs_detected[:2]:
                r = get_record(lang, topic)
                if r:
                    parts.append(f"### {LANG_LABEL.get(lang, lang)}\n{r.get('definition', '')}\n{r.get('explanation', '')}")
            if parts:
                return "\n\n---\n\n".join(parts)
        rec = get_record_by_alias(text, language)
        if rec:
            return _fmt_record(rec, trace)
        return no_content_response(intent, language, topic)

    # ── Request quiz ──────────────────────────────────────────────────────────
    if intent == "request_quiz":
        if language == "unspecified":
            return _ask_language(intent, text, topic, ctx, trace,
                                 prompt="Which language should the quiz be on — **Python**, **Java** or **C**?")
        quiz_lang = language if language in LANGS else None
        state = start_quiz(quiz_lang, topic)
        if not state:
            return format_quiz_session([])
        ctx["quiz"] = state
        trace["quiz_started"] = True
        trace["chips"] = quiz_chips(state)
        return quiz_intro(state) + "\n\n" + format_current_question(state)

    # ── Fallback ──────────────────────────────────────────────────────────────
    return fallback_response()
