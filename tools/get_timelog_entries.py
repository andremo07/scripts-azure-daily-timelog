"""
Fetch TimeLog extension documents for the current user.

Returns:
  frequency  — minutes per WI over the last N days (excludes OVERHEAD_WI_ID)
  today_ids  — document IDs for today (used for overwrite/delete)

Usage : python tools/get_timelog_entries.py [days=7]
Output: JSON {"frequency": {wi_id: minutes}, "today_ids": [...]}
"""
import os
import sys
import json
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from utils import get_bearer, auth_headers, TIMELOG_URL

load_dotenv()

USER_ID = os.environ["AZURE_DEVOPS_USER_ID"]
FIXED_WI = int(os.environ["OVERHEAD_WI_ID"])


def get_timelog_entries(days=7):
    bearer = get_bearer()
    resp = requests.get(TIMELOG_URL, headers=auth_headers(bearer))
    resp.raise_for_status()

    today = datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    my_docs = [d for d in resp.json() if d.get("userId") == USER_ID]
    today_ids = [d["id"] for d in my_docs if d.get("date") == today]

    frequency = {}
    for d in my_docs:
        if d.get("date", "") >= cutoff and int(d.get("workItemId", 0)) != FIXED_WI:
            wi_id = int(d["workItemId"])
            frequency[wi_id] = frequency.get(wi_id, 0) + int(d.get("minutes", 0))

    return {"frequency": frequency, "today_ids": today_ids}


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    print(json.dumps(get_timelog_entries(days), indent=2))
