# Mission Control Dashboard

8-bit retro × Factorio-style monitoring UI for autonomous AI agent systems.

## Overview

A single-file HTML dashboard that visualizes scheduled task activity, service health, and production metrics using NES.css styling, CRT effects, and a Factorio-inspired factory floor layout. Includes an optional Node.js server for interactive task control.

## Quick Start

### Read-only mode (static file server)

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080/mission-control.html`

### Interactive mode (with task control)

```bash
node server.js
```

Open `http://localhost:8080/mission-control.html`

This enables the Run/Stop toggle in machine popups, which writes back to `tasks.json` and logs actions to `activity.json`.

## Project Structure

```
mission-control-dashboard/
├── mission-control.html   # Single-file dashboard (HTML + CSS + JS)
├── server.js              # Optional Node.js server with PATCH API
├── data/
│   ├── tasks.json         # Scheduled task status and metrics
│   ├── activity.json      # Rolling event feed
│   ├── services.json      # Connected service health
│   └── metrics.json       # Throughput stats and token usage
└── README.md
```

## API

When using `server.js`, a single endpoint is available:

**`PATCH /data/tasks.json`** — Update a task's status

```json
{
  "id": "morning-briefing",
  "status": "running"
}
```

Allowed fields: `status`, `lastResult`, `lastRun`, `nextRun`. Also appends a log entry to `activity.json`.

## Data Files

The dashboard reads from JSON files in `data/` via `fetch()` with 30-second polling. These files are designed to be updated by external processes (scheduled tasks, cron jobs, etc.) or by the dashboard itself via the server API.

### tasks.json
Tracks each scheduled task: status, schedule, last/next run, success rate, input/output connections.

### activity.json
Rolling feed of recent events (last 50) with timestamps, sources, and status indicators.

### services.json
Connected service health: status, last checked, throughput counters.

### metrics.json
Aggregate stats: daily/weekly counters, token usage history (7-day sparkline), cost tracking.

## Features

- **Canvas factory floor** — Pixel art machines with animated gears, conveyor belts with flowing items, service nodes with connector lines
- **Interactive task control** — Click a machine, hit Run/Stop to toggle status (requires server.js)
- **3 themes** — CRT green, amber, and full color (press `T` to cycle)
- **8-bit sound effects** — Boot chime, click beeps, success/error jingles (Web Audio API)
- **Day/night cycle** — Background shifts based on time of day
- **Alt-mode** — Press `A` to overlay success rate and run count on machines
- **Idle worker** — Pixel character wanders the floor when no tasks are running
- **Service panel** — Real-time health indicators with throughput counters
- **Production stats** — Bar charts, 7-day token sparkline, cost tracker
- **Alert ticker** — Scrolling event feed with color-coded status
- **CRT effects** — Scanlines and subtle flicker
- **Keyboard shortcuts** — `T` theme, `M` mute, `A` alt-mode, `Esc` close

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `T` | Cycle theme (green → amber → color) |
| `M` | Toggle sound on/off |
| `A` | Toggle alt-mode (detailed metrics overlay) |
| `Esc` | Close popup |

## Tech Stack

- [NES.css](https://nostalgic-css.github.io/NES.css/) v2.3.0 — 8-bit CSS framework
- [Press Start 2P](https://fonts.google.com/specimen/Press+Start+2P) — Pixel font
- Canvas API — Factory floor rendering with pixel art sprites
- Web Audio API — Synthesized 8-bit sound effects
- Node.js (optional) — Zero-dependency server for task control API
