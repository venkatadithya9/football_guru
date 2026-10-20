"""
Test API Streaming & SSE Parser
Validates the StreamParser logic and API status endpoints.
"""

import unittest
from unittest.mock import MagicMock
from football_api import StreamParser


class TestStreamParser(unittest.TestCase):
    def test_pure_token_stream(self):
        parser = StreamParser()
        chunk = MagicMock()
        chunk.content = "Arsenal played brilliantly with high pressing."
        chunk.additional_kwargs = {}

        events = parser.process_chunk(chunk)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "token")
        self.assertEqual(events[0]["content"], "Arsenal played brilliantly with high pressing.")

    def test_thought_tag_stream(self):
        parser = StreamParser()
        chunk1 = MagicMock()
        chunk1.content = "<thought>Analyzing form for Arsenal and Man City"
        chunk1.additional_kwargs = {}

        events1 = parser.process_chunk(chunk1)
        self.assertEqual(len(events1), 1)
        self.assertEqual(events1[0]["type"], "thought")
        self.assertEqual(events1[0]["content"], "Analyzing form for Arsenal and Man City")

        chunk2 = MagicMock()
        chunk2.content = " based on 2024 records.</thought>Here is the tactical breakdown:"
        chunk2.additional_kwargs = {}

        events2 = parser.process_chunk(chunk2)
        self.assertEqual(len(events2), 2)
        self.assertEqual(events2[0]["type"], "thought")
        self.assertEqual(events2[0]["content"], " based on 2024 records.")
        self.assertEqual(events2[1]["type"], "token")
        self.assertEqual(events2[1]["content"], "Here is the tactical breakdown:")

    def test_kwargs_reasoning_stream(self):
        parser = StreamParser()
        chunk = MagicMock()
        chunk.content = ""
        chunk.additional_kwargs = {"reasoning_content": "Deep tactical reflection on midfield pivot"}

        events = parser.process_chunk(chunk)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "thought")
        self.assertEqual(events[0]["content"], "Deep tactical reflection on midfield pivot")


if __name__ == "__main__":
    unittest.main()
