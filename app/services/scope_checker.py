
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ── Outcome enum ─────────────────────────────────────────────────────────────

class Outcome(str, Enum):
    ANSWER               = "ANSWER"
    GAP                  = "GAP"
    OOS                  = "OOS"
    CLARIFY              = "CLARIFY"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"

@dataclass
class ScopeResult:
    outcome:    Outcome
    confidence: float            # 0.0–1.0
    reason:     str = ""
    # Which evidence fired (for debug / Phase 4 logging)
    prog_signals:  list = field(default_factory=list)
    oos_signals:   list = field(default_factory=list)
    kb_matches:    list = field(default_factory=list)

    @property
    def is_oos(self) -> bool:
        return self.outcome == Outcome.OOS

    @property
    def is_gap(self) -> bool:
        return self.outcome == Outcome.GAP

# ── Layer 1: strong programming signals ─────────────────────────────────────
# Each entry is a substring matched against the lowercased message.
PROGRAMMING_SIGNALS = frozenset([
    # Languages (explicit)
    "python", "java", "c programming", "c language",
    # Core CS concepts
    "variable", "variables",
    "data type", "data types",
    "integer", "float", "boolean", "string type",
    "operator", "operators",
    "expression", "expressions",
    "loop", "loops", "for loop", "while loop", "do while",
    "if statement", "else if", "elif", "switch case",
    "function", "functions", "def ", "return value",
    "method", "methods",
    "class ", "classes", "object", "objects",
    "array", "arrays", "array list", "linked list", "array of",
    "dictionary", "dictionaries", "hashmap", "hash map",
    "stack", "queue",
    "recursion", "recursive",
    "algorithm", "algorithms",
    "sorting", "bubble sort", "merge sort", "quick sort", "insertion sort",
    "binary search", "linear search",
    "pointer", "pointers", "memory address",
    "syntax", "compile", "compiler", "interpreter",
    "inheritance", "polymorphism", "encapsulation", "abstraction",
    "exception", "try catch", "try except", "error handling",
    "import ", "library", "module",
    "print(", "printf", "system.out",
    "index", "iterate", "iteration",
    "variable scope", "global variable", "local variable",
    "parameter", "argument", "return type",
    "input(", "scanner", "stdin",
    "debugging", "breakpoint", "stack trace",
    "ide ", "vscode", "pycharm", "eclipse",
    "terminal", "command line", "shell script",
    "git ", "version control",
    "api ", "json ", "xml ",
    "sql ", "database query",
    "oop", "object oriented", "object-oriented",
    "fibonacci", "factorial", "palindrome",
    "sorting algorithm", "search algorithm",
    # Activity-specific signals — prevent OOS false positives
    "hotel booking system", "hotel reservation system",
    "hotel booking program", "hotel management system",
    "booking system", "reservation system",
    "banking system", "bank account system", "bank transaction",
    "payroll system", "inventory system", "library system",
    "student information", "hospital appointment",
    "restaurant order", "bus ticket", "online exam",
])

# ── Layer 2: out-of-scope subject words ──────────────────────────────────────
_OOS_FOOD = [
    "salad", "recipe", "cooking", "baking", "cake", "pizza", "burger",
    "pasta", "noodle", "soup", "sandwich", "snack", "meal", "dinner",
    "lunch", "breakfast", "cuisine", "ingredient", "chef", "restaurant menu",
    "dessert", "cookie", "bread", "fry", "frying", "grilling", "roasting",
    "smoothie", "juice", "coffee recipe", "tea recipe",
    "cook chicken", "cook meat", "cook rice", "cook fish",
    # Filipino / local food names
    "adobo", "sinigang", "lechon", "kare-kare", "tinola", "nilaga",
    "pancit", "lumpia", "sisig", "bulalo", "pinakbet", "paksiw",
    "kaldereta", "menudo", "afritada",
]
_OOS_WEATHER = [
    "weather", "forecast", "temperature outside", "humidity", "rainfall",
    "snowfall", "typhoon", "hurricane", "tornado", "climate today",
    "sunny day", "rainy day", "cloudy",
    "will it rain", "will it snow", "chance of rain",
]
_OOS_HEALTH_FITNESS = [
    "lose weight", "weight loss", "diet plan", "my diet", "calorie", "workout plan",
    "exercise routine", "gym routine", "muscle gain", "body fat",
    "keto diet", "intermittent fasting", "yoga pose", "meditation guide",
    "vitamins", "supplement", "skincare routine", "hair care",
    "build muscle", "gain muscle", "workout routine", "fitness routine",
    "how to get fit", "lose belly fat",
    # Body / gym slang
    "get abs", "get a six pack", "six pack abs", "flat stomach",
    "how to get bigger", "get toned", "get buff", "get ripped",
    "chest workout", "arm workout", "leg workout", "back workout",
    "how to get muscles", "grow muscles",
]
_OOS_FINANCE = [
    "crypto", "cryptocurrency", "bitcoin", "ethereum", "stock market",
    "invest in", "trading stocks", "forex", "nft ", "nfts",
    "loan application", "mortgage", "insurance plan",
]
_OOS_ENTERTAINMENT = [
    "movie recommendation", "good movie", "watch a movie", "best movie", "film review",
    "tv show", "netflix show", "anime to watch", "song recommendation",
    "song playlist", "music playlist", "concert ticket", "book recommendation",
    "best novel", "celebrity", "celebrity gossip",
    "recommend a movie", "what movie should", "anime right now", "best anime",
    "movies to watch", "show to watch", "should i watch", "what should i watch",
]
_OOS_RELATIONSHIPS = [
    "love letter", "pick up line", "relationship advice", "how to ask",
    "break up", "marriage proposal", "dating advice", "flirting",
    "make someone like me", "my girlfriend", "my boyfriend",
    "my husband", "my wife",
    "ask someone out", "how to date", "how to flirt",
    "poem about love", "write a poem for", "love poem",
]
_OOS_TRAVEL = [
    "best place to visit", "travel itinerary", "tourist spot", "hotel booking",
    "flight ticket", "visa application", "travel guide",
    "road trip", "backpacking",
]
_OOS_ANIMALS_PETS = [
    "my dog", "my cat", "my pet", "dog breed", "cat breed",
    "pet food", "pet care", "vet advice", "animal behavior",
    "fish tank", "aquarium setup",
]
_OOS_SOCIAL_MEDIA = [
    "instagram", "tiktok", "facebook post", "twitter post", "youtube channel",
    "grow followers", "social media strategy", "go viral",
    "influencer", "content creator",
]
_OOS_GENERAL_LIFE = [
    "horoscope", "astrology", "zodiac sign", "tarot", "lottery numbers",
    "prayer", "meditation mantra", "dream meaning", "what does my dream",
    "home renovation", "interior design", "furniture",
    "car repair", "oil change", "tire change",
    "fashion tips", "outfit idea", "makeup tutorial",
    "wedding plan", "plan my wedding", "plan a wedding", "baby name", "parenting advice",
    "resume writing", "cover letter",
    "job interview tips",
    "write a story", "write a poem", "write an essay",
    "translate this text",
]

OOS_SUBJECTS = frozenset(
    _OOS_FOOD + _OOS_WEATHER + _OOS_HEALTH_FITNESS + _OOS_FINANCE +
    _OOS_ENTERTAINMENT + _OOS_RELATIONSHIPS + _OOS_TRAVEL +
    _OOS_ANIMALS_PETS + _OOS_SOCIAL_MEDIA + _OOS_GENERAL_LIFE
)

# Force KB vocab cache to rebuild whenever this module is reloaded
_KB_VOCAB = None

# Domain categories for OOS signals (used in ScopeResult.reason)
_OOS_CATEGORIES = {
    "food":          frozenset(_OOS_FOOD),
    "weather":       frozenset(_OOS_WEATHER),
    "health":        frozenset(_OOS_HEALTH_FITNESS),
    "finance":       frozenset(_OOS_FINANCE),
    "entertainment": frozenset(_OOS_ENTERTAINMENT),
    "relationships": frozenset(_OOS_RELATIONSHIPS),
    "travel":        frozenset(_OOS_TRAVEL),
    "pets":          frozenset(_OOS_ANIMALS_PETS),
    "social_media":  frozenset(_OOS_SOCIAL_MEDIA),
    "general_life":  frozenset(_OOS_GENERAL_LIFE),
}

# ── KB Vocabulary Index ───────────────────────────────────────────────────────
# Built lazily from the live KB on first use.  Contains lowercase substrings
# that confirm a message is about a topic the bot actually covers.

_KB_VOCAB: Optional[frozenset] = None

def _build_kb_vocab() -> frozenset:
    terms: set[str] = set()

    try:
        from app import get_kb, get_examples, get_templates
        from app.services.topic_resolver import ACTIVITY_MAP, TOPIC_ALIASES

        # KB records: keywords, aliases, topic slugs
        kb = get_kb() or []
        for rec in kb:
            for kw in rec.get("keywords", []):
                terms.add(kw.lower().strip())
            for alias in rec.get("aliases", []):
                terms.add(alias.lower().strip())
            topic = rec.get("topic", "")
            if topic:
                # "python_list" → "python list", "list"
                terms.add(topic.replace("_", " ").lower())
                parts = topic.split("_")
                if len(parts) > 1:
                    terms.add(parts[-1].lower())  # e.g. "list" from "python_list"

        # TOPIC_ALIASES: all alias strings
        for topic, aliases in TOPIC_ALIASES.items():
            terms.add(topic.replace("_", " ").lower())
            for alias in aliases:
                terms.add(alias.lower().strip())

        # Code examples: topics and titles
        examples = get_examples() or []
        for ex in examples:
            t = ex.get("topic", "")
            if t:
                terms.add(t.replace("_", " ").lower())
            title = ex.get("title", "")
            if title:
                terms.add(title.lower().strip())

        # Templates: trigger phrases
        templates = get_templates() or []
        for tmpl in templates:
            for phrase in tmpl.get("trigger_phrases", []):
                terms.add(phrase.lower().strip())

        # Activity map: trigger phrases and display names
        for act_id, meta in ACTIVITY_MAP.items():
            for phrase in meta.get("trigger", []):
                terms.add(phrase.lower().strip())
            display = meta.get("display", "")
            if display:
                terms.add(display.lower().strip())

    except Exception:
        # If anything fails (no app context, missing data), return empty set —
        # evaluate_scope() will fall back to the keyword-only layers.
        return frozenset()

    # Remove very short terms (≤ 2 chars) to avoid noise
    return frozenset(t for t in terms if len(t) > 2)

def _get_kb_vocab() -> frozenset:
    global _KB_VOCAB
    if _KB_VOCAB is None:
        _KB_VOCAB = _build_kb_vocab()
    return _KB_VOCAB

def reset_kb_vocab() -> None:
    global _KB_VOCAB
    _KB_VOCAB = None

# ── Helpers ───────────────────────────────────────────────────────────────────

def _prog_hits(t: str) -> list:
    return [sig for sig in PROGRAMMING_SIGNALS if sig in t]

def _oos_hits(t: str) -> list:
    return [subj for subj in OOS_SUBJECTS if subj in t]

def _kb_hits(t: str) -> list:
    vocab = _get_kb_vocab()
    hits = [term for term in vocab if term in t]
    return hits[:10]

def _oos_category(hits: list) -> str:
    for hit in hits:
        for cat, members in _OOS_CATEGORIES.items():
            if hit in members:
                return cat
    return "unknown"

# ── Public API: backward-compatible bool ─────────────────────────────────────

def is_out_of_scope(text: str) -> bool:
    t = text.lower()
    if any(sig in t for sig in PROGRAMMING_SIGNALS):
        return False
    return any(subj in t for subj in OOS_SUBJECTS)

# ── Public API: rich five-outcome evaluator ───────────────────────────────────

def evaluate_scope(
    text:     str,
    language: str = "unspecified",
    intent:   str = "clarification",
    topic:    str = "programming_basics",
    tconf:    str = "low",
) -> ScopeResult:
    t = text.lower()

    prog  = _prog_hits(t)
    oos   = _oos_hits(t)
    kb    = _kb_hits(t)
    lang_known = language in ("python", "java", "c", "multiple")

    # ── 1. Unsupported language ──────────────────────────────────────────────
    # (detect_unsupported_language already fires before this in the pipeline;
    #  we include it here for standalone use only)
    try:
        from app.services.language_detector import detect_unsupported_language
        unsup = detect_unsupported_language(text)
        if unsup and not prog and not lang_known:
            return ScopeResult(
                outcome=Outcome.UNSUPPORTED_LANGUAGE,
                confidence=0.90,
                reason=f"Names unsupported language: {unsup}",
                prog_signals=prog, oos_signals=oos, kb_matches=kb,
            )
    except ImportError:
        pass

    # ── 2. ANSWER — strong programming evidence ──────────────────────────────
    if prog:
        # Layer 1 hit — definitely programming-related.
        # ANSWER if there is also specific KB vocabulary OR a known language.
        if kb or lang_known or tconf in ("high", "medium"):
            return ScopeResult(
                outcome=Outcome.ANSWER,
                confidence=0.92 if (kb or lang_known) else 0.75,
                reason="Programming signal present with KB/language match",
                prog_signals=prog, oos_signals=oos, kb_matches=kb,
            )
        # Programming signal but low KB coverage → GAP
        return ScopeResult(
            outcome=Outcome.GAP,
            confidence=0.65,
            reason="Programming signal present but no KB coverage found",
            prog_signals=prog, oos_signals=oos, kb_matches=kb,
        )

    # ── 3. OOS — OOS subject with no programming signal ──────────────────────
    # But only when no supported language was explicitly named. If the user
    # said "python" or "java" we treat the message as programming-related
    # even if an OOS word also appeared (e.g. "java coffee recipe").
    if oos and not lang_known:
        cat = _oos_category(oos)
        return ScopeResult(
            outcome=Outcome.OOS,
            confidence=0.90,
            reason=f"OOS subject detected (category: {cat})",
            prog_signals=prog, oos_signals=oos, kb_matches=kb,
        )

    # ── 4. ANSWER — a supported language was explicitly named ─────────────────
    # Even if no CS keyword fired, naming "Python", "Java", or "C" is strong
    # enough evidence that the user is asking about programming.
    if lang_known:
        return ScopeResult(
            outcome=Outcome.ANSWER,
            confidence=0.80,
            reason="Supported language explicitly named",
            prog_signals=prog, oos_signals=oos, kb_matches=kb,
        )

    # ── 5. GAP — KB vocab match without a language or strong signal ───────────
    # The message uses programming-adjacent vocabulary (from the KB) but no
    # unambiguous CS keyword and no language name fired.
    if kb:
        return ScopeResult(
            outcome=Outcome.GAP,
            confidence=0.60,
            reason="KB vocabulary match without strong programming signal",
            prog_signals=prog, oos_signals=oos, kb_matches=kb,
        )

    # ── 6. CLARIFY — insufficient evidence either way ────────────────────────
    # No programming signal, no OOS signal, no KB match, no known language.
    if intent == "clarification" or tconf == "low":
        return ScopeResult(
            outcome=Outcome.CLARIFY,
            confidence=0.50,
            reason="Insufficient evidence to classify scope",
            prog_signals=prog, oos_signals=oos, kb_matches=kb,
        )

    # ── 7. Default: ANSWER ────────────────────────────────────────────────────
    # Mixed or unclear evidence — let the normal pipeline proceed.
    return ScopeResult(
        outcome=Outcome.ANSWER,
        confidence=0.55,
        reason="Default pass-through (mixed evidence)",
        prog_signals=prog, oos_signals=oos, kb_matches=kb,
    )
