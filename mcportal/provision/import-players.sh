#!/usr/bin/env bash
# Minecraft Family Portal - take over the allowlist and operators from another server folder (e.g. the test phase).
#
#   sudo bash provision/import-players.sh --from <old server dir> [--allowlist-only] [--conf FILE]
#
# --allowlist-only: only the allowlist; operators stay as they are in the target (27.10.: none in the new world)
#
# Target is MC_DIR from server.conf. Minecraft must not be running there (the server rewrites both files itself).
# Entries already in the target stay; for the same player the old folder wins. Backup of the target files first:
#   <MC_HOME>/mcportal-backups/<time>_pre_import-players/ (same place as deploy/world-pack.sh)
# Only counts are printed - names and XUIDs stay in the files.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

FROM="" CONF="" ONLY=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from) FROM="${2:-}"; shift ;;
    --conf) CONF="${2:-}"; shift ;;
    --allowlist-only) ONLY=(--allowlist-only) ;;
    *) echo "Aufruf: sudo bash $0 --from <alter Serverordner> [--allowlist-only] [--conf DATEI]"; exit 2 ;;
  esac
  shift
done
[[ "$(id -u)" == 0 ]] || fail "Bitte mit sudo ausführen"
[[ -n "$FROM" ]] || fail "--from <alter Serverordner> fehlt"
load_conf "$CONF"

step "1/3 Prüfungen"
FROM="$(realpath -e "$FROM")" || fail "Ordner nicht gefunden: $FROM"
[[ -f "$FROM/allowlist.json" ]] || fail "$FROM/allowlist.json fehlt"
[[ -x "$MC_DIR/bedrock_server" ]] || fail "Ziel $MC_DIR ist nicht eingerichtet (zuerst setup.sh)"
[[ "$FROM" != "$(realpath -e "$MC_DIR")" ]] || fail "Quelle und Ziel sind derselbe Ordner"
if [[ "$(systemctl is-active "$UNIT" || true)" == active \
      && "$(systemctl show -p WorkingDirectory --value "$UNIT")" == "$MC_DIR" ]]; then
  fail "Minecraft läuft in $MC_DIR – bitte zuerst stoppen"
fi
pgrep -f "^$MC_DIR/bedrock_server" >/dev/null && fail "ein bedrock_server läuft aus $MC_DIR – bitte zuerst stoppen"
SRC_COUNT="$(python3 -I "$HERE/players.py" count "$FROM")" || fail "Quelle ungültig"
DST_COUNT="$(python3 -I "$HERE/players.py" count "$MC_DIR")" || fail "Ziel ungültig"
info "Quelle: $FROM ($SRC_COUNT)"
info "Ziel:   $MC_DIR ($DST_COUNT)"

step "2/3 Sicherung"
BK="$MC_HOME/mcportal-backups/$(date +%Y-%m-%d_%H-%M-%S)_pre_import-players"
mkdir -p "$BK"
for f in allowlist.json permissions.json; do
  [[ -f "$MC_DIR/$f" ]] && cp -a "$MC_DIR/$f" "$BK/"
done
chown -R "$MC_USER:$MC_USER" "$MC_HOME/mcportal-backups"
chmod 750 "$MC_HOME/mcportal-backups" "$BK"
info "$BK"

step "3/3 Übernehmen"
COUNTS="$(python3 -I "$HERE/players.py" import "$FROM" "$MC_DIR" "${ONLY[@]}")" || fail "nichts geändert (Sicherung: $BK)"
for f in allowlist.json permissions.json; do   # new files (none in the target before) belong to MC_USER
  chown "$MC_USER:$MC_USER" "$MC_DIR/$f"
done
read -r _ _ kept total ops <<<"$(tr ' ' '\n' <<<"$COUNTS" | cut -d= -f2 | tr '\n' ' ')"
info "Whitelist: $total Einträge ($kept waren schon im Ziel), Operatoren: $ops${ONLY:+ (nur Whitelist übernommen)}"
printf '\n\033[1;32mÜbernommen.\033[0m Wirksam beim nächsten Start. Rückgängig: sudo cp -a %s/*.json %s/\n' "$BK" "$MC_DIR"
