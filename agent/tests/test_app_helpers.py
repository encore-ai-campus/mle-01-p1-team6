import unittest

from app홍기표 import (
    has_cover_url,
    initial_messages,
    normalize_question,
    run_agent_query,
    chunk_books,
)


class AppHelpersTests(unittest.TestCase):
    def test_normalize_question_strips_user_whitespace(self):
        self.assertEqual(
            normalize_question("  잔잔한 소설 추천해줘  "),
            "잔잔한 소설 추천해줘",
        )


    def test_normalize_question_returns_empty_for_whitespace_only(self):
        self.assertEqual(normalize_question("   \n\t"), "")


    def test_has_cover_url_only_accepts_non_empty_string(self):
        self.assertTrue(has_cover_url("https://example.com/cover.jpg"))
        self.assertFalse(has_cover_url(""))
        self.assertFalse(has_cover_url(None))


    def test_initial_messages_contains_greeting(self):
        self.assertEqual(
            initial_messages(),
            [{"role": "assistant", "content": "원하는 책을 자연어로 말씀해 주세요."}],
        )

    def test_run_agent_query_forwards_thread_id(self):
        calls = []

        def fake_runner(question, thread_id):
            calls.append((question, thread_id))
            return "답변", []

        result = run_agent_query(
            "따뜻한 소설 추천해줘",
            "streamlit-session-1",
            runner=fake_runner,
        )

        self.assertEqual(result, ("답변", []))
        self.assertEqual(calls, [("따뜻한 소설 추천해줘", "streamlit-session-1")])

    def test_chunk_books_keeps_all_books_in_rows_of_three(self):
        books = [{"title": str(index)} for index in range(10)]

        self.assertEqual(
            chunk_books(books),
            [
                books[0:3],
                books[3:6],
                books[6:9],
                books[9:10],
            ],
        )
