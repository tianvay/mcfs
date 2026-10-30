#!/usr/bin/env bash
# Set (or change) the portal's admin password.
#
#   sudo bash ~/mcportal-src/deploy/set-password.sh
#
# Asks twice (nothing is shown while typing), stores only a scrypt hash in /etc/mcportal/config.toml
# and restarts the portal - not Minecraft. All existing admin logins end with a new password.
# Undo: the previous config.toml is kept as /etc/mcportal/config.toml.bak
set -euo pipefail

CONF=/etc/mcportal/config.toml
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }
[[ -f "$CONF" ]] || { echo "$CONF fehlt - erst deploy/install.sh ausführen." >&2; exit 1; }

cp -a "$CONF" "$CONF.bak"
# app/auth.py needs only the standard library - the system python is enough
(cd "$SRC" && python3 -m app.auth set-password "$CONF")

if systemctl is-active -q mcportal; then
  systemctl restart mcportal
  echo "Portal neu gestartet (Minecraft läuft unverändert weiter)."
fi
