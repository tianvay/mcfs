#!/usr/bin/env bash
# Minecraft Family Server - never suspend the server laptop
#
#   sudo bash deploy/no-suspend.sh apply     lid close does nothing, suspend/hibernate disabled
#   sudo bash deploy/no-suspend.sh rollback  back to the system defaults
#   sudo bash deploy/no-suspend.sh status
#
# Why: after a reboot with the lid closed, systemd-logind suspended the laptop 2 s after login
# (2026-10-26) - the desktop's own lid setting only applies once the session is up.
set -euo pipefail
CONF=/etc/systemd/logind.conf.d/50-mcserver-no-suspend.conf
TARGETS="sleep.target suspend.target hibernate.target hybrid-sleep.target"

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }

case "${1:-}" in
apply)
  mkdir -p "$(dirname "$CONF")"
  cat > "$CONF" <<'EOF'
# Minecraft Family Server: closing the lid must never suspend the server (deploy/no-suspend.sh)
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF
  systemctl kill -s HUP systemd-logind      # re-read config, sessions stay
  # shellcheck disable=SC2086
  systemctl mask $TARGETS >/dev/null
  echo "Deckel schließen: ignoriert. Ruhezustand/Hibernate: abgeschaltet."
  ;;
rollback)
  rm -f "$CONF"
  systemctl kill -s HUP systemd-logind
  # shellcheck disable=SC2086
  systemctl unmask $TARGETS >/dev/null
  echo "Zurück auf Systemstandard (Deckel zu = Ruhezustand)."
  ;;
status)
  [[ -f "$CONF" ]] && echo "Deckel-Regel: aktiv ($CONF)" || echo "Deckel-Regel: nicht gesetzt"
  # shellcheck disable=SC2086
  for t in $TARGETS; do printf '%-22s %s\n' "$t" "$(systemctl is-enabled "$t" 2>/dev/null)"; done
  ;;
*) echo "Aufruf: sudo bash $0 apply|rollback|status"; exit 2 ;;
esac
