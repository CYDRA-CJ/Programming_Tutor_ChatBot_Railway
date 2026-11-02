"""
scope_checker.py
────────────────
Two-layer out-of-scope detection.  No ML needed — purely keyword-based.

Layer 1 — PROGRAMMING_SIGNALS
  A set of strong, unambiguous CS/programming terms.  If ANY of these appear
  in the user's message the message is treated as in-scope regardless of
  what else is in it.  "python", "loop", "variable", "recursion" etc. are
  real anchors; bare "code" and "program" are intentionally excluded here
  because "make me a code for salad" contains "code" yet is clearly OOS.

Layer 2 — OOS_SUBJECTS
  A set of non-programming subject words grouped by real-world domain.
  If at least one of these matches AND Layer 1 found no programming signal
  the message is out-of-scope.

Decision: oos_hits > 0  AND  programming_hits == 0  →  out-of-scope.

This deliberately errs on the side of NOT blocking:
  • "write a Python program for a cooking website" → "python" is a signal → IN
  • "write a for loop for recipes"                → "for loop" is a signal → IN
  • "make a code for salad"                       → no signal, "salad" = OOS → OUT
  • "what is the weather today"                   → no signal, "weather" = OOS → OUT
"""

# ── Layer 1: strong programming signals ─────────────────────────────────────
# Each entry is a substring that must appear in the lowercased message.
# Keep these unambiguous — avoid words that appear in everyday English.
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
# Each entry is a substring that must appear in the lowercased message.
# Grouped by domain for readability — all go into one flat frozenset.
_OOS_FOOD = [
    "salad", "recipe", "cooking", "baking", "cake", "pizza", "burger",
    "pasta", "noodle", "soup", "sandwich", "snack", "meal", "dinner",
    "lunch", "breakfast", "cuisine", "ingredient", "chef", "restaurant menu",
    "dessert", "cookie", "bread", "fry", "frying", "grilling", "roasting",
    "smoothie", "juice", "coffee recipe", "tea recipe",
    "cook chicken", "cook meat", "cook rice", "cook fish",
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


# ── Public API ────────────────────────────────────────────────────────────────

def is_out_of_scope(text: str) -> bool:
    """
    Return True when the message is clearly not about programming.

    Rule: OOS subject found  AND  no programming signal found → out-of-scope.

    Intentional non-blocking cases:
      • "write a Python program for a cooking website"  → "python" signal → False
      • "build a recipe app in Java"                    → "java" signal → False
      • "for loop for iterating over food items"        → "for loop" signal → False

    Intentional blocking cases:
      • "make me a code for salad"        → no signal, "salad" OOS → True
      • "what is the weather today"       → no signal, "weather" OOS → True
      • "recommend a good movie"          → no signal, "movie recommendation" OOS → True
    """
    t = text.lower()

    # Layer 1 — any programming signal → definitely in-scope.
    if any(sig in t for sig in PROGRAMMING_SIGNALS):
        return False

    # Layer 2 — any OOS subject with no programming signal → out-of-scope.
    oos_hit = any(subj in t for subj in OOS_SUBJECTS)
    return oos_hit
