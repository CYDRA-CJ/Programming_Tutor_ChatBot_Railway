import re
from app import get_templates


def find_template(language, topic, user_text=""):
    # Find the best matching template for the given language and topic.
    templates = get_templates()
    if templates is None:
        return None

    # 1. Exact language + topic — prefer trigger match.
    exact = [t for t in templates if t["language"] == language and t["topic"] == topic]
    if exact:
        triggered = _best_trigger_match(exact, user_text)
        if triggered:
            return triggered
        return exact[0]

    # 2. Search ALL templates for this language by trigger phrases.
    lang_templates = [t for t in templates if t["language"] == language]
    if lang_templates:
        triggered = _best_trigger_match(lang_templates, user_text)
        if triggered:
            return triggered

    # 3. Try shared topic match across all languages.
    for t in templates:
        if t["topic"] == topic and t["language"] == language:
            return t

    return None


def _best_trigger_match(candidates, user_text):
    # Return the candidate whose trigger phrases best match the user text.
    # Returns None only if NO trigger phrase matches at all.
    text_lower = user_text.lower()

    best        = None
    best_score  = 0

    for tmpl in candidates:
        score = 0
        for phrase in tmpl.get("trigger_phrases", []):
            if phrase.lower() in text_lower:
                score += 1
                # Bonus: longer trigger phrase = more specific match.
                score += len(phrase) / 100
        if score > best_score:
            best_score = score
            best        = tmpl

    return best if best_score > 0 else None


def fill_template(template_record, user_params=None):
    # Fill a template's {{placeholders}} with provided or default values.
    if template_record is None:
        return None, None, None

    code        = template_record.get("template", "")
    explanation = template_record.get("explanation", "")
    language    = template_record.get("language", "")

    # Build the substitution map: user params override defaults.
    sub_map = {}
    for param in template_record.get("parameters", []):
        name    = param["name"]
        default = param.get("default", "")
        value   = user_params.get(name, default) if user_params else default
        sub_map[name] = str(value)

    # Replace {{param_name}} placeholders.
    for name, value in sub_map.items():
        placeholder = "{{" + name + "}}"
        code        = code.replace(placeholder, value)

    # Safety: reject if any placeholder was not filled (template mismatch).
    unfilled = re.findall(r"\{\{[^}]+\}\}", code)
    if unfilled:
        # Fall back to the pre-filled example.
        code = template_record.get("filled_example", code)

    return code, explanation, language


def generate_code_response(language, topic, user_text="", user_params=None):
    # High-level entry point: find template, fill it, return formatted response.
    # Returns only the code + brief explanation — not a wall of text.
    tmpl = find_template(language, topic, user_text)
    if tmpl is None:
        return None

    code, explanation, lang = fill_template(tmpl, user_params)
    if code is None:
        return None

    lang_label = lang if lang else language
    parts = []
    parts.append(f"```{lang_label}")
    parts.append(code)
    parts.append("```")
    if explanation:
        parts.append("")
        parts.append(explanation)

    return "\n".join(parts)
