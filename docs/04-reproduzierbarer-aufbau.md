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

- `world-pack.sh` läuft heute als `fred` (Besitzer der Welt) → muss als `minecraft` laufen
  (`sudo -u minecraft`, oder über die Update-Helfer-Unit).
- `install.sh`, `m2-console.sh`, Update-Helfer: nehmen Pfad und Benutzer schon aus der Unit; prüfen.
- Docs/Skill: Pfade `~/Downloads/…` durch `/opt/minecraft/bedrock` ersetzen.

## Umstieg am Stichtag (auf diesem Laptop)

```text
Vorher (Tage davor, ohne Ausfall):
  setup.sh --prepare     neues Programm, Konfiguration, Welt mit allen Packs in /opt/minecraft vorbereiten,
                         einmal mit anderen Ports probestarten (wie der Testserver), verify.sh, wieder stoppen

Stichtag (ca. 5 Minuten Ausfall):
  1. Testserver stoppen, Testinstallation komplett archivieren (bleibt liegen, wird nicht gelöscht)
  2. setup.sh            Unit auf /opt/minecraft umstellen, Portal neu ausrichten
  3. import-players.sh   Whitelist + Operatoren aus der Testinstallation
  4. Portal-Daten der Testphase archivieren (Statistik, Erfolge, Events, Karte, Versionshistorie)
  5. Start, verify.sh, Kartenlauf
Rückweg: alte Unit-Datei zurück, daemon-reload, Start – die Testinstallation ist unverändert da.
```

## Schritte

| Schritt | Inhalt |
|---|---|
| **R1** | `provision/` anlegen: Overrides, Haupt-Unit, `packs.list`, `server.conf.example` |
| **R2** | `setup.sh` mit `--prepare` (Probe-Installation in eigenem Ordner, andere Ports, eigener Benutzer) |
| **R3** | `verify.sh` und `import-players.sh` |
| **R4** | `world-pack.sh` & Co. für den Benutzer `minecraft`; Docs und Skill auf neue Pfade |
| **R5** | Probelauf auf dem Laptop parallel zum laufenden Testserver (`--prepare`), danach aufräumen |
| **R6** | Stichtag (mit dir zusammen) |

## Zu entscheiden

1. **Weltname und Servername** (Anzeige in der Serverliste).
2. **Seed:** zufällig oder ein bestimmter (z. B. vorher auf Chunkbase ausgesucht)?
3. **Spieleinstellungen:** wie heute (Überleben, Schwierigkeit „Einfach“, max. 10 Spieler, Cheats an)?
4. **Whitelist/Operatoren:** alle heutigen Einträge übernehmen?
5. **Portal-Daten der Testphase:** archivieren und bei 0 starten (Vorschlag – neue Welt, faire Erfolge), oder
   übernehmen? (Wegpunkte und Bau-Register liegen in der Welt und beginnen mit ihr ohnehin neu.)
6. **Automatische Events** ab dem ersten Tag an? (Vorschlag: ja)
7. **Termin** für den Umstieg.
