# Scripted conversations — run after every change to see how the chat FEELS.
#
#   python tests/chat_scenarios.py              # all scenarios
#   python tests/chat_scenarios.py followups    # one scenario by name
#
# Uses Flask's test client and a throw-away database, so it never touches
# data/conversations.db. Requires models/classifier.joblib (run train.py first).

import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["CHATBOT_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test_conversations.db")

from app import create_app          # noqa: E402

app = create_app()
client = app.test_client()
MAX_SHOWN = 700                      # characters of each reply to print


def say(msg, sid=None, language="auto", quiet=False):
    body = {"message": msg, "language": language}
    body["session_id"] = sid
    r = client.post("/api/chat", json=body).get_json()
    if not quiet:
        text = r["text"]
        shown = text if len(text) <= MAX_SHOWN else text[:MAX_SHOWN] + " […]"
        print(f"\nUSER : {msg}")
        print(f"BOT  : [{r['intent']} | {r['language']} | {r['topic']} | conf {r['confidence']}]")
        print("       " + shown.replace("\n", "\n       "))
        if r.get("suggestions"):
            print(f"       chips: {r['suggestions']}")
    return r


def scenario(name):
    print("\n" + "=" * 78 + f"\n  SCENARIO: {name}\n" + "=" * 78)


def followups():
    scenario("followups")
    r = say("How do for loops work in Java?")
    sid = r["session_id"]
    for m in ["Show me an example", "Show another example", "Do the same in Python",
              "Explain it simpler", "Tell me more", "What's the output?"]:
        say(m, sid)


def memory_and_switching():
    scenario("language memory + switching")
    r = say("Explain variables in Python")
    sid = r["session_id"]
    say("show me an example of loops", sid)          # no language named -> Python assumed, with a note
    say("what about Java?", sid)
    say("and C", sid)
    say("another example", sid)


def pending_question():
    scenario("pending 'which language?' question")
    r = say("write a simple calculator program")
    sid = r["session_id"]
    say("Java", sid)
    say("show me an example of recursion", sid)      # remembered language: Java
    say("quiz me", sid)


def quiz_flow():
    scenario("in-chat quiz")
    r = say("Quiz me on Python loops")
    sid = r["session_id"]
    for m in ["B", "a", "skip", "explain recursion", "C", "stop quiz"]:
        say(m, sid)


def pasted_code():
    scenario("pasted code")
    r = say('Explain this C code: for(int i=0;i<3;i++) printf("%d\\n",i);')
    sid = r["session_id"]
    say("What's the output?", sid)
    say("explain it simpler", sid)
    r = say("Why doesn't this work?\nif x = 5\n    print(x)")
    say("Help, my Java code has an error:\nint x = 5\nSystem.out.println(x);")
    say("what does eval() do in Python?")           # a question, not an attack


def smalltalk_and_edges():
    scenario("small talk and edge cases")
    say("hello")
    say("Good afternoon! I need help understanding classes in Java.")
    say("thanks!")
    say("write a javascript program")
    say("can you run this code for me?")
    say("loops python")                              # unclear -> keyword answer
    say("asdfgh")
    say("what is the correct output of a for loop in c?")


def new_conversation():
    scenario("'New conversation' starts clean")
    a = say("Explain loops in Java")["session_id"]
    b = say("show me an example", None)["session_id"]    # session_id null = new chat
    print("\nsame session?", a == b)


SCENARIOS = {f.__name__: f for f in
             (followups, memory_and_switching, pending_question, quiz_flow,
              pasted_code, smalltalk_and_edges, new_conversation)}

if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SCENARIOS)
    for name in wanted:
        SCENARIOS[name]()
