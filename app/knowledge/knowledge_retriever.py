from app import get_kb, get_examples


# ── Keyword-based retrieval (primary strategy) ────────────────────────────────

def get_record_by_keywords(text, language):
    # Find the best-matching KB record by checking the keywords field.
    kb = get_kb()
    if kb is None:
        return None

    text_lower = text.lower()

    def _score_record(rec):
        score = 0
        for kw in rec.get("keywords", []):
            if kw.lower() in text_lower:
                score += 1 + len(kw.split()) * 0.1
        return score

    if language == "unspecified":
        # Pass 1 — shared records only.
        best_shared = None
        best_shared_score = 0
        for rec in kb:
            if rec.get("language") != "shared":
                continue
            s = _score_record(rec)
            if s > best_shared_score:
                best_shared_score = s
                best_shared = rec
        if best_shared_score > 0:
            return best_shared

        # Pass 2 — no shared match, fall back to any language.
        best_record = None
        best_score = 0
        for rec in kb:
            s = _score_record(rec)
            if s > best_score:
                best_score = s
                best_record = rec
        return best_record if best_score > 0 else None

    # Language is known — search that language + shared together.
    best_record = None
    best_score  = 0
    for rec in kb:
        if rec.get("language") not in (language, "shared"):
            continue
        s = _score_record(rec)
        if s > best_score:
            best_score  = s
            best_record = rec
    return best_record if best_score > 0 else None


# ── KB record retrieval ───────────────────────────────────────────────────────

def get_record(language, topic, prefer_overview=False):
    # Return the best-matching KB record for the given language and topic.
    # If prefer_overview=True, prefer records with "overview" in their ID
    # over records with "history" in their ID.
    kb = get_kb()
    if kb is None:
        return None

    # 1. Exact language + topic match — collect ALL matches.
    exact = [r for r in kb if r["language"] == language and r["topic"] == topic]

    if exact:
        if prefer_overview:
            # Prefer overview over history when both exist.
            for r in exact:
                if "overview" in r["id"]:
                    return r
            return exact[0]
        # For history questions, prefer history record.
        for r in exact:
            if "history" in r["id"]:
                return r
        return exact[0]

    # 2. Shared record for cross-language questions.
    for rec in kb:
        if rec["language"] == "shared" and rec["topic"] == topic:
            return rec

    return None


def get_record_by_id(record_id):
    # Return a KB record by its stable ID.
    kb = get_kb()
    if kb is None:
        return None
    for rec in kb:
        if rec["id"] == record_id:
            return rec
    return None


def get_records_by_topic(topic):
    # Return all KB records for a given topic across all languages.
    kb = get_kb()
    if kb is None:
        return []
    return [r for r in kb if r["topic"] == topic]


def get_record_by_alias(text, language="unspecified"):
    # Search KB record aliases for a match with the user text.
    kb = get_kb()
    if kb is None:
        return None
    text_lower = text.lower()

    best_record = None
    best_score  = 0

    for rec in kb:
        if language not in ("unspecified", "multiple"):
            if rec["language"] not in (language, "shared"):
                continue

        score = 0
        for alias in rec.get("aliases", []):
            if alias.lower() in text_lower:
                score += 1

        if score > best_score:
            best_score  = score
            best_record = rec

    return best_record if best_score > 0 else None


def format_record_response(record, concise=False):
    # Format a KB record into a response string.
    # Uses quick_facts + image_path if available (new interactive format).
    # Falls back to definition + explanation for records without quick_facts.
    if record is None:
        return None

    parts = []

    # ── New interactive format (records with quick_facts) ─────────────────────
    if record.get("quick_facts"):
        # Image reference — rendered by the UI from this path token.
        if record.get("image_path"):
            parts.append(f"[IMAGE:{record['image_path']}|{record.get('image_caption', '')}]")
            parts.append("")

        # Opening sentence / definition.
        parts.append(record.get("definition", ""))
        parts.append("")

        # Quick facts bullets.
        parts.append("Here are some key facts:")
        for fact in record["quick_facts"]:
            if isinstance(fact, dict):
                parts.append(f"- **{fact['label']}:** {fact['value']}")
            else:
                # plain string fallback
                parts.append(f"- {fact}")
        parts.append("")

        # Extra explanation if not concise.
        if not concise and record.get("explanation"):
            parts.append(record["explanation"])
            parts.append("")

        # Fun fact.
        if record.get("fun_fact"):
            parts.append(f"**Fun fact:** {record['fun_fact']}")
            parts.append("")

        return "\n".join(parts).strip()

    # ── Legacy format (records without quick_facts) ───────────────────────────
    parts.append(f"**{record['title']}**")
    parts.append("")
    parts.append(record.get("definition", ""))

    if concise:
        parts.append("")
        parts.append("*Ask me to elaborate if you want more detail.*")
        return "\n".join(parts)

    explanation = record.get("explanation", "")
    if explanation:
        parts.append("")
        parts.append(explanation)

    common = record.get("common_mistakes", [])
    if common:
        parts.append("")
        parts.append("**Common mistakes to avoid:**")
        for m in common:
            parts.append(f"- {m}")

    related = record.get("related_topics", [])
    if related:
        parts.append("")
        parts.append(f"*Related topics: {', '.join(related)}*")

    source_name = record.get("source_name", "")
    source_url  = record.get("source_url", "")
    if source_name and source_url:
        parts.append("")
        parts.append(f"*Source: [{source_name}]({source_url})*")

    return "\n".join(parts)


# ── Code example retrieval ────────────────────────────────────────────────────

def get_example(example_id):
    # Return a code example by its ID.
    examples = get_examples()
    if examples is None:
        return None
    for ex in examples:
        if ex["id"] == example_id:
            return ex
    return None


def get_examples_by_topic(topic, language=None):
    # Return all code examples for a given topic, optionally filtered by language.
    examples = get_examples()
    if examples is None:
        return []
    results = [e for e in examples if e["topic"] == topic]
    if language and language not in ("unspecified", "multiple"):
        results = [e for e in results if e["language"] == language]
    return results


def get_examples_by_language(language):
    # Return all code examples for a given language.
    examples = get_examples()
    if examples is None:
        return []
    return [e for e in examples if e["language"] == language]


def format_example_response(example):
    # Format a code example into a response string with fenced code block.
    if example is None:
        return None

    lang_label = example.get("language", "")
    parts = []
    parts.append(f"```{lang_label}")
    parts.append(example.get("code", ""))
    parts.append("```")
    parts.append("")
    parts.append(example.get("explanation", ""))

    return "\n".join(parts)


def format_example_full(example):
    # Format a code example with output included.
    if example is None:
        return None

    lang_label = example.get("language", "")
    parts = []
    parts.append(f"```{lang_label}")
    parts.append(example.get("code", ""))
    parts.append("```")
    parts.append("")
    parts.append("**Output:**")
    parts.append("```")
    parts.append(example.get("output", ""))
    parts.append("```")
    parts.append("")
    parts.append(example.get("explanation", ""))

    return "\n".join(parts)
