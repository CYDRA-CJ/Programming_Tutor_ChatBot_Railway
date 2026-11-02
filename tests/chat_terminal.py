# Interactive terminal chatbot for testing before the UI is ready.
# Uses the same Flask routes that the UI will call — same model, same backend.
# This is NOT a separate implementation — it talks to the actual running server.
#
# HOW TO RUN:
#   Step 1 — Start the Flask server in one terminal:
#       .venv\Scripts\python.exe main.py
#
#   Step 2 — In a SECOND terminal, run this file:
#       .venv\Scripts\python.exe tests\chat_terminal.py
#
# COMMANDS DURING CONVERSATION:
#   Type any message and press Enter to send.
#   /clear       — clear conversation history
#   /history     — show last 10 messages
#   /quit or /exit — exit the terminal chat
#   /help        — show these commands

import sys
import os
import json
import textwrap
import re

# Try to import requests; tell the user clearly if it is missing.
try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is not installed.")
    print("Run: .venv\\Scripts\\python.exe -m pip install requests")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_URL    = "http://127.0.0.1:5000"
WRAP_WIDTH  = 90     # wrap long lines for readability
SESSION_COOKIE = {}  # will hold the session cookie after first request

# ── ANSI colour helpers (Windows-safe via colorama if available) ──────────────
try:
    import colorama
    colorama.init(autoreset=True)
    COLOR_USER   = "\033[96m"   # cyan
    COLOR_BOT    = "\033[92m"   # green
    COLOR_SYSTEM = "\033[93m"   # yellow
    COLOR_ERROR  = "\033[91m"   # red
    COLOR_DIM    = "\033[90m"   # dark grey
    COLOR_RESET  = "\033[0m"
    COLOR_BOLD   = "\033[1m"
    COLORS_ON    = True
except ImportError:
    COLOR_USER = COLOR_BOT = COLOR_SYSTEM = COLOR_ERROR = COLOR_DIM = ""
    COLOR_RESET = COLOR_BOLD = ""
    COLORS_ON   = False


def c(color, text):
    # Apply a colour to text (no-op if colours are off).
    return f"{color}{text}{COLOR_RESET}" if COLORS_ON else text


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def post_chat(message):
    # Send a chat message to /chat and return the response dict.
    global SESSION_COOKIE
    try:
        resp = requests.post(
            f"{BASE_URL}/chat",
            json={"message": message},
            cookies=SESSION_COOKIE,
            timeout=15,
        )
        # Persist the session cookie across requests (mimics browser behaviour).
        if resp.cookies:
            SESSION_COOKIE.update(resp.cookies.get_dict())
        return resp.json(), resp.status_code
    except requests.exceptions.ConnectionError:
        return None, 0
    except requests.exceptions.Timeout:
        return None, -1


def post_clear():
    # Send a clear-history request to /clear.
    global SESSION_COOKIE
    try:
        resp = requests.post(
            f"{BASE_URL}/clear",
            cookies=SESSION_COOKIE,
            timeout=10,
        )
        if resp.cookies:
            SESSION_COOKIE.update(resp.cookies.get_dict())
        return resp.json(), resp.status_code
    except Exception:
        return None, 0


def get_history():
    # Retrieve the last 10 messages from /history.
    global SESSION_COOKIE
    try:
        resp = requests.get(
            f"{BASE_URL}/history",
            cookies=SESSION_COOKIE,
            timeout=10,
        )
        if resp.cookies:
            SESSION_COOKIE.update(resp.cookies.get_dict())
        return resp.json(), resp.status_code
    except Exception:
        return None, 0


def check_server():
    # Return True if the Flask server is reachable.
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# ── Display helpers ───────────────────────────────────────────────────────────

def strip_markdown(text):
    # Remove common markdown so terminal output is clean.
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)      # bold
    text = re.sub(r"\*(.+?)\*",     r"\1", text)       # italic
    text = re.sub(r"^#{1,3} ",      "",    text, flags=re.MULTILINE)  # headers
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)    # links → label only
    return text


def format_code_blocks(text):
    # Highlight fenced code blocks visually in terminal.
    lines   = text.split("\n")
    out     = []
    in_code = False
    lang    = ""
    for line in lines:
        if line.startswith("```"):
            if not in_code:
                in_code = True
                lang    = line[3:].strip()
                header  = f"[{lang.upper()} CODE]" if lang else "[CODE]"
                out.append(c(COLOR_DIM, "─" * 60))
                out.append(c(COLOR_DIM, header))
            else:
                in_code = False
                out.append(c(COLOR_DIM, "─" * 60))
        else:
            if in_code:
                out.append(c(COLOR_DIM, "  " + line))
            else:
                out.append(line)
    return "\n".join(out)


def print_bot_response(data):
    # Pretty-print the bot's response with intent/language metadata.
    response = data.get("response", "")
    intent   = data.get("intent",   "?")
    language = data.get("language", "?")
    topic    = data.get("topic",    "?")
    conf     = data.get("confidence", 0)

    # Print metadata line.
    meta = f"[{intent} | {language} | {topic} | conf={conf:.2f}]"
    print(c(COLOR_DIM, meta))
    print()

    # Process the response text.
    response = format_code_blocks(response)
    response = strip_markdown(response)

    # Word-wrap and print each paragraph.
    paragraphs = response.split("\n")
    for para in paragraphs:
        if para.strip() == "---":
            print(c(COLOR_DIM, "─" * WRAP_WIDTH))
        elif para.strip():
            wrapped = textwrap.fill(para, width=WRAP_WIDTH, subsequent_indent="  ")
            print(c(COLOR_BOT, wrapped))
        else:
            print()


def print_history(data):
    # Print the conversation history.
    messages = data.get("history", [])
    if not messages:
        print(c(COLOR_SYSTEM, "No conversation history yet."))
        return
    print(c(COLOR_SYSTEM, f"Last {len(messages)} messages:"))
    print(c(COLOR_DIM, "─" * WRAP_WIDTH))
    for msg in messages[-10:]:
        role      = msg.get("role", "?")
        content   = msg.get("content", "")[:200]
        timestamp = msg.get("timestamp", "")[:16]
        if role == "user":
            print(c(COLOR_USER,   f"  You  [{timestamp}]: {content}"))
        else:
            print(c(COLOR_BOT,    f"  Bot  [{timestamp}]: {content}..."))
    print(c(COLOR_DIM, "─" * WRAP_WIDTH))


def print_welcome():
    print()
    print(c(COLOR_BOLD, "=" * WRAP_WIDTH))
    print(c(COLOR_BOLD, "  Programming Language Tutor — Terminal Test Mode"))
    print(c(COLOR_BOLD, "=" * WRAP_WIDTH))
    print(c(COLOR_SYSTEM, "  Connected to: " + BASE_URL))
    print(c(COLOR_SYSTEM, "  Model: MLP/ANN (93.7% accuracy)"))
    print(c(COLOR_SYSTEM, "  Languages: Python, Java, C"))
    print()
    print(c(COLOR_DIM,    "  Commands: /clear  /history  /help  /quit"))
    print(c(COLOR_BOLD,   "=" * WRAP_WIDTH))
    print()


def print_help():
    print()
    print(c(COLOR_SYSTEM, "COMMANDS:"))
    print(c(COLOR_SYSTEM, "  /clear    — clear conversation history and reset context"))
    print(c(COLOR_SYSTEM, "  /history  — show last 10 messages"))
    print(c(COLOR_SYSTEM, "  /quit     — exit the terminal chat"))
    print(c(COLOR_SYSTEM, "  /exit     — same as /quit"))
    print(c(COLOR_SYSTEM, "  /help     — show this help"))
    print()
    print(c(COLOR_SYSTEM, "EXAMPLE MESSAGES TO TRY:"))
    examples = [
        "Hello!",
        "What is Python?",
        "Explain variables in Java.",
        "Show me a C for loop example.",
        "Write a Python grade calculator.",
        "Compare Python lists with Java arrays.",
        "What is a pointer in C?",
        "Quiz me on Python loops.",
        "Who created Java?",
        "Debug: my Java loop runs forever.",
    ]
    for ex in examples:
        print(c(COLOR_DIM, f"  → {ex}"))
    print()


# ── Main loop ─────────────────────────────────────────────────────────────────

def main():
    # Check server is running first.
    print()
    print("Connecting to Flask server...")
    if not check_server():
        print()
        print("ERROR: Cannot reach the Flask server at " + BASE_URL)
        print()
        print("Make sure the server is running in another terminal:")
        print("  .venv\\Scripts\\python.exe main.py")
        print()
        sys.exit(1)

    print_welcome()

    # Send an automatic greeting to warm up the session.
    data, status = post_chat("Hello!")
    if data:
        print(c(COLOR_BOT, "Tutor:"))
        print_bot_response(data)
    print()

    # Main input loop.
    while True:
        try:
            user_input = input(c(COLOR_USER, "You: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print()
            print(c(COLOR_SYSTEM, "Goodbye! Use the full UI when it is ready."))
            break

        if not user_input:
            continue

        # Handle commands.
        cmd = user_input.lower()

        if cmd in ("/quit", "/exit"):
            print(c(COLOR_SYSTEM, "Goodbye! Use the full UI when it is ready."))
            break

        if cmd == "/help":
            print_help()
            continue

        if cmd == "/clear":
            data, status = post_clear()
            if status == 200:
                SESSION_COOKIE.clear()
                print(c(COLOR_SYSTEM, "Conversation cleared. Starting fresh."))
            else:
                print(c(COLOR_ERROR, "Could not clear history."))
            print()
            continue

        if cmd == "/history":
            data, status = get_history()
            if data:
                print_history(data)
            else:
                print(c(COLOR_ERROR, "Could not retrieve history."))
            print()
            continue

        # Send normal chat message.
        print(c(COLOR_DIM, "Thinking..."))
        data, status = post_chat(user_input)
        print()

        if data is None:
            if status == 0:
                print(c(COLOR_ERROR, "Connection lost. Is the server still running?"))
            elif status == -1:
                print(c(COLOR_ERROR, "Request timed out. The server may be busy."))
            else:
                print(c(COLOR_ERROR, f"Unexpected error (HTTP {status})."))
        elif status == 200:
            print(c(COLOR_BOT, "Tutor:"))
            print_bot_response(data)
        else:
            print(c(COLOR_ERROR, f"Error from server (HTTP {status}): {data}"))

        print()


if __name__ == "__main__":
    main()
