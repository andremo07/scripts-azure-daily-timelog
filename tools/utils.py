import os
import sys
import subprocess
import base64
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

TENANT = os.environ["AZURE_DEVOPS_TENANT"]
AZ = os.environ.get("AZ_PATH", "az")
ORG = os.environ["AZURE_DEVOPS_ORG"]
PAT = os.environ.get("AZURE_DEVOPS_PAT", "")

_org_name = ORG.rstrip("/").split("/")[-1]
TIMELOG_URL = (
    f"https://extmgmt.dev.azure.com/{_org_name}/_apis/ExtensionManagement"
    "/InstalledExtensions/TimeLog/time-logging-extension"
    "/Data/Scopes/Default/Current/Collections/TimeLogData/Documents"
)


def get_bearer():
    if PAT:
        return None  # signal to use PAT auth instead
    result = subprocess.run(
        [AZ, "account", "get-access-token",
         "--resource", "499b84ac-1321-427f-aa17-267ca6975798",
         "--tenant", TENANT,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True,
    )
    token = result.stdout.strip()
    if result.returncode != 0 or not token:
        print(
            f"ERROR: Failed to get Bearer token.\n"
            f"Run: az login --tenant {TENANT} --allow-no-subscriptions",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def auth_headers(bearer, json_body=False):
    if PAT:
        b64 = base64.b64encode(f":{PAT}".encode()).decode()
        h = {
            "Authorization": f"Basic {b64}",
            "Accept": "application/json;api-version=3.1-preview.1",
            "x-tfs-fedauthredirect": "Suppress",
        }
    else:
        h = {
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/json;api-version=3.1-preview.1",
            "x-tfs-fedauthredirect": "Suppress",
        }
    if json_body:
        h["Content-Type"] = "application/json"
    return h
