"""
benchmark/scenario_generator.py
================================
Generates synthetic multi-turn test scenarios covering:

  IN-SCOPE:
    A. KB coverage  — one scenario per KB record (explain_concept intent)
    B. Code example — one scenario per example   (show_example intent)
    C. Code template— one scenario per template  (generate_code intent)
    Each scenario has 3-5 turns:
      Turn 1 : initial query
      Turn 2 : follow-up ("show me an example" / "explain it simpler" / "quiz me on this")
      Turn 3 : language switch ("do the same in Java" / "now in C" / "now in Python")
      Turn 4 : another follow-up ("show another example")
      Turn 5 : (templates only) parameter-tweaked regeneration

  OUT-OF-SCOPE (OOS):
    D. Direct OOS   — single-turn OOS query
    E. Mid-drift    — Turn 1 valid, Turn 2 OOS, checks context survived
    F. Recovery     — Turn 1 valid, Turn 2 OOS, Turn 3 valid follow-up

Output: benchmark/data/synthetic_scenarios.json
"""
import json
import os
import random
from typing import Optional

ROOT       = os.path.dirname(os.path.dirname(__file__))
DATA_DIR   = os.path.join(ROOT,      "data")
OUT_PATH   = os.path.join(ROOT,      "benchmark", "data", "synthetic_scenarios.json")

LANGS      = ("python", "java", "c")
LANG_LABEL = {"python": "Python", "java": "Java", "c": "C"}

# ── Load source data ──────────────────────────────────────────────────────────

def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

kb_data       = _load(os.path.join(DATA_DIR, "knowledge_base.json"))
ce_data       = _load(os.path.join(DATA_DIR, "code_examples.json"))
ct_data       = _load(os.path.join(DATA_DIR, "code_templates.json"))

KB_RECORDS    = kb_data.get("records", [])
CE_EXAMPLES   = ce_data.get("examples", [])
CT_TEMPLATES  = ct_data.get("templates", [])

# ── Helpers ───────────────────────────────────────────────────────────────────

def _other_lang(lang: str) -> str:
    """Return a different language than the given one."""
    others = [l for l in LANGS if l != lang]
    return random.choice(others)

def _lang_label(lang: Optional[str]) -> str:
    return LANG_LABEL.get(lang or "python", "Python")


def _explain_query(record: dict) -> str:
    """Build a natural initial explain_concept query from a KB record."""
    title   = record.get("title", "").replace("—", "").strip()
    topic   = record.get("topic", "programming_basics").replace("_", " ")
    lang    = record.get("language", "shared")
    llabel  = LANG_LABEL.get(lang, "")

    # Strip "in Python / in Java / in C" suffix from title to avoid duplication
    import re as _re
    title_clean = _re.sub(r'\s+[Ii]n\s+(Python|Java|C)\s*$', '', title).strip()
    topic_clean = topic  # topic slug never has a language suffix

    lang_suffix = f" in {llabel}" if llabel else ""

    templates_query = [
        f"What is {title_clean}?",
        f"Can you explain {title_clean}{lang_suffix}?",
        f"Tell me about {topic_clean}{lang_suffix}",
        f"Explain {title_clean}{lang_suffix}",
        f"What does {title_clean} mean{lang_suffix}?",
    ]
    return random.choice(templates_query)


def _example_query(example: dict) -> str:
    """Build a natural show_example query from a code example."""
    lang   = example.get("language", "python")
    topic  = example.get("topic", "loops").replace("_", " ")
    title  = example.get("title", topic)
    llabel = LANG_LABEL.get(lang, "Python")

    # Clean title — remove special chars and overly specific file references
    import re as _re
    title_clean = _re.sub(r'[—\-–].*$', '', title).strip()   # drop subtitle after dash
    title_clean = _re.sub(r'[^\w\s]', '', title_clean).strip()
    if not title_clean:
        title_clean = topic

    templates_query = [
        f"Show me a {llabel} {topic} example",
        f"Give me an example of {topic} in {llabel}",
        f"Show me sample code for {topic} in {llabel}",
        f"Can you show a {title_clean} example in {llabel}?",
        f"I want to see an example of {topic} using {llabel}",
    ]
    return random.choice(templates_query)


def _template_query(template: dict) -> str:
    """Build a natural generate_code query from a template."""
    lang   = template.get("language", "python")
    topic  = template.get("topic", "loops").replace("_", " ")
    title  = template.get("title", topic)
    llabel = LANG_LABEL.get(lang, "Python")
    tid    = template.get("id", "")

    # Build a param-enriched query if the template has parameters
    params     = template.get("parameters", [])
    param_hint = ""
    if params:
        sample_pairs = []
        for p in params[:1]:    # only use first param
            name    = p["name"]
            default = p.get("default", "")
            default_str = str(default).strip()
            # Skip numeric-only defaults (look like code) and
            # skip params whose name contains underscore (internal placeholder names)
            if default_str and not default_str.isdigit() and "_" not in name:
                sample_pairs.append(f"{name} {default_str}")
        if sample_pairs:
            param_hint = " with " + " and ".join(sample_pairs)

    # Strip leading language name from title to avoid "Java code for Java Methods"
    import re as _re2
    display_name = title if title else topic
    display_name = _re2.sub(r'^(Python|Java|C)\s+', '', display_name, flags=_re2.IGNORECASE).strip()
    if not display_name:
        display_name = topic

    templates_query = [
        f"Write a {llabel} {display_name} program{param_hint}",
        f"Generate {llabel} code for {display_name}{param_hint}",
        f"Create a {display_name} using {llabel}{param_hint}",
        f"Make a {llabel} {display_name}{param_hint}",
        f"Write {llabel} code for a {display_name}{param_hint}",
    ]
    return random.choice(templates_query)


def _switch_turn(lang: str) -> dict:
    other = _other_lang(lang)
    other_label = LANG_LABEL[other]
    phrases = [
        f"Do the same in {other_label}",
        f"Now in {other_label}",
        f"Show me the {other_label} version",
        f"What about {other_label}?",
        f"Give me the {other_label} equivalent",
        f"Can you show the same thing in {other_label}?",
    ]
    return {
        "turn":    "switch_language",
        "message": random.choice(phrases),
        "expect":  {
            "intent_in":  ["show_example", "generate_code", "explain_concept", "follow_up"],
            "language":   other,
            "has_code":   None,
        },
        "switch_language": other,
    }


# ── Assertion helpers ─────────────────────────────────────────────────────────

def _expect_explain(record: dict) -> dict:
    lang  = record.get("language", "shared")
    topic = record.get("topic", "")
    lang_in = ([lang, "unspecified"]) if lang in LANGS else list(LANGS) + ["unspecified", "multiple"]
    return {
        "intent_in":   ["explain_concept", "show_example", "show_syntax",
                        "compare_concepts", "clarification", "request_quiz"],
        "language_in": lang_in,
        "topic":       topic,
        "has_code":    None,
        "response_contains": [],
    }

def _expect_example(example: dict) -> dict:
    return {
        "intent_in":   ["show_example", "explain_concept", "generate_code"],
        "language_in": [example.get("language", "python"), "unspecified"],
        "has_code":    True,
        "response_contains": ["```"],
    }

def _expect_generate(template: dict) -> dict:
    return {
        "intent_in":   ["generate_code", "show_example"],
        "language_in": [template.get("language", "python"), "unspecified"],
        "has_code":    True,
        "response_contains": ["```"],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  A. KB-coverage scenarios
# ══════════════════════════════════════════════════════════════════════════════

def build_kb_scenarios() -> list:
    scenarios = []
    for record in KB_RECORDS:
        rid    = record["id"]
        lang   = record.get("language", "shared")
        topic  = record.get("topic", "programming_basics")
        llabel = LANG_LABEL.get(lang, "")
        ui_lang = lang if lang in LANGS else "auto"

        # Turn 1 — explain concept
        t1_msg = _explain_query(record)

        # Turn 2 — ask for example
        t2_phrases = [
            "Show me an example",
            "Give me a code example",
            "Can you show me an example of that?",
            "Show me one",
        ]
        t2_msg = random.choice(t2_phrases)

        # Turn 3 — ask for simpler
        t3_phrases = [
            "Explain it simpler",
            "I am confused, can you simplify that?",
            "Can you make it easier to understand?",
            "Too complex — break it down",
        ]
        t3_msg = random.choice(t3_phrases)

        # Turn 4 — quiz me (only for non-shared records)
        t4_msg = "Quiz me on this" if lang in LANGS else "Tell me more"

        # Build language_in allowing 'multiple' for shared records
        lang_in_followup = ([lang] if lang in LANGS else list(LANGS)) + ["unspecified", "multiple"]

        scenario = {
            "id":          f"kb_{rid}",
            "category":    "in_scope_kb",
            "description": f"KB coverage: {rid}",
            "source_id":   rid,
            "ui_language": ui_lang,
            "turns": [
                {
                    "turn":    "initial",
                    "message": t1_msg,
                    "expect":  _expect_explain(record),
                },
                {
                    "turn":    "follow_up_example",
                    "message": t2_msg,
                    "expect":  {
                        "intent_in":   ["show_example", "explain_concept", "generate_code",
                                        "follow_up", "compare_concepts"],
                        "language_in": lang_in_followup,
                        "has_code":    None,
                        "response_contains": [],
                    },
                },
                {
                    "turn":    "follow_up_simpler",
                    "message": t3_msg,
                    "expect":  {
                        "intent_in":   ["explain_concept", "show_example", "follow_up",
                                        "clarification", "compare_concepts"],
                        "language_in": lang_in_followup,
                        "has_code":    None,
                        "response_contains": [],
                    },
                },
                {
                    "turn":    "follow_up_quiz",
                    "message": t4_msg,
                    "expect":  {
                        "intent_in":   ["request_quiz", "explain_concept", "follow_up",
                                        "show_example", "clarification", "compare_concepts"],
                        "language_in": lang_in_followup,
                        "has_code":    None,
                        "response_contains": [],
                    },
                },
            ],
        }
        scenarios.append(scenario)

    return scenarios


# ══════════════════════════════════════════════════════════════════════════════
#  B. Code-example coverage scenarios
# ══════════════════════════════════════════════════════════════════════════════

def build_example_scenarios() -> list:
    scenarios = []
    for example in CE_EXAMPLES:
        eid    = example["id"]
        lang   = example.get("language", "python")
        topic  = example.get("topic", "loops")
        llabel = LANG_LABEL.get(lang, "Python")

        t1_msg   = _example_query(example)
        other    = _other_lang(lang)
        other_lbl= LANG_LABEL[other]

        scenario = {
            "id":          f"ce_{eid}",
            "category":    "in_scope_example",
            "description": f"Code example coverage: {eid}",
            "source_id":   eid,
            "ui_language": lang,
            "turns": [
                {
                    "turn":    "initial",
                    "message": t1_msg,
                    "expect":  _expect_example(example),
                },
                {
                    "turn":    "follow_up_explain",
                    "message": random.choice([
                        "Explain this code",
                        "Walk me through it",
                        "How does this work?",
                        "What does each line do?",
                    ]),
                    "expect":  {
                        "intent_in":   ["explain_code", "explain_concept", "follow_up"],
                        "language_in": [lang, "unspecified"],
                        "has_code":    None,
                        "response_contains": [],
                    },
                },
                {
                    "turn":    "switch_language",
                    "message": f"Do the same in {other_lbl}",
                    "expect":  {
                        "intent_in":   ["show_example", "generate_code", "follow_up"],
                        "language":    other,
                        "has_code":    None,
                        "response_contains": [],
                    },
                    "switch_language": other,
                },
                {
                    "turn":    "follow_up_another",
                    "message": random.choice([
                        "Show another example",
                        "Give me one more",
                        "Show a different example",
                    ]),
                    "expect":  {
                        "intent_in":   ["show_example", "generate_code", "follow_up",
                                        "explain_concept", "explain_code"],
                        "language_in": [lang, other, "unspecified"],
                        "has_code":    None,
                        "response_contains": [],
                    },
                },
            ],
        }
        scenarios.append(scenario)

    return scenarios


# ══════════════════════════════════════════════════════════════════════════════
#  C. Code-template coverage scenarios
# ══════════════════════════════════════════════════════════════════════════════

def build_template_scenarios() -> list:
    scenarios = []
    for tmpl in CT_TEMPLATES:
        tid   = tmpl["id"]
        lang  = tmpl.get("language", "python")
        topic = tmpl.get("topic", "loops")
        llabel= LANG_LABEL.get(lang, "Python")
        params= tmpl.get("parameters", [])

        t1_msg = _template_query(tmpl)

        # Build a re-parameterised Turn 5 only if there are params
        regen_turn = None
        if params:
            # pick a different default value for the first param
            p0     = params[0]
            name0  = p0["name"]
            cur    = str(p0.get("default", "5"))
            newval = "10" if cur != "10" else "20"
            regen_turn = {
                "turn":    "regenerate_with_new_params",
                "message": f"Now use {name0} = {newval} instead",
                "expect":  {
                    "intent_in":   ["generate_code", "show_example", "follow_up"],
                    "language_in": [lang, "unspecified"],
                    "has_code":    True,
                    "response_contains": ["```"],
                },
            }

        other     = _other_lang(lang)
        other_lbl = LANG_LABEL[other]

        turns = [
            {
                "turn":    "initial",
                "message": t1_msg,
                "expect":  _expect_generate(tmpl),
            },
            {
                "turn":    "follow_up_explain",
                "message": random.choice([
                    "Explain this code",
                    "How does this code work?",
                    "Walk me through it step by step",
                ]),
                "expect":  {
                    "intent_in":   ["explain_code", "explain_concept", "follow_up"],
                    "language_in": [lang, "unspecified"],
                    "has_code":    None,
                    "response_contains": [],
                },
            },
            {
                "turn":    "switch_language",
                "message": f"Now do it in {other_lbl}",
                "expect":  {
                    "intent_in":   ["generate_code", "show_example", "follow_up"],
                    "language":    other,
                    "has_code":    None,
                    "response_contains": [],
                },
                "switch_language": other,
            },
        ]
        if regen_turn:
            turns.append(regen_turn)

        scenarios.append({
            "id":          f"ct_{tid}",
            "category":    "in_scope_template",
            "description": f"Template coverage: {tid}",
            "source_id":   tid,
            "ui_language": lang,
            "turns":       turns,
        })

    return scenarios


# ══════════════════════════════════════════════════════════════════════════════
#  D. Direct Out-of-Scope scenarios
# ══════════════════════════════════════════════════════════════════════════════

OOS_DIRECT = [
    # Food
    "How do I make a salad?",
    "Give me a recipe for pasta",
    "What is the best way to cook chicken?",
    "Tell me how to bake a chocolate cake",
    "What are good breakfast ideas?",
    # Weather
    "What is the weather today?",
    "Will it rain tomorrow?",
    "What is the humidity right now?",
    # Health
    "How can I lose weight fast?",
    "What is a good diet plan?",
    "How do I build muscle?",
    "Tell me about keto diet",
    # Finance
    "Should I invest in bitcoin?",
    "What is the best crypto to buy?",
    "How does the stock market work?",
    # Entertainment
    "Recommend a good movie to watch",
    "What Netflix show should I watch?",
    "What is the best anime right now?",
    # Relationships
    "Write a love letter for me",
    "Give me a pick up line",
    "How do I ask someone out?",
    # Social Media
    "How do I grow my Instagram followers?",
    "What should I post on TikTok?",
    "How do I go viral on YouTube?",
    # General life
    "What is my horoscope today?",
    "Write a poem about love",
    "What does my dream mean?",
    "Help me plan my wedding",
    "Give me fashion tips",
    # Tricky: has "code" but OOS subject
    "Make me a code for salad",
    "Create a program for my dog",
    "Generate code for a birthday cake recipe",
    "Write code for cooking pasta",
    "Build a program for my workout routine",
]

def build_oos_direct_scenarios() -> list:
    scenarios = []
    for i, msg in enumerate(OOS_DIRECT):
        scenarios.append({
            "id":          f"oos_direct_{i+1:03d}",
            "category":    "oos_direct",
            "description": f"Direct OOS (Turn 1): {msg[:50]}",
            "ui_language": "auto",
            "turns": [
                {
                    "turn":    "oos_query",
                    "message": msg,
                    "expect":  {
                        "is_oos":            True,
                        "intent_in":         ["clarification"],
                        "response_contains": ["programming", "tutor", "Python", "Java", "C"],
                        "must_not_contain":  ["def ", "public class", "int main", "#include"],
                    },
                }
            ],
        })
    return scenarios


# ══════════════════════════════════════════════════════════════════════════════
#  E. Mid-conversation drift scenarios
#     Turn 1: valid in-scope query
#     Turn 2: OOS question — chatbot must reject it
#     Check: ctx["last_answer"] from Turn 1 must survive
# ══════════════════════════════════════════════════════════════════════════════

MID_DRIFT_PAIRS = [
    # (in-scope T1, OOS T2)
    ("What is a for loop in Python?",             "How do I cook pasta?"),
    ("Show me a Java class example",              "What movies should I watch?"),
    ("Explain recursion in C",                    "What is the weather today?"),
    ("Write a Python bubble sort program",        "Make me a salad recipe"),
    ("What is inheritance in Java?",              "How do I lose weight?"),
    ("Show me a binary search example in C",      "Write a love letter"),
    ("Explain variables in Python",               "Should I invest in bitcoin?"),
    ("Write a Java calculator program",           "How do I grow Instagram followers?"),
    ("What is a pointer in C?",                   "What is my horoscope?"),
    ("Show me a Python fibonacci example",        "How do I bake a cake?"),
    ("What is encapsulation in Java?",            "Give me fashion tips"),
    ("Explain arrays in C",                       "Write a poem about love"),
    ("What is a Python dictionary?",              "Recommend a Netflix show"),
    ("Show me a login system in Python",          "What should I post on TikTok?"),
    ("Explain scope in Java",                     "Help me plan my wedding"),
    ("Write a C factorial program",               "Tell me about keto diet"),
    ("What is a Java interface?",                 "How do I build muscle?"),
    ("Show me a Python class example",            "What is the best crypto to buy?"),
    ("Explain string operations in Python",       "What is a good pet food?"),
    ("What is malloc in C?",                      "Give me a pick up line"),
]

def build_oos_mid_drift_scenarios() -> list:
    scenarios = []
    for i, (t1_msg, t2_msg) in enumerate(MID_DRIFT_PAIRS):
        scenarios.append({
            "id":          f"oos_drift_{i+1:03d}",
            "category":    "oos_mid_drift",
            "description": f"Mid-drift OOS: '{t1_msg[:35]}...' then '{t2_msg[:35]}'",
            "ui_language": "auto",
            "turns": [
                {
                    "turn":    "valid_initial",
                    "message": t1_msg,
                    "expect":  {
                        "is_oos":    False,
                        "intent_in": ["explain_concept", "show_example", "generate_code",
                                      "show_syntax", "explain_code", "clarification"],
                        "has_code":  None,
                        "response_contains": [],
                    },
                },
                {
                    "turn":    "oos_drift",
                    "message": t2_msg,
                    "expect":  {
                        "is_oos":            True,
                        "intent_in":         ["clarification"],
                        "response_contains": ["programming", "tutor", "Python", "Java", "C"],
                        "must_not_contain":  ["def ", "public class", "int main", "#include"],
                    },
                },
            ],
        })
    return scenarios


# ══════════════════════════════════════════════════════════════════════════════
#  F. Scope recovery scenarios
#     Turn 1: valid in-scope query
#     Turn 2: OOS → rejected
#     Turn 3: valid follow-up to Turn 1 — must still work (last_answer survived)
# ══════════════════════════════════════════════════════════════════════════════

RECOVERY_TRIPLES = [
    # (in-scope T1, OOS T2, valid T3 follow-up)
    (
        "Explain for loops in Python",
        "How do I cook pasta?",
        "Show me an example of that",
    ),
    (
        "Show me a Java class example",
        "Recommend a movie",
        "Explain this code",
    ),
    (
        "What is recursion in C?",
        "What is the weather today?",
        "Give me an example of recursion",
    ),
    (
        "Write a Python fibonacci program",
        "How do I lose weight?",
        "Do the same in Java",
    ),
    (
        "Explain inheritance in Java",
        "Tell me my horoscope",
        "Quiz me on this",
    ),
    (
        "Show me a bubble sort in C",
        "Write me a poem about love",
        "Show another example",
    ),
    (
        "What is a Python list?",
        "Give me a recipe for cake",
        "Tell me more about lists",
    ),
    (
        "Explain pointers in C",
        "Should I invest in bitcoin?",
        "Explain it simpler",
    ),
    (
        "Write a Java bank account program",
        "How do I grow Instagram followers?",
        "Show me the Python version",
    ),
    (
        "What is a dictionary in Python?",
        "What movies should I watch?",
        "Show me a dictionary code example",
    ),
    (
        "Explain scope in Python",
        "How do I build muscle?",
        "Give me an example of that",
    ),
    (
        "Show me a C struct example",
        "What is keto diet?",
        "How does that code work?",
    ),
    (
        "What is encapsulation in Java?",
        "Write a love letter for me",
        "Show me an example in Java",
    ),
    (
        "Explain arrays in Python",
        "Best crypto to buy?",
        "Quiz me on Python arrays",
    ),
    (
        "Write a C factorial function",
        "Help me plan my wedding",
        "Do the same in Python",
    ),
]

def build_oos_recovery_scenarios() -> list:
    scenarios = []
    for i, (t1_msg, t2_msg, t3_msg) in enumerate(RECOVERY_TRIPLES):
        scenarios.append({
            "id":          f"oos_recovery_{i+1:03d}",
            "category":    "oos_recovery",
            "description": f"OOS recovery: T1='{t1_msg[:30]}' T2=OOS T3='{t3_msg[:30]}'",
            "ui_language": "auto",
            "turns": [
                {
                    "turn":    "valid_initial",
                    "message": t1_msg,
                    "expect":  {
                        "is_oos":    False,
                        "intent_in": ["explain_concept", "show_example", "generate_code",
                                      "show_syntax", "explain_code", "clarification"],
                        "has_code":  None,
                        "response_contains": [],
                    },
                },
                {
                    "turn":    "oos_drift",
                    "message": t2_msg,
                    "expect":  {
                        "is_oos":            True,
                        "intent_in":         ["clarification"],
                        "response_contains": ["programming", "tutor", "Python", "Java", "C"],
                        "must_not_contain":  ["def ", "public class", "int main", "#include"],
                    },
                },
                {
                    "turn":    "scope_recovery",
                    "message": t3_msg,
                    "expect":  {
                        "is_oos":    False,
                        "intent_in": ["explain_concept", "show_example", "generate_code",
                                      "show_syntax", "explain_code", "follow_up",
                                      "request_quiz", "clarification"],
                        "has_code":  None,
                        "response_contains": [],
                        "context_preserved": True,  # last_answer from T1 must be accessible
                    },
                },
            ],
        })
    return scenarios


# ══════════════════════════════════════════════════════════════════════════════
#  Main — assemble all scenarios
# ══════════════════════════════════════════════════════════════════════════════

def generate_all() -> dict:
    random.seed(42)  # reproducible

    kb_scenarios       = build_kb_scenarios()
    ce_scenarios       = build_example_scenarios()
    ct_scenarios       = build_template_scenarios()
    oos_direct         = build_oos_direct_scenarios()
    oos_mid_drift      = build_oos_mid_drift_scenarios()
    oos_recovery       = build_oos_recovery_scenarios()

    all_scenarios = (
        kb_scenarios + ce_scenarios + ct_scenarios +
        oos_direct   + oos_mid_drift + oos_recovery
    )

    # Stats
    by_cat = {}
    for s in all_scenarios:
        cat = s["category"]
        by_cat[cat] = by_cat.get(cat, 0) + 1

    total_turns = sum(len(s["turns"]) for s in all_scenarios)

    result = {
        "metadata": {
            "total_scenarios": len(all_scenarios),
            "total_turns":     total_turns,
            "by_category":     by_cat,
            "kb_records_covered":    len(kb_scenarios),
            "ce_examples_covered":   len(ce_scenarios),
            "ct_templates_covered":  len(ct_scenarios),
            "oos_direct":            len(oos_direct),
            "oos_mid_drift":         len(oos_mid_drift),
            "oos_recovery":          len(oos_recovery),
        },
        "scenarios": all_scenarios,
    }
    return result


if __name__ == "__main__":
    print("Generating synthetic benchmark scenarios …")
    data = generate_all()
    meta = data["metadata"]
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  Total scenarios : {meta['total_scenarios']}")
    print(f"  Total turns     : {meta['total_turns']}")
    print(f"  By category:")
    for cat, cnt in meta["by_category"].items():
        print(f"    {cat:30s}: {cnt}")
    print(f"\nSaved → {OUT_PATH}")
