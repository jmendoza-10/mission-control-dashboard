---
name: mission-control
description: |
  Orchestrate Jorge's Mission Control Dashboard — the 8-bit retro monitoring UI for his autonomous AI agent system. Use this skill whenever the user mentions the dashboard, agent status, Janus, Vulcan, task queue, activity log, or wants to simulate/update agent work. Also trigger when the user asks to "have an agent do something", check agent status, queue a task, log an event, or update dashboard metrics — even if they don't say "dashboard" explicitly. This is the go-to skill for anything involving the mission control system.
---

# Mission Control Dashboard Orchestrator

You are managing Jorge's Mission Control Dashboard — a Factorio-inspired, 8-bit retro monitoring UI that visualizes autonomous AI agent activity. The dashboard polls JSON data files every 30 seconds and renders them as an animated pixel-art factory floor.

## Coding Task Delegation — IMPORTANT

**All coding tasks default to Vulcan.** When the user reports a bug, requests a code change, or describes any task that involves editing HTML/JS/CSS/Python/shell files, Janus should NOT implement the fix directly. Instead:

1. **Triage** — Janus investigates and identifies the root cause, target files, and what needs to change.
2. **Spec** — Janus writes a clear, scoped task description (what to fix, which file(s), expected behavior).
3. **Delegate** — Queue it for Vulcan via `queue-add` or dispatch it directly via `agent-runner.sh code-patch`.
4. **Verify** — After Vulcan completes, Janus reviews the output and confirms the fix.

Janus should only implement code changes directly when:
- Vulcan is confirmed offline (`curl -s http://localhost:11434/api/tags` fails)
- Jorge explicitly says "just do it" or "handle it yourself"
- The fix is a single-line JSON data edit (not code)

When in doubt, delegate. The forge handles code — Janus handles orchestration.

## Architecture at a Glance

The dashboard is a single-file HTML app (`mission-control.html`) that reads from six JSON files in `data/`. There is no backend required — you update the JSON files directly and the dashboard picks up changes within 30 seconds.

**Data directory**: Find it relative to this skill — it's at `../../data/` from this SKILL.md, or look for a `data/` folder containing `agents.json` in the project root.

## The Helper Script

A Python CLI tool handles all atomic updates. Find it by searching for `dashboard_update.py` — it could be in any of these locations depending on how the skill was installed:

- `~/.claude/skills/mission-control/scripts/dashboard_update.py` (installed skill)
- `<project-root>/.claude/skills/mission-control/scripts/dashboard_update.py` (in-repo)
- Or search: `find / -name dashboard_update.py -path "*/mission-control/*" 2>/dev/null | head -1`

The script auto-discovers the `data/` directory. If it can't find it, set `MC_DATA_DIR` to the path containing your JSON files (e.g., `export MC_DATA_DIR=~/workspace/mission-control-dashboard/data`).

### Available Commands

| Command | What it does |
|---------|-------------|
| `agent-start --agent <id> --task "description"` | Set agent active, assign task, bump tasksToday, log activity |
| `agent-complete --agent <id>` | Complete current task, return to idle, bump tasksCompleted, update queue + metrics |
| `agent-idle --agent <id>` | Return to idle without completing (pause/cancel) |
| `queue-add --title "task name" --agent <id> --priority high\|medium\|low` | Add a new task to the queue |
| `queue-update --title "task name" --status queued\|in_progress\|completed` | Change a queue item's status |
| `task-update --task-id <id> --status running\|idle --result success\|error` | Update a scheduled task |
| `log --source <id> --message "text" --status success\|error\|info` | Custom activity log entry |
| `metric --field <name> --increment <n>` | Bump a daily/weekly metric |
| `status` | Print full dashboard state summary |
| `status --agent <id>` | Print one agent's state |

### Current Agents

- **janus** — Orchestrator: email triage, calendar sync, briefings, summaries
- **vulcan** — Builder: research, code generation, document creation, deep work

### Scheduled Tasks (tasks.json)

- `morning-briefing` — Daily 8AM brief
- `daily-eod-summary` — Daily 9PM end-of-day summary
- `openclaw-research` — On-demand research tasks
- `heartbeat` — Service health check every 30 min

### Task Queue (in agents.json)

Items have: id, title, assignedTo, priority (high/medium/low), status (queued/in_progress/completed)

## How to Handle User Requests

The whole point of this skill is that Jorge should be able to give natural, high-level instructions and you handle the details. Here's how to translate intent into actions:

### "Have Vulcan work on X" / "Simulate Vulcan doing X"

This is a two-phase operation with a time delay to make it feel real on the dashboard:

1. **Start phase**: Run `agent-start --agent vulcan --task "X"`
2. **Wait**: Use `sleep` for a realistic duration (30s for small tasks, 60-120s for bigger ones)
3. **Complete phase**: Run `agent-complete --agent vulcan`

If the task is already in the queue, the script handles updating its status automatically. If it's not in the queue, consider adding it first with `queue-add`.

### "Fix X" / "Have the team work on X" / Collaborative coding tasks

When the user mentions "the team", "both agents", or describes a task that involves **debugging, bug fixes, code changes, or system improvements**, use the collaborative workflow. Janus triages and specs; Vulcan builds and ships.

**Phase 1 — Janus triages** (10-20s):
1. `queue-add --title "X" --agent janus --priority <infer>` (if not already queued)
2. `agent-start --agent janus --task "Triage: X"`
3. *Actually investigate the issue* — read files, check logs, identify root cause
4. `log --source janus --message "Triaged: <brief diagnosis>" --status info`
5. `agent-complete --agent janus`

**Phase 2 — Vulcan builds** (30-120s depending on scope):
1. `agent-start --agent vulcan --task "Fix: X"`
2. *Actually implement the fix* — edit code, write tests, etc.
3. `log --source vulcan --message "Fixed: <what changed>" --status success`
4. `agent-complete --agent vulcan`

**Phase 3 — Janus verifies** (10s):
1. `agent-start --agent janus --task "Verify: X"`
2. *Verify the fix* — review changes, confirm no regressions
3. `log --source janus --message "Verified: <outcome>" --status success`
4. `agent-complete --agent janus`

**How to detect collaborative tasks**: If the user says any of the following, use this workflow instead of the single-agent pattern:
- "the team", "have them fix", "both agents"
- Bug reports: "there's an issue with", "X is broken", "fix the"
- System work: "update the dashboard", "patch", "refactor"
- Any task where Janus's triage skills AND Vulcan's build skills are both clearly useful

**Timing**: Keep waits short between handoffs (2-5s) so the user sees the baton pass on the dashboard. The "real work" happens during each agent's active phase — you should actually do the investigation/coding, not just simulate it.

### "Queue up X for Vulcan/Janus"

Run `queue-add --title "X" --agent vulcan --priority medium` (infer priority from context — urgent/ASAP = high, normal = medium, backlog/whenever = low).

### "What's the dashboard status?" / "How are the agents?"

Run `status` to get a summary, then relay it conversationally.

### "Log that X happened"

Run `log --source <relevant-agent-or-system> --message "X" --status <infer: success/error/info>`

### "Run the morning briefing" / "Trigger heartbeat"

Run `task-update --task-id <id> --status running`, wait an appropriate duration, then `task-update --task-id <id> --status idle --result success`.

## Important Details

- **Timestamps**: The script generates UTC ISO 8601 timestamps automatically. You never need to construct them manually.
- **Activity log**: The script auto-appends to activity.json and caps it at 50 entries. No manual log management needed.
- **Metrics cascade**: `agent-complete` automatically bumps both the agent's `tasksCompleted` and the global `metrics.json` daily/weekly counters.
- **Recent actions**: Capped at 10 per agent, oldest dropped automatically.
- **Cross-file consistency**: The script updates agents.json, activity.json, and metrics.json in the right order. Don't edit these files by hand when the script can do it.

## When to Edit JSON Directly

The script covers ~90% of use cases. For these, edit the JSON files directly:

- Adding a brand new agent to agents.json
- Modifying service health in services.json
- Changing token history in metrics.json
- Updating alert configuration in alerts.json
- Modifying scheduled task definitions (cron, inputs/outputs) in tasks.json

When editing directly, always update the `lastUpdated` field to the current UTC timestamp so the dashboard picks up the change.

## File Locations Reference

```
data/
├── agents.json    — Agent state + task queue
├── tasks.json     — Scheduled task definitions
├── activity.json  — Rolling event log (max 50)
├── services.json  — Connected service health
├── metrics.json   — Daily/weekly performance stats
└── alerts.json    — Alert configuration
```
