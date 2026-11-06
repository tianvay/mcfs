#!/usr/bin/env bash
# Minecraft Family Portal - set up the real Bedrock server from the repo (docs/04-reproduzierbarer-aufbau.md).
#
#   sudo bash provision/setup.sh --prepare     [--conf FILE]
#   sudo bash provision/setup.sh --switch      [--conf FILE] [--import-players | --import-allowlist]
#   sudo bash provision/setup.sh --switch-back
#   sudo bash provision/setup.sh --install     [--conf FILE] [--seed SEED] [--name SERVERNAME] [--world WORLDNAME]
#                                              [--players MAXPLAYERS]
#
# --install sets up a FRESH Ubuntu server (24.04+, or Linux Mint 22+; no test installation to replace,
#   docs/15-installation.md): packages (python3-venv, acl, curl, polkit, libcurl), /etc/mcportal/server.conf from
#   the example; server name, world name, seed and max. players are asked on a terminal unless given (Enter =
#   "Family and Friends", "FAF", random seed, 10; without a terminal these defaults apply), steps 1-5 as --prepare, main unit +
#   console socket, deploy/install.sh (portal, start check, public IP, update helpers), firewall ports, no suspend,
#   first start (the world is created now), game rules, verify.sh. No probe copy: the real start is checked the
#   same way (start check, every pack reports, no script errors). Laptop-only tweaks of the family server
#   (WLAN power saving, fixed IP, router port forwarding) are NOT part of it.
#   Re-running is safe; an existing world is kept (seed and world name are then not asked again).
#
# KEEP THIS CURRENT: every new pack (packs.list), deploy script, unit, drop-in or system package that the family
#   server gets must also be set up by --install - a fresh server has to end up exactly like the running one.
#
# --prepare runs alongside the test server, without downtime:
#   1. checks (root, tools, disk space, probe ports free, Laravel answer as reference)
#   2. system user MC_USER and MC_DIR (750, owned by MC_USER; nothing 777, nothing root)
#   3. newest official server from minecraft.net (same checks as the portal's update button)
#   4. server.properties = Mojang's file + provision/server.properties.overrides
#   5. all packs from packs.list into worlds/<WORLD_NAME>/ BEFORE the first start (no world is generated here)
#   6. probe start of a throwaway copy on other ports (no LAN), with the real unit + console + start check + game
#      rules as
#      runtime units mcportal-probe.* (/run, gone after a reboot): the start check must pass, every pack must
#      report, no script errors, clean stop via "stop"; then the copy is deleted
#   Does NOT touch the systemd units of the test server, the portal or Laravel.
#
# --switch (cut-over day, ~5 minutes without Minecraft; needs the real settings, not the example):
#   1-6 as --prepare with the final settings (still without downtime), then
#   7. restore point in /var/backups/mcportal-switch/<time>/ (old unit + socket, portal config) - root only
#   8. stop the test server; with --import-players: allowlist + operators from the test installation,
#      with --import-allowlist: only the allowlist (27.10.: the new world starts without operators)
#   9. portal data of the test phase -> /var/lib/mcportal/archive/<time>_testphase/ (statistics, achievements,
#      events, waypoints, map, update backups - the update rollback must never bring back the test server;
#      without --import-players also the pending operator assignments, so nobody becomes operator on joining)
#  10. main unit (User=MC_USER, sandbox) + console socket for MC_USER; deploy/install.sh points the portal to
#      the new folder (ACLs, config, helper units)
#  11. start - the world is created now, with the seed from server.conf; game rules from gamerules.list
#      (e.g. pvp false) through the console; verify.sh
#   The test installation stays as it is (folder, world, files) - nothing is deleted.
#   If the start fails, --switch-back runs automatically.
#
# --switch-back: back to the test installation from the newest restore point (unit, socket, portal config and
#   portal data); the data of the real server is moved to /var/lib/mcportal/archive/<time>_after-switch/.
#
# Idempotent: with a world, --prepare keeps program and world; without one (only prepared) it fetches the newest
# server again. It always re-applies the overrides and probes again.
# Settings: --conf FILE, else /etc/mcportal/server.conf, else provision/server.conf.example (placeholder names).
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
# stable @minecraft/server version, same as deploy/world-pack.sh
SERVER_API=2.10.0
PROBE_V4=19160
PROBE_V6=19161
MIN_FREE_MB=2048
PORTAL=http://127.0.0.1:8080
DATA=/var/lib/mcportal
SWITCH_BACKUPS=/var/backups/mcportal-switch
UNIT_FILE="/etc/systemd/system/$UNIT"
SOCKET_FILE=/etc/systemd/system/minecraft-bedrock.socket
# portal files that belong to the world of the test phase (archived on --switch)
GAME_DATA=(stats.json achievements.json events.json waypoints.json map)
# pending operator assignments of the portal (current and first file name)
PENDING_OPS=(pending_operator.json pending_survival.json)

MODE="" CONF="" IMPORT="" SEED="" SEED_SET=0 NAME="" WORLD_ARG="" PLAYERS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepare) MODE=prepare ;;
    --switch) MODE=switch ;;
    --switch-back) MODE=switch-back ;;
    --install) MODE=install ;;
    --import-players) IMPORT=all ;;
    --import-allowlist) IMPORT=allowlist ;;
    --conf) CONF="${2:-}"; shift ;;
    --seed) SEED="${2:-}"; SEED_SET=1; shift ;;
    --name) NAME="${2:-}"; shift ;;
    --world) WORLD_ARG="${2:-}"; shift ;;
    --players) PLAYERS="${2:-}"; shift ;;
    *) MODE=""; break ;;
  esac
  shift
done
[[ -n "$MODE" ]] || { echo "Aufruf: sudo bash $0 --prepare|--switch|--switch-back|--install [--conf DATEI] [--seed SEED] [--name SERVERNAME] [--world WELTNAME] [--players MAXSPIELER] [--import-players|--import-allowlist]"; exit 2; }
[[ "$(id -u)" == 0 ]] || fail "Bitte mit sudo ausführen"

laravel_code() { curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1/ || true; }
players_online() { curl -s -m 5 "$PORTAL/api/status" | python3 -I -c 'import sys,json; print(len(json.load(sys.stdin)["players"]))'; }
as_mc() { runuser -u "$MC_USER" -- "$@"; }
# step numbers: --install runs the preparation as steps 3-7 of 12
STEP_OFFSET=0 STEP_TOTAL=6
pstep() { local n="$1"; shift; step "$((n + STEP_OFFSET))/$STEP_TOTAL $*"; }

# ===========================================================================
# preparation (steps 1-6) - shared by --prepare, --switch and --install
# ===========================================================================
prepare_checks() {
  pstep 1 "Prüfungen"
  info "Einstellungen: $CONF"
  for tool in python3 curl tar runuser ss systemd-analyze; do command -v "$tool" >/dev/null || fail "$tool fehlt"; done
  mkdir -p "$MC_HOME"   # needed for the free-space check; owner fixed below
  local free; free="$(df -Pm "$MC_HOME" | awk 'NR==2 {print $4}')"
  (( free >= MIN_FREE_MB )) || fail "Nur $free MB frei unter $MC_HOME (mindestens $MIN_FREE_MB MB)"
  info "Speicher: $free MB frei unter $MC_HOME"
  local port
  for port in "$PROBE_V4" "$PROBE_V6"; do
    ! ss -Htuln "sport = :$port" | grep -q . || fail "Probe-Port $port ist belegt"
  done
  for port in "$PORT_V4" "$PORT_V6"; do
    if ss -Htuln "sport = :$port" | grep -q .; then info "Port $port belegt (laufender Testserver – in Ordnung)"; fi
  done
}

prepare_user() {
  pstep 2 "Benutzer und Ordner"
  if id -u "$MC_USER" >/dev/null 2>&1; then
    info "Benutzer $MC_USER gibt es schon"
  else
    useradd --system --home-dir "$MC_HOME" --no-create-home --shell /usr/sbin/nologin --user-group "$MC_USER"
    info "Systembenutzer $MC_USER angelegt (keine Anmeldung)"
  fi
  chown "$MC_USER:$MC_USER" "$MC_HOME"
  chmod 750 "$MC_HOME"
}

prepare_program() {
  pstep 3 "Serverprogramm"
  if [[ -x "$MC_DIR/bedrock_server" ]] && compgen -G "$MC_DIR/worlds/*/db" >/dev/null; then
    info "schon vorhanden in $MC_DIR, mit Welt – bleibt (Updates über den Knopf im Portal)"
  else
    # never started (only prepared): always the newest version - players' clients update automatically and
    # cannot join an older server. Packs and server.properties are rebuilt in the next steps anyway.
    [[ -d "$MC_DIR" ]] && info "nur vorbereitet ($(cat "$MC_DIR/.provisioned-version" 2>/dev/null || echo '?')), noch nie gestartet – neueste Version"
    local stage="$MC_HOME/.staging" version
    rm -rf "$stage"
    mkdir "$stage"
    # as root: MC_USER cannot read the repo in the admin's home; owner is fixed right after
    version="$(python3 -I "$HERE/fetch_server.py" "$stage/server")" || fail "Download fehlgeschlagen"
    rm -rf "$MC_DIR"   # only after a good download; no world in it (checked above)
    mv "$stage/server" "$MC_DIR"
    rm -rf "$stage"
    printf '%s\n' "$version" > "$MC_DIR/.provisioned-version"
    info "Bedrock $version nach $MC_DIR"
  fi
  chown -R "$MC_USER:$MC_USER" "$MC_DIR"
  chmod 750 "$MC_DIR"
}

prepare_properties() {
  pstep 4 "server.properties"
  python3 -I "$HERE/properties.py" merge "$MC_DIR/server.properties" "$HERE/server.properties.overrides" "$CONF" \
    || fail "server.properties konnte nicht angepasst werden"
  local key value
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" == \#* ]] && continue
    info "$(grep -m1 "^$key=" "$MC_DIR/server.properties")"
  done < <(python3 -I "$HERE/properties.py" render "$HERE/server.properties.overrides" "$CONF")
  chown "$MC_USER:$MC_USER" "$MC_DIR/server.properties"
}

EXPECT=()   # log lines the probe start must show
prepare_packs() {
  pstep 5 "Packs in die Welt"
  if [[ -d "$WORLD/db" ]]; then
    info "Welt $WORLD_NAME gibt es schon – Packs bleiben unverändert (Änderungen: deploy/world-pack.sh)"
    return 0
  fi
  # folders of worlds that were prepared but never started (e.g. the world name changed since --prepare)
  local d
  for d in "$MC_DIR"/worlds/*/; do
    [[ -d "$d" && ! -d "$d/db" && "${d%/}" != "$WORLD" ]] && { rm -rf "$d"; info "nie gestartete Vorbereitung entfernt: $(basename "$d")"; }
  done
  as_mc mkdir -p "$WORLD/behavior_packs" "$WORLD/resource_packs"
  local bp="[]" rp="[]" kind pack dst uuid version entry
  while read -r kind pack; do
    dst="$WORLD/${kind}_packs/$pack"
    rm -rf "$dst"
    as_mc mkdir "$dst"
    (cd "$PACKS_SRC/$pack" && tar --exclude=./tests --exclude=./tools -cf - .) | as_mc tar --no-same-owner -xf - -C "$dst"
    as_mc sed -i "s/@SERVER_API@/$SERVER_API/" "$dst/manifest.json"
    uuid="$(manifest "$dst/manifest.json" uuid)"; version="$(manifest "$dst/manifest.json" version)"
    entry="$(python3 -I -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]) + [{"pack_id": sys.argv[2], "version": [int(x) for x in sys.argv[3].split(".")]}]))' \
      "$([[ $kind == behavior ]] && echo "$bp" || echo "$rp")" "$uuid" "$version")"
    if [[ $kind == behavior ]]; then bp="$entry"; else rp="$entry"; fi
    info "$kind  $pack $version"
    [[ $kind == behavior ]] && mapfile -t -O "${#EXPECT[@]}" EXPECT < <(pack_log_patterns "$dst")
  done <<<"$PACKS"
  python3 -I -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]), indent=2))' "$bp" | as_mc tee "$WORLD/world_behavior_packs.json" >/dev/null
  python3 -I -c 'import json,sys; print(json.dumps(json.loads(sys.argv[1]), indent=2))' "$rp" | as_mc tee "$WORLD/world_resource_packs.json" >/dev/null
  info "world_behavior_packs.json, world_resource_packs.json geschrieben"
}

# The probe copy runs through the same unit, console socket and start check as the real server later,
# as runtime units under other names. Differences: folder, ports, no LAN, Restart=no, and the start check is
# taken from the repo (run with bash, /run is noexec) - so it may be newer than the installed one.
PROBE_UNIT=mcportal-probe
PROBE_RUN=/run/systemd/system
PROBE_BIN=/run/mcportal-probe-bin
PROBE_FIFO=/run/mcportal-probe/console

probe_cleanup() {
  systemctl stop "$PROBE_UNIT.service" "$PROBE_UNIT.socket" 2>/dev/null || true
  rm -rf "$PROBE_RUN/$PROBE_UNIT.service" "$PROBE_RUN/$PROBE_UNIT.service.d" "$PROBE_RUN/$PROBE_UNIT.socket" "$PROBE_BIN"
  systemctl daemon-reload
  systemctl reset-failed "$PROBE_UNIT.service" "$PROBE_UNIT.socket" 2>/dev/null || true
}

probe_start() {
  pstep 6 "Probestart (Kopie, Ports $PROBE_V4/$PROBE_V6, mit Konsole und Startprüfung)"
  if [[ ${#EXPECT[@]} == 0 ]]; then
    info "übersprungen – die Welt gibt es schon, sie wird nicht für einen Probelauf kopiert"
    return 0
  fi
  local dir="$MC_HOME/probe" log="$MC_HOME/probe/probe.log" pat
  rm -rf "$dir"
  cp -a "$MC_DIR" "$dir"
  python3 -I - "$dir/server.properties" "$PROBE_V4" "$PROBE_V6" <<'PY'
import sys
path, v4, v6 = sys.argv[1:4]
want = {"server-port": v4, "server-portv6": v6, "enable-lan-visibility": "false", "server-name": "mcportal probe"}
lines = [f"{l.split('=', 1)[0]}={want[l.split('=', 1)[0]]}" if l.split("=", 1)[0] in want else l
         for l in open(path, encoding="utf-8").read().splitlines()]
open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
PY
  chown -R "$MC_USER:$MC_USER" "$dir"

  probe_cleanup
  install -d -m 755 "$PROBE_BIN" "$PROBE_RUN/$PROBE_UNIT.service.d"
  install -m 755 "$REPO/deploy/mc-start-check" "$PROBE_BIN/mc-start-check"
  python3 -I "$HERE/properties.py" render "$HERE/minecraft-bedrock.service.in" "$CONF" "MC_DIR=$dir" \
    | sed 's/^Description=.*/Description=Minecraft Family Portal - probe start (setup.sh)/' \
    > "$PROBE_RUN/$PROBE_UNIT.service" || fail "Probe-Unit konnte nicht erzeugt werden"
  sed -e "s#^ListenFIFO=.*#ListenFIFO=$PROBE_FIFO#" -e "s#@MC_USER@#$MC_USER#" -e "s#^SocketGroup=.*#SocketGroup=$MC_USER#" \
      -e 's/^Description=.*/Description=Minecraft Family Portal - probe console (setup.sh)/' \
      "$REPO/deploy/minecraft-bedrock.socket" > "$PROBE_RUN/$PROBE_UNIT.socket"
  sed -e "s#minecraft-bedrock.socket#$PROBE_UNIT.socket#g" -e "s#/run/minecraft-bedrock/console#$PROBE_FIFO#g" \
      "$REPO/deploy/10-portal.conf" > "$PROBE_RUN/$PROBE_UNIT.service.d/10-portal.conf"
  sed -e "s#/opt/mcportal/bin/mc-start-check#/bin/bash $PROBE_BIN/mc-start-check#g" \
      "$REPO/deploy/20-startcheck.conf" > "$PROBE_RUN/$PROBE_UNIT.service.d/20-startcheck.conf"
  printf '[Service]\nRestart=no\nEnvironment="MC_PORTS=%s %s" "MC_CONSOLE=%s"\n' "$PROBE_V4" "$PROBE_V6" "$PROBE_FIFO" \
    > "$PROBE_RUN/$PROBE_UNIT.service.d/99-probe.conf"
  systemctl daemon-reload
  systemd-analyze verify "$PROBE_RUN/$PROBE_UNIT.service" "$PROBE_RUN/$PROBE_UNIT.socket" 2>&1 \
    | grep -E "$PROBE_UNIT" | sed 's/^/    /' || true

  local ok=1 started=0
  # blocks until the start check (ExecStartPost) has passed or failed
  if systemctl start "$PROBE_UNIT.service"; then started=1; else ok=0; fi
  sleep 3   # late script errors
  local inv; inv="$(systemctl show -p InvocationID --value "$PROBE_UNIT.service")"
  if (( started )); then
    gamerules_apply "$PROBE_FIFO" "$PROBE_UNIT.service" || ok=0   # same commands as on the real world
    systemctl stop "$PROBE_UNIT.service" || ok=0   # ExecStop: "stop" through the console
  fi
  journalctl -q -o cat --no-pager _SYSTEMD_INVOCATION_ID="$inv" > "$log" 2>/dev/null || true
  journalctl -q -o cat --no-pager -u "$PROBE_UNIT.service" --since "-10min" | grep -a 'start-check:' >> "$log" || true
  probe_cleanup

  grep -aE 'Version:|Pack Stack|mcportal-[a-z]*\] \{"v":[0-9]*,"started"|Server started|start-check:|Quit correctly' "$log" \
    | sort -u | cut -c1-160 | sed 's/^/    /' | head -20
  local errors; errors="$(log_errors < "$log")"
  if [[ -n "$errors" ]]; then
    printf '%s\n' "$errors" | sed 's/^/    /' | head -30
    ok=0
  fi
  for pat in 'Server started\.' 'start-check: OK' 'Quit correctly' "${EXPECT[@]}"; do
    grep -aq -- "$pat" "$log" || { info "fehlt: $pat"; ok=0; }
  done
  (( ok )) || fail "Probestart nicht sauber – Log bleibt zur Ansicht: $log (Kopie löschen: sudo rm -rf $dir)"
  rm -rf "$dir"
  info "Startprüfung bestanden, alle ${#EXPECT[@]} Pack-Meldungen da, sauber gestoppt, keine Fehler – Kopie gelöscht"
}

prepare_all() {
  prepare_checks
  prepare_user
  prepare_program
  prepare_properties
  prepare_packs
  chown -R "$MC_USER:$MC_USER" "$MC_DIR"
  probe_start
}

check_rights() {
  local bad; bad="$(find "$MC_HOME" ! -type l \( -perm -o+w -o ! -user "$MC_USER" \) -print -quit)"
  [[ -z "$bad" ]] || fail "Rechte nicht sauber: $bad"
  info "Rechte: alles unter $MC_HOME gehört $MC_USER, nichts für alle schreibbar"
}

# ===========================================================================
# switching (steps 7-11)
# ===========================================================================
render_socket() {  # $1 = user
  sed "s#@MC_USER@#$1#" "$REPO/deploy/minecraft-bedrock.socket" > "$SOCKET_FILE"
  chmod 644 "$SOCKET_FILE"
}

portal_install() {
  info "deploy/install.sh – Portal folgt der Unit"
  bash "$REPO/deploy/install.sh" 2>&1 | sed 's/^/  | /'   # pipefail: fails when install.sh fails
}

wait_minecraft() {  # systemctl start already waited for the start check; make sure it stayed up
  sleep 5
  systemctl is-active -q "$UNIT"
}

do_switch() {
  conf_is_example && fail "Für --switch die echten Einstellungen anlegen: /etc/mcportal/server.conf (Vorlage: $HERE/server.conf.example)"
  local old_dir old_user
  old_dir="$(systemctl show -p WorkingDirectory --value "$UNIT")"
  old_user="$(systemctl show -p User --value "$UNIT")"
  [[ "$old_dir" != "$MC_DIR" ]] || fail "Die Unit zeigt schon auf $MC_DIR – bereits umgestellt"
  [[ -f "$UNIT_FILE" && -f "$SOCKET_FILE" ]] || fail "$UNIT_FILE oder $SOCKET_FILE fehlt"
  [[ ! -d "$WORLD/db" ]] || fail "Die Welt $WORLD_NAME gibt es schon in $MC_DIR – bitte prüfen"
  id mcportal >/dev/null 2>&1 || fail "Portal nicht installiert (deploy/install.sh)"
  local n; n="$(players_online)" || fail "Portal nicht erreichbar"
  [[ "$n" == 0 ]] || fail "$n Spieler online – bitte warten, bis niemand spielt"
  info "Testinstallation: $old_dir (Benutzer $old_user), niemand online"

  prepare_all   # still without downtime; probe with the final settings

  step "7/11 Wiederherstellungspunkt"
  local ts; ts="$(date +%Y-%m-%d_%H-%M-%S)"
  local bk="$SWITCH_BACKUPS/$ts"
  install -d -m 700 "$SWITCH_BACKUPS" "$bk"
  cp -a "$UNIT_FILE" "$SOCKET_FILE" "$bk/"
  [[ -f /etc/mcportal/config.toml ]] && cp -a /etc/mcportal/config.toml "$bk/"
  printf 'OLD_DIR=%s\nOLD_USER=%s\nNEW_DIR=%s\nARCHIVE=%s\n' "$old_dir" "$old_user" "$MC_DIR" "$DATA/archive/${ts}_testphase" > "$bk/switch.info"
  info "$bk"

  step "8/11 Testserver stoppen"
  systemctl stop "$UNIT"
  systemctl stop minecraft-bedrock.socket
  info "gestoppt (sauber über die Konsole)"
  if [[ -n "$IMPORT" ]]; then
    local only=()
    [[ "$IMPORT" == allowlist ]] && only=(--allowlist-only)
    bash "$HERE/import-players.sh" --from "$old_dir" "${only[@]}" --conf "$CONF" 2>&1 | sed 's/^/  | /' \
      || { do_switch_back; fail "Übernahme der Spieler fehlgeschlagen – zurückgestellt"; }
  else
    info "Whitelist/Operatoren nicht übernommen (--import-players/--import-allowlist) – neue Welt startet mit leerer Whitelist"
  fi

  step "9/11 Portal-Daten der Testphase archivieren"
  systemctl stop mcportal.service
  local archive="$DATA/archive/${ts}_testphase" f
  install -d -m 750 -o mcportal -g mcportal "$DATA/archive" "$archive"
  local data=("${GAME_DATA[@]}")
  # operator assignments waiting for a player's first join - only valid if the operators came along
  [[ "$IMPORT" == all ]] || data+=("${PENDING_OPS[@]}")
  for f in "${data[@]}"; do
    [[ -e "$DATA/$f" ]] && mv "$DATA/$f" "$archive/" && info "$f"
  done
  if compgen -G "$DATA/backups/*_pre_update" >/dev/null; then
    install -d -m 750 -o mcportal -g mcportal "$archive/backups"
    mv "$DATA"/backups/*_pre_update "$archive/backups/"
    info "Update-Sicherungen der Testphase (kein Rollback auf den Testserver)"
  fi
  info "-> $archive"

  step "10/11 Unit umstellen, Portal ausrichten"
  python3 -I "$HERE/properties.py" render "$HERE/minecraft-bedrock.service.in" "$CONF" > "$UNIT_FILE.new" \
    || { do_switch_back; fail "Unit konnte nicht erzeugt werden – zurückgestellt"; }
  chmod 644 "$UNIT_FILE.new"
  mv "$UNIT_FILE.new" "$UNIT_FILE"
  render_socket "$MC_USER"
  systemctl daemon-reload
  systemctl enable "$UNIT" >/dev/null 2>&1
  info "$UNIT_FILE: $MC_DIR, Benutzer $MC_USER"
  portal_install || { do_switch_back; fail "install.sh fehlgeschlagen – zurückgestellt"; }

  step "11/11 Start (die Welt entsteht jetzt)"
  if ! systemctl start "$UNIT" || ! wait_minecraft; then
    journalctl -u "$UNIT" -n 30 -o cat --no-pager | sed 's/^/    /'
    do_switch_back
    fail "Start fehlgeschlagen – Testserver läuft wieder"
  fi
  info "$(journalctl -u "$UNIT" -o cat --no-pager -n 300 | grep -a -m1 'start-check: OK' || echo 'gestartet')"
  # game rules live in the world, so they can only be set now that it exists (verify.sh checks them again)
  gamerules_apply /run/minecraft-bedrock/console "$UNIT" \
    || warn "Spielregeln nicht vollständig gesetzt – von Hand in der Konsole: gamerule <Regel> <Wert>"
  bash "$HERE/verify.sh" --conf "$CONF" --laravel "$LARAVEL_BEFORE" || warn "verify.sh meldet Fehler (siehe oben)"
  printf '\n\033[1;32mUmgestellt.\033[0m Minecraft läuft aus %s als %s. Die Testinstallation liegt unverändert in %s.\n' \
    "$MC_DIR" "$MC_USER" "$old_dir"
  printf 'Zurück zur Testinstallation: sudo bash %s/setup.sh --switch-back\n' "$HERE"
}

do_switch_back() {
  step "Zurück zur Testinstallation"
  local bk; bk="$(find "$SWITCH_BACKUPS" -mindepth 1 -maxdepth 1 -type d ! -name '*.used' 2>/dev/null | sort | tail -n 1)"
  [[ -n "$bk" && -f "$bk/switch.info" ]] || fail "kein Wiederherstellungspunkt in $SWITCH_BACKUPS"
  local old_dir archive
  old_dir="$(sed -n 's/^OLD_DIR=//p' "$bk/switch.info")"
  archive="$(sed -n 's/^ARCHIVE=//p' "$bk/switch.info")"
  [[ -x "$old_dir/bedrock_server" ]] || fail "Testinstallation nicht gefunden: $old_dir"
  info "Wiederherstellungspunkt: $bk"
  systemctl stop "$UNIT" 2>/dev/null || true
  systemctl stop minecraft-bedrock.socket 2>/dev/null || true
  systemctl stop mcportal.service 2>/dev/null || true
  cp -a "$bk/$(basename "$UNIT_FILE")" "$UNIT_FILE"
  cp -a "$bk/$(basename "$SOCKET_FILE")" "$SOCKET_FILE"
  systemctl daemon-reload
  info "Unit und Konsole wieder auf $old_dir"
  if [[ -d "$archive" ]]; then
    local after f
    after="$DATA/archive/$(date +%Y-%m-%d_%H-%M-%S)_after-switch"
    install -d -m 750 -o mcportal -g mcportal "$after"
    for f in "${GAME_DATA[@]}" "${PENDING_OPS[@]}"; do
      [[ -e "$DATA/$f" ]] && mv "$DATA/$f" "$after/"
      [[ -e "$archive/$f" ]] && mv "$archive/$f" "$DATA/"
    done
    if [[ -d "$archive/backups" ]]; then mv "$archive"/backups/* "$DATA/backups/" 2>/dev/null || true; rmdir "$archive/backups" 2>/dev/null || true; fi
    info "Portal-Daten der Testphase zurück (Daten danach: $after)"
  fi
  portal_install || warn "install.sh meldet einen Fehler – Portal bitte prüfen"
  systemctl start "$UNIT" || fail "Testserver startet nicht – journalctl -u $UNIT -n 50"
  mv "$bk" "$bk.used"   # the next --switch-back must not use it again
  info "Testserver läuft wieder ($old_dir)"
}

# ===========================================================================
# fresh installation (--install)
# ===========================================================================
# Ubuntu 24.04+ or a derivative on that base (Linux Mint 22+); others get a warning, polkit is checked below
check_os() {
  local id="" version="" name=""
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    id="$(. /etc/os-release; echo "${ID:-}")"; version="$(. /etc/os-release; echo "${VERSION_ID:-}")"
    name="$(. /etc/os-release; echo "${PRETTY_NAME:-$id}")"
  fi
  local min=""
  case "$id" in
    ubuntu) min=24.04 ;;
    linuxmint) min=22 ;;
  esac
  if [[ -z "$min" ]]; then
    warn "${name:-unbekanntes System} – getestet nur mit Ubuntu 24.04+ (bzw. Linux Mint 22+), es geht trotzdem weiter"
  elif [[ "$(printf '%s\n%s\n' "$min" "$version" | sort -V | head -n1)" != "$min" ]]; then
    fail "$name ist zu alt – nötig: Ubuntu 24.04 oder neuer (polkit mit JavaScript-Regeln für die Knöpfe im Portal)"
  else
    info "$name"
  fi
  command -v apt-get >/dev/null || fail "apt-get fehlt – nur Ubuntu/Debian-Systeme werden unterstützt"
  [[ "$(uname -m)" == x86_64 ]] || fail "Bedrock-Server gibt es nur für 64-Bit x86 (hier: $(uname -m))"
}

install_packages() {
  step "1/12 System und Pakete"
  check_os
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q >/dev/null || fail "apt-get update fehlgeschlagen"
  local pkgs=(python3 python3-venv curl acl ca-certificates iproute2 tar util-linux) missing=() p
  # the portal's polkit rule is JavaScript: "polkitd" (Ubuntu 23.10 and newer); Bedrock needs libcurl
  pkgs+=("$(apt-cache show polkitd >/dev/null 2>&1 && echo polkitd || echo policykit-1)")
  pkgs+=("$(apt-cache show libcurl4t64 >/dev/null 2>&1 && echo libcurl4t64 || echo libcurl4)")
  for p in "${pkgs[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p"); done
  if (( ${#missing[@]} )); then
    apt-get install -y -q --no-install-recommends "${missing[@]}" >/dev/null || fail "apt-get install ${missing[*]} fehlgeschlagen"
    info "installiert: ${missing[*]}"
  else
    info "alles vorhanden"
  fi
  [[ -d /etc/polkit-1/rules.d ]] || fail "polkit ohne /etc/polkit-1/rules.d – Ubuntu 24.04 oder neuer nötig"
}

# set_conf <key> <value>: change one line of server.conf; checked by properties.py before it is kept
set_conf() {
  local tmp="$CONF.new"
  if grep -q "^$1=" "$CONF"; then sed "s|^$1=.*|$1=$2|" "$CONF" > "$tmp"; else { cat "$CONF"; printf '%s=%s\n' "$1" "$2"; } > "$tmp"; fi
  python3 -I "$HERE/properties.py" conf "$tmp" >/dev/null || { rm -f "$tmp"; fail "ungültiger Wert für $1: '$2'"; }
  chmod 644 "$tmp"
  mv "$tmp" "$CONF"
}

# ask <KEY> <question> <default> <shown default> <variable>: read a value on the terminal until it is allowed
# (same rules as server.conf); Enter takes the default
ask() {
  local key="$1" question="$2" def="$3" shown="$4" value
  while true; do
    read -r -p "    $question [$shown]: " value || value=""
    [[ -z "$value" ]] && value="$def"
    python3 -I "$HERE/properties.py" check "$key" "$value" 2>/dev/null && break
    case "$key" in
      LEVEL_SEED) warn "Seed: Zahl (z. B. -1234567890) oder ein Wort aus Buchstaben, Ziffern und _ (bis 30 Zeichen)" ;;
      MAX_PLAYERS) warn "Spielerzahl: eine Zahl von 1 bis 99" ;;
      *) warn "Erlaubt: Buchstaben, Ziffern, Leerzeichen, _ ' - (bis 40 Zeichen)" ;;
    esac
  done
  printf -v "$5" '%s' "$value"
}

conf_value() { sed -n "s/^$1=//p" "$CONF"; }

install_conf() {
  step "2/12 Einstellungen"
  if [[ -z "$CONF" ]]; then
    CONF=/etc/mcportal/server.conf
    if [[ ! -f "$CONF" ]]; then
      install -d -m 755 /etc/mcportal
      install -m 644 "$HERE/server.conf.example" "$CONF"
      info "$CONF angelegt (aus server.conf.example)"
    fi
  fi
  load_conf "$CONF"
  info "Einstellungen: $CONF"
  if [[ -d "$MC_DIR/worlds/$WORLD_NAME/db" ]]; then
    # re-run: the world exists - seed and world name belong to it
    (( SEED_SET )) && warn "Die Welt $WORLD_NAME gibt es schon – der Seed ändert nichts mehr"
    [[ -z "$WORLD_ARG" || "$WORLD_ARG" == "$WORLD_NAME" ]] \
      || fail "Die Welt $WORLD_NAME gibt es schon – ein anderer Weltname ($WORLD_ARG) würde eine zweite Welt anlegen"
  else
    # new world: everything not given on the command line is asked (Enter = value from server.conf, i.e.
    # "Family and Friends", "FAF", a random seed and 10 players on a fresh server); without a terminal those apply
    local name="${NAME:-$(conf_value SERVER_NAME)}" world="${WORLD_ARG:-$WORLD_NAME}" seed
    local players="${PLAYERS:-$(conf_value MAX_PLAYERS)}"
    seed="$( (( SEED_SET )) && printf '%s' "$SEED" || conf_value LEVEL_SEED)"
    if [[ -t 0 ]] && { [[ -z "$NAME" ]] || [[ -z "$WORLD_ARG" ]] || (( ! SEED_SET )) || [[ -z "$PLAYERS" ]]; }; then
      info "Neue Welt – bitte angeben (Enter = Vorschlag in Klammern):"
      [[ -n "$NAME" ]] || ask SERVER_NAME "Servername (Anzeige in der Serverliste)" "$name" "$name" name
      [[ -n "$WORLD_ARG" ]] || ask WORLD_NAME "Weltname (Ordner der Welt)" "$world" "$world" world
      (( SEED_SET )) || ask LEVEL_SEED "Seed" "$seed" "${seed:-zufällig}" seed
      [[ -n "$PLAYERS" ]] || ask MAX_PLAYERS "Höchstzahl Spieler gleichzeitig" "$players" "$players" players
    elif [[ ! -t 0 ]]; then
      info "kein Terminal – keine Abfrage, es gelten die Angaben bzw. die Werte aus $CONF"
    fi
    set_conf SERVER_NAME "$name"
    set_conf WORLD_NAME "$world"
    set_conf LEVEL_SEED "$seed"
    set_conf MAX_PLAYERS "$players"
    NAME="" PLAYERS=""   # applied
  fi
  # name and player count may change on a re-run too (server.properties is rebuilt; wirksam beim nächsten Start)
  [[ -n "$NAME" ]] && set_conf SERVER_NAME "$NAME"
  [[ -n "$PLAYERS" ]] && set_conf MAX_PLAYERS "$PLAYERS"
  load_conf "$CONF"
  local seed; seed="$(sed -n 's/^LEVEL_SEED=//p' "$CONF")"
  info "Server: $(sed -n 's/^SERVER_NAME=//p' "$CONF"), Welt: $WORLD_NAME, Seed: ${seed:-zufällig}, max. $(sed -n 's/^MAX_PLAYERS=//p' "$CONF") Spieler"

  if [[ -f "$UNIT_FILE" ]]; then
    local dir; dir="$(systemctl show -p WorkingDirectory --value "$UNIT")"
    [[ "$dir" == "$MC_DIR" ]] || fail "Hier gibt es schon einen Minecraft-Server ($dir) – zum Ablösen: --prepare / --switch"
    info "$UNIT gibt es schon ($MC_DIR) – erneute Installation"
  fi
}

# the home network of the default route, e.g. 192.168.1.0/24 (the portal is only reachable from there)
lan_cidr() {
  local dev; dev="$(ip -4 route show default | awk '{for (i = 1; i < NF; i++) if ($i == "dev") {print $(i + 1); exit}}')"
  [[ -n "$dev" ]] || return 0
  ip -4 -o addr show dev "$dev" | awk '{print $4; exit}' \
    | python3 -I -c 'import ipaddress,sys; print(ipaddress.ip_interface(sys.stdin.read().strip()).network)' 2>/dev/null || true
}

install_units() {
  step "8/12 Dienst und Konsole"
  python3 -I "$HERE/properties.py" render "$HERE/minecraft-bedrock.service.in" "$CONF" > "$UNIT_FILE.new" \
    || fail "Unit konnte nicht erzeugt werden"
  chmod 644 "$UNIT_FILE.new"
  mv "$UNIT_FILE.new" "$UNIT_FILE"
  render_socket "$MC_USER"
  install -d -m 755 "$UNIT_FILE.d"
  install -m 644 "$REPO/deploy/10-portal.conf" "$UNIT_FILE.d/10-portal.conf"
  # mc-public-ip asks the router (UPnP) for the public IPv4 - here the default gateway, not a fixed address
  local gw; gw="$(ip -4 route show default | awk '{print $3; exit}')"
  if [[ -n "$gw" ]]; then
    printf '# Router for mc-public-ip (default gateway at installation, provision/setup.sh --install)\n[Service]\nEnvironment=MC_ROUTER=%s\n' "$gw" \
      > "$UNIT_FILE.d/31-router.conf"
    info "Router für die öffentliche IPv4: $gw"
  fi
  systemctl daemon-reload
  systemctl enable "$UNIT" >/dev/null 2>&1
  info "$UNIT_FILE: $MC_DIR, Benutzer $MC_USER, Konsole $SOCKET_FILE"
}

install_portal() {
  step "9/12 Portal, Startprüfung, öffentliche IP"
  local lan; lan="$(lan_cidr)"
  [[ -n "$lan" ]] && export LAN_CIDR="$lan"
  portal_install || fail "deploy/install.sh fehlgeschlagen"
}

install_system() {
  # no deploy/wifi-no-powersave.sh here: that is a fix for the WLAN chip of the family server's laptop
  step "10/12 Firewall und Ruhezustand"
  if ufw status 2>/dev/null | grep -q '^Status: active'; then
    local udp; udp="$(sed -n 's/^Environment=MC_UDP_PORTS=//p' "$REPO/deploy/30-public-ip.conf")"
    ufw allow "$PORT_V4" comment minecraft >/dev/null
    ufw allow "$PORT_V6" comment minecraft >/dev/null
    ufw allow "${udp/-/:}/udp" comment 'minecraft nethernet' >/dev/null
    info "ufw: $PORT_V4, $PORT_V6 (TCP+UDP) und $udp/udp erlaubt"
  else
    info "ufw nicht aktiv – nichts zu tun"
  fi
  bash "$REPO/deploy/no-suspend.sh" apply 2>&1 | sed 's/^/    /' || warn "no-suspend.sh fehlgeschlagen"
}

install_start() {
  step "11/12 Start (die Welt entsteht jetzt)"
  if systemctl is-active -q "$UNIT"; then
    info "läuft schon – kein Neustart (Packs ändern: deploy/world-pack.sh)"
  elif ! systemctl start "$UNIT" || ! wait_minecraft; then
    journalctl -u "$UNIT" -n 30 -o cat --no-pager | sed 's/^/    /'
    fail "Start fehlgeschlagen (Log oben)"
  fi
  info "$(journalctl -u "$UNIT" -o cat --no-pager -n 300 | grep -a -m1 'start-check: OK' || echo 'gestartet')"
  local seed
  seed="$(python3 -I - "$REPO/app/adapters/bedrock/leveldat.py" "$WORLD" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("leveldat", sys.argv[1]); m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(m.read_seed(Path(sys.argv[2])))
PY
)" || seed="?"
  info "Seed der Welt: $seed"
  gamerules_apply /run/minecraft-bedrock/console "$UNIT" \
    || warn "Spielregeln nicht vollständig gesetzt – von Hand in der Konsole: gamerule <Regel> <Wert>"
}

do_install() {
  install_packages
  install_conf
  PACKS="$(pack_lines)"
  WORLD="$MC_DIR/worlds/$WORLD_NAME"
  STEP_OFFSET=2 STEP_TOTAL=12
  prepare_checks
  prepare_user
  prepare_program
  prepare_properties
  prepare_packs
  chown -R "$MC_USER:$MC_USER" "$MC_DIR"
  install_units
  install_portal
  install_system
  install_start
  step "12/12 Abnahme (verify.sh)"
  check_rights
  local ok=1
  bash "$HERE/verify.sh" --conf "$CONF" || ok=0
  if [[ -t 0 ]] && grep -qx 'password_hash = ""' /etc/mcportal/config.toml; then
    step "Admin-Passwort für das Portal (Whitelist, Events, Server-Seite)"
    bash "$REPO/deploy/set-password.sh" || warn "Passwort nicht gesetzt – später: sudo bash $REPO/deploy/set-password.sh"
  fi
  (( ok )) || fail "verify.sh meldet Fehler (siehe oben)"
  printf '\n\033[1;32mInstalliert.\033[0m Minecraft läuft aus %s als %s, Portal: http://%s:8080\n' \
    "$MC_DIR" "$MC_USER" "$(hostname -I | awk '{print $1}')"
}

# ===========================================================================
if [[ "$MODE" == install ]]; then
  do_install
  exit 0
fi
LARAVEL_BEFORE="$(laravel_code)"
info "Laravel: HTTP $LARAVEL_BEFORE auf Port 80 (Vergleichswert)"
case "$MODE" in
  prepare)
    load_conf "$CONF"
    conf_is_example && warn "Beispiel-Einstellungen (Servername/Weltname noch offen) – reicht für den Probelauf"
    PACKS="$(pack_lines)"
    WORLD="$MC_DIR/worlds/$WORLD_NAME"
    prepare_all
    check_rights
    ;;
  switch)
    load_conf "$CONF"
    PACKS="$(pack_lines)"
    WORLD="$MC_DIR/worlds/$WORLD_NAME"
    do_switch
    ;;
  switch-back)
    do_switch_back
    bash "$HERE/verify.sh" --laravel "$LARAVEL_BEFORE" || warn "verify.sh meldet Fehler (siehe oben)"
    ;;
esac
LARAVEL_AFTER="$(laravel_code)"
info "Laravel: HTTP $LARAVEL_AFTER (vorher $LARAVEL_BEFORE)"
[[ "$LARAVEL_AFTER" == "$LARAVEL_BEFORE" ]] || warn "Laravel-Antwort hat sich geändert!"
[[ "$MODE" == prepare ]] && printf '\n\033[1;32mVorbereitet.\033[0m %s ist bereit, die Welt entsteht erst beim Umstellen. Der Testserver läuft unverändert.\n' "$MC_DIR"
exit 0
