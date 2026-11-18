# Redline Sec — 24/7 Monitor (GitHub-hosted)

Runs checks **even when your PC is off**: GitHub Actions runs `monitor.py` every
5 minutes, pushes alerts to Discord `#incident-reports`, and the dashboard is
served free from GitHub Pages (or Vercel — it's static).

## Setup (one-time, ~5 minutes)

### 1. Create the repo
1. github.com → **New repository** → name it `redline-monitor` (private works too*)
2. Upload **everything in this folder** as the repo root (`monitor.py`,
   `targets.json`, `state.json`, `docs/`, `.github/`)
3. Edit `targets.json` and put your real client/sim sites in it (name + URL)

*Private repos work, but free Actions minutes are limited (2,000/month).
Public repos = unlimited.  5-min cron ≈ 8,600 runs/month → **use a public repo**.

### 2. Add the Discord webhook as a secret
Repo → **Settings → Secrets and variables → Actions → New repository secret**
- Name: `DISCORD_ALERT_WEBHOOK`
- Value: the webhook URL from your local `.env`
  (`DISCORD_ALERT_WEBHOOK=https://discord.com/api/webhooks/...`)

### 3. Enable the dashboard
Repo → **Settings → Pages** → Source: *Deploy from a branch*
→ Branch: `main`, folder: **`/docs`** → Save

Your dashboard: `https://<your-username>.github.io/redline-monitor/`
(It updates every 5 minutes as the workflow commits new state/events.)

### 4. Test it
Repo → **Actions** → *Redline Monitor* → **Run workflow**.
Watch the log; a heartbeat event appears on the dashboard, and any
change/outage fires a Discord embed.

## Deploy the same dashboard on Vercel instead (optional)
`docs/index.html` is pure static. On vercel.com: **Add New → Project** → import
the repo → Framework preset **Other** → Output Directory: `docs` → Deploy.
Vercel serves the UI; GitHub Actions keeps the data fresh. Same result.

## Notes
- GitHub cron may drift a few minutes under load — treat it as "≤10 min" alerts.
- `state.json` (hashes/statuses) and `docs/events.json` grow in git history;
  that is what gives the monitor memory between runs.
- Real-time seconds-level entries still come from the agent on authorized
  servers (local dashboard). This GitHub monitor is the 24/7 external watchdog.
