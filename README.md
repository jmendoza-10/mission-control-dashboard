# Mission Control Dashboard

8-bit retro × Factorio-style monitoring UI for autonomous AI agent systems.

## Overview

A single-file HTML dashboard that visualizes scheduled task activity, service health, and production metrics using NES.css styling, CRT effects, and a Factorio-inspired factory floor layout.

## Quick Start

1. Serve locally (required for `fetch()` to load JSON data):
   ```bash
   npx live-server --port=8080
   ```
   Or use Python:
   ```bash
   python3 -m http.server 8080
   ```

2. Open `http://localhost:8080/mission-control.html`

## Project Structure

```
mission-control-dashboard/
├── mission-control.html   # Single-file dashboard (HTML + CSS + JS)
├── data/
│   ├── tasks.json         # Scheduled task status and metrics
│   ├── activity.json      # Rolling event feed
│   ├── services.json      # Connected service health
│   └── metrics.json       # Throughput stats and token usage
└── README.md
```

## Data Files

The dashboard reads from JSON files in `data/` via `fetch()` with 30-second polling. These files are designed to be updated by external processes (scheduled tasks, cron jobs, etc.).

### tasks.json
Tracks each scheduled task: status, schedule, last/next run, success rate, input/output connections.

### activity.json
Rolling feed of recent events with timestamps, sources, and status indicators.

### services.json
Connected service health: status, last checked, throughput counters.

### metrics.json
Aggregate stats: daily/weekly counters, token usage history (7-day sparkline), cost tracking.

## Features

- **Factory floor** — Visual layout of tasks as machines with animated conveyor belts
- **Service panel** — Real-time health indicators for connected services
- **Production stats** — Bar charts for tasks, emails, files, research hours
- **Token sparkline** — 7-day usage graph with cost tracker
- **Alert ticker** — Scrolling event feed at the bottom
- **CRT effects** — Scanlines and subtle flicker for retro atmosphere
- **Machine popups** — Click any machine for detailed task info
- **Auto-refresh** — Polls data every 30 seconds

## Tech Stack

- [NES.css](https://nostalgic-css.github.io/NES.css/) v2.3.0 — 8-bit CSS framework
- [Press Start 2P](https://fonts.google.com/specimen/Press+Start+2P) — Pixel font
- Vanilla JavaScript — No build tools, no dependencies
- CSS animations — Conveyor belts, CRT overlay, ticker scroll

## Roadmap

- [ ] Canvas-rendered factory floor with pixel art sprites
- [ ] Sound effects (Web Audio API)
- [ ] Keyboard shortcuts (alt-mode, minimap)
- [ ] Day/night background cycle
- [ ] Theme toggle (CRT green / amber / full color)
- [ ] Mobile responsive stacking
