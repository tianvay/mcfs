#!/usr/bin/env bash
# Minecraft Family Portal - change M5: block statistics pack in the world
#
#   bash deploy/m5-stats-pack.sh apply             install (restarts Minecraft once, ~10 s)
#   bash deploy/m5-stats-pack.sh rollback          undo apply exactly
#   bash deploy/m5-stats-pack.sh upgrade           M6: replace an installed pack by the repo version
#   bash deploy/m5-stats-pack.sh rollback-upgrade  undo the last upgrade (previous pack version back)
#   bash deploy/m5-stats-pack.sh status
#
# Runs as the Minecraft user (fred), no sudo. Changes:
#   worlds/<level>/behavior_packs/mcportal_stats/     (new folder)
#   worlds/<level>/world_behavior_packs.json          (one entry added)
#   server.properties: content-log-console-output-enabled=true, content-log-level=warning
#     (so the pack's lines reach the server log; only warnings, to keep the log small)
# Backups: ~/mcportal-backups/<time>_pre_m5/
set -euo pipefail

UNIT=minecraft-bedrock.service
PORTAL=http://127.0.0.1:8080
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK_SRC="$SRC/minecraft-pack/mcportal_stats"
PACK_UUID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["header"]["uuid"])' "$PACK_SRC/manifest.json")"
PACK_VERSION="$(python3 -c 'import json,sys; print(".".join(map(str, json.load(open(sys.argv[1]))["header"]["version"])))' "$PACK_SRC/manifest.json")"
# stable @minecraft/server version, verified on the test server for Bedrock 1.26.52.3
SERVER_API=2.10.0
BACKUPS="$HOME/mcportal-backups"

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
fail() { printf '\n\033[1;31mFEHLER: %s\033[0m\n' "$*" >&2; exit 1; }

MC_DIR="$(systemctl show -p WorkingDirectory --value "$UNIT")"
[[ -x "$MC_DIR/bedrock_server" ]] || fail "Minecraft-Verzeichnis nicht gefunden"
[[ "$(id -un)" == "$(systemctl show -p User --value "$UNIT")" ]] || fail "Bitte als $(systemctl show -p User --value "$UNIT") ausführen (ohne sudo)"
LEVEL="$(sed -n 's/^level-name=//p' "$MC_DIR/server.properties")"
WORLD="$MC_DIR/worlds/$LEVEL"
[[ -d "$WORLD/db" ]] || fail "Welt nicht gefunden: $WORLD"
PACK_DST="$WORLD/behavior_packs/mcportal_stats"
WBP="$WORLD/world_behavior_packs.json"
PROPS="$MC_DIR/server.properties"

players_online() {
  curl -s -m 5 "$PORTAL/api/status" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)["players"]))'
}

restart_and_wait() {  # all given patterns must appear in the log after the start
  local t0; t0="$(date +%s)"
  local code; code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$PORTAL/api/server/restart")"
  [[ "$code" == 202 ]] || fail "Portal hat den Neustart abgelehnt (HTTP $code – PIN gesetzt?)"
  for _ in $(seq 1 120); do
    sleep 1
    local logtext; logtext="$(journalctl -u "$UNIT" --since "@$t0" -o cat --no-pager -q)"
    local ok=1 pat
    for pat in 'Server started\.' "$@"; do grep -q "$pat" <<<"$logtext" || ok=0; done
    [[ $ok == 1 ]] && return 0
  done
  return 1
}

set_world_entry() {  # add or update our entry in world_behavior_packs.json (in place, others kept)
  python3 - "$WBP" "$PACK_UUID" "$PACK_VERSION" <<'PY'
import json, sys
path, uuid, version = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(".")]
packs = json.load(open(path)) if open(path).read().strip() else []
packs = [p for p in packs if p.get("pack_id") != uuid] + [{"pack_id": uuid, "version": version}]
with open(path, "r+") as f:   # in place: keep owner/permissions
    f.seek(0); json.dump(packs, f, indent=2); f.truncate()
PY
}

PACK_ALIVE=("Family Portal Statistik.*version: $PACK_VERSION" '\[mcportal-stats\] {"v":[0-9]*,"started":true}')

case "${1:-}" in
status)
  [[ -d "$PACK_DST" ]] && info "Pack-Ordner vorhanden: $PACK_DST" || info "Pack-Ordner fehlt"
  grep -q "$PACK_UUID" "$WBP" && info "In world_behavior_packs.json eingetragen" || info "Nicht eingetragen"
  [[ -f "$PACK_DST/manifest.json" ]] && info "Installierte Pack-Version: $(python3 -c 'import json,sys; print(".".join(map(str, json.load(open(sys.argv[1]))["header"]["version"])))' "$PACK_DST/manifest.json") (Repo: $PACK_VERSION)"
  grep -E '^content-log-(console-output-enabled|level)=' "$PROPS" | sed 's/^/    /'
  ;;

apply)
  step "1/5 Prüfungen"
  [[ ! -d "$PACK_DST" ]] || fail "Pack ist bereits installiert ($0 status)"
  n="$(players_online)" || fail "Portal nicht erreichbar"
  [[ "$n" == 0 ]] || fail "$n Spieler online – bitte warten, bis niemand spielt"
  info "Welt: $WORLD, niemand online"

  step "2/5 Sicherung"
  BK="$BACKUPS/$(date +%Y-%m-%d_%H-%M-%S)_pre_m5"
  mkdir -p "$BK"
  cp -a "$PROPS" "$WBP" "$BK/"
  ls -la "$WORLD/behavior_packs" > "$BK/behavior_packs-before.txt"
  info "$BK"

  step "3/5 Pack installieren"
  cp -r "$PACK_SRC" "$PACK_DST"
  sed -i "s/@SERVER_API@/$SERVER_API/" "$PACK_DST/manifest.json"
  set_world_entry
  info "world_behavior_packs.json: $(tr -d ' \n' < "$WBP")"

  step "4/5 server.properties: Script-Ausgabe ins Log (nur Warnungen)"
  sed -i -e 's/^content-log-console-output-enabled=.*/content-log-console-output-enabled=true/' \
         -e 's/^content-log-level=.*/content-log-level=warning/' "$PROPS"
  grep -E '^content-log-(console-output-enabled|level)=' "$PROPS" | sed 's/^/    /'
  diff <(grep -vE '^content-log-(console-output-enabled|level)=' "$BK/server.properties") \
       <(grep -vE '^content-log-(console-output-enabled|level)=' "$PROPS") >/dev/null \
    || fail "server.properties hat sich unerwartet weiter verändert – bitte rollback ausführen"

  step "5/5 Minecraft neu starten und prüfen"
  if restart_and_wait "${PACK_ALIVE[@]}"; then
    info "Server gestartet, Statistik-Pack meldet sich: aktiv"
    printf '\n\033[1;32mM5 erfolgreich.\033[0m Rückgängig: bash %s rollback\n' "$0"
  else
    journalctl -u "$UNIT" -n 30 -o cat --no-pager | grep -iE 'script|error|pack' | sed 's/^/    /' || true
    info "Pack meldet sich nicht – stelle vorherigen Zustand wieder her"
    "$0" rollback
    fail "M5 zurückgerollt"
  fi
  ;;

rollback)
  BK="$(find "$BACKUPS" -maxdepth 1 -type d -name '*_pre_m5' 2>/dev/null | sort | tail -n 1)"
  [[ -n "$BK" ]] || fail "keine M5-Sicherung gefunden"
  step "Rollback aus $BK"
  cat "$BK/server.properties" > "$PROPS"          # in place: keep owner/permissions/ACLs
  cat "$BK/world_behavior_packs.json" > "$WBP"
  if [[ -d "$PACK_DST" ]]; then
    mv "$PACK_DST" "$BK/mcportal_stats.removed"   # kept in the backup, not deleted
  fi
  info "server.properties und world_behavior_packs.json wiederhergestellt, Pack entfernt"
  restart_and_wait 'Server started' && info "Server läuft wieder" || fail "Server meldet nicht 'Server started.'"
  ;;

upgrade)
  step "1/4 Prüfungen"
  [[ -d "$PACK_DST" ]] || fail "Pack ist nicht installiert – zuerst: $0 apply"
  n="$(players_online)" || fail "Portal nicht erreichbar"
  [[ "$n" == 0 ]] || fail "$n Spieler online – bitte warten, bis niemand spielt"
  OLD_VERSION="$(python3 -c 'import json,sys; print(".".join(map(str, json.load(open(sys.argv[1]))["header"]["version"])))' "$PACK_DST/manifest.json")"
  info "installiert: $OLD_VERSION  ->  neu: $PACK_VERSION, niemand online"

  step "2/4 Sicherung"
  BK="$BACKUPS/$(date +%Y-%m-%d_%H-%M-%S)_pre_m6"
  mkdir -p "$BK"
  cp -a "$WBP" "$BK/"
  mv "$PACK_DST" "$BK/mcportal_stats.previous"   # the old pack moves into the backup
  info "$BK"

  step "3/4 Neue Version einsetzen"
  cp -r "$PACK_SRC" "$PACK_DST"
  sed -i "s/@SERVER_API@/$SERVER_API/" "$PACK_DST/manifest.json"
  set_world_entry
  info "world_behavior_packs.json: $(tr -d ' 
' < "$WBP")"

  step "4/4 Minecraft neu starten und prüfen"
  if restart_and_wait "${PACK_ALIVE[@]}"; then
    info "Server gestartet, Statistik-Pack $PACK_VERSION meldet sich: aktiv"
    printf '
[1;32mUpgrade erfolgreich.[0m Rückgängig: bash %s rollback-upgrade
' "$0"
  else
    journalctl -u "$UNIT" -n 40 -o cat --no-pager | grep -iE 'script|error|pack' | sed 's/^/    /' || true
    info "Neue Version meldet sich nicht – stelle vorherige Version wieder her"
    "$0" rollback-upgrade
    fail "Upgrade zurückgerollt"
  fi
  ;;

rollback-upgrade)
  BK="$(find "$BACKUPS" -maxdepth 1 -type d -name '*_pre_m6' 2>/dev/null | sort | tail -n 1)"
  [[ -n "$BK" && -d "$BK/mcportal_stats.previous" ]] || fail "keine Upgrade-Sicherung gefunden"
  step "Rollback des Upgrades aus $BK"
  [[ -d "$PACK_DST" ]] && mv "$PACK_DST" "$BK/mcportal_stats.failed"
  cp -r "$BK/mcportal_stats.previous" "$PACK_DST"
  cat "$BK/world_behavior_packs.json" > "$WBP"
  info "vorherige Pack-Version und world_behavior_packs.json wiederhergestellt"
  restart_and_wait 'mcportal-stats' && info "Server läuft wieder mit der vorherigen Version"     || fail "Server/Pack meldet sich nicht – bitte Log prüfen"
  ;;

*) echo "Aufruf: bash $0 apply|rollback|upgrade|rollback-upgrade|status"; exit 2 ;;
esac
