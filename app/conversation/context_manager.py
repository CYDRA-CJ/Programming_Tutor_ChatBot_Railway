import copy

from app.conversation import conversation_store as store

LANGUAGE_MEMORY_TURNS = 8

_DEFAULT_CONTEXT = {
    "kind":           "chat",          
    "turn":           0,              
    "language":       None,            
    "language_turn":  -999,           
    "notice_shown":   False,          
    "topic":          "programming_basics",
    "last_intent":    None,          
    "last_answer":    None,
    "pending":        None,
    "quiz":           None,
    "shown_examples": [],
}


# ── Load / save ───────────────────────────────────────────────────────────────

def get_context(session_id):
    # Load the context for a session (or a fresh default one).
    ctx  = copy.deepcopy(_DEFAULT_CONTEXT)
    data = store.load_context(session_id)
    if data:
        for key in _DEFAULT_CONTEXT:
            if key in data:
                ctx[key] = data[key]
    return ctx


def save_context(session_id, ctx):
    store.save_context(session_id, ctx)


def clear_context(session_id):
    # Reset context for a session (clear history button).
    kind  = get_context(session_id).get("kind", "chat")
    fresh = copy.deepcopy(_DEFAULT_CONTEXT)
    fresh["kind"] = kind
    store.save_context(session_id, fresh)


def update_context(session_id, **kwargs):
    # Convenience wrapper: load, change some keys, save.
    ctx = get_context(session_id)
    for key, value in kwargs.items():
        if key in _DEFAULT_CONTEXT:
            ctx[key] = value
    store.save_context(session_id, ctx)
    return ctx


# ── Turn helpers ──────────────────────────────────────────────────────────────

def begin_turn(ctx):
    ctx["turn"] = int(ctx.get("turn", 0)) + 1


def remember_language(ctx, language):
    # Remember the language the user is working in.
    if not language or language in ("unspecified", "multiple"):
        return
    if language != ctx.get("language"):
        ctx["notice_shown"] = False      
    ctx["language"]      = language
    ctx["language_turn"] = ctx["turn"]


def active_language(ctx):
    # Return the remembered language if it was used recently, else None.
    lang = ctx.get("language")
    if lang and ctx["turn"] - ctx.get("language_turn", -999) <= LANGUAGE_MEMORY_TURNS:
        return lang
    return None


def set_pending(ctx, **fields):
    ctx["pending"] = dict(fields)


def take_pending(ctx):
    # Return and clear the pending question. A pending question lives one turn.
    pending = ctx.get("pending")
    ctx["pending"] = None
    return pending


def mark_example_shown(ctx, example_id):
    shown = ctx.setdefault("shown_examples", [])
    if example_id and example_id not in shown:
        shown.append(example_id)
        del shown[:-60]               


def record_answer(ctx, intent, language, topic, text, trace):
    # Remember what the bot just answered so follow-ups can act on it.
    ctx["last_answer"] = {
        "intent":        intent,
        "language":      language,
        "topic":         topic,
        "text":          text[:300],
        "record_id":     trace.get("record_id"),
        "example_id":    trace.get("example_id"),
        "template_id":   trace.get("template_id"),
        "code":          (trace.get("code") or "")[:3000] or None,
        "code_language": trace.get("code_language"),
    }
