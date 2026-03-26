#!/usr/bin/env python3
"""
Mission Control Dashboard — atomic JSON updater.

Handles all state transitions across the dashboard's JSON data files,
keeping them consistent (timestamps, cross-file references, activity log).

Usage examples:
    # Set an agent active with a task
    python dashboard_update.py agent-start --agent vulcan --task "OpenClaw contributor guide draft"

    # Complete the agent's current task
    python dashboard_update.py agent-complete --agent vulcan

    # Set an agent back to idle (without completing — e.g. paused/failed)
    python dashboard_update.py agent-idle --agent vulcan

    # Mark a task-queue item as in_progress or completed
    python dashboard_update.py queue-update --title "OpenClaw contributor guide draft" --status completed

    # Update a scheduled task's status
    python dashboard_update.py task-update --task-id morning-briefing --status running

    # Log a custom activity event
    python dashboard_update.py log --source vulcan --message "Research phase started" --status info

    # Bump a daily metric
    python dashboard_update.py metric --field tasksCompleted --increment 1

    # Show current state of an agent or the full dashboard
    python dashboard_update.py status --agent vulcan
    python dashboard_update.py status
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── locate data directory ──────────────────────────────────────────────
# Works whether called from the repo root, the skill directory, or anywhere else.
SCRIPT_DIR = Path(__file__).resolve().parent
POSSIBLE_DATA_DIRS = [
    SCRIPT_DIR.parent.parent.parent / "data",          # skill lives inside repo
    SCRIPT_DIR.parent.parent.parent.parent / "data",    # one more level up
    Path.cwd() / "data",                                # CWD fallback
    Path.home() / "workspace" / "mission-control-dashboard" / "data",  # Jorge's project
    Path("/Users/jorgemendoza/workspace/mission-control-dashboard/data"),  # absolute fallback
]

DATA_DIR = None

# Env var takes priority (explicit override)
env = os.environ.get("MC_DATA_DIR")
if env and Path(env).is_dir():
    DATA_DIR = Path(env)
else:
    for d in POSSIBLE_DATA_DIRS:
        if d.is_dir() and (d / "agents.json").exists():
            DATA_DIR = d
            break

if DATA_DIR is None:
    print("ERROR: Cannot find data/ directory. Set MC_DATA_DIR or run from the repo root.", file=sys.stderr)
    sys.exit(1)


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(name):
    with open(DATA_DIR / name) as f:
        return json.load(f)


def save(name, data):
    data["lastUpdated"] = now_iso()
    with open(DATA_DIR / name, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  ✓ Wrote {name}")


def find_agent(data, agent_id):
    for a in data["agents"]:
        if a["id"] == agent_id.lower():
            return a
    names = [a["id"] for a in data["agents"]]
    print(f"ERROR: Agent '{agent_id}' not found. Available: {names}", file=sys.stderr)
    sys.exit(1)


def append_activity(source, message, status="info", event_type="task"):
    """Append an event to activity.json, keeping it under 50 entries."""
    activity = load("activity.json")
    event = {
        "timestamp": now_iso(),
        "type": event_type,
        "source": source,
        "message": message,
        "status": status,
    }
    activity["events"].insert(0, event)
    activity["events"] = activity["events"][:50]
    save("activity.json", activity)


def find_queue_item(data, title):
    """Find a task queue item by title (case-insensitive substring match)."""
    title_lower = title.lower()
    for item in data.get("taskQueue", []):
        if title_lower in item["title"].lower():
            return item
    return None


# ── Token estimation defaults ──────────────────────────────────────────
TOKEN_ESTIMATES = {
    "cowork-session": 15000,
    "scheduled-task": 8000,
    "research": 25000,
    "briefing": 12000,
    "vulcan-run": 5000,
    "interactive": 10000,
}


def bump_tokens(tokens, source="system"):
    """Add estimated token usage to daily/weekly metrics and update today's history entry."""
    metrics = load("metrics.json")
    d = metrics["daily"]
    d["tokensUsed"] = d.get("tokensUsed", 0) + tokens
    d["apiCalls"] = d.get("apiCalls", 0) + 1

    # Estimate cost using blended rate
    est = metrics.get("tokenEstimates", {})
    cost_per_1k = est.get("blendedCostPer1KTokens", 0.03)
    cost = (tokens / 1000) * cost_per_1k
    d["estimatedCost"] = round(d.get("estimatedCost", 0) + cost, 2)

    metrics["weekly"]["tokensUsed"] = metrics["weekly"].get("tokensUsed", 0) + tokens
    metrics["weekly"]["estimatedCost"] = round(
        metrics["weekly"].get("estimatedCost", 0) + cost, 2
    )

    # Update today's entry in tokenHistory
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history = metrics.get("tokenHistory", [])
    updated = False
    for entry in history:
        if entry["date"] == today_str:
            entry["tokens"] = entry.get("tokens", 0) + tokens
            updated = True
            break
    if not updated:
        history.append({"date": today_str, "tokens": tokens})
    # Keep last 7 days
    metrics["tokenHistory"] = history[-7:]

    save("metrics.json", metrics)
    print(f"  → Tokens bumped +{tokens} (est ${cost:.2f}) from {source}")


def estimate_tokens_for_task(task_description):
    """Infer token estimate from task description keywords."""
    desc = task_description.lower()
    if any(w in desc for w in ["research", "deep-dive", "analysis", "report"]):
        return TOKEN_ESTIMATES["research"]
    if any(w in desc for w in ["briefing", "morning", "eod", "summary"]):
        return TOKEN_ESTIMATES["briefing"]
    if any(w in desc for w in ["code", "review", "workspace", "refactor"]):
        return TOKEN_ESTIMATES["vulcan-run"]
    return TOKEN_ESTIMATES["interactive"]


# ── commands ───────────────────────────────────────────────────────────

def cmd_agent_start(args):
    """Set an agent to active status and assign a task."""
    agents = load("agents.json")
    agent = find_agent(agents, args.agent)

    agent["status"] = "active"
    agent["currentTask"] = args.task
    agent["metrics"]["tasksToday"] = agent["metrics"].get("tasksToday", 0) + 1
    agent["uptime"]["sessionsToday"] = agent["uptime"].get("sessionsToday", 0) + 1

    # Add to recentActions
    agent["recentActions"].insert(0, {
        "timestamp": now_iso(),
        "action": f"Started {args.task}",
        "status": "in_progress",
    })
    agent["recentActions"] = agent["recentActions"][:10]  # keep recent

    save("agents.json", agents)

    # Update matching queue item if it exists
    if find_queue_item(agents, args.task):
        queue_item = find_queue_item(agents, args.task)
        queue_item["status"] = "in_progress"
        save("agents.json", agents)

    # Log activity
    append_activity(
        source=agent["id"],
        message=f"{agent['name']} started: {args.task}",
        status="info",
    )

    # Auto-bump token estimate for the agent
    est = estimate_tokens_for_task(args.task)
    agent["metrics"]["tokensUsedToday"] = agent["metrics"].get("tokensUsedToday", 0) + est
    save("agents.json", agents)
    bump_tokens(est, source=agent["id"])

    print(f"  → {agent['name']} is now active on: {args.task} (~{est} tokens estimated)")


def cmd_agent_complete(args):
    """Complete the agent's current task and return to idle."""
    agents = load("agents.json")
    agent = find_agent(agents, args.agent)

    task_name = agent.get("currentTask") or args.task or "unknown task"

    agent["status"] = "idle"
    agent["currentTask"] = None
    agent["metrics"]["tasksCompleted"] = agent["metrics"].get("tasksCompleted", 0) + 1

    agent["recentActions"].insert(0, {
        "timestamp": now_iso(),
        "action": f"{task_name} completed",
        "status": "success",
    })
    agent["recentActions"] = agent["recentActions"][:10]

    # Update matching queue item
    queue_item = find_queue_item(agents, task_name)
    if queue_item:
        queue_item["status"] = "completed"

    save("agents.json", agents)

    # Log activity
    append_activity(
        source=agent["id"],
        message=f"{agent['name']} completed: {task_name}",
        status="success",
    )

    # Bump daily metrics
    metrics = load("metrics.json")
    metrics["daily"]["tasksCompleted"] = metrics["daily"].get("tasksCompleted", 0) + 1
    metrics["weekly"]["tasksCompleted"] = metrics["weekly"].get("tasksCompleted", 0) + 1
    save("metrics.json", metrics)

    print(f"  → {agent['name']} completed: {task_name}")


def cmd_agent_idle(args):
    """Set an agent back to idle without completing the task."""
    agents = load("agents.json")
    agent = find_agent(agents, args.agent)
    task_name = agent.get("currentTask") or "current task"

    agent["status"] = "idle"
    agent["currentTask"] = None

    agent["recentActions"].insert(0, {
        "timestamp": now_iso(),
        "action": f"{task_name} paused",
        "status": "info",
    })
    agent["recentActions"] = agent["recentActions"][:10]

    save("agents.json", agents)
    print(f"  → {agent['name']} is now idle")


def cmd_queue_update(args):
    """Update a task queue item's status."""
    agents = load("agents.json")
    item = find_queue_item(agents, args.title)
    if not item:
        print(f"ERROR: No queue item matching '{args.title}'", file=sys.stderr)
        sys.exit(1)
    item["status"] = args.status
    save("agents.json", agents)
    append_activity(
        source=item.get("assignedTo", "system"),
        message=f"Queue item '{item['title']}' → {args.status}",
        status="info",
    )
    print(f"  → Queue item '{item['title']}' is now {args.status}")


def cmd_queue_add(args):
    """Add a new item to the task queue."""
    agents = load("agents.json")
    queue = agents.get("taskQueue", [])

    # Generate next ID
    max_id = 0
    for item in queue:
        try:
            num = int(item["id"].split("-")[1])
            max_id = max(max_id, num)
        except (IndexError, ValueError):
            pass

    new_item = {
        "id": f"tq-{max_id + 1}",
        "title": args.title,
        "assignedTo": args.agent.lower(),
        "priority": args.priority,
        "status": "queued",
        "createdAt": now_iso(),
    }
    queue.append(new_item)
    agents["taskQueue"] = queue
    save("agents.json", agents)

    append_activity(
        source=args.agent.lower(),
        message=f"New task queued: {args.title} ({args.priority} priority)",
        status="info",
    )
    print(f"  → Added to queue: {args.title} (assigned to {args.agent})")


def cmd_task_update(args):
    """Update a scheduled task's status/result."""
    tasks = load("tasks.json")
    target = None
    for t in tasks["tasks"]:
        if t["id"] == args.task_id:
            target = t
            break
    if not target:
        ids = [t["id"] for t in tasks["tasks"]]
        print(f"ERROR: Task '{args.task_id}' not found. Available: {ids}", file=sys.stderr)
        sys.exit(1)

    if args.status:
        target["status"] = args.status
    if args.result:
        target["lastResult"] = args.result
        target["lastRun"] = now_iso()
    if args.output:
        target["lastOutput"] = {
            "type": "summary",
            "title": args.output_title or target["name"],
            "content": args.output,
            "generatedAt": now_iso(),
        }

    save("tasks.json", tasks)
    print(f"  → Task '{target['name']}' updated")


def cmd_log(args):
    """Log a custom event to activity.json."""
    append_activity(
        source=args.source,
        message=args.message,
        status=args.status,
        event_type=args.type,
    )
    print(f"  → Logged: {args.message}")


def cmd_metric(args):
    """Bump a daily/weekly metric."""
    metrics = load("metrics.json")
    field = args.field
    inc = args.increment

    if field in metrics["daily"]:
        metrics["daily"][field] = metrics["daily"][field] + inc
    if field in metrics["weekly"]:
        metrics["weekly"][field] = metrics["weekly"][field] + inc

    save("metrics.json", metrics)
    print(f"  → {field} bumped by {inc}")


def cmd_token_bump(args):
    """Manually bump estimated token usage."""
    tokens = args.tokens
    if tokens <= 0 and args.task_type:
        tokens = TOKEN_ESTIMATES.get(args.task_type, TOKEN_ESTIMATES["interactive"])
    elif tokens <= 0:
        tokens = TOKEN_ESTIMATES["interactive"]

    source = args.source or "manual"

    # Also update agent's tokensUsedToday if an agent is specified
    if args.agent:
        agents = load("agents.json")
        agent = find_agent(agents, args.agent)
        agent["metrics"]["tokensUsedToday"] = agent["metrics"].get("tokensUsedToday", 0) + tokens
        save("agents.json", agents)

    bump_tokens(tokens, source=source)
    append_activity(
        source=source,
        message=f"Token usage +{tokens} estimated ({source})",
        status="info",
        event_type="system",
    )


def cmd_status(args):
    """Print current state of an agent or full dashboard summary."""
    agents = load("agents.json")

    if args.agent:
        agent = find_agent(agents, args.agent)
        print(json.dumps(agent, indent=2))
    else:
        # Summary view
        print("═══ Mission Control Status ═══\n")
        for a in agents["agents"]:
            status_icon = "🟢" if a["status"] == "active" else "⚪"
            task = a.get("currentTask") or "—"
            print(f"  {status_icon} {a['name']} ({a['role']}): {a['status']}  task: {task}")
            print(f"     completed: {a['metrics']['tasksCompleted']}  today: {a['metrics']['tasksToday']}  success: {a['metrics']['successRate']:.0%}")
        print(f"\n  Queue: {len(agents.get('taskQueue', []))} items")
        for q in agents.get("taskQueue", []):
            icon = {"queued": "⏳", "in_progress": "🔄", "completed": "✅"}.get(q["status"], "?")
            print(f"    {icon} {q['title']} → {q['assignedTo']} [{q['priority']}]")


# ── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mission Control Dashboard updater")
    sub = parser.add_subparsers(dest="command", required=True)

    # agent-start
    p = sub.add_parser("agent-start", help="Activate an agent on a task")
    p.add_argument("--agent", required=True)
    p.add_argument("--task", required=True)

    # agent-complete
    p = sub.add_parser("agent-complete", help="Complete agent's current task")
    p.add_argument("--agent", required=True)
    p.add_argument("--task", default=None, help="Override task name (uses currentTask if omitted)")

    # agent-idle
    p = sub.add_parser("agent-idle", help="Set agent to idle (pause, no completion)")
    p.add_argument("--agent", required=True)

    # queue-update
    p = sub.add_parser("queue-update", help="Update a queue item's status")
    p.add_argument("--title", required=True)
    p.add_argument("--status", required=True, choices=["queued", "in_progress", "completed"])

    # queue-add
    p = sub.add_parser("queue-add", help="Add a new item to the task queue")
    p.add_argument("--title", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--priority", default="medium", choices=["high", "medium", "low"])

    # task-update
    p = sub.add_parser("task-update", help="Update a scheduled task")
    p.add_argument("--task-id", required=True)
    p.add_argument("--status", choices=["idle", "running"])
    p.add_argument("--result", choices=["success", "error"])
    p.add_argument("--output", help="Output content text")
    p.add_argument("--output-title", help="Output title")

    # log
    p = sub.add_parser("log", help="Log a custom activity event")
    p.add_argument("--source", required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--status", default="info", choices=["success", "error", "info"])
    p.add_argument("--type", default="task", choices=["task", "system", "manual"])

    # metric
    p = sub.add_parser("metric", help="Bump a daily/weekly metric")
    p.add_argument("--field", required=True)
    p.add_argument("--increment", type=float, default=1)

    # token-bump
    p = sub.add_parser("token-bump", help="Bump estimated token usage")
    p.add_argument("--tokens", type=int, default=0, help="Exact token count (or 0 to auto-estimate)")
    p.add_argument("--task-type", default=None,
                   choices=list(TOKEN_ESTIMATES.keys()),
                   help="Task type for auto-estimation")
    p.add_argument("--agent", default=None, help="Agent to attribute tokens to")
    p.add_argument("--source", default=None, help="Source label for the log entry")

    # status
    p = sub.add_parser("status", help="Show current dashboard state")
    p.add_argument("--agent", default=None)

    args = parser.parse_args()

    commands = {
        "agent-start": cmd_agent_start,
        "agent-complete": cmd_agent_complete,
        "agent-idle": cmd_agent_idle,
        "queue-update": cmd_queue_update,
        "queue-add": cmd_queue_add,
        "task-update": cmd_task_update,
        "log": cmd_log,
        "metric": cmd_metric,
        "token-bump": cmd_token_bump,
        "status": cmd_status,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
