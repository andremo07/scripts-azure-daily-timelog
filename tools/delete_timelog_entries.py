"""
Delete TimeLog entries by document ID (used to overwrite today's entries).

Usage : python tools/delete_timelog_entries.py <doc_id> [<doc_id> ...]
Output: Prints each deleted ID to stdout
"""
import os
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from utils import get_bearer, auth_headers, TIMELOG_URL

load_dotenv()


def delete_entries(doc_ids):
    if not doc_ids:
        print("No entries to delete.")
        return
    bearer = get_bearer()
    headers = auth_headers(bearer)
    for doc_id in doc_ids:
        resp = requests.delete(f"{TIMELOG_URL}/{doc_id}", headers=headers)
        if resp.status_code in (200, 204):
            print(f"Deleted: {doc_id}")
        else:
            print(f"ERROR deleting {doc_id}: {resp.status_code} — {resp.text}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/delete_timelog_entries.py <doc_id> [<doc_id> ...]")
        sys.exit(1)
    delete_entries(sys.argv[1:])
