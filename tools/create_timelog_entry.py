"""
Create a single TimeLog entry via the extension API.

Usage : python tools/create_timelog_entry.py <wi_id> <minutes> <type> <comment> [date]
Example: python tools/create_timelog_entry.py 220396 20 "Demanda de operacao" "Lançamento Horas do dia"
         python tools/create_timelog_entry.py 220396 20 "Demanda de operacao" "Lançamento Horas do dia" 2026-04-28
Output: JSON with the created entry id
"""
import os
import sys
import json
from datetime import datetime

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from utils import get_bearer, auth_headers, TIMELOG_URL

load_dotenv()

USER_ID = os.environ["AZURE_DEVOPS_USER_ID"]
USER_DISPLAY = os.environ["AZURE_DEVOPS_USER_DISPLAY"]


def create_entry(wi_id, minutes, entry_type, comment, date_str=None):
    bearer = get_bearer()
    if date_str is None:
        date_obj = datetime.now()
    else:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

    body = {
        "minutes": minutes,
        "user": USER_DISPLAY,
        "userId": USER_ID,
        "date": date_obj.strftime("%Y-%m-%d"),
        "dateWeek": date_obj.strftime("%G-W%V"),
        "workItemId": wi_id,
        "type": entry_type,
        "comment": comment,
    }
    resp = requests.post(TIMELOG_URL, headers=auth_headers(bearer, json_body=True), json=body)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python tools/create_timelog_entry.py <wi_id> <minutes> <type> <comment> [date]")
        sys.exit(1)
    date_arg = sys.argv[5] if len(sys.argv) > 5 else None
    result = create_entry(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4], date_arg)
    print(json.dumps(result, indent=2, ensure_ascii=False))
