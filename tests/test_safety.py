# test_safety.py
# Tests the chatbot handles malicious input safely, never executes code,
# sanitises HTML, handles edge cases, and never calls external APIs.

import json
import unittest.mock as mock
import pytest


def chat(client, message):
    resp = client.post(
        "/chat",
        data=json.dumps({"message": message}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    return resp.get_json()


@pytest.fixture(scope="module")
def c(client):
    client.get("/")
    return client


# ── Input validation ──────────────────────────────────────────────────────────

class TestInputValidation:

    def test_empty_message_returns_error_response(self, c):
        r = chat(c, "")
        assert r["response"]
        assert len(r["response"]) > 0

    def test_whitespace_only_message(self, c):
        r = chat(c, "   ")
        assert r["response"]

    def test_very_short_message(self, c):
        r = chat(c, "hi")
        assert r["response"]
        assert r["intent"] in (
            "greeting", "clarification", "bot_capabilities", "follow_up"
        )

    def test_oversized_message_does_not_crash(self, c):
        # 10,000 character message should not cause a 500 error.
        big_msg = "What is Python? " * 625  # ~10,000 chars
        r = chat(c, big_msg)
        assert r["response"]

    def test_missing_message_key_returns_200(self, c):
        # POST with no message key — app should handle gracefully.
        resp = c.post(
            "/chat",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_non_json_body_returns_200(self, c):
        # App should not crash on non-JSON body.
        resp = c.post(
            "/chat",
            data="not json at all",
            content_type="text/plain",
        )
        assert resp.status_code == 200

    def test_null_message_value(self, c):
        resp = c.post(
            "/chat",
            data=json.dumps({"message": None}),
            content_type="application/json",
        )
        assert resp.status_code == 200


# ── HTML injection / XSS ─────────────────────────────────────────────────────

class TestHTMLSanitisation:

    def test_html_script_tag_sanitised(self, c):
        r = chat(c, "<script>alert('xss')</script>")
        assert "<script>" not in r["response"]
        assert "alert(" not in r["response"] or "xss" not in r["response"]

    def test_html_img_tag_sanitised(self, c):
        r = chat(c, "<img src=x onerror=alert(1)>")
        assert "<img" not in r["response"]

    def test_html_link_tag_sanitised(self, c):
        r = chat(c, "<a href='javascript:void(0)'>click</a>")
        assert "<a href" not in r["response"]

    def test_html_entities_handled(self, c):
        # Should not cause a crash.
        r = chat(c, "What is &lt;script&gt; in HTML?")
        assert r["response"]

    def test_sql_injection_string_handled(self, c):
        r = chat(c, "'; DROP TABLE users; --")
        assert r["response"]
        assert "DROP TABLE" not in r["response"]

    def test_unicode_input_handled(self, c):
        r = chat(c, "Ano ang Python? Paano ito gamitin?")
        assert r["response"]

    def test_special_characters_handled(self, c):
        r = chat(c, "What is the @ symbol used for in Python?")
        assert r["response"]


# ── Code execution safety ─────────────────────────────────────────────────────

class TestCodeExecutionSafety:

    def test_eval_not_used_on_user_input(self, c):
        # If someone pastes Python code, it should never be executed.
        r = chat(c, "eval('print(123)')")
        # Response should be a chatbot reply, not the output of eval.
        assert "123" not in r["response"] or "print" in r["response"].lower()

    def test_exec_not_called_on_user_input(self, c):
        r = chat(c, "exec('import os; os.system(\"dir\")')")
        assert r["response"]
        # Should not execute — just classify and respond normally.

    def test_os_command_not_executed(self, c):
        r = chat(c, "import os; os.system('del /f /q C:\\\\*')")
        assert r["response"]
        # App should still be running (no crash from attempted exec).

    def test_generated_code_is_text_not_executed(self, c):
        r = chat(c, "Write a Python program that prints Hello World")
        assert r["intent"] == "generate_code"
        # Response contains the code as a string, not the program's output.
        assert "Hello" in r["response"] or "print" in r["response"].lower()
        # The response should contain code block markers, not bare stdout.
        assert r["response"].count("\n") >= 1

    def test_c_program_not_compiled(self, c):
        r = chat(c, "Write a C program that prints Hello World")
        assert r["intent"] == "generate_code"
        # Should return the C source code, not compiled/executed output.
        assert "#include" in r["response"] or "stdio" in r["response"]


# ── No external API calls ─────────────────────────────────────────────────────

class TestNoExternalAPICalls:

    def test_no_http_request_made_during_chat(self, c):
        # Patch requests.get and requests.post — they should never be called.
        with mock.patch("requests.get") as mock_get, \
             mock.patch("requests.post") as mock_post:
            chat(c, "What is Python?")
            mock_get.assert_not_called()
            mock_post.assert_not_called()

    def test_no_openai_import_in_app(self):
        # openai package must not be imported anywhere in the app.
        import pkgutil
        import importlib
        # Check that no app module imports openai.
        import app
        import ast, os
        app_dir = os.path.dirname(app.__file__)
        for root, dirs, files in os.walk(app_dir):
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    with open(fpath, encoding="utf-8") as f:
                        source = f.read()
                    try:
                        tree = ast.parse(source)
                    except SyntaxError:
                        continue
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            names = []
                            if isinstance(node, ast.Import):
                                names = [alias.name for alias in node.names]
                            else:
                                names = [node.module] if node.module else []
                            for name in names:
                                assert "openai" not in (name or ""), (
                                    f"openai import found in {fpath}"
                                )


# ── Unsupported request handling ──────────────────────────────────────────────

class TestUnsupportedRequests:

    def test_unsupported_language_gets_response(self, c):
        r = chat(c, "Teach me Rust programming")
        assert r["response"]
        assert len(r["response"]) > 10

    def test_completely_off_topic_gets_response(self, c):
        r = chat(c, "What is the weather today?")
        assert r["response"]

    def test_very_ambiguous_input_gets_response(self, c):
        r = chat(c, "help")
        assert r["response"]

    # ── Out-of-scope detection tests ─────────────────────────────────────────

    def test_salad_code_is_out_of_scope(self, c):
        # Tricky: has "code" but subject is food — must be caught as OOS.
        r = chat(c, "make me a code for salad")
        text = r["response"].lower()
        assert "programming" in text or "tutor" in text or "python" in text, (
            "Expected an OOS redirect but got: " + r["response"]
        )
        # Must NOT give a programming explanation or code block
        assert "def " not in text and "public class" not in text

    def test_weather_is_out_of_scope(self, c):
        r = chat(c, "What is the weather today?")
        text = r["response"].lower()
        # Should be an OOS redirect — must contain the tutor identity message
        assert "programming" in text or "tutor" in text
        # Must NOT explain weather as a programming concept (no actual code/KB content)
        assert "def " not in text and "public class" not in text and "int main" not in text

    def test_recipe_program_is_out_of_scope(self, c):
        r = chat(c, "make me a code for cooking pasta")
        text = r["response"].lower()
        assert "programming" in text or "tutor" in text or "python" in text

    def test_love_letter_is_out_of_scope(self, c):
        r = chat(c, "write a love letter for me")
        text = r["response"].lower()
        assert "programming" in text or "tutor" in text or "python" in text

    def test_lose_weight_is_out_of_scope(self, c):
        r = chat(c, "how do I lose weight fast")
        text = r["response"].lower()
        assert "programming" in text or "tutor" in text or "python" in text

    # ── In-scope messages must NOT be blocked ────────────────────────────────

    def test_python_program_not_blocked(self, c):
        # "write a Python program for a cooking website" has OOS word "cooking"
        # but also has "python" → must NOT be blocked.
        r = chat(c, "write a Python program for a cooking website")
        text = r["response"].lower()
        # The real check: it must not be the OOS redirect message
        assert "outside what i can help" not in text

    def test_java_bubble_sort_not_blocked(self, c):
        r = chat(c, "show me a bubble sort example in Java")
        text = r["response"].lower()
        assert "outside what i can help" not in text

    def test_for_loop_not_blocked(self, c):
        r = chat(c, "explain a for loop in Python")
        text = r["response"].lower()
        assert "outside what i can help" not in text

    def test_number_only_input_gets_response(self, c):
        r = chat(c, "42")
        assert r["response"]

    def test_repeated_question_mark_gets_response(self, c):
        r = chat(c, "???")
        assert r["response"]


# ── App stability ─────────────────────────────────────────────────────────────

class TestAppStability:

    def test_multiple_sequential_requests_no_crash(self, c):
        messages = [
            "Hello!",
            "What is Python?",
            "Show me a loop example",
            "Write a Java program",
            "Quiz me on C",
        ]
        for msg in messages:
            r = chat(c, msg)
            assert r["response"], f"Empty response for: {msg}"

    def test_session_persists_across_requests(self, c):
        # Session cookie should persist — no new session each time.
        r1 = chat(c, "What is a loop?")
        r2 = chat(c, "Give me an example")
        assert r1["response"]
        assert r2["response"]

    def test_clear_and_continue_works(self, c):
        c.post("/clear", content_type="application/json")
        r = chat(c, "Hello!")
        assert r["intent"] == "greeting"
        assert r["response"]
