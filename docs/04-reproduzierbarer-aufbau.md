# Reproduzierbarer Aufbau – Plan für den echten Server

Stand: 2026-10-26 (abends, nach Events-Paket 3 + 1.4.0) · Entscheidungen bisher: **derselbe Laptop**,
**neue Welt**, **sauberer Aufbau unter `/opt/minecraft`**

## Ziel

Ein Ablauf richtet den kompletten Server so ein, wie er in der Testphase entstanden ist – auf diesem Laptop zum
Start des echten Servers, und genauso auf jedem frischen Ubuntu/Linux Mint. Alles Wissen aus der Testphase steckt
in Scripts, nicht in Handarbeit oder im Chatverlauf.

## Was heute dazugehört (Bestand 26.10.)

| Teil | Wo heute | Herkunft |
|---|---|---|
| Bedrock-Server 1.26.52.3 | `~/Downloads/bedrock-server-1.21.51.02` (Benutzer `fred`) | von Hand entpackt |
| systemd `minecraft-bedrock.service` | `/etc/systemd/system/` | **von Hand geschrieben, nicht im Repo** |
| Konsole + sauberer Stopp (M2) | `minecraft-bedrock.socket`, `…service.d/10-portal.conf` | Repo (`m2-console.sh`) |
| Startprüfung (M8) | `…service.d/20-startcheck.conf`, `/opt/mcportal/bin/mc-start-check` | Repo (`install.sh`) |
| Kein Ruhezustand bei zugeklapptem Deckel | logind, Sleep-Targets maskiert | Repo (`no-suspend.sh`) |
| Portal (Übersicht, Whitelist, Statistik, Events, Karte, Server) | `/opt/mcportal`, `/etc/mcportal`, `/var/lib/mcportal` | Repo (`install.sh`) |
| Update per Knopf, Helfer-Units, polkit | `mcportal-update*`, `50-mcportal.rules` | Repo |
| `server.properties` | 4 Abweichungen vom Mojang-Standard: `allow-cheats=true`, `content-log-console-output-enabled=true`, `content-log-level=warning`, `texturepack-required=true` | von Hand / M5 / M8 |
| Behavior Packs | Statistik 2.0.0, Wegpunkte 1.4.0, Events 1.4.0 (mit eigenen Mobs), Erfolge 1.4.0 | Repo (`world-pack.sh`) |
| Resource Packs | Wegpunkte-Grafik 1.0.0, Events-Grafik 1.1.0 (Bosse, Hexen, Spuk-Nebel) | Repo (`world-pack.sh`) |
| Whitelist, Operatoren | `allowlist.json`, `permissions.json` | im Portal gepflegt – **personenbezogen, nie im Repo** |
| Spieldaten | Welt (inkl. Wegpunkte, Erfolge, Bau-Register in der Welt), Portal-Daten (Statistik, Erfolge, Events, Karte) | entstehen beim Spielen |

## Was heute nicht reproduzierbar ist

| Heute (Testphase) | Problem |
|---|---|
| Server in `~/Downloads/…`, Ordner 777, Teile gehörten root | hat das erste Update scheitern lassen |
| Minecraft läuft als `fred` | hätte Zugriff auf alles von fred (inkl. Laravel-Projekt) |
| Haupt-Unit von Hand, nicht im Repo | geht beim Neuaufsetzen verloren |
| Packs nacheinander mit Neustarts eingesetzt | Reihenfolge und Versionen stehen nur in den Docs |
| `server.properties`-Abweichungen | nirgends als Datei festgehalten |

## Ziel-Aufbau

```text
/opt/minecraft/                      Benutzer "minecraft" (Systembenutzer, keine Anmeldung)
└── bedrock/                         Serverprogramm + Welt + Konfiguration (750, nur minecraft)
    ├── worlds/<Weltname>/           neue Welt, alle Packs von Anfang an drin
    ├── server.properties            Mojang-Standard + provision/server.properties.overrides
    ├── allowlist.json, permissions.json   (personenbezogen – nie im Repo)
/etc/systemd/system/minecraft-bedrock.service   aus dem Repo (User=minecraft, Sandbox)
            + .socket, .service.d/10-portal.conf, 20-startcheck.conf   (wie heute)
/opt/mcportal, /var/lib/mcportal, /etc/mcportal  Portal wie heute
```

Der Unit-Name bleibt `minecraft-bedrock.service` – Portal, polkit-Regel, Startprüfung und Scripts funktionieren
unverändert.

## Neue Dateien im Repo

```text
provision/
├── server.conf.example          Einstellungen: Weltname, Servername, Seed, Schwierigkeit, max. Spieler, Ports
├── server.properties.overrides  die 4 Abweichungen + Werte aus server.conf
├── minecraft-bedrock.service.in Haupt-Unit (User=minecraft, Sandbox, Restart=on-failure)
├── packs.list                   welche Packs in welcher Version in die neue Welt kommen (Reihenfolge!)
├── setup.sh                     alles in einem, idempotent (mehrfach ausführbar); --prepare für den Probelauf
├── import-players.sh            Whitelist + Operatoren aus der Testinstallation übernehmen
└── verify.sh                    Abnahmetest (siehe unten)
```

**`setup.sh` macht der Reihe nach:**

1. **Prüfen:** Ports frei bzw. von der eigenen Installation belegt, Speicher, Laravel-Antwort merken.
2. **Benutzer und Ordner:** `minecraft`, `/opt/minecraft/bedrock` mit sauberen Rechten (nichts 777, nichts root).
3. **Serverprogramm:** neueste offizielle Version mit derselben Prüfung wie der Update-Knopf (nur minecraft.net,
   Zip-Prüfung, keine `../`-Pfade).
4. **Konfiguration:** `server.properties` aus dem Zip + Overrides.
5. **Alle Packs** aus `packs.list` in die neue Welt, **bevor sie das erste Mal startet** (kein Neustart je Pack);
   `world_behavior_packs.json` / `world_resource_packs.json` mit den exakten Manifest-Versionen.
6. **systemd:** Haupt-Unit + Konsole (M2) + Startprüfung (M8); `no-suspend.sh`.
7. **Portal:** das bestehende `install.sh` – zeigt automatisch auf den neuen Ordner.
8. **Start + `verify.sh`**, dann ein erster Kartenlauf (Bau-Register beginnt leer – neue Welt, keine Bauten).

**`verify.sh` prüft:** beide Dienste aktiv, Spieler-Port 19132 offen, Konsole erreichbar, alle Packs melden sich
(„started“-Zeilen, richtige Versionen), keine Script-/Inhaltsfehler, Portal antwortet, Update-Prüfung geht,
Laravel antwortet wie vorher, Rechte (kein 777, nichts root unter `/opt/minecraft`).

## Anpassungen an bestehenden Scripts

Umgesetzt in R4 (siehe unten). Die Docs 01–11 beschreiben die Testphase und bleiben, wie sie sind. Angepasst sind
die Anleitungen, nach denen gearbeitet wird (Skill, dieses Dokument).

## R4 – gebaut

- **Lesezugriff des Portals (wichtigster Fund):** Das Portal liest den ganzen Serverordner: für die Karte, den Seed
  und die Sicherung vor einem Update (`tar` als `mcportal`). Das ging bisher nur, weil der Testordner für alle
  lesbar ist. Unter `/opt/minecraft/bedrock` (750, Server mit `UMask 0027`) wären Karte, Seed und Update-Sicherung
  ausgefallen.
  - `install.sh` (M3) gibt `mcportal` jetzt rekursiv Lesezugriff und setzt eine **Default-ACL**, damit auch Dateien
    lesbar sind, die der Server später anlegt. „Andere“ bekommen weiter nichts.
  - Das passiert **nur, wenn etwas nicht lesbar ist**; im Testordner ist alles lesbar, dort ändert sich nichts.
  - `install.sh` bricht ab, wenn danach noch etwas nicht lesbar ist. `uninstall.sh` entfernt auch die rekursiven
    Einträge.
- **`world-pack.sh`** läuft als Benutzer der Unit (heute `fred`, unverändert) **oder mit sudo**. Das ist später
  nötig, weil `minecraft` das Repo in `/home/fred` nicht lesen kann. Mit sudo gehört alles, was es schreibt,
  danach `minecraft`. Sicherungen liegen im Home des Minecraft-Benutzers: heute `~fred/mcportal-backups` wie bisher,
  später `/opt/minecraft/mcportal-backups`. `import-players.sh` sichert an dieselbe Stelle.
- **Unverändert passend:** `m2-console.sh`, die Update-Helfer-Units, `mc-start-check` und `no-suspend.sh` nehmen
  Pfad und Benutzer schon aus der Unit bzw. sind pfadunabhängig.
  - Der Update-Helfer darf `/opt/minecraft` schreiben (`MC_PARENT`); dort entstehen beim Rollback
    `bedrock.failed-…`.
  - `mc-start-check` prüft fest die Ports 19132/19133; das passt, solange `server.conf` die Standard-Ports behält.
- **Skill:** Abschnitt „Install into the world“ beschreibt beide Phasen. Nach dem Umstieg braucht `world-pack.sh`
  sudo, Packs installiert dann der Admin mit dem angegebenen Befehl.
- **Geprüft:** Syntax aller Scripts, `world-pack.sh status` als `fred` wie vorher, Testordner vollständig lesbar
  (die neue ACL-Stelle greift dort nicht). Die sudo-Wege (ACL, `chown`) laufen in R5.
- **Für R5 vorgemerkt:** Die neue Haupt-Unit selbst (Sandbox) einmal unter einem eigenen Namen auf den Probe-Ports
  starten, statt nur das Programm. Sonst würde sie erst am Stichtag zum ersten Mal laufen.

## R1 – gebaut

- `provision/server.conf.example` – alle Einstellungen des echten Servers (Namen, Seed, Spiel, Ports, Benutzer,
  Ordner); Werte wie heute, nur der Servername ist ein Platzhalter (Entscheidung offen).
- `provision/server.properties.overrides` – die 4 festen Abweichungen + Platzhalter aus `server.conf`.
- `provision/packs.list` – die 6 Packs in der Reihenfolge der heutigen Welt; Versionen kommen immer aus den Manifests.
- `provision/minecraft-bedrock.service.in` – Haupt-Unit als Benutzer `minecraft` mit Sandbox (schreibt nur den
  eigenen Ordner; Netz nur IPv4/IPv6/Unix/Netlink). Die Drop-ins für Konsole und Startprüfung bleiben getrennt.
- `provision/properties.py` – prüft `server.conf` streng (jeder Wert landet in einer Unit bzw. in
  `server.properties`), setzt die Abweichungen in Mojangs Datei (Kommentare und Reihenfolge bleiben) und füllt
  Vorlagen; unbekannte Platzhalter sind ein Fehler.
- **Geprüft:** 4 Tests (`python -m unittest discover -s provision/tests` in `mcportal/`): gültige/ungültige Einstellungen,
  Zusammenführen, Unit. Auf dem Laptop: Mojangs `server.properties` aus dem Zip + heutige Werte ergibt **genau** die
  heutige `server.properties`; die erzeugte Unit besteht `systemd-analyze verify` (bis auf das noch fehlende
  Serverprogramm am Zielort).

## R2 – gebaut

- `provision/` liegt jetzt in `mcportal/provision/` – neben `deploy/`, damit die eine Kopie `~/mcportal-src` alles
  enthält.
- `provision/fetch_server.py` – lädt die neueste offizielle Version mit dem unveränderten `release.py` des Portals
  (dieselben Prüfungen wie der Update-Knopf), nur Python-Standardbibliothek.
- `provision/setup.sh --prepare [--conf DATEI]` (mit sudo) – Prüfungen (Werkzeuge, ≥ 2 GB frei, Probe-Ports frei,
  Laravel-Antwort als Vergleich) → Systembenutzer `minecraft` → Serverprogramm nach `/opt/minecraft/bedrock` →
  `server.properties` + Overrides → alle Packs aus `packs.list` in `worlds/<Weltname>/` (noch **ohne** Welt) →
  Probestart in einer Kopie `/opt/minecraft/probe` auf Ports 19160/19161 ohne LAN als `minecraft`: jedes Behavior
  Pack muss im „Pack Stack“ mit seiner Version stehen und seine „started“-Zeile schreiben, keine Script-/Inhalts-
  fehler; danach Stopp und Kopie löschen. Am Ende: Laravel-Antwort unverändert, unter `/opt/minecraft` gehört alles
  `minecraft`, nichts ist für alle schreibbar.
- Fasst **nicht** an: systemd-Units, Testserver, Portal, Laravel. Mehrfach ausführbar (Programm und eine vorhandene
  Welt bleiben).
- **Geprüft** (als `fred`, ohne Systemänderung): Download 1.26.52.3 (319 MB, Rechte 755/644); dieselben Schritte in
  einem Wegwerf-Ordner auf 19160/19161 – Bedrock übernimmt die vorab eingetragenen Packs beim Anlegen der Welt, alle
  4 Behavior Packs melden sich, keine Fehler. Das Log enthält ein NUL-Byte → `grep -a`. Der Lauf mit `sudo`
  (Benutzer, `/opt/minecraft`) ist R5.

## R3 – gebaut

- `provision/lib.sh` – Gemeinsames für die drei Scripts: Einstellungen laden, `packs.list` lesen, erwartete
  Log-Zeilen je Pack, Fehlerfilter. `setup.sh` nutzt es jetzt auch.
- `provision/verify.sh [--conf DATEI] [--laravel CODE]` – Abnahmetest, **ändert nichts**. Er prüft die Installation,
  auf die die Unit zeigt:
  - **Dienste:** beide Dienste und die Konsole aktiv, Spieler-Port offen. Bedrock 1.26 lauscht per **TCP** auf
    19132, deshalb prüft er TCP und UDP.
  - **Packs:** Jedes Pack aus `packs.list` hat in der Welt die Repo-Version, steht in `world_*_packs.json` und hat
    sich beim **letzten Start** gemeldet. Gelesen wird das Log genau dieses Laufs (`_SYSTEMD_INVOCATION_ID`).
  - **Fehler:** Script- und Pack-Fehler zählen als FEHLER. Meldungen von Minecraft selbst über eine alte Welt
    erscheinen nur als HINWEIS.
  - **Portal:** antwortet, die Update-Prüfung geht, Laravel antwortet wie vorher.
  - **Rechte:** nichts unter dem Ordner ist für alle schreibbar, nichts gehört root. Mit sudo zusätzlich: Das
    Portal darf `allowlist.json` und `permissions.json` schreiben und die Welt lesen (Karte, Seed).
  - Mit `--conf` muss die Unit außerdem auf `MC_DIR` und `MC_USER` zeigen (nach dem Umstieg).
- `provision/import-players.sh --from <alter Ordner>` mit sudo – übernimmt Whitelist und Operatoren in `MC_DIR`.
  - Läuft nur, wenn dort kein Minecraft läuft. Vorher sichert er die Zieldateien nach
    `/opt/minecraft/mcportal-backups/<Zeit>_pre_import-players/`.
  - Einträge im Ziel bleiben, beim selben Spieler (XUID, sonst Name) gewinnt die Quelle.
  - Prüft streng: Namen, XUIDs nur Ziffern, Rechte nur operator/member/visitor. Er schreibt im Format des Servers
    und gibt **nur Anzahlen** aus.
  - Die Logik steckt in `provision/players.py` mit 6 Tests.
- **Geprüft:**
  - **Tests:** 10 Tests in `provision/tests` grün.
  - **`verify.sh` als `fred` gegen den Testserver:** alles OK bis auf einen echten Befund, den 777-Ordner der
    Testinstallation (verschwindet mit `/opt/minecraft`). Die 5 Minecraft-Meldungen über die alte 1.21-Welt
    erscheinen als HINWEIS; die neue Welt im Probestart hatte keine.
  - **`players.py import`** mit Kopien der echten Dateien in einen Wegwerf-Ordner: inhaltlich identisch (3 Einträge,
    2 Operatoren), ein zweiter Lauf ändert nichts.
  - **Noch offen (R5):** die sudo-Teile.

## R5 – Probelauf (26.10., 22:13–22:15)

- **Vorher umgebaut:** Der Probestart läuft über die **echte Haupt-Unit**. Sie wird als Laufzeit-Unit
  `mcportal-probe.service` in `/run` gerendert, mit `MC_DIR=/opt/minecraft/probe`, `Restart=no` und ohne die
  Drop-ins M2/M8. So hat die Unit mit Sandbox, Benutzer und `UMask` vor dem Stichtag schon einmal wirklich
  gestartet.
- **`sudo setup.sh --prepare`** (Beispiel-Einstellungen, Namen und Seed noch offen):
  - Benutzer `minecraft` (uid 994) angelegt, ohne Anmeldung, Home `/opt/minecraft`.
  - Bedrock 1.26.52.3 nach `/opt/minecraft/bedrock`, ausgegeben „Vorbereitet.“
  - **Probe-Unit:** In 5 s gestartet, alle 4 Behavior Packs im „Pack Stack“ mit ihren Versionen und mit
    „started“, keine Fehler. Sie hat sauber gestoppt (220 MB Speicher, 6 s Rechenzeit) und ist danach
    entfernt.
  - Rechte unter `/opt/minecraft` sauber. Laravel vorher und nachher HTTP 302. Testserver und Portal liefen
    durchgehend.
- **`sudo verify.sh --laravel 302`** gegen den Testserver: alles OK, auch alle Zugriffe des Portals. Einziger
  FEHLER ist der bekannte 777-Testordner. Die 5 Meldungen von Minecraft über die alte Welt erscheinen als HINWEIS.
- **Bleibt bis zum Stichtag liegen:** `/opt/minecraft/bedrock` (vorbereitet, ohne Welt) und der Benutzer
  `minecraft`. `setup.sh` behält das Programm bei einem zweiten Lauf, ein Update geht danach über den Knopf.
  - Rückgängig: `sudo rm -rf /opt/minecraft` und `sudo userdel minecraft`.
- **Noch nicht mit sudo gelaufen**, erst am Stichtag:
  - `import-players.sh`: Die Logik ist mit Kopien der echten Dateien geprüft.
  - Die neue ACL-Stelle in `install.sh`: Sie bricht ab, wenn das Portal danach etwas nicht lesen kann.
  - `world-pack.sh` mit sudo.

## R6 (Teil 1) – Umstellung gebaut: `setup.sh --switch` / `--switch-back`

- **Fund beim Bauen – die Startprüfung (M8) wäre am Stichtag gescheitert:** `mc-start-check post` liest die
  Zeilen des Servers mit `journalctl`.
  - Das ging bisher nur, weil `fred` in der Gruppe `adm` ist. Der Systembenutzer `minecraft` darf das Journal
    nicht lesen. Die Prüfung hätte „Server started.“ nie gesehen, den Server nach 150 s gestoppt, und systemd
    hätte es 4-mal versucht und dann aufgegeben.
  - Jetzt läuft `post` als root (`ExecStartPost=+…` in `20-startcheck.conf`); `pre` läuft weiter als Benutzer.
  - Der Spieler-Port kommt aus `MC_PORTS` (Standard 19132 19133) statt fest 19132.
  - Gilt für den Testserver ab dem nächsten `install.sh` und dem nächsten Start; geprüft: `post` erkennt den
    laufenden Testserver.
- **Probestart jetzt mit der vollständigen Kette:** Unit, Konsolen-Socket, `10-portal.conf`
  (Stopp über `stop`) und `20-startcheck.conf`, als Laufzeit-Units `mcportal-probe.service/.socket` in `/run`.
  - **Bedingungen:** Die Startprüfung muss bestehen, alle Packs müssen sich melden, das Log muss „Quit correctly“
    zeigen (sauber über die Konsole gestoppt), keine Fehler.
  - **Startprüfung aus dem Repo:** Sie wird mit `bash` aus `/run` ausgeführt (`/run` ist noexec) – so wird auch
    eine noch nicht installierte Version geprüft.
  - **Geprüft als `fred`:** gerenderte Units mit Drop-ins bestehen `systemd-analyze verify`, `Restart=no` aus dem
    Probe-Drop-in gewinnt.
- **`install.sh` richtet das Portal nach der Unit aus:** Steht in `/etc/mcportal/config.toml` ein anderer
  `server_dir`, wird nur diese Zeile angepasst (PIN usw. bleiben); vorher wird die Datei gesichert.
- **`sudo setup.sh --switch [--import-players]`:**
  - **Prüft vorher:** echte `/etc/mcportal/server.conf` statt Beispiel, niemand online, die Welt gibt es noch
    nicht, die Unit zeigt noch auf den Testordner.
  - **Ohne Ausfall:** die Vorbereitung mit den endgültigen Einstellungen, inklusive Probestart.
  - **Wiederherstellungspunkt** in `/var/backups/mcportal-switch/<Zeit>/` (nur root – `minecraft` darf nicht
    ändern können, was root später zurückspielt): alte Unit, Socket, Portal-Konfiguration.
  - **Ab hier ca. 5 Minuten ohne Minecraft:**
    1. Testserver stoppen. Mit `--import-players` Whitelist und Operatoren übernehmen.
    2. Portal-Daten der Testphase nach `/var/lib/mcportal/archive/<Zeit>_testphase/` verschieben: Statistik,
       Erfolge, Events, Wegpunkte, Karte **und die Update-Sicherungen**. Sonst würde der Rollback-Knopf den
       Testserver in den neuen Ordner zurückspielen.
    3. Haupt-Unit und Socket für `minecraft` schreiben.
    4. `install.sh` ausführen: ACLs, Konfiguration, Helfer-Units, Startprüfung.
    5. Start – die Welt entsteht jetzt mit dem Seed aus `server.conf`.
    6. `verify.sh --conf … --laravel …`.
  - **Bei einem Fehler** ab dem Stopp stellt das Script automatisch zurück.
- **`sudo setup.sh --switch-back`:**
  - Nimmt den neuesten unbenutzten Wiederherstellungspunkt und stellt damit Unit und Socket zurück.
  - Holt die Portal-Daten der Testphase zurück; die des echten Servers kommen nach `…_after-switch/`.
  - Danach `install.sh`, Start und `verify.sh`.
  - Der Testordner selbst wird nie angefasst.
- **Bleiben bei der Umstellung:** Versionshistorie, Protokoll, offene Operator-/Überleben-Aufträge, PIN.

## Umstieg am Stichtag (auf diesem Laptop)

```text
Vorher (ohne Ausfall):
  sudo bash ~/mcportal-src/deploy/install.sh               neue Startprüfung auch für den Testserver
  sudo bash ~/mcportal-src/provision/setup.sh --prepare    Probestart mit Konsole + Startprüfung
  /etc/mcportal/server.conf anlegen (aus provision/server.conf.example) mit den Entscheidungen

Stichtag (ca. 5 Minuten Ausfall, niemand online):
  sudo bash ~/mcportal-src/provision/setup.sh --switch [--import-players]
  danach: Kartenlauf im Portal
Rückweg: sudo bash ~/mcportal-src/provision/setup.sh --switch-back – die Testinstallation ist unverändert da.
```

## Schritte

| Schritt | Inhalt |
|---|---|
| **R1** | `provision/` anlegen: Overrides, Haupt-Unit, `packs.list`, `server.conf.example` |
| **R2** | `setup.sh` mit `--prepare` (Probe-Installation in eigenem Ordner, andere Ports, eigener Benutzer) |
| **R3** | `verify.sh` und `import-players.sh` |
| **R4** | `world-pack.sh` & Co. für den Benutzer `minecraft`; Docs und Skill auf neue Pfade |
| **R5** | Probelauf auf dem Laptop parallel zum laufenden Testserver (`--prepare`), danach aufräumen |
| **R6** | `--switch` / `--switch-back` (gebaut), dann Stichtag (mit dir zusammen) |

## Zu entscheiden

1. **Weltname und Servername** (Anzeige in der Serverliste).
2. **Seed:** zufällig oder ein bestimmter (z. B. vorher auf Chunkbase ausgesucht)?
3. **Spieleinstellungen:** wie heute (Überleben, Schwierigkeit „Einfach“, max. 10 Spieler, Cheats an)?
4. **Whitelist/Operatoren:** alle heutigen Einträge übernehmen?
5. **Portal-Daten der Testphase:** archivieren und bei 0 starten (Vorschlag – neue Welt, faire Erfolge), oder
   übernehmen? (Wegpunkte und Bau-Register liegen in der Welt und beginnen mit ihr ohnehin neu.)
6. **Automatische Events** ab dem ersten Tag an? (Vorschlag: ja)
7. **Termin** für den Umstieg.
