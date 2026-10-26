#!/usr/bin/env bash
# Minecraft Family Portal - set up the real Bedrock server from the repo (docs/04-reproduzierbarer-aufbau.md).
#
#   sudo bash provision/setup.sh --prepare [--conf FILE]
#
# --prepare (R2) runs alongside the test server, without downtime:
#   1. checks (root, tools, disk space, probe ports free, Laravel answer as reference)
#   2. system user MC_USER and MC_DIR (750, owned by MC_USER; nothing 777, nothing root)
#   3. newest official server from minecraft.net (same checks as the portal's update button)
#   4. server.properties = Mojang's file + provision/server.properties.overrides
#   5. all packs from packs.list into worlds/<WORLD_NAME>/ BEFORE the first start (no world is generated here)
#   6. probe start in a throwaway copy (other ports, no LAN) as MC_USER: every pack must report, no script errors;
#      then stop and delete the copy - the real world is only created on the cut-over day (undecided seed)
# Does NOT install or switch the systemd unit, does NOT touch the running test server, the portal or Laravel.
# Idempotent: a second run keeps the server program and an existing world, re-applies the overrides and probes again.
#
# Settings: --conf FILE, else /etc/mcportal/server.conf, else provision/server.conf.example (placeholder names).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PACKS_SRC="$REPO/minecraft-pack"
# stable @minecraft/server version, same as deploy/world-pack.sh
SERVER_API=2.10.0
PROBE_V4=19160
PROBE_V6=19161
PROBE_TIMEOUT=240
MIN_FREE_MB=2048

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '    \033[1;33mWARNUNG: %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mFEHLER: %s\033[0m\n' "$*" >&2; exit 1; }

MODE="" CONF=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepare) MODE=prepare ;;
    --conf) CONF="${2:-}"; shift ;;
    *) echo "Aufruf: sudo bash $0 --prepare [--conf DATEI]"; exit 2 ;;
  esac
  shift
done
[[ "$MODE" == prepare ]] || fail "Nur --prepare ist gebaut (Umstellung am Stichtag folgt in R6)"
[[ "$(id -u)" == 0 ]] || fail "Bitte mit sudo ausführen"

if [[ -z "$CONF" ]]; then
  CONF=/etc/mcportal/server.conf
  [[ -f "$CONF" ]] || CONF="$HERE/server.conf.example"
fi
[[ -f "$CONF" ]] || fail "Einstellungen nicht gefunden: $CONF"

# checked KEY=value lines -> variables (properties.py refuses anything unexpected)
CONF_LINES="$(python3 "$HERE/properties.py" conf "$CONF")" || fail "Einstellungen ungültig: $CONF"
while IFS='=' read -r key value; do
  case "$key" in
    WORLD_NAME|MC_USER|MC_DIR|PORT_V4|PORT_V6) printf -v "$key" '%s' "$value" ;;
  esac
done <<<"$CONF_LINES"
MC_HOME="$(dirname "$MC_DIR")"
PROBE_DIR="$MC_HOME/probe"
WORLD="$MC_DIR/worlds/$WORLD_NAME"

# ---------------------------------------------------------------------------
step "1/6 Prüfungen"
info "Einstellungen: $CONF"
[[ "$CONF" == "$HERE/server.conf.example" ]] && warn "Beispiel-Einstellungen (Servername/Weltname noch offen) – reicht für den Probelauf"
for tool in python3 curl tar runuser ss; do command -v "$tool" >/dev/null || fail "$tool fehlt"; done
grep -qv '^\s*\(#\|$\)' "$HERE/packs.list" || fail "packs.list ist leer"
mkdir -p "$MC_HOME"   # needed for the free-space check; owner fixed below
FREE_MB="$(df -Pm "$MC_HOME" | awk 'NR==2 {print $4}')"
(( FREE_MB >= MIN_FREE_MB )) || fail "Nur $FREE_MB MB frei unter $MC_HOME (mindestens $MIN_FREE_MB MB)"
info "Speicher: $FREE_MB MB frei unter $MC_HOME"
for port in "$PROBE_V4" "$PROBE_V6"; do
  ! ss -Hlun "sport = :$port" | grep -q . || fail "Probe-Port $port/udp ist belegt"
done
for port in "$PORT_V4" "$PORT_V6"; do
  ss -Hlun "sport = :$port" | grep -q . && info "Port $port/udp belegt (laufender Testserver – für --prepare in Ordnung)"
done
LARAVEL_BEFORE="$(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1/ || true)"
info "Laravel: HTTP $LARAVEL_BEFORE auf Port 80 (Vergleichswert)"

# ---------------------------------------------------------------------------
step "2/6 Benutzer und Ordner"
if id -u "$MC_USER" >/dev/null 2>&1; then
  info "Benutzer $MC_USER gibt es schon"
else
  useradd --system --home-dir "$MC_HOME" --no-create-home --shell /usr/sbin/nologin --user-group "$MC_USER"
  info "Systembenutzer $MC_USER angelegt (keine Anmeldung)"
fi
chown "$MC_USER:$MC_USER" "$MC_HOME"
chmod 750 "$MC_HOME"
as_mc() { runuser -u "$MC_USER" -- "$@"; }

# ---------------------------------------------------------------------------
step "3/6 Serverprogramm"
if [[ -x "$MC_DIR/bedrock_server" ]]; then
  info "schon vorhanden in $MC_DIR – bleibt (Updates später über den Knopf im Portal)"
else
  STAGE="$MC_HOME/.staging"
  rm -rf "$STAGE"
  mkdir "$STAGE"
  # as root: MC_USER cannot read the repo in the admin's home; owner is fixed right after
  VERSION="$(python3 -I "$HERE/fetch_server.py" "$STAGE/server")" || fail "Download fehlgeschlagen"
  mv "$STAGE/server" "$MC_DIR"
  rm -rf "$STAGE"
  printf '%s\n' "$VERSION" > "$MC_DIR/.provisioned-version"
  info "Bedrock $VERSION nach $MC_DIR"
fi
chown -R "$MC_USER:$MC_USER" "$MC_DIR"
chmod 750 "$MC_DIR"

# ---------------------------------------------------------------------------
step "4/6 server.properties"
python3 -I "$HERE/properties.py" merge "$MC_DIR/server.properties" "$HERE/server.properties.overrides" "$CONF" \
  || fail "server.properties konnte nicht angepasst werden"
while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" == \#* ]] && continue
  info "$(grep -m1 "^$key=" "$MC_DIR/server.properties")"
done < <(python3 "$HERE/properties.py" render "$HERE/server.properties.overrides" "$CONF")

# ---------------------------------------------------------------------------
step "5/6 Packs in die Welt"
manifest() { python3 -I -c 'import json,sys; h=json.load(open(sys.argv[1]))["header"]; print(h[sys.argv[2]] if sys.argv[2] != "version" else ".".join(map(str, h["version"])))' "$1" "$2"; }
EXPECT=()   # log lines the probe start must show
if [[ -d "$WORLD/db" ]]; then
  info "Welt $WORLD_NAME gibt es schon – Packs bleiben unverändert (Änderungen: deploy/world-pack.sh)"
else
  as_mc mkdir -p "$WORLD/behavior_packs" "$WORLD/resource_packs"
  BP_LIST="[]" RP_LIST="[]"
  while read -r kind pack; do
    [[ -z "$kind" || "$kind" == \#* ]] && continue
    [[ "$kind" =~ ^(behavior|resource)$ && "$pack" =~ ^[a-z0-9_]+$ && -f "$PACKS_SRC/$pack/manifest.json" ]] \
      || fail "packs.list: ungültige Zeile '$kind $pack'"
    DST="$WORLD/${kind}_packs/$pack"
    rm -rf "$DST"
    as_mc mkdir "$DST"
    (cd "$PACKS_SRC/$pack" && tar --exclude=./tests --exclude=./tools -cf - .) | as_mc tar --no-same-owner -xf - -C "$DST"
    as_mc sed -i "s/@SERVER_API@/$SERVER_API/" "$DST/manifest.json"
    uuid="$(manifest "$DST/manifest.json" uuid)"; version="$(manifest "$DST/manifest.json" version)"
    entry="$(python3 -I -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]) + [{"pack_id": sys.argv[2], "version": [int(x) for x in sys.argv[3].split(".")]}]))' \
      "$([[ $kind == behavior ]] && echo "$BP_LIST" || echo "$RP_LIST")" "$uuid" "$version")"
    if [[ $kind == behavior ]]; then BP_LIST="$entry"; else RP_LIST="$entry"; fi
    info "$kind  $pack $version"
    if [[ $kind == behavior ]]; then
      EXPECT+=("$(manifest "$DST/manifest.json" name).*version: $version")
      if [[ -f "$DST/scripts/main.js" ]]; then
        tag="$(grep -om1 '\[mcportal-[a-z]*\]' "$DST/scripts/main.js" || true)"
        [[ -n "$tag" ]] && EXPECT+=("\\$tag {\"v\":[0-9]*,\"started\":true}")
      fi
    fi
  done < "$HERE/packs.list"
  python3 -I -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]), indent=2))' "$BP_LIST" | as_mc tee "$WORLD/world_behavior_packs.json" >/dev/null
  python3 -I -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]), indent=2))' "$RP_LIST" | as_mc tee "$WORLD/world_resource_packs.json" >/dev/null
  info "world_behavior_packs.json, world_resource_packs.json geschrieben"
fi
chown -R "$MC_USER:$MC_USER" "$MC_DIR"   # server.properties was merged as root

# ---------------------------------------------------------------------------
step "6/6 Probestart (Kopie, Ports $PROBE_V4/$PROBE_V6)"
if [[ ${#EXPECT[@]} == 0 ]]; then
  info "übersprungen – die Welt gibt es schon, sie wird nicht für einen Probelauf kopiert"
else
  rm -rf "$PROBE_DIR"
  cp -a "$MC_DIR" "$PROBE_DIR"
  python3 -I - "$PROBE_DIR/server.properties" "$PROBE_V4" "$PROBE_V6" <<'PY'
import sys
path, v4, v6 = sys.argv[1:4]
want = {"server-port": v4, "server-portv6": v6, "enable-lan-visibility": "false", "server-name": "mcportal probe"}
lines = [f"{l.split('=', 1)[0]}={want[l.split('=', 1)[0]]}" if l.split("=", 1)[0] in want else l
         for l in open(path, encoding="utf-8").read().splitlines()]
open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
PY
  chown -R "$MC_USER:$MC_USER" "$PROBE_DIR"
  LOG="$PROBE_DIR/probe.log"
  FIFO="$PROBE_DIR/console"
  as_mc mkfifo "$FIFO"
  as_mc touch "$LOG"
  # the console fifo stays open on fd 3 so the server keeps reading until "stop"
  exec 3<>"$FIFO"
  (cd "$PROBE_DIR" && LD_LIBRARY_PATH=. timeout "$((PROBE_TIMEOUT + 60))" runuser -u "$MC_USER" -- ./bedrock_server <"$FIFO" >>"$LOG" 2>&1) &
  PID=$!
  ok=0
  for _ in $(seq 1 "$PROBE_TIMEOUT"); do
    sleep 1
    kill -0 "$PID" 2>/dev/null || break
    all=1
    for pat in 'Server started\.' "${EXPECT[@]}"; do grep -aq -- "$pat" "$LOG" || all=0; done
    [[ $all == 1 ]] && { ok=1; break; }
  done
  sleep 3   # late script errors
  echo stop >&3
  for _ in $(seq 1 30); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
  kill -0 "$PID" 2>/dev/null && { warn "Probe-Server reagiert nicht auf stop – wird beendet"; kill "$PID" || true; }
  wait "$PID" 2>/dev/null || true
  exec 3>&-

  grep -aE 'Version:|Pack Stack|mcportal-[a-z]*\] \{"v":[0-9]*,"started"|Server started' "$LOG" | sed 's/^/    /' | head -20
  ERRORS="$(grep -aE '\[Scripting\]|ERROR|\[Json|\[Item|\[Texture|\[Recipes\]' "$LOG" | grep -v 'mcportal-[a-z]*\]' || true)"
  if [[ -n "$ERRORS" ]]; then
    printf '%s\n' "$ERRORS" | sed 's/^/    /' | head -30
    ok=0
  fi
  if [[ $ok == 1 ]]; then
    rm -rf "$PROBE_DIR"
    info "alle ${#EXPECT[@]} Meldungen da, keine Fehler – Probe-Kopie gelöscht"
  else
    for pat in 'Server started\.' "${EXPECT[@]}"; do grep -aq -- "$pat" "$LOG" || info "fehlt: $pat"; done
    fail "Probestart nicht sauber – Log bleibt zur Ansicht: $LOG (Kopie löschen: sudo rm -rf $PROBE_DIR)"
  fi
fi

# ---------------------------------------------------------------------------
LARAVEL_AFTER="$(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1/ || true)"
info "Laravel: HTTP $LARAVEL_AFTER (vorher $LARAVEL_BEFORE)"
[[ "$LARAVEL_AFTER" == "$LARAVEL_BEFORE" ]] || warn "Laravel-Antwort hat sich geändert!"
BAD="$(find "$MC_HOME" \( -perm -o+w -o ! -user "$MC_USER" \) -print -quit)"
[[ -z "$BAD" ]] || fail "Rechte nicht sauber: $BAD"
info "Rechte: alles unter $MC_HOME gehört $MC_USER, nichts für alle schreibbar"
printf '\n\033[1;32mVorbereitet.\033[0m %s ist bereit, die Welt entsteht erst am Stichtag. Der Testserver läuft unverändert.\n' "$MC_DIR"
