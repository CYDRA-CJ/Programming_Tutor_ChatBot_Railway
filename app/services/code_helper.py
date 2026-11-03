import re

LANG_NAMES = {"python": "Python", "java": "Java", "c": "C"}

_SIGNALS = [
    re.compile(r"#include\s*<"),
    re.compile(r"\bpublic\s+static\s+void\s+main\b|\bpublic\s+class\s+\w+"),
    re.compile(r"\bSystem\.out\.print"),
    re.compile(r"\bprintf\s*\(\s*\""),
    re.compile(r"\bscanf\s*\(\s*\""),
    re.compile(r"\bint\s+main\s*\("),
    re.compile(r"\bdef\s+\w+\s*\([^)]*\)\s*:"),
    re.compile(r"\bprint\s*\(\s*[\"'fr\w]"),
    re.compile(r"\bfor\s*\([^)]*;[^)]*;[^)]*\)"),
    re.compile(r"\bfor\s+\w+\s+in\s+[\w\[\]().,\s]+:"),
    re.compile(r"\b(?:if|while|elif)\b[^\n]*:\s*(?:\n|$)"),
    re.compile(r"\b(?:int|float|double|char|long|boolean|String)\s+\w+\s*(?:=|;|\[)"),
    re.compile(r";\s*(?:\n|$)"),
    re.compile(r"[{}]"),
    re.compile(r"\w\s*(?:\+\+|--|\+=|-=|==|!=|<=|>=)\s*\w"),
    re.compile(r"^\s*return\b[^\n]*", re.MULTILINE),
    re.compile(r"\n[ \t]{2,}\S"),                      # indented block
    re.compile(r"\w+\s*=\s*(?:input|int|float|str|len|range)\s*\("),
]

# ── Single-statement signals ──────────────────────────────────────────────────
# These patterns each identify a standalone code statement.  They are weaker
# than the multi-signal threshold (which requires ≥ 2 hits from _SIGNALS), so
# they are only used in two specific situations:
#   1. The colon-instruction path: "explain this: <code>" — the tail after the
#      colon needs only 1 hit (from _SIGNALS or _SINGLE_STMT) to be accepted.
#   2. A standalone message whose ENTIRE content is a single recognisable
#      statement (e.g. "print(2 + 3 * 4)" with no surrounding prose).
_SINGLE_STMT = [
    # Python print with arbitrary content — catches print(2 + 3 * 4) etc.
    re.compile(r"^\s*print\s*\(.*\)\s*;?\s*$"),
    # Plain Python assignment: name = expr  (no type keyword needed)
    re.compile(r"^\s*[A-Za-z_]\w*\s*=\s*[^=\n].+$"),
    # Augmented assignment: x += 1, total -= cost, etc.
    re.compile(r"^\s*[A-Za-z_]\w*\s*(?:\+=|-=|\*=|/=|//=|%=)\s*.+$"),
    # System.out (Java)
    re.compile(r"\bSystem\.out\."),
    # printf / scanf (C)
    re.compile(r"\b(?:printf|scanf)\s*\("),
    # Bare arithmetic expression inside print: print(2 + 3 * 4)
    re.compile(r"\bprint\s*\(\s*[\w\s+\-*/().,]+\)"),
    # C/Java statement ending with semicolon on a single line
    re.compile(r"^[^;\n]+;\s*$"),
]

# Instruction words that appear before a colon in "explain this: <code>" style.
_INSTRUCTION_WORDS = re.compile(
    r"\b(explain|why|what|fix|debug|check|output|predict|error|wrong|help|code|program|snippet|"
    r"trace|find|tell|does|doesn'?t|isn'?t|not working|print|prints|does this print|step by step)\b",
    re.IGNORECASE)


def _score(text):
    """Return the number of _SIGNALS that match text."""
    return sum(1 for rx in _SIGNALS if rx.search(text))


def _single_stmt_score(text):
    """Return the number of _SINGLE_STMT that match text."""
    return sum(1 for rx in _SINGLE_STMT if rx.search(text))


def looks_like_code(text):
    # Fenced code block is always code.
    if "```" in text:
        return True

    # Standard path: ≥ 2 strong signals anywhere in the message.
    if _score(text) >= 2:
        return True

    # ── Colon-instruction path ────────────────────────────────────────────────
    # Pattern: "explain this: <code>" or "what does this print: print(x + y)"
    # Condition: instruction word appears before a colon within the first 90
    # characters, the tail after the colon has ≥ 1 strong signal OR ≥ 1
    # single-statement signal, and the head itself is not code.
    if ":" in text[:90]:
        colon_pos = text.index(":")
        head = text[:colon_pos].strip()
        tail = text[colon_pos + 1:].strip()
        if (tail
                and _INSTRUCTION_WORDS.search(head)
                and not _score(head) >= 2          # head must not itself be code
                and (_score(tail) >= 1 or _single_stmt_score(tail) >= 1)):
            return True

    # ── Standalone single-statement path ─────────────────────────────────────
    # A message whose ENTIRE content is a single recognisable code statement
    # with no surrounding prose.
    # Two sub-cases:
    #   a) Has at least 1 strong signal + 1 single-stmt signal — confident.
    #   b) Matches a _SINGLE_STMT assignment pattern with an operator or
    #      arithmetic expression — catches bare "x = 10" and "result = (8+4)/2"
    #      which score 0 on _SIGNALS but are unambiguously assignments.
    stripped = text.strip()
    if "\n" not in stripped:
        if _score(stripped) >= 1 and _single_stmt_score(stripped) >= 1:
            return True
        # Sub-case b: bare assignment with no prose words around it.
        # Require: looks like "name = expr" or "name op= expr", short, no spaces
        # that look like a natural-language sentence (no verb words).
        _BARE_ASSIGN = re.compile(
            r"^\s*[A-Za-z_]\w*\s*(?:=(?!=)|\+=|-=|\*=|/=)\s*[^\n]+$"
        )
        _PROSE_WORDS = re.compile(
            r"\b(?:is|are|was|were|do|does|how|why|what|who|when|where|"
            r"explain|tell|show|give|make|write|can|could|would|should|the|a|an)\b",
            re.IGNORECASE,
        )
        if (_BARE_ASSIGN.match(stripped)
                and not _PROSE_WORDS.search(stripped)
                and len(stripped.split()) <= 8):
            return True

    return False


def extract_code(text):
    # Split a message into (instruction, code).
    m = re.search(r"```[A-Za-z+#]*\n?(.*?)```", text, re.DOTALL)
    if m:
        code = m.group(1).strip("\n")
        instruction = (text[:m.start()] + " " + text[m.end():]).strip()
        return instruction, code

    # "Explain this C code: for(int i=0;i<3;i++) printf(...);"
    if ":" in text[:90]:
        head, tail = text.split(":", 1)
        if _INSTRUCTION_WORDS.search(head) and not looks_like_code(head) and tail.strip():
            return head.strip(), tail.strip()

    # First line is the question, the rest is code.
    if "\n" in text:
        first, rest = text.split("\n", 1)
        if rest.strip() and _INSTRUCTION_WORDS.search(first) and not looks_like_code(first):
            return first.strip(), rest.strip()

    return "", text.strip()


def detect_code_language(code):
    # Guess the language of a snippet from its syntax.
    c = code
    if re.search(r"#include\s*<|\bprintf\s*\(|\bscanf\s*\(|\bint\s+main\s*\(|\bmalloc\s*\(", c):
        return "c"
    if re.search(r"\bSystem\.out\.|public\s+static\s+void\s+main|\bpublic\s+class\b|\bString\[\]|\bnew\s+\w+\s*\(", c):
        return "java"
    if re.search(r"\bdef\s+\w+\s*\(|\bprint\s*\(|\belif\b|\bimport\s+\w+\s*$|\bfor\s+\w+\s+in\b|:\s*$", c, re.MULTILINE):
        if not re.search(r";\s*$", c, re.MULTILINE):
            return "python"
    return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_strings(line):
    # Replace string/char literals with empty quotes so brackets inside them
    # are not counted.
    line = re.sub(r'"(?:\\.|[^"\\])*"', '""', line)
    line = re.sub(r"'(?:\\.|[^'\\])*'", "''", line)
    return line


def _strip_comment(line, language):
    if language == "python":
        out, in_s, q = [], False, ""
        for ch in line:
            if in_s:
                out.append(ch)
                if ch == q:
                    in_s = False
            elif ch in "\"'":
                in_s, q = True, ch
                out.append(ch)
            elif ch == "#":
                break
            else:
                out.append(ch)
        return "".join(out)
    idx = line.find("//")
    return line if idx < 0 else line[:idx]


_PY_BLOCK_START = re.compile(r"^(if|elif|else|for|while|def|class|try|except|finally|with)\b")
_C_CONTROL      = re.compile(r"^(?:\}\s*)?(if|else|for|while|do|switch|case|default|try|catch|finally)\b")


# ── Mistake checker ──────────────────────────────────────────────────────────

def check_code(code, language):
    # Return a list of "Line N: ..." strings describing likely mistakes.
    issues = []
    lines = code.splitlines()

    stripped_all = []
    for raw in lines:
        stripped_all.append(_strip_comment(raw, language).rstrip())

    # ---- balanced brackets (whole snippet) ----
    flat = "\n".join(_strip_strings(s) for s in stripped_all)
    for open_c, close_c, name in (("(", ")", "parentheses ( )"), ("[", "]", "square brackets [ ]"), ("{", "}", "curly braces { }")):
        o, c = flat.count(open_c), flat.count(close_c)
        if o != c:
            more = "opening" if o > c else "closing"
            issues.append(f"The {name} are not balanced — there are {abs(o - c)} extra {more} one(s).")

    for i, s in enumerate(stripped_all, 1):
        line = s.strip()
        if not line:
            continue

        # unclosed string quote on one line
        no_esc = line.replace('\\"', "").replace("\\'", "")
        if language != "python" or '"""' not in line and "'''" not in line:
            if no_esc.count('"') % 2 == 1:
                issues.append(f"Line {i}: a double quote `\"` is opened but never closed.")

        if language == "python":
            if _PY_BLOCK_START.match(line) and not line.endswith(":") and not line.endswith(("\\", "(", ",")):
                kw = _PY_BLOCK_START.match(line).group(1)
                issues.append(f"Line {i}: `{kw}` line must end with a colon `:`.")
            if re.match(r"^else\s+if\b", line):
                issues.append(f"Line {i}: Python uses `elif`, not `else if`.")
            if re.match(r"^print\s+[\"'\w]", line):
                issues.append(f"Line {i}: in Python 3, `print` needs parentheses — `print(...)`.")
            m = re.match(r"^(?:if|elif|while)\b(.*?):?$", line)
            if m and re.search(r"(?<![=!<>:])=(?!=)", m.group(1)):
                issues.append(f"Line {i}: a single `=` assigns a value. To compare in a condition use `==`.")
            # expected indented block
            if line.endswith(":") and _PY_BLOCK_START.match(line):
                j = i
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines):
                    cur_indent = len(lines[i - 1]) - len(lines[i - 1].lstrip())
                    nxt_indent = len(lines[j]) - len(lines[j].lstrip())
                    if nxt_indent <= cur_indent:
                        issues.append(f"Line {j + 1}: expected an indented block after the `:` on line {i}.")
                else:
                    issues.append(f"Line {i}: the `:` must be followed by an indented block of code.")
        else:
            # ---- Java / C ----
            m = re.match(r"^(?:\}\s*)?(?:else\s+)?(if|while)\s*\((.*)\)\s*\{?$", line)
            if m and re.search(r"(?<![=!<>])=(?!=)", m.group(2)):
                issues.append(f"Line {i}: a single `=` inside `{m.group(1)}( )` assigns a value. To compare use `==`.")
            if language == "java" and re.search(r"\b\w+\s*(?:==|!=)\s*\"", line):
                issues.append(f"Line {i}: strings in Java are compared with `.equals(...)`, not `==`.")

            if language == "c":
                sm = re.search(r'scanf\s*\(\s*"([^"]*)"\s*,\s*(.*)\)\s*;?$', line)
                if sm:
                    fmt, args = sm.group(1), [a.strip() for a in sm.group(2).split(",")]
                    non_string = [a for a in args if re.fullmatch(r"\w+", a)]
                    if non_string and "%s" not in fmt:
                        issues.append(f"Line {i}: `scanf` needs `&` before each variable (for example `&{non_string[0]}`).")

            # missing semicolon
            if (not line.endswith((";", "{", "}", ",", "(", "&&", "||", "+", "-", "*", "/", ":", "\\"))
                    and not line.startswith(("#", "@", "//", "/*", "*"))
                    and not _C_CONTROL.match(line)
                    and not line.startswith(("else",))):
                nxt = ""
                for k in range(i, len(stripped_all)):
                    if stripped_all[k].strip():
                        nxt = stripped_all[k].strip()
                        break
                is_signature = nxt.startswith("{")          # brace on the next line
                if not is_signature:
                    issues.append(f"Line {i}: this statement looks like it is missing a `;` at the end.")

    # main() present? (only when it is clearly a whole program)
    if language == "c" and "#include" in code and not re.search(r"\bmain\s*\(", code):
        issues.append("I do not see a `main()` function — every C program starts there.")
    if language == "java" and re.search(r"\bpublic\s+class\b", code) and not re.search(r"\bmain\s*\(", code):
        issues.append("I do not see a `main` method — a Java program starts at `public static void main(String[] args)`.")

    # de-duplicate, keep order
    seen, out = set(), []
    for it in issues:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out[:8]


def format_check_result(issues, language):
    lang = LANG_NAMES.get(language, "this")
    if issues:
        lines = ["I can't run code, but reading it through I found these likely problems:", ""]
        lines += [f"- {it}" for it in issues]
        lines += ["", "Fix these first, then check again. If there is still an error, paste the error message too."]
        return "\n".join(lines)
    return (
        "I read through the code and did not spot a common syntax mistake. "
        "I can't run code, so here is what to check next:\n\n"
        "- Read the error message from the top — it names the **line** and the **kind** of error.\n"
        "- Check variable names for typos and capital letters.\n"
        f"- Print or log values before the line that fails to see what they really are ({lang}).\n\n"
        "If you paste the error message, I can explain it."
    )


# ── Line-by-line explanation ─────────────────────────────────────────────────

_TYPE = r"(?:int|long|short|float|double|char|boolean|String|byte|var|unsigned\s+int|size_t)"


def _split_paren(s):
    # "(a(b) > 1) return x;" -> ("a(b) > 1", "return x;")  — finds the MATCHING closing parenthesis.
    s = s.strip()
    if not s.startswith("("):
        return None
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return s[1:i].strip(), s[i + 1:].strip()
    return None


def _short(s, n=60):
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _explain_line(raw, language):
    s = _strip_comment(raw, language).strip()
    if not s or s in ("{", "}", "};", "});"):
        return None
    if language != "python" and raw.strip().startswith(("//", "/*", "*")):
        return "A comment — the computer ignores it; it is a note for people."
    if language == "python" and raw.strip().startswith("#") and not raw.strip().startswith("#!"):
        return "A comment — the computer ignores it; it is a note for people."

    # imports / headers
    m = re.match(r"#include\s*<([^>]+)>", s)
    if m:
        return f"Includes the `{m.group(1)}` header so the program can use its functions."
    m = re.match(r"import\s+([\w.*]+);?$", s) or re.match(r"from\s+([\w.]+)\s+import\s+(.+)$", s)
    if m:
        return f"Brings in `{m.group(1)}` so its tools can be used."

    # entry points & definitions
    if re.search(r"\bpublic\s+static\s+void\s+main\s*\(", s):
        return "The entry point — a Java program starts running here."
    if re.match(r"(?:int|void)\s+main\s*\(", s):
        return "The `main` function — a C program starts running here."
    m = re.match(r"(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?class\s+(\w+)", s)
    if m:
        return f"Defines a class named `{m.group(1)}`."
    m = re.match(r"def\s+(\w+)\s*\((.*?)\)\s*:", s)
    if m:
        params = m.group(2).strip()
        return f"Defines a function `{m.group(1)}`" + (f" that takes `{params}`." if params else " that takes no input.")
    m = re.match(r"(?:(?:public|private|protected|static|final)\s+)*(" + _TYPE + r"|void)\s+(\w+)\s*\((.*?)\)\s*\{?$", s)
    if m and not re.match(r"(if|for|while|switch)\b", s):
        params = m.group(3).strip()
        what = "method" if language == "java" else "function"
        ret = "returns nothing" if m.group(1) == "void" else f"returns a `{m.group(1)}`"
        return f"Defines the {what} `{m.group(2)}`" + (f" taking `{params}`" if params else " with no parameters") + f" — it {ret}."

    # loops
    m = re.match(r"for\s*\(\s*(?:" + _TYPE + r"\s+)?(\w+)\s*=\s*([^;]+);\s*([^;]+);\s*([^)]+)\)", s)
    if m:
        var, init, cond, step = (g.strip() for g in m.groups())
        return (f"A `for` loop: `{var}` starts at `{init}`, the loop keeps going while `{cond}`, "
                f"and `{step}` runs after every pass.")
    m = re.match(r"for\s+(\w+)\s+in\s+range\((.*?)\)\s*:", s)
    if m:
        return f"A `for` loop: `{m.group(1)}` takes the values produced by `range({m.group(2)})`, one per pass."
    m = re.match(r"for\s+(\w+)\s+in\s+(.+?)\s*:", s)
    if m:
        return f"A `for` loop: `{m.group(1)}` takes each item of `{_short(m.group(2))}` in turn."
    m = re.match(r"for\s*\(\s*(?:final\s+)?" + _TYPE + r"\s+(\w+)\s*:\s*(.+?)\)", s)
    if m:
        return f"A for-each loop: `{m.group(1)}` takes each item of `{m.group(2)}` in turn."
    if s.startswith("while") and language != "python":
        sp = _split_paren(s[5:])
        if sp:
            return f"A `while` loop: repeats as long as `{_short(sp[0])}` is true."
    m = re.match(r"while\s+(.+?)\s*:$", s)
    if m:
        return f"A `while` loop: repeats as long as `{_short(m.group(1))}` is true."
    if s.startswith("do") and s.rstrip("{ ") == "do":
        return "A `do-while` loop: the body runs once first, then repeats while the condition at the end is true."

    # conditions
    m = re.match(r"(?:\}\s*)?else\s+if\b(.*)$", s)
    if m and language != "python":
        sp = _split_paren(m.group(1))
        if sp:
            return f"Otherwise, if `{_short(sp[0])}` is true, the next block runs."
    m = re.match(r"elif\s+(.+?)\s*:$", s)
    if m:
        return f"Otherwise, if `{_short(m.group(1))}` is true, the next block runs."
    if re.match(r"if\b", s):
        if language == "python":
            m = re.match(r"if\s+(.+?)\s*:$", s)
            if m:
                return f"Checks the condition `{_short(m.group(1))}`; the indented block runs only if it is true."
        else:
            sp = _split_paren(s[2:])
            if sp:
                rest = sp[1].rstrip("{ ").strip()
                tail = f" — in that case it runs `{_short(rest, 40)}`." if rest else "; the next block runs only if it is true."
                return f"Checks the condition `{_short(sp[0])}`{tail}"
    if re.match(r"(?:\}\s*)?else\s*:?\s*\{?$", s):
        return "Runs when none of the conditions above were true."
    if s.startswith(("break",)):
        return "Leaves the loop immediately."
    if s.startswith("continue"):
        return "Skips the rest of this pass and goes to the next one."

    # output / input
    m = re.match(r"print\s*\((.*)\)\s*$", s)
    if m:
        return f"Prints `{_short(m.group(1))}` to the screen."
    m = re.match(r"System\.out\.print(ln)?\s*\((.*)\)\s*;?$", s)
    if m:
        extra = " and moves to a new line" if m.group(1) else ""
        return f"Prints `{_short(m.group(2))}`{extra}."
    m = re.match(r"printf\s*\((.*)\)\s*;?$", s)
    if m:
        return f"Prints formatted text: `{_short(m.group(1))}` (`%d` is a placeholder for a whole number)."
    if "scanf" in s:
        return "Reads a value typed by the user and stores it in the variable."
    if "input(" in s:
        return "Asks the user to type something and stores their answer."
    if "Scanner" in s:
        return "Creates a `Scanner` so the program can read what the user types."

    # return
    m = re.match(r"return\b\s*(.*?)\s*;?$", s)
    if m:
        return f"Sends `{m.group(1)}` back to whoever called this function." if m.group(1) else "Ends the function."

    # declarations / assignments
    m = re.match(r"(?:final\s+)?(" + _TYPE + r")\s*(\[\])?\s+(\w+)\s*(?:=\s*(.+?))?\s*;?$", s)
    if m:
        t, arr, name, val = m.group(1), m.group(2) or "", m.group(3), m.group(4)
        return f"Creates a variable `{name}` of type `{t}{arr}`" + (f" and sets it to `{_short(val)}`." if val else ".")
    m = re.match(r"(\w+)\s*(\+\+|--)\s*;?$", s)
    if m:
        return f"{'Adds' if m.group(2) == '++' else 'Subtracts'} 1 {'to' if m.group(2) == '++' else 'from'} `{m.group(1)}`."
    m = re.match(r"(\w+)\s*([+\-*/%]=)\s*(.+?)\s*;?$", s)
    if m:
        return f"Updates `{m.group(1)}` using `{m.group(2)}` with `{_short(m.group(3))}`."
    m = re.match(r"([\w\[\].]+)\s*=\s*(.+?)\s*;?$", s)
    if m and "==" not in s.split("=")[0]:
        return f"Stores `{_short(m.group(2))}` in `{m.group(1)}`."
    return None


def explain_code(code, language, limit=30):
    # Return a line-by-line explanation in markdown (at most `limit` lines).
    lines = [l for l in code.splitlines() if l.strip()]
    rows = []
    for raw in lines[:limit]:
        note = _explain_line(raw, language or "python")
        if note:
            rows.append((raw.strip(), note))
    if not rows:
        return None
    out = ["Here is what the code does, line by line:", ""]
    rows = rows[:limit]
    for n, (src, note) in enumerate(rows, 1):
        out.append(f"{n}. `{_short(src, 70)}` — {note}")
    if len(lines) > limit:
        out.append("")
        out.append(f"*(I explained the first {limit} lines.)*")
    return "\n".join(out)


# ── Tiny output tracer (integer counting loops only) ─────────────────────────

def _range_values(start, stop, step):
    vals, v, guard = [], start, 0
    while ((step > 0 and v < stop) or (step < 0 and v > stop)) and guard < 100:
        vals.append(v)
        v += step
        guard += 1
    return vals


def trace_simple_loop(code, language):
    # If the code is a simple counting loop that prints the loop variable,
    # return the text it would print. Otherwise return None.
    # Pure arithmetic on integer literals — nothing is executed.
    values, var, body = None, None, ""

    if language == "python":
        m = re.search(r"for\s+(\w+)\s+in\s+range\(\s*(-?\d+)\s*(?:,\s*(-?\d+)\s*)?(?:,\s*(-?\d+)\s*)?\)\s*:\s*(.*)", code, re.DOTALL)
        if m:
            var = m.group(1)
            a, b, c = m.group(2), m.group(3), m.group(4)
            if b is None:
                start, stop, step = 0, int(a), 1
            else:
                start, stop, step = int(a), int(b), int(c) if c else 1
            if step == 0:
                return None
            values, body = _range_values(start, stop, step), m.group(5)
    else:
        m = re.search(
            r"for\s*\(\s*(?:int\s+)?(\w+)\s*=\s*(-?\d+)\s*;\s*\1\s*(<=|<|>=|>|!=)\s*(-?\d+)\s*;\s*\1\s*"
            r"(\+\+|--|\+=\s*\d+|-=\s*\d+)\s*\)\s*\{?(.*)", code, re.DOTALL)
        if m:
            var, start, op, limit, stepx, body = m.group(1), int(m.group(2)), m.group(3), int(m.group(4)), m.group(5), m.group(6)
            step = 1 if stepx == "++" else -1 if stepx == "--" else int(re.sub(r"\s", "", stepx[2:])) * (1 if stepx[0] == "+" else -1)
            if step == 0:
                return None
            values, v, guard = [], start, 0
            cmp = {"<": lambda x: x < limit, "<=": lambda x: x <= limit, ">": lambda x: x > limit,
                   ">=": lambda x: x >= limit, "!=": lambda x: x != limit}[op]
            while cmp(v) and guard < 100:
                values.append(v)
                v += step
                guard += 1

    if values is None or var is None:
        return None

    # What does the body print? Only "print the loop variable" is supported.
    out = None
    if language == "python":
        pm = re.match(r"\s*print\(\s*" + re.escape(var) + r"\s*\)", body)
        if pm:
            out = "".join(f"{v}\n" for v in values)
    elif language == "java":
        pm = re.match(r"\s*System\.out\.print(ln)?\(\s*" + re.escape(var) + r"\s*\)\s*;", body)
        if pm:
            out = "".join(f"{v}{chr(10) if pm.group(1) else ''}" for v in values)
    else:
        pm = re.match(r"\s*printf\(\s*\"([^\"]*)\"\s*,\s*" + re.escape(var) + r"\s*\)\s*;", body)
        if pm and re.fullmatch(r"(?:[^%\\]|\\n|\\t|%d)*", pm.group(1)) and pm.group(1).count("%d") == 1:
            fmt = pm.group(1).replace("\\n", "\n").replace("\\t", "\t")
            out = "".join(fmt.replace("%d", str(v)) for v in values)
    if out is None:
        return None
    return out.rstrip("\n") if out.strip() else None
