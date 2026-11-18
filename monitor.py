"""
Redline Sec — GitHub Actions Monitor (one check per run)

Designed to run every 5 minutes via GitHub Actions cron — your SOC checks
keep running 24/7 even with your PC off. On change/outage/defacement it
pushes an embed to Discord #incident-reports via DISCORD_ALERT_WEBHOOK.

State (targets.json → state.json/events.json) is committed back to the repo,
so memory survives between runs and the GitHub Pages dashboard auto-updates.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(BASE, "targets.json")
STATE_FILE = os.path.join(BASE, "docs", "state.json")
EVENTS_FILE = os.path.join(BASE, "docs", "events.json")
WEBHOOK = os.environ.get("DISCORD_ALERT_WEBHOOK", "").strip()

UA = "Mozilla/5.0 (compatible; RedlineSecMonitor/1.0)"
DEFACE_RE = re.compile(r"(?i)(hacked|defaced|owned\s*by|pwned|#op\w+)")
MAX_EVENTS = 100

RED = 0xE74C3C
ORANGE = 0xE67E22


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, r.read(), None
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"", None
    except Exception as e:
        return 0, b"", f"{type(e).__name__}"


def check(target, state_entry):
    url = target["url"]
    name = target["name"]
    status, body, err = fetch(url)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {"name": name, "url": url, "ts": now}
    events = []

    if err:
        prev = state_entry.get("last_status")
        entry.update(last_status=0, latency=None, title=None, last_hash=state_entry.get("last_hash"))
        if prev not in (None, 0):
            events.append(("outage", "critical",
                           f"{name} UNREACHABLE ({err}) — {url}"))
        return entry, events

    latency = None  # urllib gives no easy timing without patching; skip
    h = hashlib.sha256(body).hexdigest()[:16]
    m = re.search(rb"<title[^>]*>(.*?)</title>", body[:20000], re.S | re.I)
    title = m.group(1).decode("utf-8", "replace").strip()[:100] if m else ""
    entry.update(last_status=status, latency=latency, title=title, last_hash=h)

    prev_status = state_entry.get("last_status")
    if prev_status is None:
        events.append(("monitor-online", "info", f"{name} first check — HTTP {status}"))
    else:
        if prev_status < 500 <= status or (prev_status not in (0,) and status == 0):
            events.append(("outage", "critical", f"{name} DOWN — HTTP {status} ({url})"))
        elif prev_status >= 500 and 200 <= status < 400:
            events.append(("recovered", "info", f"{name} back online — HTTP {status}"))

    prev_hash = state_entry.get("last_hash")
    if prev_hash and h != prev_hash:
        low = body.decode("utf-8", "replace").lower()
        if DEFACE_RE.search(low):
            events.append(("defacement-suspect", "critical",
                           f"POSSIBLE DEFACEMENT — {name}: content changed with "
                           f"defacement keywords. Title: {title or 'n/a'}"))
        else:
            events.append(("content-changed", "warn",
                           f"{name}: content changed ({prev_hash[:8]}→{h[:8]}). "
                           f"Title: {title or 'n/a'} — legit deploy or tampering?"))
    return entry, events


def discord_alert(kind, severity, detail):
    if not WEBHOOK:
        print("[warn] DISCORD_ALERT_WEBHOOK secret not set — alert skipped")
        return
    embed = {"title": f"{'🚨' if severity == 'critical' else '⚠️'} {kind}",
             "description": detail[:2000], "color": RED if severity == "critical" else ORANGE,
             "footer": {"text": "Redline Sec — GitHub Actions Monitor"},
             "timestamp": datetime.now(timezone.utc).isoformat()}
    payload = json.dumps({"username": "Redline Alerts", "embeds": [embed]}).encode()
    req = urllib.request.Request(WEBHOOK, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
        print(f"[alert] sent to Discord: {kind}")
    except Exception as e:
        print(f"[alert] failed: {type(e).__name__}")


def main():
    targets = load(TARGETS_FILE, [])
    if not targets:
        print("[fatal] targets.json is empty — add targets first")
        return
    state = load(STATE_FILE, {})
    events_log = load(EVENTS_FILE, [])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    new_state, all_events = {}, []
    for t in targets:
        prev = state.get(t["name"], {})
        entry, events = check(t, prev)
        new_state[t["name"]] = entry
        for kind, sev, detail in events:
            all_events.append({"ts": now, "target": t["name"], "kind": kind,
                               "severity": sev, "detail": detail})

    for ev in all_events:
        print(f"[event] {ev['severity'].upper():8} {ev['kind']}: {ev['detail'][:110]}")
        if ev["severity"] in ("warn", "critical"):
            discord_alert(ev["kind"], ev["severity"], ev["detail"])

    if all_events:
        events_log = (all_events + events_log)[:MAX_EVENTS]
    else:
        heartbeat = {"ts": now, "target": "system", "kind": "heartbeat",
                     "severity": "info",
                     "detail": f"Scheduled check OK — {len(targets)} target(s) all quiet"}
        events_log = [heartbeat] + events_log[:MAX_EVENTS - 1]

    save(STATE_FILE, new_state)
    save(EVENTS_FILE, events_log)
    print(f"[done] checked {len(targets)} target(s), {len(all_events)} new event(s)")


if __name__ == "__main__":
    main()
