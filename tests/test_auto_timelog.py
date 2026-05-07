import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Make sure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("OVERHEAD_WI_ID", "220396")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

from auto_timelog import _distribute_with_claude, OVERHEAD_WI


def _mock_response(json_array):
    """Build a mock anthropic response containing the given JSON array as text."""
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(json_array))]
    return msg


class TestDistributeWithClaude(unittest.TestCase):

    @patch("auto_timelog.anthropic.Anthropic")
    def test_returns_parsed_entries(self, MockAnthropic):
        payload = [
            {"wi_id": 237051, "minutes": 320, "type": "Atividade de projeto", "comment": "Implementacao"},
            {"wi_id": 238063, "minutes": 60,  "type": "Atividade de projeto", "comment": "Implementacao"},
            {"wi_id": 230057, "minutes": 60,  "type": "Atividade de projeto", "comment": "Implementacao"},
        ]
        MockAnthropic.return_value.messages.create.return_value = _mock_response(payload)

        active_wis = [{"id": 237051, "title": "A"}, {"id": 238063, "title": "B"}, {"id": 230057, "title": "C"}]
        frequency = {237051: 5, 238063: 2, 230057: 1}

        result = _distribute_with_claude(active_wis, frequency)

        assert result == [(237051, 320, "Atividade de projeto", "Implementacao"),
                          (238063, 60,  "Atividade de projeto", "Implementacao"),
                          (230057, 60,  "Atividade de projeto", "Implementacao")]

    @patch("auto_timelog.anthropic.Anthropic")
    def test_strips_markdown_fences(self, MockAnthropic):
        payload = [{"wi_id": 237051, "minutes": 440, "type": "Atividade de projeto", "comment": "Implementacao"}]
        raw = "```json\n" + json.dumps(payload) + "\n```"
        msg = MagicMock()
        msg.content = [MagicMock(text=raw)]
        MockAnthropic.return_value.messages.create.return_value = msg

        active_wis = [{"id": 237051, "title": "A"}]
        frequency = {237051: 3}

        result = _distribute_with_claude(active_wis, frequency)
        assert result == [(237051, 440, "Atividade de projeto", "Implementacao")]

    @patch("auto_timelog.anthropic.Anthropic")
    def test_raises_on_wrong_total(self, MockAnthropic):
        payload = [{"wi_id": 237051, "minutes": 300, "type": "Atividade de projeto", "comment": "Implementacao"}]
        MockAnthropic.return_value.messages.create.return_value = _mock_response(payload)

        active_wis = [{"id": 237051, "title": "A"}]
        frequency = {237051: 3}

        with self.assertRaises(ValueError):
            _distribute_with_claude(active_wis, frequency)

    @patch("auto_timelog.anthropic.Anthropic")
    def test_raises_on_invalid_json(self, MockAnthropic):
        msg = MagicMock()
        msg.content = [MagicMock(text="not valid json at all")]
        MockAnthropic.return_value.messages.create.return_value = msg

        active_wis = [{"id": 237051, "title": "A"}]
        frequency = {237051: 3}

        with self.assertRaises(Exception):
            _distribute_with_claude(active_wis, frequency)


if __name__ == "__main__":
    unittest.main()
