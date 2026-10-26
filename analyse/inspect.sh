#!/usr/bin/env bash
# Minecraft Family Portal – Bestandsaufnahme (STRIKT READ-ONLY)
#
# Dieses Script ändert NICHTS: keine Dateien, keine Dienste, keine Pakete.
# Es liest nur Informationen aus und schreibt einen Bericht nach
#   ~/mc-inspect-<datum>.txt
# Secrets (.env-Inhalte, Passwörter) werden bewusst NICHT ausgegeben.
#
# Aufruf:   bash inspect.sh            (normaler Benutzer, reicht meistens)
#   oder:   sudo bash inspect.sh       (zeigt zusätzlich Prozessnamen an Ports, Firewall)

set -u
OUT="${HOME}/mc-inspect-$(date +%Y-%m-%d_%H-%M).txt"
exec > >(tee "$OUT") 2>&1

h()   { printf '\n\n==================== %s ====================\n' "$*"; }
run() { printf '\n$ %s\n' "$*"; bash -c "$*" 2>&1 | head -n "${LIMIT:-200}"; }

h "SYSTEM"
run "date; hostname; whoami; id"
run "cat /etc/os-release"
run "uname -a"
run "uptime"
run "df -h -x tmpfs -x devtmpfs -x squashfs"
run "free -h"
run "nproc"

h "BEDROCK: BINARIES SUCHEN"
SEARCH_DIRS="/home /opt /srv /var /usr/local /root /mnt /media"
mapfile -t BINS < <(find $SEARCH_DIRS -xdev -type f -name 'bedrock_server' 2>/dev/null)
printf '%s\n' "${BINS[@]:-<keine gefunden>}"

h "BEDROCK: LAUFENDE PROZESSE"
run "ps -eo pid,ppid,user,lstart,etime,args | grep -iE 'bedrock|minecraft' | grep -v grep"
for PID in $(pgrep -f bedrock_server 2>/dev/null); do
  echo "--- PID $PID ---"
  run "readlink /proc/$PID/cwd"
  run "readlink /proc/$PID/exe"
  run "ls -l /proc/$PID/fd/0 /proc/$PID/fd/1 /proc/$PID/fd/2"
  run "cat /proc/$PID/cgroup"
  run "pstree -aps $PID 2>/dev/null || ps -o pid,ppid,args -p \$(ps -o ppid= -p $PID)"
done

for BIN in "${BINS[@]:-}"; do
  [ -z "$BIN" ] && continue
  D="$(dirname "$BIN")"
  h "BEDROCK-VERZEICHNIS: $D"
  run "ls -la '$D'"
  run "du -sh '$D' '$D/worlds' 2>/dev/null"
  run "ls -la '$D/worlds' 2>/dev/null"
  run "stat -c '%U:%G %a %y %n' '$D' '$BIN' '$D'/*.json '$D/server.properties' 2>/dev/null"
  for F in server.properties allowlist.json whitelist.json permissions.json; do
    [ -f "$D/$F" ] && { echo; echo "--- $D/$F ---"; cat "$D/$F"; }
  done
  run "ls -la '$D'/*.txt '$D'/*.log '$D/logs' 2>/dev/null"
  LIMIT=40 run "grep -rhoE 'Version:? ?[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?' '$D' --include='*.log' --include='*.txt' 2>/dev/null | sort | uniq -c"
  LIMIT=60 run "tail -n 60 '$D'/*.log '$D'/logs/*.log 2>/dev/null"
  run "ls -la '$D'/.. "
done

h "SYSTEMD: MINECRAFT-BEZOGENE UNITS"
run "systemctl list-unit-files --type=service --no-pager | grep -iE 'minecraft|bedrock|mc[-_]?' "
run "systemctl list-units --all --no-pager | grep -iE 'minecraft|bedrock'"
for U in $(systemctl list-unit-files --no-pager --no-legend 2>/dev/null | awk '{print $1}' | grep -iE 'minecraft|bedrock'); do
  echo "--- $U ---"
  run "systemctl cat '$U' --no-pager"
  run "systemctl is-enabled '$U'; systemctl is-active '$U'"
  run "systemctl show '$U' -p ActiveEnterTimestamp -p ExecMainStartTimestamp -p User -p WorkingDirectory -p StandardInput -p StandardOutput --no-pager"
  LIMIT=80 run "journalctl -u '$U' --no-pager -n 80"
  LIMIT=20 run "journalctl -u '$U' --no-pager | grep -iE 'version|Player (connected|disconnected)' | tail -n 20"
done
run "systemctl --user list-unit-files --no-pager 2>/dev/null | grep -iE 'minecraft|bedrock'"
run "ls -la /etc/systemd/system/ | grep -iE 'minecraft|bedrock'"

h "ANDERE STARTMECHANISMEN"
run "crontab -l"
run "sudo -n crontab -l -u root 2>/dev/null || echo '(root-crontab nicht lesbar ohne sudo)'"
run "ls -la /etc/cron.d; grep -rilE 'bedrock|minecraft' /etc/cron* 2>/dev/null"
run "screen -ls"
run "tmux ls"
run "cat /etc/rc.local 2>/dev/null"
run "grep -rilE 'bedrock|minecraft' ~/.config/autostart ~/.bashrc ~/.profile 2>/dev/null"
run "ls -la ~ "
run "find /home /opt /srv /usr/local -xdev -maxdepth 4 -type f \\( -name '*.sh' -o -name '*.service' \\) 2>/dev/null | xargs grep -liE 'bedrock_server|minecraft' 2>/dev/null"

h "NETZWERK / PORTS"
run "sudo -n ss -tulpn 2>/dev/null || ss -tuln"
run "sudo -n ufw status verbose 2>/dev/null || echo '(ufw-Status braucht sudo)'"
run "ip -4 addr show | grep inet"

h "WEBSERVER / LARAVEL"
for S in nginx apache2 httpd caddy lighttpd php-fpm php8.1-fpm php8.2-fpm php8.3-fpm php8.4-fpm mysql mariadb postgresql redis-server supervisor docker; do
  printf '%-14s enabled=%-10s active=%s\n' "$S" "$(systemctl is-enabled $S 2>/dev/null)" "$(systemctl is-active $S 2>/dev/null)"
done
run "ls -la /etc/nginx/sites-enabled /etc/apache2/sites-enabled 2>/dev/null"
LIMIT=120 run "grep -hE '^\s*(listen|server_name|root|proxy_pass|Listen|<VirtualHost|DocumentRoot|ServerName)' /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*.conf /etc/apache2/sites-enabled/* /etc/apache2/ports.conf 2>/dev/null"
echo; echo "--- Laravel-Projekte (Fundorte von 'artisan', .env wird NICHT gelesen) ---"
find /var/www /home /srv /opt -xdev -maxdepth 5 -type f -name artisan 2>/dev/null | while read -r A; do
  P="$(dirname "$A")"; echo "$P  (owner: $(stat -c %U:%G "$P"))  .env vorhanden: $([ -f "$P/.env" ] && echo ja || echo nein)"
done
run "ls /etc/supervisor/conf.d 2>/dev/null"
run "systemctl list-units --type=service --state=running --no-pager"

h "LAUFZEITUMGEBUNGEN"
run "php -v | head -1"
run "composer --version 2>/dev/null | head -1"
run "node -v; npm -v"
run "python3 --version; python3 -c 'import venv; print(\"venv ok\")'"
run "dpkg -l | grep -E '^ii\s+(python3-venv|python3-pip|nodejs|unzip|curl|wget|rsync|zstd)\s' "
run "docker ps 2>/dev/null"

h "BERECHTIGUNGEN (nur Anzeige)"
run "sudo -n -l 2>/dev/null || echo '(sudo -l braucht Passwort – übersprungen)'"
run "getent passwd | awk -F: '\$3>=1000 && \$3<65000 {print \$1, \$6, \$7}'"

h "FERTIG"
echo "Bericht gespeichert unter: $OUT"
