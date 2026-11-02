import re

# ── Keyword tables ────────────────────────────────────────────────────────────

# Strong Python signals.
_PYTHON_KEYWORDS = {
    "python", "py", "pip", "django", "flask", "numpy", "pandas",
    "def ", "print(", "elif ", "lambda ", "self.", "__init__",
    "list comprehension", "f-string", "f'", 'f"',
    "python 3", "python 2", "guido", "van rossum", "cpython",
    "using python", "code in python", "code using python",
    "sample code using python", "program in python", "write python",
    "give me python", "show python", "create a python",
    "basic python", "what if using python",
    "calculator using python", "loop using python", "program using python",
    # Virtual environment and pip are Python-specific
    "virtual environment", "venv", "pip install", "pip freeze",
    "pip list", "requirements.txt", "activate venv",
    "deactivate venv", "python environment",
}

# Strong Java signals.
_JAVA_KEYWORDS = {
    "java", "jvm", "javac", "jdk", "jre", "maven", "gradle", "spring boot",
    "jar file", "public class", "public static", "system.out", "arraylist",
    "hashmap", "throws", "implements", "extends class",
    "java 8", "java 11", "java 17", "james gosling", "oracle java",
    "using java", "code in java", "code using java",
    "sample code using java", "program in java", "write java",
    "give me java", "show java", "create a java",
    "basic java", "what if using java",
    "calculator using java", "loop using java", "program using java",
}

# Strong C signals.
# C is a single letter so we use specific multi-word phrases and
# context markers (" in c.", " in c?", " c ", etc.) to avoid matching
# "C" inside unrelated words like "because", "voice", "science".
_C_KEYWORDS = {
    # "C" with explicit language context (most reliable)
    "c program", "c language", "c code", "c syntax",
    "c programming", "the c language",
    "what is c", "what is the c", "about c",
    "c language uses", "c language features",
    "c language history", "c language predecessor",
    "c language applications", "c language characteristics",
    # History keywords
    "history of c", "history of the c",
    "who created c", "who made c", "who developed c",
    "why was c", "c was created", "c was developed",
    "c and unix", "c for unix", "dennis ritchie", "bell labs c",
    "c89", "c99", "c11", "c17", "b language c", "bcpl c",
    # Concept keywords with "c" prefix
    "c pointer", "c array", "c string", "c struct",
    "c function", "c loop", "c variable", "c type",
    "c operator", "c condition", "c for loop",
    "c while", "c do while", "c error", "c debug",
    "c input", "c output", "c memory",
    "c scope", "c recursion",
    # Code / generation keywords
    "using c", "using the c", "code in c", "code using c",
    "sample code using c", "program in c",
    "give me c", "show c", "c example", "c code example",
    "create a c", "basic c program", "basic c code",
    "write a c", "make a c program",
    # Library / syntax tokens (very specific to C)
    "printf(", "scanf(", "#include", "stdlib.h", "stdio.h",
    "int main", "void main", "malloc(", "free(",
    # Short "c" with strong context markers (space + c + punctuation/space)
    " in c.", " in c?", " in c,", " in c ",
    " using c.", " using c?", " using c ",
    "of c.", "of c?", " of c ", " for c.", " for c?",
    "c's ", "c-based", "c-style",
    # "c" followed by a noun (common shortcut patterns)
    "c application", "c feature", "c advantage",
    "c strength", "c characteristic", "c property",
    "c industry", "c job", "c project",
    "c embedded", "c kernel", "c performance",
}


def _compile(keywords):
    # Build ONE regex from a keyword set.
    # A keyword that starts (or ends) with a letter/digit gets a word boundary
    # on that side, so "py" no longer matches inside "copy".
    parts = []
    for kw in sorted(keywords, key=len, reverse=True):
        pat = re.escape(kw)
        if kw[0].isalnum() or kw[0] == "_":
            pat = r"(?<![A-Za-z0-9_])" + pat
        if kw[-1].isalnum() or kw[-1] == "_":
            pat = pat + r"(?![A-Za-z0-9_])"
        parts.append(pat)
    return re.compile("|".join(parts))


_PY_RE   = _compile(_PYTHON_KEYWORDS)
_JAVA_RE = _compile(_JAVA_KEYWORDS)
_C_RE    = _compile(_C_KEYWORDS)

# "c" as a whole word — but not c++, c#, c-sharp, or part of "a, b, c".
_STANDALONE_C = re.compile(r"(?<![\w+#.-])c(?![\w+#]|-sharp)")
# "option c", "answer c", "choice c", "(c)" — an answer letter, not the language.
_ANSWER_LETTER = re.compile(r"\b(option|answer|choice|letter)\s+c\b|\(c\)")

_CONCEPT_WORDS = [
    "what is", "who", "when", "where", "why", "how",
    "history", "creator", "author", "made", "created",
    "example", "syntax", "loop", "array", "pointer",
    "program", "function", "about", "tell me", "explain",
    "code", "language", "programming",
]

# ── Languages the tutor does NOT teach ───────────────────────────────────────
_UNSUPPORTED = [
    ("C++",         r"(?<![\w])c\+\+"),
    ("C#",          r"(?<![\w])c#|\bc[- ]?sharp\b|\bcsharp\b"),
    ("JavaScript",  r"\bjavascript\b|\bnode\.?js\b|\bjs\b|\bjquery\b"),
    ("TypeScript",  r"\btypescript\b"),
    ("PHP",         r"\bphp\b"),
    ("Ruby",        r"\bruby\b"),
    ("Go",          r"\bgolang\b|\bgo language\b|\bgo lang\b"),
    ("Rust",        r"\brust\b"),
    ("Swift",       r"\bswift\b"),
    ("Kotlin",      r"\bkotlin\b"),
    ("Scala",       r"\bscala\b"),
    ("Perl",        r"\bperl\b"),
    ("R",           r"\br language\b|\br programming\b"),
    ("Dart",        r"\bdart\b|\bflutter\b"),
    ("Lua",         r"\blua\b"),
    ("Haskell",     r"\bhaskell\b"),
    ("MATLAB",      r"\bmatlab\b"),
    ("Objective-C", r"\bobjective[- ]c\b"),
    ("Visual Basic", r"\bvisual basic\b|\bvb\.?net\b"),
    ("Pascal",      r"\bpascal\b"),
    ("COBOL",       r"\bcobol\b"),
    ("Fortran",     r"\bfortran\b"),
    ("SQL",         r"\bsql\b|\bmysql\b|\bpostgres(?:ql)?\b"),
    ("HTML/CSS",    r"\bhtml\b|\bcss\b"),
    ("Bash",        r"\bbash\b|\bshell script\b|\bpowershell\b"),
]
_UNSUPPORTED_RE = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in _UNSUPPORTED]


def detect_unsupported_language(text):
    # Return the display name of an unsupported language mentioned in the text
    # (e.g. "JavaScript", "C++"), or None.
    for name, rx in _UNSUPPORTED_RE:
        if rx.search(text):
            return name
    return None


# "python" / "in Java" / "using c please" — a reply that is only a language.
_LANG_ONLY = re.compile(
    r"^\W*(?:(?:in|for|using|with|use|the|try|let'?s do|lets do|go with|i choose|i pick|i want|i'd like)\s+)*"
    r"(python|java|c)(?:\s+(?:language|version|please|pls|one|programming))*\W*$",
    re.IGNORECASE,
)


def language_only_reply(text):
    # If the whole message is just a language name ("Java", "in C please"),
    # return that language, else None.
    m = _LANG_ONLY.match(text.strip())
    return m.group(1).lower() if m else None


def _text_lower(text):
    return text.lower()


def _has_standalone_c(text_lower):
    # Returns True if the text contains "c" used as the C language shortcut.
    # Only counted when concept/question words are present, so a stray
    # letter c in an unrelated sentence does not trigger it.
    if _ANSWER_LETTER.search(text_lower):
        return False
    if not _STANDALONE_C.search(text_lower):
        return False
    return any(cw in text_lower for cw in _CONCEPT_WORDS)


def detect_language(text, context_language=None, intent=None):
    # Detect language from user text.
    # context_language: the active language from the session context (may be None).
    # intent: if provided and is a global intent, skip context carry-forward.
    # Returns (language_str, confidence_str) where confidence is "high"/"medium"/"low".

    # Global intents never carry forward a language from context.
    GLOBAL_INTENTS = {"greeting", "bot_capabilities", "clarification"}
    if intent in GLOBAL_INTENTS:
        context_language = None

    t = _text_lower(text)

    # A message that is only a language name ("Java", "in C").
    only = language_only_reply(t)
    if only:
        return only, "high"

    has_python = bool(_PY_RE.search(t))
    has_java   = bool(_JAVA_RE.search(t))
    has_c      = bool(_C_RE.search(t))

    # If no C keyword matched yet, try standalone "c" shortcut detection.
    if not has_c:
        has_c = _has_standalone_c(t)

    count = sum([has_python, has_java, has_c])

    # Explicit multi-language question.
    if count >= 2:
        return "multiple", "high"

    # Single clear language detected.
    if has_python:
        return "python", "high"
    if has_java:
        return "java", "high"
    if has_c:
        return "c", "high"

    # No explicit cue — carry forward context language if available.
    if context_language and context_language != "unspecified":
        return context_language, "low"

    return "unspecified", "low"


def detect_all_languages(text):
    # Return a list of all languages detected in the text.
    t = _text_lower(text)
    found = []
    if _PY_RE.search(t):
        found.append("python")
    if _JAVA_RE.search(t):
        found.append("java")
    if _C_RE.search(t) or _has_standalone_c(t):
        found.append("c")
    return found if found else ["unspecified"]


def is_language_switch(text, current_language):
    # Return True if the user is explicitly switching to a different language.
    lang, conf = detect_language(text)
    return (
        conf == "high"
        and lang not in ("unspecified", "multiple")
        and lang != current_language
    )
