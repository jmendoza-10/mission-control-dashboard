const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8080;
const ROOT = __dirname;

const MIME = {
  '.html': 'text/html',
  '.css':  'text/css',
  '.js':   'application/javascript',
  '.json': 'application/json',
  '.png':  'image/png',
  '.svg':  'image/svg+xml',
};

const server = http.createServer((req, res) => {
  // CORS headers for local dev
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    return res.end();
  }

  // ── PATCH /data/tasks.json — update a single task's fields ──
  if (req.method === 'PATCH' && req.url === '/data/tasks.json') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const patch = JSON.parse(body);
        if (!patch.id) throw new Error('Missing task id');

        const filePath = path.join(ROOT, 'data', 'tasks.json');
        const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));

        const task = data.tasks.find(t => t.id === patch.id);
        if (!task) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ error: 'Task not found' }));
        }

        // Apply allowed fields
        const ALLOWED = ['status', 'lastResult', 'lastRun', 'nextRun', 'lastOutput'];
        ALLOWED.forEach(key => {
          if (patch[key] !== undefined) task[key] = patch[key];
        });
        data.lastUpdated = new Date().toISOString();

        fs.writeFileSync(filePath, JSON.stringify(data, null, 2));

        // Also append to activity log
        const actPath = path.join(ROOT, 'data', 'activity.json');
        try {
          const activity = JSON.parse(fs.readFileSync(actPath, 'utf8'));
          const action = patch.status === 'running' ? 'started' : 'stopped';
          activity.events.unshift({
            timestamp: new Date().toISOString(),
            type: 'manual',
            source: patch.id,
            message: `${task.name} manually ${action} from Mission Control`,
            status: patch.status === 'running' ? 'info' : 'success',
          });
          // Keep last 50 events
          activity.events = activity.events.slice(0, 50);
          activity.lastUpdated = new Date().toISOString();
          fs.writeFileSync(actPath, JSON.stringify(activity, null, 2));
        } catch (e) { /* activity log write is best-effort */ }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, task }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── PATCH /data/agents.json — update a single agent's fields ──
  if (req.method === 'PATCH' && req.url === '/data/agents.json') {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try {
        const patch = JSON.parse(body);
        if (!patch.id) throw new Error('Missing agent id');

        const filePath = path.join(ROOT, 'data', 'agents.json');
        const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));

        const agent = data.agents.find(a => a.id === patch.id);
        if (!agent) {
          res.writeHead(404, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ error: 'Agent not found' }));
        }

        const ALLOWED = ['status', 'currentTask', 'metrics', 'recentActions'];
        ALLOWED.forEach(key => {
          if (patch[key] !== undefined) agent[key] = patch[key];
        });
        data.lastUpdated = new Date().toISOString();

        fs.writeFileSync(filePath, JSON.stringify(data, null, 2));

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ ok: true, agent }));
      } catch (e) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
    return;
  }

  // ── Static file serving ──
  let filePath = path.join(ROOT, req.url.split('?')[0]);
  if (filePath.endsWith('/')) filePath = path.join(filePath, 'index.html');
  if (filePath === path.join(ROOT, '/')) filePath = path.join(ROOT, 'mission-control.html');

  const ext = path.extname(filePath);
  const contentType = MIME[ext] || 'application/octet-stream';

  fs.readFile(filePath, (err, data) => {
    if (err) {
      if (err.code === 'ENOENT') {
        // Try serving mission-control.html for root
        if (req.url === '/') {
          fs.readFile(path.join(ROOT, 'mission-control.html'), (e2, d2) => {
            if (e2) { res.writeHead(404); return res.end('Not found'); }
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(d2);
          });
          return;
        }
        res.writeHead(404);
        return res.end('Not found');
      }
      res.writeHead(500);
      return res.end('Server error');
    }
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(data);
  });
});

server.listen(PORT, () => {
  console.log(`\n  ⚙ Mission Control server running`);
  console.log(`  → http://localhost:${PORT}/mission-control.html\n`);
});
