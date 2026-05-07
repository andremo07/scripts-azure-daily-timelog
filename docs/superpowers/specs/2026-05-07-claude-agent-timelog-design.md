# Design: Claude-Agent auto_timelog

**Date:** 2026-05-07
**Status:** Approved

## Problem

`auto_timelog.py` was built for unattended execution (Windows Task Scheduler) but hardcodes the distribution logic in Python. This violates the WAT framework: AI should handle reasoning, deterministic code should handle execution. The `_distribute()` function re-implements judgment that belongs to the agent layer.

## Goal

Replace the hardcoded `_distribute()` function with a Claude API call. The workflow file (`workflows/daily_timelog.md`) becomes the system prompt verbatim — the same SOP used for interactive runs also drives the unattended routine. One source of truth.

## Architecture

`auto_timelog.py` remains the single entry point. Only `_distribute()` changes. Everything else (data gathering, delete, create) is untouched.

```
get_timelog_entries(7)       →  frequency + today_ids  ┐
get_board_workitems()        →  active WIs              ├→  Claude API  →  JSON plan  →  execute tools
workflows/daily_timelog.md   →  system prompt           ┘
```

## Claude API Call

- **Model:** `claude-haiku-4-5-20251001` — fast and cheap for a structured reasoning task this size
- **System prompt:** full content of `workflows/daily_timelog.md`, sent with `cache_control: {"type": "ephemeral"}` (static content, ideal for prompt caching)
- **User message:** structured JSON containing `frequency` (dict of wi_id → count) and `active_wis` (list of `{id, title}`)
- **Requested output:** JSON array for the 440 min variable entries only. Fixed entries (20min Daily + 20min Lançamento) are always identical and not included in Claude's decision.

### Output schema

```json
[
  {"wi_id": 237051, "minutes": 320, "type": "Atividade de projeto", "comment": "Implementacao"},
  {"wi_id": 238063, "minutes": 60,  "type": "Atividade de projeto", "comment": "Implementacao"},
  {"wi_id": 230057, "minutes": 60,  "type": "Atividade de projeto", "comment": "Implementacao"}
]
```

The prompt instructs Claude to return ONLY this JSON array with no surrounding text, so it can be parsed with `json.loads()` directly.

## Fallback

If the API call raises any exception (network error, rate limit, auth failure) or returns JSON that fails to parse or validate:

1. Log the error with full traceback
2. Create a single fallback entry: `WI#220396, 440min, "Atividade de projeto", "Suporte para o time"`
3. Continue — fixed entries still get created, total remains 480min

This matches the "No active WIs" edge case in the workflow, keeping the log clean and complete.

## Configuration

- `ANTHROPIC_API_KEY` added to `.env`
- No other env var changes

## Dependencies

- `anthropic` added to `requirements.txt`

## What Does NOT Change

- All four tool scripts in `tools/` — untouched
- Fixed entries (Daily + Lançamento) — always hardcoded, not part of Claude's decision
- Delete step — unchanged
- Logging format — unchanged
- Windows Task Scheduler setup — unchanged (still calls `python auto_timelog.py`)

## Validation

After implementation, manual test run (not via Task Scheduler):

```
python auto_timelog.py
```

Verify:
1. Script fetches data from Azure DevOps successfully
2. Claude API call completes and returns valid JSON
3. Distribution sums to exactly 440min
4. All entries created in TimeLog
5. Log file written to `.tmp/timelog_YYYYMMDD.log`
6. Fallback path works when `ANTHROPIC_API_KEY` is unset or invalid
