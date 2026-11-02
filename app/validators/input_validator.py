# Input validator.
# Sanitises user messages before they reach the classifier or any service.
# Rules:
#   - Strip leading/trailing whitespace.
#   - Reject empty or whitespace-only messages.
#   - Enforce a maximum length (2000 characters — enough to paste a program).
#   - Escape HTML special characters when text is embedded in HTML.
#   - Never execute, compile, or eval user-submitted or generated code.
#
# NOTE: the old "code-execution attempt" filter was removed on purpose.
# The chatbot never runs anything, so a message such as
# "what does eval() do in Python?" or code that contains re.compile(...)
# is perfectly safe — and it is exactly what a programming student asks.
# A request to RUN code is answered politely in chat.py instead of rejected.

import html

# Maximum allowed message length.
MAX_LENGTH = 2000


def validate(text):
    # Validate and sanitise user input.
    # Returns (clean_text, error_message).
    # error_message is None when the input is valid.

    if not text or not isinstance(text, str) or not text.strip():
        return None, "empty"

    text = text.replace("\x00", "").strip()

    if len(text) > MAX_LENGTH:
        return None, f"too_long:{MAX_LENGTH}"

    return text, None


def sanitise_for_html(text):
    # Escape HTML special characters in a string.
    return html.escape(text, quote=True)


def sanitise_response(text):
    # Light sanitisation of chatbot response text before sending to client.
    # Strips null bytes and normalises line endings.
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def get_error_response(error_code):
    # Return a user-friendly message for each validation error code.
    messages = {
        "empty": "Please type a message before sending.",
        f"too_long:{MAX_LENGTH}": (
            f"Your message is too long. Please keep it under {MAX_LENGTH} characters "
            "(paste just the part of the code you have a question about)."
        ),
    }
    return messages.get(error_code, "Invalid input. Please rephrase your question.")
