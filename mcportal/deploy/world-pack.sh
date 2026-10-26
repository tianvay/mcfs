#!/usr/bin/env bash
# Minecraft Family Portal - install, upgrade or remove a behavior or resource pack in the world.
#
#   bash deploy/world-pack.sh <pack> apply      install or upgrade to the repo version (restarts Minecraft)
#   bash deploy/world-pack.sh <pack> rollback   back to the state before the last apply (previous version or none)
#   bash deploy/world-pack.sh <pack> status
#
#   <pack> = folder name in mcportal/minecraft-pack/, e.g. mcportal_achievements
#
# The kind of pack (behavior/resource) comes from its manifest. NO_RESTART=1 puts a pack in place
# without restarting - to install several packs with a single restart:
#   NO_RESTART=1 bash deploy/world-pack.sh mcportal_waypoints_rp apply
#                bash deploy/world-pack.sh mcportal_waypoints apply
#
# Runs as the Minecraft user, no sudo. Touches only
#   worlds/<level>/{behavior,resource}_packs/<pack>/  and  worlds/<level>/world_{behavior,resource}_packs.json
# Requires the content-log settings from M5 (script output reaches the log).
# Backups: ~/mcportal-backups/<time>_pre_<pack>/  (pack list of the world + previous pack folder)
set -euo pipefail

UNIT=minecraft-bedrock.service
PORTAL=http://127.0.0.1:8080
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# stable @minecraft/server version, verified on the test server for Bedrock 1.26.52.3
SERVER_API=2.10.0
BACKUPS="$HOME/mcportal-backups"

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
fail() { printf '\n\033[1;31mFEHLER: %s\033[0m\n' "$*" >&2; exit 1; }

PACK="${1:-}"; ACTION="${2:-}"
[[ "$PACK" =~ ^[a-z0-9_]+$ && -f "$SRC/minecraft-pack/$PACK/manifest.json" ]] \
  || { echo "Aufruf: bash $0 <pack> apply|rollback|status   (Packs: $(ls "$SRC/minecraft-pack" | tr '\n' ' '))"; exit 2; }

PACK_SRC="$SRC/minecraft-pack/$PACK"
manifest() { python3 -c 'import json,sys; h=json.load(open(sys.argv[1]))["header"]; print(h[sys.argv[2]] if sys.argv[2] != "version" else ".".join(map(str, h["version"])))' "$1" "$2"; }
PACK_UUID="$(manifest "$PACK_SRC/manifest.json" uuid)"
PACK_NAME="$(manifest "$PACK_SRC/manifest.json" name)"
PACK_VERSION="$(manifest "$PACK_SRC/manifest.json" version)"
KIND="$(python3 -c 'import json,sys; t={m["type"] for m in json.load(open(sys.argv[1]))["modules"]}; print("resource" if "resources" in t else "behavior")' "$PACK_SRC/manifest.json")"
TAG=""
if [[ -f "$PACK_SRC/scripts/main.js" ]]; then
  TAG="$(grep -om1 '\[mcportal-[a-z]*\]' "$PACK_SRC/scripts/main.js" || true)"
  [[ -n "$TAG" ]] || fail "Kein Log-Tag [mcportal-…] in scripts/main.js gefunden"
fi

MC_DIR="$(systemctl show -p WorkingDirectory --value "$UNIT")"
[[ -x "$MC_DIR/bedrock_server" ]] || fail "Minecraft-Verzeichnis nicht gefunden"
[[ "$(id -un)" == "$(systemctl show -p User --value "$UNIT")" ]] || fail "Bitte als $(systemctl show -p User --value "$UNIT") ausführen (ohne sudo)"
LEVEL="$(sed -n 's/^level-name=//p' "$MC_DIR/server.properties")"
WORLD="$MC_DIR/worlds/$LEVEL"
[[ -d "$WORLD/db" ]] || fail "Welt nicht gefunden: $WORLD"
DST="$WORLD/${KIND}_packs/$PACK"
WBP="$WORLD/world_${KIND}_packs.json"

players_online() {
  curl -s -m 5 "$PORTAL/api/status" | python3 -c 'import sys,json; print(len(json.load(sys.stdin)["players"]))'
}

restart_and_wait() {  # all given patterns must appear in the log after the start
  local t0; t0="$(date +%s)"
  local code; code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$PORTAL/api/server/restart")"
  [[ "$code" == 202 ]] || fail "Portal hat den Neustart abgelehnt (HTTP $code – PIN gesetzt?)"
  # the start check (M8) may wait for the port, so allow a few minutes
  for _ in $(seq 1 400); do
    sleep 1
    local logtext; logtext="$(journalctl -u "$UNIT" --since "@$t0" -o cat --no-pager -q)"
    local ok=1 pat
    for pat in 'Server started\.' "$@"; do grep -q -- "$pat" <<<"$logtext" || ok=0; done
    [[ $ok == 1 ]] && return 0
  done
  return 1
}

set_world_entry() {  # $1 = version or "remove"; edits the world's pack list in place
  python3 - "$WBP" "$PACK_UUID" "$1" <<'PY'
import json, sys
path, uuid, version = sys.argv[1], sys.argv[2], sys.argv[3]
packs = json.load(open(path)) if open(path).read().strip() else []
packs = [p for p in packs if p.get("pack_id") != uuid]
if version != "remove":
    packs.append({"pack_id": uuid, "version": [int(x) for x in version.split(".")]})
with open(path, "r+") as f:   # in place: keep owner/permissions
    f.seek(0); json.dump(packs, f, indent=2); f.truncate()
PY
}

# what must appear in the log after the restart: behavior packs are listed in "Pack Stack",
# packs with a script write their startup line
ALIVE=()
[[ "$KIND" == behavior ]] && ALIVE+=("$PACK_NAME.*version: $PACK_VERSION")
[[ -n "$TAG" ]] && ALIVE+=("\\$TAG {\"v\":[0-9]*,\"started\":true}")

case "$ACTION" in
status)
  info "Pack: $PACK_NAME ($PACK, $KIND pack), Repo-Version $PACK_VERSION${TAG:+, Log-Tag $TAG}"
  if [[ -f "$DST/manifest.json" ]]; then info "installiert: Version $(manifest "$DST/manifest.json" version)"; else info "nicht installiert"; fi
  grep -qs "$PACK_UUID" "$WBP" && info "in $(basename "$WBP") eingetragen" || info "nicht in $(basename "$WBP")"
  ;;

apply)
  step "1/4 Prüfungen"
  grep -qx 'content-log-console-output-enabled=true' "$MC_DIR/server.properties" \
    && grep -qx 'content-log-level=warning' "$MC_DIR/server.properties" \
    || fail "Script-Ausgabe ist nicht im Log eingeschaltet – zuerst M5 (m5-stats-pack.sh apply)"
  n="$(players_online)" || fail "Portal nicht erreichbar"
  [[ "$n" == 0 ]] || fail "$n Spieler online – bitte warten, bis niemand spielt"
  OLD="$( [[ -f "$DST/manifest.json" ]] && manifest "$DST/manifest.json" version || echo "-" )"
  info "$PACK_NAME ($KIND pack): installiert $OLD -> neu $PACK_VERSION, niemand online"

  step "2/4 Sicherung"
  BK="$BACKUPS/$(date +%Y-%m-%d_%H-%M-%S)_pre_$PACK"
  mkdir -p "$BK"
  [[ -f "$WBP" ]] || echo "[]" > "$WBP"   # world_resource_packs.json may not exist yet
  cp -a "$WBP" "$BK/"
  [[ -d "$DST" ]] && mv "$DST" "$BK/previous"   # the old version moves into the backup
  info "$BK"

  step "3/4 Pack einsetzen"
  mkdir -p "$DST"
  (cd "$PACK_SRC" && tar --exclude=./tests --exclude=./tools -cf - .) | tar -xf - -C "$DST"
  sed -i "s/@SERVER_API@/$SERVER_API/" "$DST/manifest.json"
  set_world_entry "$PACK_VERSION"
  info "$(basename "$WBP"): $(tr -d ' \n' < "$WBP")"

  if [[ "${NO_RESTART:-}" == 1 ]]; then
    printf '\n\033[1;32mEingesetzt, noch nicht aktiv\033[0m (NO_RESTART=1) – wirksam mit dem nächsten Neustart.\n'
    exit 0
  fi

  step "4/4 Minecraft neu starten und prüfen"
  if restart_and_wait "${ALIVE[@]}"; then
    info "Server gestartet, $PACK_NAME $PACK_VERSION aktiv"
    printf '\n\033[1;32mErfolgreich.\033[0m Rückgängig: bash %s %s rollback\n' "$0" "$PACK"
  else
    journalctl -u "$UNIT" -n 40 -o cat --no-pager | grep -iE 'script|error|pack' | sed 's/^/    /' || true
    info "Pack meldet sich nicht – stelle vorherigen Zustand wieder her"
    "$0" "$PACK" rollback
    fail "zurückgerollt"
  fi
  ;;

rollback)
  BK="$(find "$BACKUPS" -maxdepth 1 -type d -name "*_pre_$PACK" 2>/dev/null | sort | tail -n 1)"
  [[ -n "$BK" ]] || fail "keine Sicherung für $PACK gefunden"
  step "Rollback aus $BK"
  [[ -d "$DST" ]] && mv "$DST" "$BK/failed-$(date +%H-%M-%S)"
  if [[ -d "$BK/previous" ]]; then cp -r "$BK/previous" "$DST"; info "vorherige Version zurück"; else info "Pack entfernt (war vorher nicht installiert)"; fi
  cat "$BK/$(basename "$WBP")" > "$WBP"
  if [[ "${NO_RESTART:-}" == 1 ]]; then info "wirksam mit dem nächsten Neustart"; exit 0; fi
  restart_and_wait && info "Server läuft wieder" || fail "Server meldet nicht 'Server started.'"
  ;;

*) echo "Aufruf: bash $0 <pack> apply|rollback|status"; exit 2 ;;
esac
