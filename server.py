#!/usr/bin/env python3
"""
Mission Control server — serves static files + PATCH API for task control.
Zero dependencies beyond Python 3 stdlib.

Usage:
    python3 server.py
    python3 server.py 9090   # custom port
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
ROOT = os.path.dirname(os.path.abspath(__file__))

ALLOWED_FIELDS = {"status", "lastResult", "lastRun", "nextRun", "lastOutput"}


class MissionControlHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_PATCH(self):
        if self.path.split("?")[0] != "/data/tasks.json":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            patch = json.loads(body)
        except json.JSONDecodeError as e:
            self._json_response(400, {"error": f"Invalid JSON: {e}"})
            return

        task_id = patch.get("id")
        if not task_id:
            self._json_response(400, {"error": "Missing task id"})
            return

        tasks_path = os.path.join(ROOT, "data", "tasks.json")
        try:
            with open(tasks_path, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._json_response(500, {"error": f"Failed to read tasks.json: {e}"})
            return

        task = next((t for t in data.get("tasks", []) if t.get("id") == task_id), None)
        if not task:
            self._json_response(404, {"error": f"Task '{task_id}' not found"})
            return

        # Apply allowed fields
        for key in ALLOWED_FIELDS:
            if key in patch:
                task[key] = patch[key]

        data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

        with open(tasks_path, "w") as f:
            json.dump(data, f, indent=2)

        # Append to activity log (best-effort)
        try:
            act_path = os.path.join(ROOT, "data", "activity.json")
            with open(act_path, "r") as f:
                activity = json.load(f)

            action = "started" if patch.get("status") == "running" else "stopped"
            activity["events"].insert(0, {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "manual",
                "source": task_id,
                "message": f"{task.get('name', task_id)} manually {action} from Mission Control",
                "status": "info" if action == "started" else "success",
            })
            activity["events"] = activity["events"][:50]
            activity["lastUpdated"] = datetime.now(timezone.utc).isoformat()

            with open(act_path, "w") as f:
                json.dump(activity, f, indent=2)
        except Exception:
            pass

        self._json_response(200, {"ok": True, "task": task})

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
        # Add CORS to all responses
        if "Access-Control-Allow-Origin" not in str(self._headers_buffer):
            self._cors_headers()
        super().end_headers()


if __name__ == "__main__":
    server = HTTPServer(("", PORT), MissionControlHandler)
    print(f"\n  ⚙ Mission Control server running")
    print(f"  → http://localhost:{PORT}/mission-control.html\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
        server.shutdown()
