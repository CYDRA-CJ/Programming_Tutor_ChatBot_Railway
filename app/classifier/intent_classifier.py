import re
from app import get_classifier

APPROVED_INTENTS = [
    "greeting", "bot_capabilities", "explain_concept", "show_syntax",
    "show_example", "generate_code", "explain_code", "debug_code",
    "predict_output", "compare_concepts", "request_quiz",
    "follow_up", "clarification",
]

# Intents that are never combined with other tasks.
_SOLO_INTENTS = {"greeting", "bot_capabilities", "follow_up", "clarification"}

# Confidence threshold below which the intent is treated as unclear.
CONFIDENCE_THRESHOLD = 0.35

# A second intent is only believed when the user joined two requests together
_CONJUNCTION = re.compile(r"\b(and|then|also|plus|after that|as well|too)\b|[,;]")


def _normalise(text):
    # Lowercase and collapse whitespace — must match training normalisation.
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def predict(text):
    # Return the top predicted intent and its confidence score.
    pipeline = get_classifier()
    normalised = _normalise(text)

    # predict_proba returns an array of shape (1, n_classes).
    proba = pipeline.predict_proba([normalised])[0]
    classes = pipeline.classes_

    # Build a dict of {intent: probability}.
    scores = {cls: float(prob) for cls, prob in zip(classes, proba)}

    # Top intent.
    top_intent = max(scores, key=scores.get)
    top_conf   = scores[top_intent]

    # Fall back to clarification if confidence is too low.
    if top_conf < CONFIDENCE_THRESHOLD:
        top_intent = "clarification"

    return {
        "intent":     top_intent,
        "confidence": round(top_conf, 4),
        "all_scores": {k: round(v, 4) for k, v in sorted(scores.items(), key=lambda x: -x[1])},
    }


def predict_top_n(text, n=3, result=None):
    # Return the top-n intents with their confidence scores.
    result = result or predict(text)
    top_n = list(result["all_scores"].items())[:n]
    return [{"intent": intent, "confidence": conf} for intent, conf in top_n]


def is_multi_intent(text, threshold=0.25, secondary_threshold=0.20, result=None):
    # Detect if a message likely contains several requests.
    result = result or predict(text)
    if result["confidence"] < threshold:
        return [result["intent"]]

    if not _CONJUNCTION.search(text.lower()):
        return [result["intent"]]

    top = next(iter(result["all_scores"]))
    detected = [top] + [
        intent for intent, conf in list(result["all_scores"].items())[1:]
        if conf >= secondary_threshold
        and intent in APPROVED_INTENTS
        and intent not in _SOLO_INTENTS
    ]
    # Cap at 3 to keep responses manageable.
    return detected[:3]