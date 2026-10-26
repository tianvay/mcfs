# Minecraft Family Portal – Analyse & Architekturvorschlag

Stand: 2026-10-25 · Server `mcserver` / `192.168.178.38` · Analyse rein lesend (Rohdaten: `analyse/report.txt`)

---

## 1. Ist-Zustand Minecraft Bedrock

| Punkt | Befund |
|---|---|
| Installationsverzeichnis | `/home/fred/Downloads/bedrock-server-1.21.51.02` |
| **Tatsächliche Version** | **1.26.51.1** (laut Server-Log beim Start). Der Verzeichnisname „1.21.51.02“ ist veraltet – am 20.09.2026 wurde ein neues Zip (`bedrock-server.zip`) über die alte Installation entpackt. |
| Vorherige Version | 1.21.124.2 (letzter Start mit dieser Version: 20.09.2026 13:16) |
| Letztes Update | 20.09.2026 ~13:20 (erster Start mit 1.26.51.1) |
| Startmechanismus | **systemd**: `/etc/systemd/system/minecraft-bedrock.service`, `User=fred`, `Restart=on-failure` |
| Autostart | ja (`enabled`, `WantedBy=multi-user.target`) |
| Läuft seit | 20.09.2026 14:05:29 (PID 114914, ~35 Tage) |
| Konsole (stdin) | **`/dev/null`** → aktuell können **keine Befehle** an den Server geschickt werden (kein `list`, kein `save`, kein sauberes `stop`). |
| Logausgabe | systemd-Journal (`journalctl -u minecraft-bedrock`), persistent seit 17.12.2024 |
| Welt | `worlds/Bedrock level` (104 MB) |
| Netzwerk | `transport=nethernet`, Port 19132 (TCP), LAN-Sichtbarkeit an |
| Allowlist | `allowlist.json` – 3 Einträge: `Steve`, `Alex`, `Sunny` (Letzterer ohne XUID = noch nie verbunden, normal) |
| ⚠ Allowlist-Besitzer | **`root:root`, Modus 664** – der Minecraft-Prozess (läuft als `fred`) kann die Datei **nicht** schreiben. In-Game-/Konsolenbefehle `allowlist add/remove` würden nicht dauerhaft gespeichert. |
| Operatoren | `permissions.json`: XUIDs von `Steve` und `Alex` = operator |
| `allow-list` in server.properties | `true` |
| Weitere Startmechanismen | keine (kein cron, kein screen/tmux, kein rc.local, kein Autostart-Script) |

**Spieler-Erkennung:** Bedrock hat **kein RCON**. Das klassische UDP-Query-Protokoll fällt mit `transport=nethernet` praktisch weg. Robuste offizielle Quellen sind:
1. Server-Log (Journal): `Player connected: <Name>, xuid: …` / `Player disconnected: …` → Echtzeit-Ereignisse.
2. Konsolenbefehl `list` → maßgebliche Gegenprobe (benötigt stdin-Zugang, siehe Änderung M2).

**Sonstige Beobachtungen (werden NICHT geändert, nur zur Kenntnis):**
- Verzeichnis `Downloads/` und Serververzeichnis haben Modus **777** (für jeden lokalen Benutzer beschreibbar).
- Im Serververzeichnis liegen Altlasten: `bedrock-server.zip` (95 MB), `xampp-linux-x64-8.2.12-0-installer.run` (160 MB), `wget-log*`.

## 2. Ist-Zustand Laravel & Umgebung

| Punkt | Befund |
|---|---|
| Laravel-Projekt (aktiv) | `/var/www/html/familyrecipes` (Owner `fred:fred`), DocumentRoot `…/public` |
| Zweite Kopie | `/opt/lampp/htdocs/familyrecipes` (nicht als DocumentRoot aktiv) |
| Webserver | **XAMPP-Apache** (`xampp.service`, läuft als root, `/opt/lampp`) |
| Datenbank | XAMPP-MySQL/MariaDB auf Port 3306 |
| System-Apache (`apache2`) | disabled / failed – unbenutzt |
| nginx, php-fpm, Docker, Supervisor | nicht vorhanden |
| PHP / Composer | 8.3.6 (CLI) / 2.7.1 |
| Node.js / npm | 18.19.1 / 9.2.0 |
| Python | 3.12.3 – **`python3-venv` fehlt** (kein `ensurepip`) |
| Hilfsscript | `~/bin/rezeptbuch-update` (gehört zum Rezeptbuch, wird nicht angefasst) |
| Firewall | **ufw aktiv** (Regeln ohne sudo nicht lesbar) |
| RAM / CPU / Disk | 3,7 GB (davon ~2 GB frei, 1,3 GB Swap belegt) / 2 Kerne / 81 GB frei |

**Belegte TCP-Ports:** 21 (FTP, XAMPP), 22 (SSH), 53 (lokal DNS), 80/443 (XAMPP-Apache → Laravel), 139/445 (Samba), 631 (CUPS, lokal), 3306 (MySQL), 19132 (Minecraft).
**Port 8080 ist frei** und kommt in keiner Apache-/XAMPP-Konfiguration vor.

**Konfliktbewertung:** Keine Konflikte, wenn das Portal
- einen eigenen Prozess auf Port 8080 nutzt (kein Apache-vHost, kein Reverse-Proxy),
- **nicht** PHP/Composer/Node verwendet (keine gemeinsamen Abhängigkeiten),
- **keine** Datenbank braucht (MySQL bleibt unberührt),
- unter einem **eigenen Linux-Benutzer** läuft. Wichtig: Läuft das Portal als `fred`, hätte es automatisch Schreibrechte auf das Laravel-Projekt (`familyrecipes` gehört `fred`, `storage/` ist 775). Deshalb eigener Benutzer.

---

## 3. Architekturvorschlag

### Technik
- **Python 3.12 (System) + venv** – kein Eingriff in PHP/Node/XAMPP.
- **FastAPI + Uvicorn** (im venv, nicht global): API + Auslieferung der Web-UI.
- **Server-Sent Events (SSE)** für Live-Status, Spielerliste und Konsole (einfacher und robuster als WebSocket, ideal für „Server → Browser“).
- **Frontend:** reines HTML/CSS/JavaScript, kein Build-Schritt, mobil-first.
- **Keine Datenbank:** Konfiguration als TOML, Aktionsprotokoll als JSON-Lines-Datei.

### Komponenten

```text
mcportal (eigener systemd-Dienst, User "mcportal", Port 8080)
│
├── web/                   UI (Dashboard, Whitelist, Server, später Konsole/Backups)
├── api/                   FastAPI-Routen, SSE-Stream, Eingabevalidierung
├── services/
│   ├── MinecraftService   Status, Spieler, start/stop/restart, sendCommand (nur Allowlist an Befehlen)
│   ├── AllowlistService   lesen, hinzufügen, entfernen (Backup + atomares Schreiben)
│   ├── BackupService      (Phase 2)
│   └── UpdateService      (Phase 3)
├── adapters/bedrock/      ← einzige Stelle mit Bedrock-Wissen
│   ├── systemd.py         systemctl start/stop/restart/show (feste Argumente, kein Shell)
│   ├── journal.py         Log lesen & folgen, Player connected/disconnected, Version
│   ├── console.py         Schreiben in die Konsolen-FIFO
│   └── files.py           allowlist.json, permissions.json, server.properties
└── audit.py               Aktionsprotokoll (/var/lib/mcportal/audit.jsonl)
```

Ändert sich später Pfad, Version oder Startmechanismus, wird nur `adapters/bedrock` bzw. die Konfiguration angepasst.

### Verzeichnisse (alle außerhalb von Laravel und außerhalb des Minecraft-Verzeichnisses)

```text
/opt/mcportal/            Programmcode + venv          (root:root, nur lesbar für mcportal)
/etc/mcportal/config.toml Konfiguration                (root:mcportal, 640)
/var/lib/mcportal/        Daten: audit.jsonl, backups/ (mcportal)
    └── backups/2026-10-25_14-30_pre_allowlist/ …
```

### Sicherheit & Rechte

| Was | Wie | Warum so |
|---|---|---|
| Portal-Prozess | System-User `mcportal`, ohne Login-Shell, ohne sudo | minimale Rechte, kein Zugriff auf Laravel |
| Start/Stop/Restart | **polkit-Regel**: `mcportal` darf *ausschließlich* `start/stop/restart` von `minecraft-bedrock.service` | kein `sudo`, kein Shell-Aufruf, genau eine Unit |
| Logs lesen | `mcportal` in Gruppe `systemd-journal` | offizieller Weg zum Journal-Lesen (Nebenwirkung: darf das gesamte System-Journal lesen, nicht schreiben) |
| Dateizugriff Minecraft | **ACLs** nur auf das Minecraft-Verzeichnis + „Durchgangsrecht“ (x) auf `/home/fred` und `~/Downloads` | `mcportal` sieht keine anderen Dateien in `/home/fred`; Laravel bleibt unerreichbar |
| Konsolenbefehle | nur feste Befehlsliste (`list`, `save hold/query/resume`, `say <Text>`, `allowlist …`), Spielernamen per Regex geprüft | keine beliebigen Befehle aus User-Input |
| Prozessaufrufe | immer `subprocess` mit Argumentliste, nie `shell=True` | keine Shell-Injection |
| Zugang | nur LAN: ufw-Regel 8080 nur für `192.168.178.0/24` | |

Optional (empfohlen): einfacher PIN/Passwort-Schutz für Start/Stop/Whitelist, damit Kinder im WLAN nicht versehentlich den Server stoppen. Lesender Zugriff (Dashboard) bleibt ohne Login.

---

## 4. Notwendige Änderungen

### 4a. Am Minecraft-Server (M1–M3)

**M1 – Besitzer von `allowlist.json` korrigieren**
1. *Was:* `root:root` → `fred:fred` (Inhalt bleibt unverändert).
2. *Warum:* Der Server (läuft als `fred`) muss die Datei bei `allowlist add/remove` speichern können; aktuell würde das scheitern.
3. *Dateien:* `…/allowlist.json`
4. *Backup:* `cp -a allowlist.json /var/lib/mcportal/backups/<zeit>_pre_portal_install/` (plus Gesamtsicherung, s. u.)
5. *Rückgängig:* `sudo chown root:root allowlist.json`

**M2 – Konsole & sauberes Stoppen (systemd-Ergänzung, Originaldatei bleibt unverändert)**
1. *Was:* Neue Datei `minecraft-bedrock.socket` stellt eine Befehls-FIFO `/run/minecraft-bedrock/console` bereit. Eine Ergänzungsdatei (Drop-in) verbindet diese FIFO mit stdin des Servers und setzt `ExecStop`, das `stop` in die Konsole schreibt und auf das saubere Beenden wartet (Timeout 60 s, danach normales SIGTERM durch systemd – **kein kill -9**).
2. *Warum:* Ohne stdin gibt es weder `list` (Spielerliste), `save`-Befehle für Backups, eine Web-Konsole noch einen garantiert sauberen Stop mit Welt-Speicherung.
3. *Dateien (neu):* `/etc/systemd/system/minecraft-bedrock.socket`, `/etc/systemd/system/minecraft-bedrock.service.d/10-portal.conf`. **`minecraft-bedrock.service` selbst wird nicht verändert.**
4. *Backup:* Kopie der Original-Unit + vollständige Sicherung von Welt, Allowlist, permissions.json und server.properties vor dem Neustart.
5. *Rückgängig:* beide Dateien löschen → `systemctl daemon-reload` → `systemctl restart minecraft-bedrock`. Danach ist exakt der heutige Zustand wiederhergestellt.
- **Erfordert einen einmaligen Neustart des Minecraft-Servers (~10 s Ausfall)** – zu einem Zeitpunkt, an dem niemand spielt.

**M3 – Leserechte für das Portal (ACL)**
1. *Was:* `setfacl`: `mcportal` erhält rwx auf das Minecraft-Verzeichnis (inkl. Default-ACL für neue Dateien) und nur `x` (Durchgang, kein Auflisten) auf `/home/fred` und `/home/fred/Downloads`.
2. *Warum:* Allowlist bearbeiten, Backups lesen, später Update – ohne dem Portal Zugriff auf den Rest von `fred` (inkl. Laravel) zu geben.
3. *Dateien:* nur ACL-Metadaten, keine Inhalte.
4. *Backup:* `getfacl -R` vorher in eine Datei sichern.
5. *Rückgängig:* `setfacl -R -x u:mcportal <verzeichnis>` bzw. `setfacl --restore=<sicherung>`

### 4b. System (S1–S5) – kein Einfluss auf Laravel/XAMPP

| # | Änderung | Auswirkung auf Laravel | Rückgängig |
|---|---|---|---|
| S1 | `apt install python3-venv` (Ubuntu-Paket, nur Python-Zusatz) | keine – XAMPP bringt eigenes PHP/MySQL mit, System-PHP unberührt | `apt remove python3-venv` |
| S2 | System-User `mcportal` anlegen (+ Gruppe `systemd-journal`) | keine | `userdel mcportal` |
| S3 | polkit-Regel `/etc/polkit-1/rules.d/50-mcportal.rules` | keine | Datei löschen |
| S4 | Dienst `/etc/systemd/system/mcportal.service`, Code in `/opt/mcportal`, Daten in `/var/lib/mcportal`, Konfig in `/etc/mcportal` | keine (eigener Prozess, eigener Port) | Dienst stoppen/deaktivieren, Verzeichnisse löschen |
| S5 | `ufw allow from 192.168.178.0/24 to any port 8080 proto tcp` | keine | `ufw delete …` |

Python-Pakete (`fastapi`, `uvicorn`) landen ausschließlich im venv unter `/opt/mcportal/venv`.

---

## 5. Installationsablauf (Phase 1)

```text
1. Inspect   – erneut prüfen: Server läuft, Port 8080 frei, keine Spieler online
2. Backup    – /var/lib/mcportal/backups/<zeit>_pre_portal_install/
               (Welt, allowlist.json, permissions.json, server.properties, Unit-Datei, ACLs)
3. Change    – S1–S5, M1, M3 (alles ohne Minecraft-Neustart)
4. Validate  – systemd-analyze verify, Portal startet, Dashboard lädt, Laravel erreichbar (HTTP 200 auf Port 80)
5. Change    – M2 (Socket + Drop-in), dann Minecraft-Neustart
6. Verify    – Server „Server started.“ im Log, Port 19132 offen, `list` funktioniert, Welt geladen
   Fehler?   → Drop-in/Socket entfernen, daemon-reload, Restart, Bericht
```

Jeder Schritt mit sudo wird dir vorher als Befehl gezeigt; sudo-Befehle führst du selbst aus (oder gibst sie einzeln frei).

## 6. Phasen

- **Phase 1 (MVP):** Dashboard (Status, Version, Uptime, letzter Start, letztes Update, Spieler online live per SSE, Anzahl Whitelist), Start/Stop/Restart, Allowlist anzeigen/hinzufügen/entfernen (mit Backup), Aktionsprotokoll. Mobil-tauglich von Anfang an.
- **Phase 2:** Backup-System (manuell + automatisch, „keep last N“, Welt-Backup im laufenden Betrieb via `save hold/query/resume`), Web-Konsole mit Befehlsliste, Log-Ansicht.
- **Phase 3:** Auto-Update. Versionsprüfung über die offizielle Download-API von minecraft.net (`serverBedrockLinux`), Download nur von `minecraft.net`-Hosts, Prüfung des Zips (Integrität, erwartete Dateien – Mojang veröffentlicht leider keine Prüfsummen), Update **in ein neues Verzeichnis** statt Überschreiben, Übernahme von Welt/Allowlist/permissions/server.properties, Umschalten, Gesundheitscheck, automatischer Rollback auf das alte Verzeichnis bei Fehler. Dabei schlage ich vor, die Installation nach `/opt/minecraft-bedrock/` (versionierte Unterordner) umzuziehen – das entscheiden wir separat vor Phase 3.

## 7. Offene Entscheidungen

1. Freigabe von S1–S5 und M1–M3 wie beschrieben.
2. Zeitpunkt für den einmaligen Minecraft-Neustart (M2).
3. PIN-Schutz für schreibende Aktionen: ja/nein.
