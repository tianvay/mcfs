#!/usr/bin/env bash
# Minecraft Family Portal - change M2: server console + clean stop
#
#   sudo bash deploy/m2-console.sh apply      install (restarts Minecraft once)
#   sudo bash deploy/m2-console.sh rollback   restore the previous state exactly
#   sudo bash deploy/m2-console.sh status
#
# Adds two files; /etc/systemd/system/minecraft-bedrock.service itself stays untouched:
#   /etc/systemd/system/minecraft-bedrock.socket
#   /etc/systemd/system/minecraft-bedrock.service.d/10-portal.conf
set -euo pipefail

UNIT=minecraft-bedrock.service
SOCKET=/etc/systemd/system/minecraft-bedrock.socket
DROPIN_DIR=/etc/systemd/system/minecraft-bedrock.service.d
DROPIN="$DROPIN_DIR/10-portal.conf"
FIFO=/run/minecraft-bedrock/console
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA=/var/lib/mcportal

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
fail() { printf '\n\033[1;31mFEHLER: %s\033[0m\n' "$*" >&2; exit 1; }
confirm() { read -r -p "    $1 [j/N] " a; [[ "$a" =~ ^[jJyY]$ ]]; }

[[ $EUID -eq 0 ]] || fail "Bitte mit sudo ausführen."

wait_started() {  # $1 = unix time of start; waits for "Server started." in the journal
  local since="$1"
  for _ in $(seq 1 90); do
    if journalctl -u "$UNIT" --since "@$since" -o cat --no-pager | grep -q 'Server started\.'; then return 0; fi
    systemctl is-failed -q "$UNIT" && return 1
    sleep 1
  done
  return 1
}

do_rollback() {
  step "Rollback: Konsole entfernen, vorherigen Zustand herstellen"
  systemctl stop "$UNIT" || true
  rm -f "$DROPIN"
  rmdir "$DROPIN_DIR" 2>/dev/null || true
  systemctl stop minecraft-bedrock.socket 2>/dev/null || true
  rm -f "$SOCKET"
  systemctl daemon-reload
  systemctl reset-failed "$UNIT" minecraft-bedrock.socket 2>/dev/null || true
  local t; t="$(date +%s)"
  systemctl start "$UNIT"
  if wait_started "$t"; then info "Minecraft läuft wieder (ohne Konsole, wie vorher)"; else
    fail "Minecraft startet nicht – bitte 'journalctl -u $UNIT -n 50' prüfen"; fi
  systemctl restart mcportal 2>/dev/null || true
}

case "${1:-}" in
status)
  [[ -f "$SOCKET" && -f "$DROPIN" ]] && info "M2 ist installiert" || info "M2 ist NICHT installiert"
  [[ -p "$FIFO" ]] && info "Konsole: $FIFO vorhanden" || info "Konsole: nicht vorhanden"
  systemctl show "$UNIT" -p StandardInput -p ActiveState
  ;;

rollback)
  [[ -f "$SOCKET" || -f "$DROPIN" ]] || { info "M2 ist nicht installiert – nichts zu tun"; exit 0; }
  confirm "Minecraft wird kurz neu gestartet. Fortfahren?" || exit 1
  do_rollback
  ;;

apply)
  step "1/6 Prüfungen"
  id mcportal >/dev/null 2>&1 || fail "Benutzer mcportal fehlt – zuerst install.sh ausführen"
  [[ ! -f "$SOCKET" && ! -f "$DROPIN" ]] || fail "M2 ist bereits installiert (Status: $0 status)"
  MC_DIR="$(systemctl show -p WorkingDirectory --value "$UNIT")"
  MC_USER="$(systemctl show -p User --value "$UNIT")"
  [[ -x "$MC_DIR/bedrock_server" ]] || fail "Minecraft-Verzeichnis nicht gefunden"
  PLAYERS="$(curl -s -m 5 http://127.0.0.1:8080/api/status | python3 -c 'import sys,json; print(", ".join(p["name"] for p in json.load(sys.stdin)["players"]))' 2>/dev/null || echo '?')"
  info "Spieler online: ${PLAYERS:-keine}"
  [[ -z "$PLAYERS" ]] || info "ACHTUNG: Spieler werden getrennt; ihr letzter Fortschritt kann verloren gehen (Stop per Signal)."
  confirm "Minecraft jetzt für ca. 30 s stoppen und Konsole einrichten?" || exit 1

  TS="$(date +%Y-%m-%d_%H-%M-%S)"
  BK="$DATA/backups/${TS}_pre_m2_console"

  step "2/6 Minecraft stoppen (letztmalig auf die alte Art)"
  systemctl stop "$UNIT"
  info "gestoppt"

  step "3/6 Sicherung nach $BK (Server gestoppt = konsistent)"
  mkdir -p "$BK"
  cp -a "/etc/systemd/system/$UNIT" "$BK/"
  cp -a "$MC_DIR/allowlist.json" "$MC_DIR/permissions.json" "$MC_DIR/server.properties" "$BK/"
  tar -czf "$BK/world.tar.gz" -C "$MC_DIR" worlds
  info "$(du -sh "$BK" | cut -f1) gesichert"

  step "4/6 Dateien installieren"
  sed "s#@MC_USER@#$MC_USER#" "$SRC/deploy/minecraft-bedrock.socket" > "$SOCKET"
  install -d -m 755 "$DROPIN_DIR"
  install -m 644 "$SRC/deploy/10-portal.conf" "$DROPIN"
  chmod 644 "$SOCKET"
  info "$SOCKET"
  info "$DROPIN"
  if ! systemd-analyze verify "$SOCKET" "/etc/systemd/system/$UNIT" 2>&1 | grep -iE 'minecraft-bedrock.*(error|invalid|unknown)' ; then
    info "systemd-analyze: ok"
  else
    do_rollback; fail "Unit-Prüfung fehlgeschlagen – zurückgerollt"
  fi
  systemctl daemon-reload

  step "5/6 Minecraft starten"
  T0="$(date +%s)"
  systemctl start "$UNIT" || { do_rollback; fail "Start fehlgeschlagen – zurückgerollt"; }
  wait_started "$T0" || { do_rollback; fail "Server meldet nicht 'Server started.' – zurückgerollt"; }
  info "Server gestartet: $(journalctl -u "$UNIT" --since "@$T0" -o cat --no-pager | grep -m1 -o 'Version: .*')"

  step "6/6 Konsole prüfen"
  [[ -p "$FIFO" ]] || { do_rollback; fail "Konsolen-FIFO fehlt – zurückgerollt"; }
  T1="$(date +%s)"
  echo list > "$FIFO"
  sleep 3
  if journalctl -u "$UNIT" --since "@$T1" -o cat --no-pager | grep -q 'players online'; then
    info "Konsole antwortet: $(journalctl -u "$UNIT" --since "@$T1" -o cat --no-pager | grep -m1 'players online')"
  else
    do_rollback; fail "Server reagiert nicht auf Konsolenbefehle – zurückgerollt"
  fi
  systemctl restart mcportal
  info "Portal neu gestartet"
  printf '\n\033[1;32mM2 erfolgreich.\033[0m Stoppen erfolgt ab jetzt sauber über den Befehl "stop".\n'
  printf 'Rückgängig: sudo bash %s/deploy/m2-console.sh rollback\n' "$SRC"
  ;;

*)
  echo "Aufruf: sudo bash $0 apply|rollback|status"; exit 2 ;;
esac
