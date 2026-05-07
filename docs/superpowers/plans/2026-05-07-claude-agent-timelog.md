# Claude-Agent auto_timelog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded `_distribute()` function in `auto_timelog.py` with a Claude API call so the distribution reasoning follows the workflow SOP instead of rigid Python math.

**Architecture:** `auto_timelog.py` calls the Anthropic SDK at the distribution step, passing `workflows/daily_timelog.md` as a cached system prompt and raw Azure DevOps data as the user message. Claude returns a JSON array of entries; the script validates and executes them. Any exception triggers a safe fallback to WI#220396 for all 440 min.

**Tech Stack:** Python 3, `anthropic` SDK, `claude-haiku-4-5-20251001`, prompt caching via `cache_control`

---

### Task 1: Create feature branch and add `anthropic` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Create the feature branch**

```bash
git checkout -b feat/claude-agent-distribute
```

Expected: `Switched to a new branch 'feat/claude-agent-distribute'`

- [ ] **Step 2: Add `anthropic` to requirements.txt**

Current `requirements.txt`:
```
requests
python-dotenv
```

New `requirements.txt`:
```
requests
python-dotenv
anthropic
```

- [ ] **Step 3: Install the new dependency**

```bash
pip install anthropic
```

Expected: `Successfully installed anthropic-...`

- [ ] **Step 4: Add ANTHROPIC_API_KEY to .env**

Open `.env` and add this line (use your actual key):
```
ANTHROPIC_API_KEY=sk-ant-...
```

This file is gitignored — it will not be committed.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: add anthropic SDK dependency"
```

---

### Task 2: Write failing tests for `_distribute_with_claude`

**Files:**
- Create: `tests/test_auto_timelog.py`

- [ ] **Step 1: Create the tests directory and file**

```bash
mkdir -p tests
```

Create `tests/test_auto_timelog.py` with this content:

```python
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
```

- [ ] **Step 2: Run the tests — verify they all FAIL**

```bash
python -m pytest tests/test_auto_timelog.py -v
```

Expected: 4 errors — `ImportError: cannot import name '_distribute_with_claude'`

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_auto_timelog.py
git commit -m "test: add failing tests for _distribute_with_claude"
```

---

### Task 3: Implement `_distribute_with_claude` in `auto_timelog.py`

**Files:**
- Modify: `auto_timelog.py`

- [ ] **Step 1: Add `import anthropic` and `import json` at the top of `auto_timelog.py`**

Find the existing imports block (lines 1-20). Add these two imports after the existing ones:

```python
import json
import anthropic
```

The full imports section should look like:

```python
import os
import sys
import json
import logging
import anthropic
from datetime import datetime
from pathlib import Path
```

- [ ] **Step 2: Replace the entire `_distribute` function with `_distribute_with_claude`**

Remove this existing function (lines 28-60):

```python
def _round5(n):
    return round(n / 5) * 5


def _distribute(active_wis, frequency):
    ...
```

Replace with:

```python
def _distribute_with_claude(active_wis, frequency):
    """Call Claude API to decide the 440-min variable distribution following daily_timelog.md."""
    workflow = (ROOT / "workflows" / "daily_timelog.md").read_text(encoding="utf-8")

    client = anthropic.Anthropic()

    payload = {
        "active_wis": active_wis,
        "frequency": {str(k): v for k, v in frequency.items()},
    }

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": workflow,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": (
                    "You are executing Step 3 (Calculate distribution) of the workflow above. "
                    "Return ONLY a valid JSON array — no markdown fences, no explanation, no extra text. "
                    "Each element must have exactly these keys: "
                    "{\"wi_id\": <int>, \"minutes\": <int>, \"type\": <str>, \"comment\": <str>}. "
                    "The array must cover exactly 440 minutes total."
                ),
            },
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Here is today's data:\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
                    f"\n\nReturn the JSON distribution array for 440 minutes."
                ),
            }
        ],
    )

    text = response.content[0].text.strip()

    # Strip markdown code fences if the model adds them despite instructions
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    entries = json.loads(text)

    total = sum(e["minutes"] for e in entries)
    if total != 440:
        raise ValueError(f"Distribution total is {total}, expected 440")

    return [(e["wi_id"], e["minutes"], e["type"], e["comment"]) for e in entries]
```

- [ ] **Step 3: Update the call site in `main()` to use `_distribute_with_claude` with fallback**

Find this block in `main()` (around line 98):

```python
    # Variable entries
    entries = _distribute(active_wis, frequency)
    for wi_id, minutes, etype, comment in entries:
```

Replace with:

```python
    # Variable entries — Claude decides distribution; fall back to overhead WI on any failure
    try:
        entries = _distribute_with_claude(active_wis, frequency)
    except Exception as e:
        log.error(f"Claude distribution failed, using fallback: {e}")
        entries = [(OVERHEAD_WI, 440, "Atividade de projeto", "Suporte para o time")]
    for wi_id, minutes, etype, comment in entries:
```

- [ ] **Step 4: Run the tests — verify they all PASS**

```bash
python -m pytest tests/test_auto_timelog.py -v
```

Expected output:
```
tests/test_auto_timelog.py::TestDistributeWithClaude::test_returns_parsed_entries PASSED
tests/test_auto_timelog.py::TestDistributeWithClaude::test_strips_markdown_fences PASSED
tests/test_auto_timelog.py::TestDistributeWithClaude::test_raises_on_wrong_total PASSED
tests/test_auto_timelog.py::TestDistributeWithClaude::test_raises_on_invalid_json PASSED
4 passed
```

- [ ] **Step 5: Commit**

```bash
git add auto_timelog.py
git commit -m "feat: replace _distribute with Claude API call in auto_timelog"
```

---

### Task 4: Test the fallback path manually

**Files:** none (runtime test only)

- [ ] **Step 1: Run with an invalid API key to trigger the fallback**

In your shell, temporarily override the key and run the script in dry-run mode by setting a bad key:

```bash
ANTHROPIC_API_KEY=invalid python auto_timelog.py
```

- [ ] **Step 2: Verify fallback behaviour in the log**

Open `.tmp/timelog_<today>.log`. You should see:

```
...  Claude distribution failed, using fallback: ...
...  WI#220396 → 440min
...  Done — 480min (8h) [OK]
```

The timelog entries will have been written. Verify in Azure DevOps that only the fallback WI got the 440min, not real WIs.

> **Important:** Delete these test entries from Azure DevOps after verifying, or re-run with a valid key to overwrite them (the delete step runs first on each execution).

- [ ] **Step 3: Restore your real ANTHROPIC_API_KEY in `.env`**

Make sure `.env` has the correct key before the real integration test.

---

### Task 5: Integration test with real Claude API

**Files:** none (runtime test only)

- [ ] **Step 1: Run the script with the real API key**

```bash
python auto_timelog.py
```

- [ ] **Step 2: Verify the log**

Open `.tmp/timelog_<today>.log`. Confirm:
- No error lines
- Distribution entries sum to 440min
- Total line reads `480min (8h) [OK]`

- [ ] **Step 3: Verify entries in Azure DevOps**

Open: `https://dev.azure.com/DrogariaAraujo/_apps/hub/TimeLog.time-logging-extension.time-log-summary`

Confirm today's entries match the log.

- [ ] **Step 4: Commit the completed state**

```bash
git add .
git commit -m "feat: Claude-agent distribute — integration verified"
```

---

### Task 6: Finish branch and prepare for review

- [ ] **Step 1: Confirm all tests pass**

```bash
python -m pytest tests/test_auto_timelog.py -v
```

Expected: 4 passed, 0 failed

- [ ] **Step 2: Review final diff**

```bash
git diff main..HEAD
```

Confirm only these files changed: `auto_timelog.py`, `requirements.txt`, `tests/test_auto_timelog.py`, `docs/`

- [ ] **Step 3: Do NOT create the routine yet**

The Windows Task Scheduler entry will be created separately after the user validates the branch manually.
