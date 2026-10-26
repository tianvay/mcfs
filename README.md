# mcfs – Minecraft Family Server

Self-hosted Minecraft-Bedrock-Server fürs Heimnetz mit einem kleinen Webportal
(`http://<server>:8080`): Status, Spieler online, Start/Stop, Whitelist mit Operator-Status,
Update per Knopfdruck mit Backup und Rollback, Block-Statistik pro Spieler, Weltkarte.

> Stand: Testphase auf einem Linux-Mint-Laptop. Der eigentliche Server folgt.

## Inhalt

| Pfad | Was |
|---|---|
| [`mcportal/`](mcportal/) | Webportal (Python/FastAPI), Installations- und Änderungs-Scripts, Tests – [README](mcportal/README.md) |
| [`mcportal/minecraft-pack/`](mcportal/minecraft-pack/) | Behavior Packs: Statistik, Erfolge, Wegpunkte (+ Grafik-Pack) |
| [`docs/`](docs/) | Analyse, Architektur, Änderungen M1–M9, To-dos |
| [`analyse/inspect.sh`](analyse/inspect.sh) | Read-only Bestandsaufnahme eines Servers |
| [`.claude/skills/bedrock-behavior-pack/`](.claude/skills/bedrock-behavior-pack/) | Skill für Claude Code: Behavior Packs für diesen Server bauen, testen, installieren und ans Portal anbinden |

## Dokumentation

1. [Analyse & Architektur](docs/01-analyse-und-architektur.md) – Ausgangslage, Rechtekonzept, M1–M3
2. [Update per Knopfdruck](docs/02-update-per-knopfdruck.md) – Ablauf, geschützte Dateien, M4
3. [Statistik](docs/03-block-statistik.md) – Behavior Pack, M5/M6
4. [Reproduzierbarer Aufbau](docs/04-reproduzierbarer-aufbau.md) – Plan für den echten Server
5. [Erfolge](docs/05-erfolge.md) – eigene Achievements mit Nachricht im Spiel, M7
6. [Zuverlässiger Start & Cheats](docs/06-zuverlaessiger-start.md) – Startprüfung M8
7. [Wegpunkte](docs/07-wegpunkte.md) – craften, bauen, `/warp`, M9
8. [Weltkarte](docs/08-karte.md) – eigener Renderer, Kacheln, Tab „Karte“, M10
8. [To-dos](docs/TODO.md)

## Grundsätze

- Das Portal läuft als eigener Benutzer `mcportal`, ohne sudo und ohne Shell-Aufrufe aus Benutzereingaben.
- Privilegierte Aktionen nur über polkit für genau benannte systemd-Units.
- Welt, `allowlist.json`, `permissions.json`, `server.properties` werden nie blind überschrieben;
  jede Änderung wird vorher gesichert.
- Jede Änderung an der Minecraft-Installation (M1–M9) ist dokumentiert: was, warum, welche Dateien,
  Sicherung, Rückweg.
