import re

# ── Quick-reply chip texts (also understood as typed messages) ───────────────
CHIP_EXAMPLE    = "Show me an example"
CHIP_ANOTHER    = "Show another example"
CHIP_QUIZ       = "Quiz me on this"
CHIP_SIMPLER    = "Explain it simpler"
CHIP_EXPLAIN    = "Explain this code"
CHIP_MORE       = "Tell me more"
CHIP_SKIP       = "Skip"
CHIP_STOP_QUIZ  = "Stop quiz"
CHIP_QUIZ_AGAIN = "Quiz me again"


def chip_same_in(language_label):
    return f"Do the same in {language_label}"


def chip_write_program(language_label):
    return f"Write a {language_label} program for this"


_LANG = r"(python|java|c)"
_END  = r"[\s?.!]*$"


def _words(text):
    return len(text.split())


# ── Language switch ("now in Java", "what about C?", "do the same in Python") ─
# STRICT patterns are only a language reference — no topic words at all.
_SWITCH_STRICT = [
    re.compile(p, re.IGNORECASE) for p in [
        # "what about Python?" / "how about Java?"
        r"^(?:ok(?:ay)?[, ]*)?(?:and |now |then )?(?:what|how) about (?:the )?(?:using |in )?" + _LANG + r"(?: (?:language|version|programming|one|equivalent|then))?" + _END,
        # "do the same in C" / "show me the same in Java"
        r"^(?:ok(?:ay)?[, ]*)?(?:and )?(?:do|show|give|write|make|redo)(?: me)?(?: it| that| this)?(?: the)? same(?: thing| code| example| program)? (?:in|for|with|using) " + _LANG + _END,
        # bare "in Java" / "for C" / "using Python"
        r"^(?:and |now |then )?(?:in|for|using|with|to) " + _LANG + _END,
        # "switch to Java" / "same in C" / "equivalent in Python"
        r"^(?:now|switch to|convert (?:it |that |this )?to|translate (?:it |that |this )?to|equivalent in|same in|same for|same with|redo (?:it |that )?in|can you redo that in|can you show the same thing in) (?:in )?" + _LANG + _END,
        # bare "Java" / "Python please" / "C version"
        r"^(?:and )?" + _LANG + r"(?: (?:version|language|equivalent|one|program|please|then))?" + _END,
        # "can you show it in Java?" / "could you write that in C?"
        r"^(?:can|could) (?:you|i|we) (?:do|see|show|write|have|redo|convert|translate) (?:it|that|this|the same(?: thing)?)(?: again)? (?:in|using|with|to|for) " + _LANG + _END,
        # "give me the Java version" / "show me the Python one"
        r"^(?:give|show)(?: me)? (?:the|a) " + _LANG + r" (?:version|one|example|equivalent|code)" + _END,
        # "Java please" / "in Java please"
        r"^(?:in )?" + _LANG + r" please" + _END,
        # "how do you do that in Java?" — no topic word, just the language
        r"^how (?:do|would|can) (?:you|i|we) do (?:it|that|this) in " + _LANG + _END,
    ]
]
# LOOSE: a switch cue plus a language, but the sentence may also name a topic.
# chat.py ignores a loose match when the message contains a new topic.
_SWITCH_LOOSE = re.compile(
    r"\b(?:do|show|see|write|convert|translate|make|give|redo|use)\b.*\b(?:in|using|for|to) " + _LANG + r"\b",
    re.IGNORECASE,
)

# ── Request another example ──────────────────────────────────────────────────
_ANOTHER = [
    re.compile(p, re.IGNORECASE) for p in [
        # "another example" / "one more version" / "a different sample"
        r"\b(?:another|one more|different|next|more)\b.{0,20}\b(?:examples?|samples?|ones?|versions?)\b",
        # bare "another" / "one more please" / "next one"
        r"^(?:another|again|one more|next|more)(?: one| please| example| sample)?" + _END,
        # "show me another" / "give me more" / "give me a different one"
        r"\b(?:show|give)(?: me)? (?:another|more|a different|a new)\b",
        # explicit short phrases
        r"\bcan you give (?:me )?another(?: example)?\b",
        r"\bshow (?:me )?(?:a )?(?:different|another|one more|new) (?:example|sample|one|version)\b",
        # "try another" / "try a different one"
        r"^try (?:another|a different)(?: one| example| sample)?" + _END,
        # "let me see another one" / "let me try another"
        r"^let me (?:see|try) (?:another|a different|one more)(?: one| example| sample)?" + _END,
    ]
]

# ── Show an example ──────────────────────────────────────────────────────────
_EXAMPLE = re.compile(
    # standard: "show me an example" / "give me some code" / "can you show me a sample"
    r"^(?:ok(?:ay)?[, ]*)?(?:please )?(?:show|give|let me see|can i see|can you show|can you give)(?: me)?(?: an?| the| some)? ?"
    r"(?:examples?|samples?|sample code|code|code examples?)(?: please| of (?:this|that|it))?[\s?.!]*$"
    # "show me one" / "give me one" / "give me a sample" — no word "example" needed
    r"|^(?:show|give)(?: me)? (?:one|a sample)(?: please)?[\s?.!]*$"
    # "let me see it" / "let me see the code" / "let me see one" / bare "let me see"
    r"|^let me see(?: (?:(?:an?|the) )?(?:example|sample|code|one|it))?[\s?.!]*$",
    re.IGNORECASE,
)

# ── Explain it simpler ───────────────────────────────────────────────────────
_SIMPLER = re.compile(
    r"\b(?:simpler|simplify|simple terms|simply|easier|eli5|dumb it down|break it down|layman|"
    r"too (?:hard|complex|difficult|complicated|technical)|"
    r"(?:i )?(?:still )?(?:don'?t|do not|didn'?t|did not|can'?t) (?:really )?(?:get|understand|follow)|"
    r"confus(?:ed|ing)|not clear|what do you mean|i'?m lost|rephrase|"
    r"explain (?:it |that |this )?(?:again|differently|more simply|in simple terms|in plain english)|"
    r"in other words|plain english|plain language|plain words|"
    r"make it (?:simpler|easier|clearer)|can you simplify|"
    r"hard to (?:understand|follow|get)|difficult to (?:understand|follow)|"
    r"i(?:'m| am) (?:still )?(?:confused|lost|not following)|lost me)\b",
    re.IGNORECASE,
)

# ── Explain this code ────────────────────────────────────────────────────────
_EXPLAIN_CODE = [
    re.compile(p, re.IGNORECASE) for p in [
        # "explain this code" / "walk me through it" / "break down the program"
        r"^(?:ok(?:ay)?[, ]*)?(?:please )?(?:explain|walk me through|break down|describe|go through)(?: me)?(?: this| the| that| it)?"
        r"(?: code| example| program| snippet| one| output)?(?: to me)?(?: line by line| step by step)?" + _END,
        # "what does this do?" / "what does the code do?"
        r"^what does (?:this|it|that|the code|the program) do" + _END,
        # "line by line" anywhere in message
        r"\bline by line\b",
        # "how does this work?" / "how does it work?" — code-level question
        r"^how does (?:this|it|that|the code|the program|this code|that code) work" + _END,
        # "what is each line doing?" / "what does each part do?"
        r"^what (?:is|does) (?:each|every) (?:line|part|section|step)(?: do(?:ing)?)?" + _END,
        # "can you annotate this?" / "annotate the code"
        r"\bannotat(?:e|ion)\b.{0,20}\b(?:code|this|it|that)\b",
        # "add comments" / "add comments to the code" / "can you add comments"
        r"(?:add|put|include|write)(?: some)? comments?(?: to| on| in)?(?: the| this| that)? (?:code|program|example|it)\b",
        # "step by step" anywhere
        r"\bstep by step\b",
        # "what does X mean in the code" / "what does `i` do here"
        r"^what does .{1,20} (?:mean|do|stand for)(?: (?:here|in (?:this|the) code|in (?:this|the) example))?" + _END,
        # "how does this line work?" / "what is this line doing?"
        r"^(?:how does|what (?:is|does)) this line\b",
    ]
]

# ── Why / how does it work ───────────────────────────────────────────────────
_WHY = re.compile(
    r"^(?:but |and |so |ok(?:ay)?[, ]*)?(?:"
    r"why(?: is that| so| does (?:it|this|that) work(?: like that)?|'?s (?:it|that) (?:like that|necessary|needed|important))?|"
    r"why not|how come|"
    r"how does (?:it|that|this)(?: (?:work|work out|do that|know(?: that)?|happen|get there))?\??|"
    r"how so|how does it do that|"
    r"but (?:how|why)|"
    r"i don'?t get (?:why|how)|"
    r"what'?s the (?:reason|point|purpose)(?: (?:for|of|behind) (?:this|that|it))?"
    r")" + _END,
    re.IGNORECASE,
)

# ── Tell me more ─────────────────────────────────────────────────────────────
_MORE = re.compile(
    r"^(?:ok(?:ay)?[, ]*)?(?:"
    r"tell me more|more details?|more info(?:rmation)?|elaborate|go on|continue|keep going|expand|"
    r"can you elaborate|what else|anything more|more about (?:it|this|that)|"
    r"i need more detail(?: on that)?(?: point)?|"
    r"go (?:deeper|further)|dive (?:deeper|in)|"
    r"can you expand(?: on that| on this)?|"
    r"can you (?:go|tell me)(?: a bit)? (?:more|further|deeper)|"
    r"tell me more about (?:it|this|that)|"
    r"give me more (?:detail|info|information)(?: on (?:this|that|it))?|"
    r"what (?:else|more) (?:can|should) i know|"
    r"anything else (?:about|on|regarding) (?:this|that|it)|"
    r"what other(?: things)? (?:should|can) i know"
    r")" + _END,
    re.IGNORECASE,
)

# ── Quiz me ──────────────────────────────────────────────────────────────────
_QUIZ_THIS = re.compile(
    r"^(?:ok(?:ay)?[, ]*)?(?:quiz|test) me(?: (?:on|about) (?:this|that|it|these|the same))?" + _END
    + r"|^(?:give me|i want|let me|i'?d like) (?:a |to )?(?:quiz|practice|practise)(?: on (?:this|that|it))?" + _END
    + r"|^(?:let'?s|can we) (?:practice|practise|try a quiz)" + _END
    # "try me" / "challenge me" / "test my knowledge"
    + r"|^(?:try|challenge) me(?: on (?:this|that|it))?" + _END
    + r"|^test my knowledge(?: on (?:this|that|it))?" + _END
    # "i want to practice" / "i want to be quizzed"
    + r"|^i (?:want|need) to (?:practice|practise|be quizzed|be tested)(?: on (?:this|that|it))?" + _END
    # "can you quiz me?" / "can you test me on this?"
    + r"|^can you (?:quiz|test) me(?: (?:on|about) (?:this|that|it))?" + _END,
    re.IGNORECASE,
)

# ── Generate code for this topic ─────────────────────────────────────────────
_GENERATE = re.compile(
    # "write me a Python program for this" / "build a script for that"
    r"^(?:write|make|create|generate|build|code)(?: me)? (?:an?|the) (?:(python|java|c) )?(?:program|code|script)(?: for| about| on)? (?:this|that|it)[\s?.!]*$"
    # "code this for me" / "code it in Python"
    r"|^code (?:this|it|that)(?: for me)?(?: in (python|java|c))?[\s?.!]*$"
    # "can you make a program for this?" / "can you write a Java script for it?"
    r"|^can you (?:write|make|create|build)(?: me)? (?:an?|the) (?:(python|java|c) )?(?:program|code|script)(?: for| about| on)? (?:this|that|it)[\s?.!]*$"
    # "make me a program" — no "for this" required
    r"|^(?:write|make|create|generate|build)(?: me)? (?:an?|the) (?:(python|java|c) )?(?:program|code|script)\s*$",
    re.IGNORECASE,
)


def detect_followup(text):
    # Return {"action": str, "language": str|None, "strict": bool} or None.
    # Actions: switch, another, example, simpler, explain_code, why, more,
    #          quiz, generate.
    t = text.strip().lower()
    if not t or _words(t) > 16:   # raised from 14 → 16 to allow natural longer phrases
        return None

    # Language switch (strict — no topic words present).
    for rx in _SWITCH_STRICT:
        m = rx.match(t)
        if m:
            return {"action": "switch", "language": m.group(m.lastindex).lower(), "strict": True}

    if _GENERATE.match(t):
        m = _GENERATE.match(t)
        # Multiple capturing groups (one per branch) — find the one that matched.
        lang = next((g.lower() for g in m.groups() if g), None)
        return {"action": "generate", "language": lang, "strict": True}

    if _QUIZ_THIS.match(t):
        return {"action": "quiz", "language": None, "strict": True}
    if _MORE.match(t):
        return {"action": "more", "language": None, "strict": True}
    # explain_code before why — "how does this work?" is a code explanation, not a why-question
    for rx in _EXPLAIN_CODE:
        if rx.search(t):
            return {"action": "explain_code", "language": None, "strict": False}
    if _WHY.match(t):
        return {"action": "why", "language": None, "strict": True}
    if _EXAMPLE.match(t):
        return {"action": "example", "language": None, "strict": False}
    for rx in _ANOTHER:
        if rx.search(t):
            return {"action": "another", "language": None, "strict": False}
    # Simpler: raised word limit from 10 → 13 to catch natural phrasings.
    if _SIMPLER.search(t) and _words(t) <= 13:
        return {"action": "simpler", "language": None, "strict": False}

    m = _SWITCH_LOOSE.search(t)
    if m and _words(t) <= 10:
        return {"action": "switch", "language": m.group(1).lower(), "strict": False}
    return None


def is_pure_language_message(text):
    # True for "what about Java?", "now in C", "Python" ... (a bare language switch).
    t = text.strip().lower()
    return any(rx.match(t) for rx in _SWITCH_STRICT)


# ── Small talk ───────────────────────────────────────────────────────────────
_THANKS = re.compile(r"\b(?:thanks|thank you|thank u|thankyou|thx|tysm|ty|salamat|much appreciated|appreciate it)\b", re.IGNORECASE)
_BYE    = re.compile(r"\b(?:bye|goodbye|good bye|see you|see ya|gotta go|talk later|that'?s all|thats all|i'?m done|im done)\b", re.IGNORECASE)
_ACK    = re.compile(
    r"^(?:oh )?(?:ok(?:ay)?|k|kk|got it|i see|i get it(?: now)?|cool|nice|great|awesome|alright|all right|understood|makes sense|"
    r"i understand|perfect|good|noted|sure|yes|yeah|yep|yup|oh ok(?:ay)?|ok(?:ay)? then)(?: thanks| thank you)?" + _END,
    re.IGNORECASE,
)


def match_smalltalk(text):
    # Return "thanks", "bye", "ack" or None. Only short messages count, so
    # "thanks, but how do loops work?" is still answered as a real question.
    t = text.strip().lower()
    if _words(t) > 6:
        return None
    if _THANKS.search(t) and _words(t) <= 5:
        return "thanks"
    if _BYE.search(t):
        return "bye"
    if _ACK.match(t):
        return "ack"
    return None


# ── "Run it for me" requests ─────────────────────────────────────────────────
_RUN = re.compile(
    r"\b(?:run|execute|compile|test)\b.{0,25}\b(?:this|my|the|that|it)\b.{0,15}\b(?:code|program|script|snippet)\b"
    r"|^(?:run|execute|compile) (?:it|this|that)" + _END,
    re.IGNORECASE,
)


def is_run_request(text):
    return bool(_RUN.search(text.strip()))


# ── Greeting prefix ("Good afternoon! I need help with classes") ─────────────
_GREETING_PREFIX = re.compile(
    r"^\s*(?:hi|hello|hey|hiya|greetings|good (?:morning|afternoon|evening|night)|yo)\b[\s,!.:;-]*",
    re.IGNORECASE,
)


def strip_greeting(text):
    # Return the message without a leading greeting word.
    return _GREETING_PREFIX.sub("", text, count=1).strip()
