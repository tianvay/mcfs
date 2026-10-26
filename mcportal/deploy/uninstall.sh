#!/usr/bin/env bash
# Minecraft Family Portal - complete removal (S1-S5, M3). Minecraft keeps running.
#
#   sudo bash deploy/uninstall.sh            backups in /var/lib/mcportal are kept
#   sudo bash deploy/uninstall.sh --purge    also delete /var/lib/mcportal
#
# If M2 is installed, run "m2-console.sh rollback" first.
# M1 (owner of allowlist.json) is left as is - the original owner is recorded in
# /var/lib/mcportal/backups/*_pre_portal_install/allowlist-owner-before.txt
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }

if [[ -f /etc/systemd/system/minecraft-bedrock.socket ]]; then
  echo "M2 ist noch installiert. Zuerst: sudo bash $(dirname "$0")/m2-console.sh rollback"; exit 1
fi

systemctl disable --now mcportal.service 2>/dev/null || true
rm -f /etc/systemd/system/minecraft-bedrock.service.d/20-startcheck.conf   # M8 (uses /opt/mcportal/bin)
rm -f /etc/systemd/system/mcportal.service \
      /etc/systemd/system/mcportal-update-apply.service /etc/systemd/system/mcportal-update-rollback.service
systemctl daemon-reload
rm -f /etc/polkit-1/rules.d/50-mcportal.rules
ufw status numbered 2>/dev/null | grep -q mcportal && ufw delete allow from "${LAN_CIDR:-192.168.178.0/24}" to any port 8080 proto tcp || true

if [[ -f /var/lib/mcportal/acl-added.txt ]]; then
  while read -r p; do [[ -e "$p" ]] && setfacl -x u:mcportal "$p" && echo "ACL entfernt: $p"; done < /var/lib/mcportal/acl-added.txt
  rm -f /var/lib/mcportal/acl-added.txt
fi

rm -rf /opt/mcportal /etc/mcportal
id mcportal >/dev/null 2>&1 && userdel mcportal
[[ "${1:-}" == "--purge" ]] && rm -rf /var/lib/mcportal

echo "Portal entfernt.$([[ "${1:-}" == "--purge" ]] || echo " Sicherungen liegen weiterhin in /var/lib/mcportal.")"
