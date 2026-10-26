#!/usr/bin/env bash
# Minecraft Family Portal - Installation Phase 1 (S1-S5, M1, M3)
#
#   sudo bash ~/mcportal-src/deploy/install.sh
#
# Does NOT restart Minecraft and does NOT touch Laravel/XAMPP.
# The console change (M2) is a separate script: deploy/m2-console.sh
# Re-running is safe (idempotent); code and service file are updated.
set -euo pipefail

UNIT=minecraft-bedrock.service
PORT=8080
LAN_CIDR="${LAN_CIDR:-192.168.178.0/24}"
APP=/opt/mcportal
DATA=/var/lib/mcportal
ETC=/etc/mcportal
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS="$(date +%Y-%m-%d_%H-%M-%S)"
BK="$DATA/backups/${TS}_pre_portal_install"

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
fail() { printf '\n\033[1;31mABBRUCH: %s\033[0m\n' "$*" >&2; exit 1; }
confirm() { read -r -p "    $1 [j/N] " a; [[ "$a" =~ ^[jJyY]$ ]]; }

[[ $EUID -eq 0 ]] || fail "Bitte mit sudo ausführen."

# ---------------------------------------------------------------- 1. Inspect
step "1/9 Prüfungen"
MC_DIR="$(systemctl show -p WorkingDirectory --value "$UNIT")"
MC_USER="$(systemctl show -p User --value "$UNIT")"
[[ -n "$MC_DIR" && -x "$MC_DIR/bedrock_server" ]] || fail "Minecraft-Verzeichnis nicht gefunden ($MC_DIR)"
[[ -f "$MC_DIR/allowlist.json" ]] || fail "allowlist.json fehlt"
[[ -n "$MC_USER" && "$MC_USER" != root ]] || fail "Minecraft läuft nicht unter einem normalen Benutzer"
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$MC_DIR/allowlist.json" || fail "allowlist.json ist kein gültiges JSON"
if ss -Hltn "sport = :$PORT" | grep -q . && ! systemctl is-active -q mcportal; then
  fail "Port $PORT ist belegt"
fi
LARAVEL_BEFORE="$(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1/ || true)"
info "Minecraft:  $MC_DIR (User $MC_USER, $(systemctl is-active "$UNIT"))"
info "Laravel:    HTTP $LARAVEL_BEFORE auf Port 80 (Vergleichswert)"
info "Portal:     Port $PORT, LAN $LAN_CIDR"

# ---------------------------------------------------------------- 2. Backup
step "2/9 Sicherung nach $BK"
install -d -m 750 "$DATA" "$DATA/backups"
mkdir -p "$BK"
cp -a "$MC_DIR/allowlist.json" "$MC_DIR/permissions.json" "$MC_DIR/server.properties" "$BK/"
cp -a "/etc/systemd/system/$UNIT" "$BK/"
stat -c '%U:%G %a %n' "$MC_DIR/allowlist.json" > "$BK/allowlist-owner-before.txt"
getfacl -p "$MC_DIR/allowlist.json" "$MC_DIR/permissions.json" "$(dirname "$MC_DIR")" "$MC_DIR" /home/"$MC_USER" > "$BK/acl-before.txt" 2>/dev/null || true
info "Welt-Kopie (Server läuft – Sicherheitskopie, die konsistente Sicherung folgt bei M2) ..."
# exit code 1 = "file changed as we read it" (server is writing) - acceptable here
tar -czf "$BK/world.tar.gz" -C "$MC_DIR" worlds || [[ $? -eq 1 ]]
info "$(du -sh "$BK" | cut -f1) gesichert"
# keep only the two newest install backups (space on this machine is limited)
find "$DATA/backups" -maxdepth 1 -type d -name '*_pre_portal_install' | sort | head -n -2 | while read -r old; do
  rm -rf "$old"; info "alte Installations-Sicherung entfernt: $(basename "$old")"
done

# ---------------------------------------------------------------- S1
step "3/9 S1: python3-venv"
if dpkg -s python3-venv >/dev/null 2>&1; then
  info "bereits installiert"
else
  info "apt würde Folgendes tun:"
  apt-get -s install --no-install-recommends python3-venv | grep -E '^(Inst|Remv)' | sed 's/^/      /' || true
  confirm "python3-venv installieren?" || fail "abgebrochen"
  apt-get install -y --no-install-recommends python3-venv
fi

# ---------------------------------------------------------------- S2
step "4/9 S2: Benutzer mcportal"
if id mcportal >/dev/null 2>&1; then
  info "existiert bereits"
else
  useradd --system --user-group --home-dir "$DATA" --no-create-home --shell /usr/sbin/nologin mcportal
  info "angelegt (System-User, keine Login-Shell, kein sudo)"
fi
chown mcportal:mcportal "$DATA" "$DATA/backups"

# ---------------------------------------------------------------- S3
step "5/9 S3: polkit-Regel (nur start/stop/restart von $UNIT)"
install -m 644 -o root -g root "$SRC/deploy/50-mcportal.rules" /etc/polkit-1/rules.d/50-mcportal.rules
info "/etc/polkit-1/rules.d/50-mcportal.rules"

# ---------------------------------------------------------------- M1
step "6/9 M1: Besitzer allowlist.json"
OWNER="$(stat -c %U "$MC_DIR/allowlist.json")"
if [[ "$OWNER" != "$MC_USER" ]]; then
  chown "$MC_USER:$MC_USER" "$MC_DIR/allowlist.json"
  info "$OWNER -> $MC_USER (Rückgängig: chown $(cut -d' ' -f1 "$BK/allowlist-owner-before.txt") '$MC_DIR/allowlist.json')"
else
  info "gehört bereits $MC_USER"
fi

# ---------------------------------------------------------------- M3
step "7/9 M3: Zugriffsrechte (ACL) für mcportal"
ACL_LOG="$DATA/acl-added.txt"
touch "$ACL_LOG"
d="$MC_DIR"
dirs=()
while [[ "$d" != "/" ]]; do d="$(dirname "$d")"; dirs+=("$d"); done
for d in "${dirs[@]}"; do
  if ! runuser -u mcportal -- test -x "$d"; then
    setfacl -m u:mcportal:x "$d"
    grep -qxF "$d" "$ACL_LOG" || echo "$d" >> "$ACL_LOG"
    info "Durchgangsrecht (x) auf $d"
  fi
done
for f in allowlist.json permissions.json; do
  setfacl -m u:mcportal:rw "$MC_DIR/$f"
  grep -qxF "$MC_DIR/$f" "$ACL_LOG" || echo "$MC_DIR/$f" >> "$ACL_LOG"
  info "Lesen/Schreiben auf $f"
done
runuser -u mcportal -- test -r "$MC_DIR/server.properties" || fail "mcportal kann server.properties nicht lesen"
runuser -u mcportal -- test -w "$MC_DIR/allowlist.json" || fail "mcportal kann allowlist.json nicht schreiben"
runuser -u mcportal -- test -w "$MC_DIR/permissions.json" || fail "mcportal kann permissions.json nicht schreiben"

# ---------------------------------------------------------------- S4
step "8/9 S4: Portal installieren ($APP) und Dienst starten"
install -d -m 755 -o root -g root "$APP"
rm -rf "$APP/app.new"
cp -r "$SRC/app" "$APP/app.new"
find "$APP/app.new" -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$APP/app" && mv "$APP/app.new" "$APP/app"
install -m 644 "$SRC/requirements.txt" "$APP/requirements.txt"
[[ -x "$APP/venv/bin/python" ]] || python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install --disable-pip-version-check -q -r "$APP/requirements.txt"
install -d -m 755 "$APP/bin"
install -m 755 "$SRC/deploy/mcportal-update-helper" "$APP/bin/mcportal-update-helper"
chown -R root:root "$APP"
chmod -R go-w "$APP"

# M4: update helper units (run as $MC_USER, started by the portal via polkit)
for action in apply rollback; do
  sed -e "s#@ACTION@#$action#g" -e "s#@MC_USER@#$MC_USER#" -e "s#@MC_DIR@#$MC_DIR#" \
      -e "s#@MC_PARENT@#$(dirname "$MC_DIR")#" \
      "$SRC/deploy/mcportal-update.service.in" > "/etc/systemd/system/mcportal-update-$action.service"
  info "/etc/systemd/system/mcportal-update-$action.service"
done

install -d -m 750 -o root -g mcportal "$ETC"
if [[ ! -f "$ETC/config.toml" ]]; then
  sed "s#@SERVER_DIR@#$MC_DIR#" "$SRC/config.example.toml" > "$ETC/config.toml"
  info "Konfiguration angelegt: $ETC/config.toml"
else
  info "Konfiguration vorhanden, unverändert: $ETC/config.toml"
fi
chown root:mcportal "$ETC/config.toml"; chmod 640 "$ETC/config.toml"

sed "s#@MC_DIR@#$MC_DIR#" "$SRC/deploy/mcportal.service.in" > /etc/systemd/system/mcportal.service
systemd-analyze verify /etc/systemd/system/mcportal.service /etc/systemd/system/mcportal-update-apply.service \
  /etc/systemd/system/mcportal-update-rollback.service 2>&1 | grep -v -e '^$' | sed 's/^/      /' || true
systemctl daemon-reload
systemctl enable mcportal.service >/dev/null 2>&1
systemctl restart mcportal.service

# ---------------------------------------------------------------- S5
step "9/9 S5: Firewall"
if ufw status 2>/dev/null | grep -q '^Status: active'; then
  ufw allow from "$LAN_CIDR" to any port "$PORT" proto tcp comment 'mcportal' >/dev/null
  info "ufw: Port $PORT/tcp aus $LAN_CIDR erlaubt"
else
  info "ufw nicht aktiv – nichts zu tun"
fi

# ---------------------------------------------------------------- Validate
step "Überprüfung"
ok=""
for i in $(seq 1 60); do
  if curl -s -m 2 -o /dev/null "http://127.0.0.1:$PORT/api/auth"; then ok=1; break; fi
  sleep 1
done
[[ -n "$ok" ]] || { journalctl -u mcportal -n 30 --no-pager; fail "Portal antwortet nicht (Log oben)"; }
info "Portal: $(curl -s "http://127.0.0.1:$PORT/api/status" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["status"], "| Version", d["version"], "| Whitelist", d["allowlist_count"], "| Konsole", d["console_available"])')"
LARAVEL_AFTER="$(curl -s -o /dev/null -m 10 -w '%{http_code}' http://127.0.0.1/ || true)"
info "Laravel: HTTP $LARAVEL_AFTER (vorher $LARAVEL_BEFORE)"
[[ "$LARAVEL_AFTER" == "$LARAVEL_BEFORE" ]] || printf '    \033[1;33mWARNUNG: Laravel-Antwort hat sich geändert!\033[0m\n'
info "Minecraft: $(systemctl is-active "$UNIT") (unverändert, kein Neustart)"

IP="$(hostname -I | awk '{print $1}')"
printf '\n\033[1;32mFertig.\033[0m  Portal: http://%s:%s\n' "$IP" "$PORT"
printf 'Nächster Schritt (wenn niemand spielt): sudo bash %s/deploy/m2-console.sh apply\n' "$SRC"
