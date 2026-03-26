#!/usr/bin/env python3
"""
Mission Control server — serves static files + PATCH API for task/agent control.
Zero dependencies beyond Python 3 stdlib.

Usage:
    python3 server.py
    python3 server.py 9090   # custom port

Endpoints:
    GET  /                         → mission-control.html
    GET  /health                   → {"ok": true, "uptime": ...}
    PATCH /data/tasks.json         → update a scheduled task's fields
    PATCH /data/agents.json        → update an agent's fields
    GET  /data/*.json              → static JSON data files
"""

import json
import glob
import os
import sys
import time
import signal
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
ROOT = os.path.dirname(os.path.abspath(__file__))
START_TIME = time.time()

# Data directory — set MC_DATA_DIR to override
# Default: look for ../openclaw-docs/data/ relative to this server,
# or ~/workspace/local/openclaw-docs/data/ as fallback.
# Keeps all mutable state in openclaw-docs (no PII in this repo).
DATA_DIR = os.environ.get("MC_DATA_DIR")
if not DATA_DIR:
    _data_candidates = [
        os.path.join(ROOT, "..", "openclaw-docs", "data"),
        os.path.join(ROOT, "..", "local", "openclaw-docs", "data"),
        os.path.expanduser("~/workspace/local/openclaw-docs/data"),
    ]
    for _c in _data_candidates:
        if os.path.isdir(_c):
            DATA_DIR = os.path.realpath(_c)
            break
    if not DATA_DIR:
        DATA_DIR = os.path.join(ROOT, "data")  # fallback to local

# Live dispatch directory — set MC_DISPATCH_DIR to override
# Default: look for ../openclaw-docs/dispatch/ relative to this server,
# or ~/workspace/local/openclaw-docs/dispatch/ as fallback
DISPATCH_DIR = os.environ.get("MC_DISPATCH_DIR")
if not DISPATCH_DIR:
    # Try sibling openclaw-docs first (common iCloud layout)
    _candidates = [
        os.path.join(ROOT, "..", "openclaw-docs", "dispatch"),
        os.path.join(ROOT, "..", "local", "openclaw-docs", "dispatch"),
        os.path.expanduser("~/workspace/local/openclaw-docs/dispatch"),
    ]
    for _c in _candidates:
        if os.path.isdir(_c):
            DISPATCH_DIR = os.path.realpath(_c)
            break
    if not DISPATCH_DIR:
        DISPATCH_DIR = os.path.join(ROOT, "dispatch")  # fallback to local

TASK_ALLOWED_FIELDS = {"status", "lastResult", "lastRun", "nextRun", "lastOutput"}
AGENT_ALLOWED_FIELDS = {"status", "currentTask", "metrics", "recentActions"}


def graceful_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for clean launchd stops."""
    print(f"\n  Received signal {signum}, shutting down gracefully.")
    sys.exit(0)

signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)


class MissionControlHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    # Suppress per-request logging noise in launchd logs
    def log_message(self, format, *args):
        # Only log errors and PATCHes, skip routine GETs
        if self.command in ("PATCH", "POST") or (len(args) > 1 and str(args[1]).startswith("4")):
            super().log_message(format, *args)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        clean_path = self.path.split("?")[0]

        # Health-check endpoint for monitoring
        if clean_path == "/health":
            uptime = int(time.time() - START_TIME)
            self._json_response(200, {
                "ok": True,
                "uptime_seconds": uptime,
                "port": PORT,
                "data_dir": DATA_DIR,
                "dispatch_dir": DISPATCH_DIR,
                "pid": os.getpid(),
            })
            return

        # Live dispatch pipeline — reads directly from dispatch directories
        if clean_path == "/api/dispatch":
            self._serve_live_dispatch()
            return

        # Default: static file serving
        super().do_GET()

    def _serve_live_dispatch(self):
        """Build dispatch.json dynamically from queue/processing/completed/failed dirs."""
        stages = ["queue", "processing", "completed", "failed"]
        pipeline = {}
        all_specs = []

        for stage in stages:
            stage_dir = os.path.join(DISPATCH_DIR, stage)
            specs_in_stage = []
            if os.path.isdir(stage_dir):
                for fpath in glob.glob(os.path.join(stage_dir, "*.json")):
                    try:
                        with open(fpath, "r") as f:
                            spec = json.load(f)
                        # Normalize status from result if present
                        if "result" in spec and spec["result"]:
                            spec["status"] = spec["result"].get("status", stage)
                            spec["completedAt"] = spec["result"].get("completedAt")
                            spec["elapsedSec"] = spec["result"].get("elapsedSeconds")
                        else:
                            spec["status"] = stage
                            spec.setdefault("completedAt", None)
                            spec.setdefault("elapsedSec", None)
                        spec.setdefault("result", None)
                        specs_in_stage.append(spec)
                    except (json.JSONDecodeError, IOError):
                        continue
            pipeline[stage] = len(specs_in_stage)
            all_specs.extend(specs_in_stage)

        # Sort by requestedAt descending (newest first), take top 10
        all_specs.sort(
            key=lambda s: s.get("requestedAt", ""),
            reverse=True,
        )
        recent = all_specs[:10]

        # Compute routing stats from today's specs
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_specs = [s for s in all_specs if s.get("requestedAt", "").startswith(today)]
        vulcan_count = sum(1 for s in today_specs if s.get("requestedBy") in ("janus", "vulcan"))
        janus_count = len(today_specs) - vulcan_count

        # Try to read existing routing stats from data/dispatch.json for tokensSaved
        tokens_saved = 0
        static_dispatch = os.path.join(DATA_DIR, "dispatch.json")
        if os.path.exists(static_dispatch):
            try:
                with open(static_dispatch, "r") as f:
                    old = json.load(f)
                tokens_saved = old.get("routingStats", {}).get("tokensSaved", 0)
            except (json.JSONDecodeError, IOError):
                pass

        result = {
            "pipeline": {
                "queued": pipeline.get("queue", 0),
                "processing": pipeline.get("processing", 0),
                "completed": pipeline.get("completed", 0),
                "failed": pipeline.get("failed", 0),
            },
            "recentSpecs": [
                {
                    "id": s.get("id", "unknown"),
                    "task": s.get("task", ""),
                    "description": s.get("description", ""),
                    "status": s.get("status", "unknown"),
                    "requestedAt": s.get("requestedAt"),
                    "completedAt": s.get("completedAt"),
                    "elapsedSec": s.get("elapsedSec"),
                    "spec": s.get("spec", ""),
                    "result": s.get("result") if isinstance(s.get("result"), str) else (
                        s["result"].get("logFile") if isinstance(s.get("result"), dict) else None
                    ),
                }
                for s in recent
            ],
            "routingStats": {
                "date": today,
                "vulcanTasks": vulcan_count,
                "janusTasks": janus_count,
                "totalRouted": len(today_specs),
                "tokensSaved": tokens_saved,
            },
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }
        self._json_response(200, result)

    def do_PATCH(self):
        clean_path = self.path.split("?")[0]

        if clean_path == "/data/tasks.json":
            self._patch_tasks()
        elif clean_path == "/data/agents.json":
            self._patch_agents()
        else:
            self.send_error(404, "PATCH not supported for this path")

    # ── PATCH /data/tasks.json ──────────────────────────────────────────

    def _patch_tasks(self):
        patch = self._read_json_body()
        if patch is None:
            return

        task_id = patch.get("id")
        if not task_id:
            self._json_response(400, {"error": "Missing task id"})
            return

        tasks_path = os.path.join(DATA_DIR, "tasks.json")
        data = self._load_json(tasks_path)
        if data is None:
            return

        task = next((t for t in data.get("tasks", []) if t.get("id") == task_id), None)
        if not task:
            self._json_response(404, {"error": f"Task '{task_id}' not found"})
            return

        for key in TASK_ALLOWED_FIELDS:
            if key in patch:
                task[key] = patch[key]

        data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
        self._save_json(tasks_path, data)

        # Append to activity log (best-effort)
        self._log_activity(
            source=task_id,
            task_name=task.get("name", task_id),
            action="started" if patch.get("status") == "running" else "stopped",
        )

        self._json_response(200, {"ok": True, "task": task})

    # ── PATCH /data/agents.json ─────────────────────────────────────────

    def _patch_agents(self):
        patch = self._read_json_body()
        if patch is None:
            return

        agent_id = patch.get("id")
        if not agent_id:
            self._json_response(400, {"error": "Missing agent id"})
            return

        agents_path = os.path.join(DATA_DIR, "agents.json")
        data = self._load_json(agents_path)
        if data is None:
            return

        agent = next((a for a in data.get("agents", []) if a.get("id") == agent_id), None)
        if not agent:
            self._json_response(404, {"error": f"Agent '{agent_id}' not found"})
            return

        for key in AGENT_ALLOWED_FIELDS:
            if key in patch:
                agent[key] = patch[key]

        data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
        self._save_json(agents_path, data)

        # Log agent state changes
        if "status" in patch:
            self._log_activity(
                source=agent_id,
                task_name=agent.get("name", agent_id),
                action=f"set to {patch['status']}",
            )

        self._json_response(200, {"ok": True, "agent": agent})

    # ── Helpers ──────────────────────────────────────────────────────────

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            self._json_response(400, {"error": f"Invalid JSON: {e}"})
            return None

    def _load_json(self, filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._json_response(500, {"error": f"Failed to read {os.path.basename(filepath)}: {e}"})
            return None

    def _save_json(self, filepath, data):
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def _log_activity(self, source, task_name, action):
        try:
            act_path = os.path.join(DATA_DIR, "activity.json")
            with open(act_path, "r") as f:
                activity = json.load(f)

            activity["events"].insert(0, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "manual",
                "source": source,
                "message": f"{task_name} {action} from Mission Control",
                "status": "info" if "started" in action or "active" in action else "success",
            })
            activity["events"] = activity["events"][:50]
            activity["lastUpdated"] = datetime.now(timezone.utc).isoformat()

            with open(act_path, "w") as f:
                json.dump(activity, f, indent=2)
        except Exception:
            pass  # Activity log is best-effort

    def _json_response(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def end_headers(self):
        if "Access-Control-Allow-Origin" not in str(self._headers_buffer):
            self._cors_headers()
        super().end_headers()


if __name__ == "__main__":
    server = HTTPServer(("", PORT), MissionControlHandler)
    print(f"\n  ⚙ Mission Control server running (PID {os.getpid()})")
    print(f"  → http://localhost:{PORT}/mission-control.html\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
        server.shutdown()
