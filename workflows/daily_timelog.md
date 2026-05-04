# Daily Timelog Workflow

## Objective
Log exactly 8h (480 min) to the Azure DevOps TimeLog extension for the current day:
- **20 min** → WI `OVERHEAD_WI_ID`, type `Agenda da operacao, negocio ou coorporativa`, comment `Daily Team Integração 3.0`
- **20 min** → WI `OVERHEAD_WI_ID`, type `Demanda de operacao`, comment `Lançamento Horas do dia`
- **440 min** → distributed across WIs in state `Em Desenvolvimento` assigned to the user

Overwrite pattern: delete any existing entries for today before creating new ones.

## Required Env Vars
| Variable | Description |
|---|---|
| `AZURE_DEVOPS_ORG` | `https://dev.azure.com/<org>` |
| `AZURE_DEVOPS_PROJECT` | Project name |
| `AZURE_DEVOPS_TENANT` | AAD tenant ID (for Bearer token) |
| `AZURE_DEVOPS_USER_ID` | User GUID (filters timelog documents) |
| `AZURE_DEVOPS_USER_EMAIL` | User email (for WIQL AssignedTo filter) |
| `AZURE_DEVOPS_USER_DISPLAY` | Display name (written into timelog entries) |
| `OVERHEAD_WI_ID` | WI ID for Daily + Lançamento entries |
| `AZ_PATH` | Full path to `az.cmd` |

## Tools Used
| Tool | Purpose |
|---|---|
| `tools/get_timelog_entries.py` | GET timelog docs → `frequency` (last 7d) + `today_ids` |
| `tools/get_board_workitems.py` | GET active WIs via `az boards query` |
| `tools/delete_timelog_entries.py` | DELETE today's existing entries (overwrite) |
| `tools/create_timelog_entry.py` | POST one timelog entry |

## Process

### Step 1 — Get Bearer token
The tools call `az account get-access-token` automatically. If it fails, run:
```
az login --tenant <AZURE_DEVOPS_TENANT> --allow-no-subscriptions
```

### Step 1.5 — Handling past days
To fill entries for past days without confirmation, use the optional date parameter:
```
python tools/create_timelog_entry.py 220396 20 "Agenda da operacao, negocio ou coorporativa" "Daily Team Integração 3.0" YYYY-MM-DD
python tools/create_timelog_entry.py 220396 20 "Demanda de operacao" "Lançamento Horas do dia" YYYY-MM-DD
python tools/create_timelog_entry.py 220396 440 "Atividade de projeto" "Suporte para o time" YYYY-MM-DD
```
Run these sequentially without user confirmation for backfill scenarios.

### Step 2 — Gather context (run in parallel)
```
python tools/get_timelog_entries.py 7   # → frequency + today_ids
python tools/get_board_workitems.py     # → active WIs
```

### Step 3 — Calculate distribution
1. **Filter frequency** — keep only WI IDs that appear in the active board list. Discard any WI from history that is no longer on the board (state changed, reassigned, etc.).
2. **Select top 3** — take up to 3 WIs by filtered frequency score (highest first). Fill remaining slots with the top board WIs by priority (board order = priority ASC) that are not already selected.
3. **Distribute 440 min**:
   - If no active WIs available (or user chooses to consolidate): put all 440 min in `OVERHEAD_WI_ID` (WI#220396) with type `Atividade de projeto` and comment `Suporte para o time`
   - Otherwise:
     - WIs with no history get the minimum: 60 min
     - Subtract all minimums from 440; distribute the remainder proportionally by frequency score among WIs that have history
     - Round each to nearest 5 min; adjust the first WI to make total exactly 440 min

### Step 4 — Confirm with user
For **today's date**: Present the plan before executing:
```
Proposta para YYYY-MM-DD:
  WI#220396 — Daily Team Integração 3.0    → 20min
  WI#220396 — Lançamento Horas do dia      → 20min
  WI#{id}   — {title}                      → {min}min
  ...
  Total: 480min (8h)
Confirma? (s/n)
```

For **past dates**: Skip confirmation and execute directly (backfill mode).

### Step 5 — Execute
Delete today's entries first:
```
python tools/delete_timelog_entries.py <id1> <id2> ...
```

Create fixed entries:
```
python tools/create_timelog_entry.py 220396 20 "Agenda da operacao, negocio ou coorporativa" "Daily Team Integração 3.0"
python tools/create_timelog_entry.py 220396 20 "Demanda de operacao" "Lançamento Horas do dia"
```

Create variable entries (one per active WI):
```
python tools/create_timelog_entry.py {wi_id} {minutes} "Atividade de projeto" "Implementacao"
```

Or if consolidating all hours to WI#220396:
```
python tools/create_timelog_entry.py 220396 440 "Atividade de projeto" "Suporte para o time"
```

Run sequentially — do not parallelize writes to the same WI.

### Step 6 — Report
```
=== Daily Time Log — {date} ===
  WI#220396 — Daily Team Integração 3.0    20min
  WI#220396 — Lançamento Horas do dia      20min
  WI#{id}   — {title}                     {min}min
  ...
  Total: 480min (8h) ✓

Verifique: https://dev.azure.com/DrogariaAraujo/.../_apps/hub/TimeLog.time-logging-extension.time-log-summary
```

## Edge Cases
| Situation | Action |
|---|---|
| No active WIs or user chooses to consolidate | Add all 440 min to WI#220396 with comment `Suporte para o time` |
| `today_ids` is empty | Skip delete step, proceed to create |
| POST fails | Stop immediately, report which entries succeeded/failed |
| Bearer token expired | Prompt: `az login --tenant <TENANT> --allow-no-subscriptions` |
