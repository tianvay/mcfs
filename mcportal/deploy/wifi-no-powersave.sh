#!/usr/bin/env bash
# Minecraft Family Server - keep the WLAN awake
#
#   sudo bash deploy/wifi-no-powersave.sh apply     WLAN power saving off (NetworkManager + rtw88 driver)
#   sudo bash deploy/wifi-no-powersave.sh rollback  back to the system defaults
#   sudo bash deploy/wifi-no-powersave.sh status
#
# Why: on 2026-11-04 the Realtek RTL8723DE (driver rtw88) lost the access point for ~15 min
# (CTRL-EVENT-BEACON-LOSS, "failed to get tx report from firmware", "timed out to flush queue")
# while Minecraft kept running - nobody could reach the server. Ubuntu turns WLAN power saving
# on by default (default-wifi-powersave-on.conf: wifi.powersave = 3); rtw88 is known to hang
# with it, especially in "deep" low-power mode.
#
# apply reconnects the WLAN once (a few seconds offline, an SSH session may drop).
set -euo pipefail
NM_CONF=/etc/NetworkManager/conf.d/zz-mcserver-wifi-powersave-off.conf   # zz: read after default-*.conf
MOD_CONF=/etc/modprobe.d/mcserver-rtw88.conf
LPS_PARAM=/sys/module/rtw88_core/parameters/disable_lps_deep

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen."; exit 1; }

wifi_dev() { nmcli -t -f DEVICE,TYPE device 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}'; }

reconnect() {
  local dev; dev=$(wifi_dev)
  [[ -n "$dev" ]] || { echo "Kein WLAN-Gerät gefunden – nur Einstellung gespeichert."; return 0; }
  systemctl reload NetworkManager
  # detached, so the reconnect finishes even if this SSH session drops with the WLAN
  systemd-run --quiet --collect --unit=mcserver-wifi-reconnect \
    bash -c "sleep 2; nmcli device disconnect '$dev'; sleep 1; nmcli device connect '$dev'" \
    && echo "WLAN ($dev) verbindet sich neu – ein paar Sekunden offline."
}

case "${1:-}" in
apply)
  mkdir -p "$(dirname "$NM_CONF")"
  cat > "$NM_CONF" <<'EOF'
# Minecraft Family Server: WLAN power saving off, rtw88 hangs with it (deploy/wifi-no-powersave.sh)
[connection]
wifi.powersave = 2
EOF
  cat > "$MOD_CONF" <<'EOF'
# Minecraft Family Server: no deep low-power mode for Realtek rtw88 WLAN (deploy/wifi-no-powersave.sh)
options rtw88_core disable_lps_deep=y
EOF
  [[ -w "$LPS_PARAM" ]] && echo Y > "$LPS_PARAM"   # live, no module reload needed
  echo "WLAN-Stromsparen: aus (NetworkManager), Treiber-Tiefschlaf: aus."
  reconnect
  ;;
rollback)
  rm -f "$NM_CONF" "$MOD_CONF"
  [[ -w "$LPS_PARAM" ]] && echo N > "$LPS_PARAM"
  echo "Zurück auf Systemstandard (WLAN-Stromsparen an)."
  reconnect
  ;;
status)
  [[ -f "$NM_CONF" ]] && echo "NetworkManager-Regel: aktiv ($NM_CONF)" || echo "NetworkManager-Regel: nicht gesetzt"
  echo "wirksam: $(NetworkManager --print-config 2>/dev/null | grep -m1 'wifi.powersave' | tr -d ' ' || echo '?')  (2 = aus, 3 = an)"
  [[ -f "$MOD_CONF" ]] && echo "Treiber-Regel:        aktiv ($MOD_CONF)" || echo "Treiber-Regel:        nicht gesetzt"
  [[ -r "$LPS_PARAM" ]] && echo "rtw88 disable_lps_deep: $(cat "$LPS_PARAM")" || echo "rtw88: nicht geladen"
  ;;
*) echo "Aufruf: sudo bash $0 apply|rollback|status"; exit 2 ;;
esac
