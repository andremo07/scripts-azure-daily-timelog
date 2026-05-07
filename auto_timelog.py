"""
Automated daily timelog — full workflow without user interaction.
Called by Windows Task Scheduler at 6pm on weekdays.
Logs to .tmp/timelog_YYYYMMDD.log
"""
import os
import sys
import logging
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


def _round5(n):
    return round(n / 5) * 5


def _distribute(active_wis, frequency):
    """Return list of (wi_id, minutes, type, comment) for 440 min."""
    if not active_wis:
        return [(OVERHEAD_WI, 440, "Atividade de projeto", "Suporte para o time")]

    # Filter frequency to board WIs, pick top 3 by score
    scored = sorted(active_wis, key=lambda w: frequency.get(w["id"], 0), reverse=True)
    selected = scored[:3]

    with_hist = [w for w in selected if frequency.get(w["id"], 0) > 0]
    no_hist   = [w for w in selected if frequency.get(w["id"], 0) == 0]

    mins = {w["id"]: 60 for w in no_hist}
    remaining = 440 - sum(mins.values())

    total_score = sum(frequency[w["id"]] for w in with_hist)
    if with_hist and total_score > 0:
        alloc = {w["id"]: _round5(frequency[w["id"]] / total_score * remaining) for w in with_hist}
    else:
        alloc = {}

    dist = {**mins, **alloc}

    # Fix rounding so total is exactly 440
    diff = 440 - sum(dist.values())
    if diff and selected:
        dist[selected[0]["id"]] = dist.get(selected[0]["id"], 0) + diff

    return [(w["id"], dist[w["id"]], "Atividade de projeto", "Implementacao") for w in selected]


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

    # Variable entries
    entries = _distribute(active_wis, frequency)
    for wi_id, minutes, etype, comment in entries:
        create_entry(wi_id, minutes, etype, comment)
        log.info(f"  WI#{wi_id} → {minutes}min")

    total = 40 + sum(e[1] for e in entries)
    status = "OK" if total == 480 else f"WARN total={total}"
    log.info(f"Done — {total}min (8h) [{status}]")


if __name__ == "__main__":
    main()
