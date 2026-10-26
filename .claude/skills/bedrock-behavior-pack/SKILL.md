---
name: bedrock-behavior-pack
description: Build, test and install Minecraft Bedrock behavior packs with the Script API (@minecraft/server) for the family server in this repo (mcfs / mcportal), and wire their output into the web portal. Use this whenever the user wants a new in-game feature, statistic, counter, event log, game rule or "something the server should notice" (blocks, deaths, kills, playtime, chat, items, achievements …) on the Bedrock server - even if they never say "behavior pack" or "script" - and whenever an existing pack (e.g. minecraft-pack/mcportal_stats) has to be changed, debugged, moved to a new world or adapted after a Bedrock update.
---

# Bedrock behavior packs for the family server

Bedrock writes almost nothing about gameplay to its log (only joins/leaves). Anything the
portal should know about the game therefore comes from a small **behavior pack with a
script** that runs inside the world and reports via the server log. The block statistic
(`mcportal/minecraft-pack/mcportal_stats`, change M5, `docs/03-block-statistik.md`) is the
reference implementation - read it before building something new; copy its patterns.

The server is in use by a family. Every change to the world follows
Inspect → Backup → Change → Validate → Restart → Verify, and is explained to the user first
(what, why, which files, backup, how to undo).

## Workflow

### 1. Check what the server supports

Script API versions differ per Bedrock release. Ask the server instead of guessing:
run `scripts/test-server.sh` with API version `99.0.0` - the server refuses and prints
`Available versions:`. Use the **newest stable** one (no `-beta`/`-alpha`).
Beta APIs need the "Beta APIs" experiment, and experiments can never be switched off
in a world again, so they are not an option for the family world.

### 2. Scaffold the pack

```bash
python .claude/skills/bedrock-behavior-pack/scripts/new_pack.py mcportal/minecraft-pack/<pack_dir> "<Name>" "<Beschreibung>"
```

It creates `manifest.json` (fresh UUIDs, `@SERVER_API@` placeholder for the version,
filled in at install time) and `scripts/main.js` with the output skeleton.

### 3. Write the script - reporting conventions

- **Output channel:** `console.warn("[mcportal-<feature>] " + JSON.stringify({v: 1, ...}))`.
  It shows up in the journal as `[WARN] [Scripting] [mcportal-<feature>] {...}`.
  Why warn: script output reaches the log only with `content-log-console-output-enabled=true`,
  and the server runs with `content-log-level=warning` to keep content noise out -
  `console.log` (info) is filtered away. M5 already set both; a new pack needs no extra
  server.properties change.
- **Batch:** aggregate in memory and flush every ~20 s (`system.runInterval`), one line per
  flush, only when there is something to report. One log line per event floods the journal.
- **Startup line:** `{"v":1,"started":true}` once via `system.run` - the install script and
  the portal use it as "pack is alive".
- **Version the payload** (`"v": 1`) so the portal can ignore formats it doesn't know.
- Identify players by `player.name` (gamertag). XUIDs are not available in scripts.
- Only stable API events/props; check the event exists in the chosen version before using it
  (the test server reports subscribe errors).

### 4. Test on a throwaway server - never on the family world

```bash
scp -r mcportal/minecraft-pack/<pack_dir> fred@192.168.178.38:~/pack-under-test
ssh fred@192.168.178.38 'bash -s -- ~/pack-under-test <api-version> 30' < .claude/skills/bedrock-behavior-pack/scripts/test-server.sh
```

The script copies the installed server program (not the world) to `~/bds-test`, uses a fresh
world, other ports, no LAN visibility, and the same content-log settings as production.
Check RAM first (`free -m`; the real server uses ~0.9 GB, the laptop has 3.7 GB).
What you can verify there: pack loads, no `[Scripting]` errors, subscriptions work, startup
line appears in the expected format. What you cannot: real player events - nobody can join
(the test server must use raknet; clients only join via nethernet). That part is verified
after installation by the user playing. Delete `~/bds-test` afterwards (≈ 600 MB).

### 5. Install into the world (M5 pattern)

Copy and adapt `mcportal/deploy/m5-stats-pack.sh`. It runs as `fred` (owner of the world),
needs no sudo, and:
1. refuses while players are online (`/api/status`),
2. backs up `world_behavior_packs.json` (and anything else it touches) to `~/mcportal-backups/<time>_pre_<change>/`,
3. copies the pack to `worlds/<level>/behavior_packs/<pack_dir>`, fills in the API version,
   appends `{pack_id, version}` to `world_behavior_packs.json` (edited in place, other entries kept),
4. restarts through the portal (`POST /api/server/restart` - clean stop via console),
5. waits for `Server started.` **and** the pack's startup line, otherwise rolls back automatically.
Give each new change a number (M6, M7, …) and document it like `docs/03-block-statistik.md`.

### 6. Wire it into the portal

Follow the stats implementation:
- `app/adapters/bedrock/logparse.py`: a `parse_<feature>(line)` for the tag (exact prefix
  `"[Scripting] [mcportal-<feature>] "` after the Bedrock log prefix).
- `app/services/<feature>.py`: register in `mc.line_listeners`; persist to
  `/var/lib/mcportal/<feature>.json`; dedupe with a cursor (timestamp + hashes of lines at
  that timestamp) and catch up from the journal on startup - otherwise a portal restart
  counts lines twice or loses them. Add a small entry to `mc.extras` so the SSE snapshot
  signals "new data" and the UI can reload.
- `app/main.py`: GET endpoint; `app/web/`: tab/card; reuse existing CSS patterns.
- Tests in `tests/` with real-format lines (see `tests/test_stats.py`), including
  "no double counting across a restart".
- Simulate the pack in `app/adapters/fake.py` so the UI can be developed locally.
Deploying portal code needs `sudo bash ~/mcportal-src/deploy/install.sh` - the user runs it.

## Pitfalls we already hit

- `content-log-console-output-enabled=false` swallows all script output silently.
- With `content-log-level=warning`, the server additionally logs ~6 harmless vanilla
  content ERRORs per start (BiomeRegistry, Structure, FeatureRegistry) - not caused by packs.
- Files edited on Windows with Python text mode get CRLF → bash/JSON on the server break.
  Write with Edit/Write tools or binary mode; the repo enforces LF via `.gitattributes`.
- The repo is public: never commit real gamertags or XUIDs (tests/docs use Steve/Alex/Sunny
  and `25354000000000xx`); `analyse/report.txt` stays local.
- After a Bedrock update, check the startup line still appears. If the pinned API version
  disappeared, the log shows a `[Scripting]` error, the feature pauses, the game runs on -
  bump the version in the installed manifest and restart.
