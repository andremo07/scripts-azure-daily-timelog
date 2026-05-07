"""
Fetch work items in 'Em Desenvolvimento' assigned to the current user.

Usage : python tools/get_board_workitems.py
Output: JSON array of {id, title} to stdout
"""
import os
import sys
import json
import subprocess
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

ORG = os.environ["AZURE_DEVOPS_ORG"]
PROJECT = os.environ["AZURE_DEVOPS_PROJECT"]
USER_EMAIL = os.environ["AZURE_DEVOPS_USER_EMAIL"]
AZ = os.environ.get("AZ_PATH", "az")
PAT = os.environ.get("AZURE_DEVOPS_EXT_PAT") or os.environ.get("AZURE_DEVOPS_PAT", "")

_WIQL = (
    f"SELECT [System.Id],[System.Title],[System.State],[Microsoft.VSTS.Common.Priority] "
    f"FROM WorkItems "
    f"WHERE [System.AssignedTo]='{USER_EMAIL}' "
    f"AND [System.State]='Em Desenvolvimento' "
    f"AND [System.TeamProject]='{PROJECT}' "
    f"ORDER BY [Microsoft.VSTS.Common.Priority] ASC, [System.ChangedDate] DESC"
)


def get_active_workitems():
    if PAT:
        return _get_via_rest()
    return _get_via_az()


def _get_via_rest():
    import base64
    b64 = base64.b64encode(f":{PAT}".encode()).decode()
    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    org_name = ORG.rstrip("/").split("/")[-1]
    wiql_url = f"https://dev.azure.com/{org_name}/{PROJECT}/_apis/wit/wiql?api-version=6.0"
    resp = requests.post(wiql_url, headers=headers, json={"query": _WIQL})
    resp.raise_for_status()
    refs = resp.json().get("workItems", [])
    if not refs:
        return []
    ids = ",".join(str(r["id"]) for r in refs[:20])
    items_url = (
        f"https://dev.azure.com/{org_name}/_apis/wit/workitems"
        f"?ids={ids}&fields=System.Id,System.Title&api-version=6.0"
    )
    resp2 = requests.get(items_url, headers=headers)
    resp2.raise_for_status()
    active = []
    for item in resp2.json().get("value", []):
        fields = item.get("fields", {})
        wi_id = fields.get("System.Id")
        title = str(fields.get("System.Title", "Sem título"))
        if wi_id:
            active.append({"id": int(wi_id), "title": title[:70]})
    return active


def _get_via_az():
    result = subprocess.run(
        [AZ, "boards", "query", "--wiql", _WIQL, "--org", ORG, "--output", "json"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(result.stderr.decode("cp1252", errors="replace"), file=sys.stderr)
        sys.exit(1)
    raw = json.loads(result.stdout.decode("cp1252"))
    items = raw if isinstance(raw, list) else raw.get("value", raw.get("workItems", []))
    active = []
    for item in items:
        fields = item.get("fields", item)
        wi_id = fields.get("System.Id") or item.get("id")
        title = str(fields.get("System.Title", "Sem título"))
        if wi_id:
            active.append({"id": int(wi_id), "title": title[:70]})
    return active


if __name__ == "__main__":
    print(json.dumps(get_active_workitems(), indent=2, ensure_ascii=False))
