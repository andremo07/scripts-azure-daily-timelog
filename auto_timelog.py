"""
Automated daily timelog — full workflow without user interaction.
Called by Windows Task Scheduler at 6pm on weekdays.
Logs to .tmp/timelog_YYYYMMDD.log
"""
import os
import sys
import json
import logging
import anthropic
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "tools"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from get_timelog_entries import get_timelog_entries
from get_board_workitems import get_active_workitems
from delete_timelog_entries import delete_entries
from create_timelog_entry import create_entry

OVERHEAD_WI = int(os.environ["OVERHEAD_WI_ID"])
LOG_DIR = ROOT / ".tmp"
LOG_DIR.mkdir(exist_ok=True)


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
                    "This is an automated execution context — skip Steps 4-6 (confirmation, delete, create). "
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

    if not isinstance(entries, list):
        raise ValueError(f"Expected JSON array from Claude, got {type(entries).__name__}")

    total = sum(e["minutes"] for e in entries)
    if total != 440:
        raise ValueError(f"Distribution total is {total}, expected 440")

    return [(e["wi_id"], e["minutes"], e["type"], e["comment"]) for e in entries]


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"timelog_{today.replace('-', '')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    log = logging.getLogger()
    log.info(f"=== Daily Timelog — {today} ===")

    data = get_timelog_entries(7)
    frequency = {int(k): v for k, v in data["frequency"].items()}
    today_ids = data["today_ids"]
    active_wis = get_active_workitems()

    log.info(f"Active WIs: {[w['id'] for w in active_wis]}")
    log.info(f"Frequency: {frequency}")

    # Overwrite: delete existing entries for today
    if today_ids:
        log.info(f"Deleting {len(today_ids)} existing entries...")
        delete_entries(today_ids)

    # Fixed entries
    create_entry(OVERHEAD_WI, 20, "Agenda da operacao, negocio ou coorporativa", "Daily Team Integração 3.0")
    log.info(f"  WI#{OVERHEAD_WI} — Daily Team Integração 3.0 → 20min")

    create_entry(OVERHEAD_WI, 20, "Demanda de operacao", "Lançamento Horas do dia")
    log.info(f"  WI#{OVERHEAD_WI} — Lançamento Horas do dia → 20min")

    # Variable entries — Claude decides distribution; fall back to overhead WI on any failure
    try:
        entries = _distribute_with_claude(active_wis, frequency)
    except Exception as e:
        log.error(f"Claude distribution failed, using fallback: {e}")
        entries = [(OVERHEAD_WI, 440, "Atividade de projeto", "Suporte para o time")]
    for wi_id, minutes, etype, comment in entries:
        create_entry(wi_id, minutes, etype, comment)
        log.info(f"  WI#{wi_id} → {minutes}min")

    total = 40 + sum(e[1] for e in entries)
    status = "OK" if total == 480 else f"WARN total={total}"
    log.info(f"Done — {total}min (8h) [{status}]")


if __name__ == "__main__":
    main()
