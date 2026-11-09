# mcfs – Minecraft Family Server

Self-hosted Minecraft-Bedrock-Server fürs Heimnetz mit einem kleinen Webportal
(`http://<server>:8080`): Status, Spieler online, Start/Stop, Whitelist mit Operator-Status,
Update per Knopfdruck mit Backup und Rollback, Block-Statistik pro Spieler, Weltkarte.

> Stand: läuft auf einem Linux-Mint-Laptop. Ein frischer Ubuntu-Server lässt sich mit einem Befehl genauso
> einrichten (siehe [Installation](#installation)).

## Inhalt

| Pfad | Was |
|---|---|
| [`mcportal/`](mcportal/) | Webportal (Python/FastAPI), Installations- und Änderungs-Scripts, Tests – [README](mcportal/README.md) |
| [`mcportal/minecraft-pack/`](mcportal/minecraft-pack/) | Behavior Packs: Statistik, Erfolge, Wegpunkte (+ Grafik-Pack) |
| [`docs/`](docs/) | Analyse, Architektur, Änderungen M1–M9, To-dos |
| [`analyse/inspect.sh`](analyse/inspect.sh) | Read-only Bestandsaufnahme eines Servers |
| [`.claude/skills/bedrock-behavior-pack/`](.claude/skills/bedrock-behavior-pack/) | Skill für Claude Code: Behavior Packs für diesen Server bauen, testen, installieren und ans Portal anbinden |

## Installation

Auf einem frischen **Ubuntu 24.04** (oder neuer, auch Linux Mint 22+, 64 Bit x86) im Terminal diese eine Zeile
ausführen:

```bash
sudo apt-get update && sudo apt-get install -y git && { git clone https://github.com/tianvay/mcfs.git ~/mcfs || git -C ~/mcfs pull; } && sudo bash ~/mcfs/mcportal/provision/setup.sh --install
```

Das Script fragt nach **Servername**, **Weltname**, **Seed** und der **Höchstzahl Spieler**. Mit Enter gilt der
Vorschlag: „Family and Friends“, „FAF“, ein zufälliger Seed und 10 Spieler. Am Ende fragt es nach dem **Admin-Passwort** fürs Portal.

Danach läuft der neueste Bedrock-Server als Benutzer `minecraft` mit allen Packs (Statistik, Wegpunkte, Events,
Erfolge, Spawnfackel, Blaupause), dazu das Portal unter `http://<IP des Servers>:8080`. Beide starten beim
Hochfahren von selbst. Im Portal lassen sich die Erweiterungen einzeln abschalten (Tab „Funktionen“), bis hin
zu reinem Vanilla-Minecraft mit Statistik und Erfolgen.

Details und Optionen: [Installation auf einem frischen Server](docs/15-installation.md).

## Dokumentation

1. [Analyse & Architektur](docs/01-analyse-und-architektur.md) – Ausgangslage, Rechtekonzept, M1–M3
2. [Update per Knopfdruck](docs/02-update-per-knopfdruck.md) – Ablauf, geschützte Dateien, M4
3. [Statistik](docs/03-block-statistik.md) – Behavior Pack, M5/M6
4. [Reproduzierbarer Aufbau](docs/04-reproduzierbarer-aufbau.md) – Plan für den echten Server
5. [Erfolge](docs/05-erfolge.md) – eigene Achievements mit Nachricht im Spiel, M7
6. [Zuverlässiger Start & Cheats](docs/06-zuverlaessiger-start.md) – Startprüfung M8
7. [Wegpunkte](docs/07-wegpunkte.md) – craften, bauen, `/warp`, M9
8. [Weltkarte](docs/08-karte.md) – eigener Renderer, Kacheln, Tab „Karte“, M10
9. [Timed Events](docs/09-events.md) – Paket 1: Mining Rush, Unwetter, Glückstag, M11
10. [Timed Events Paket 2](docs/10-events-paket2.md) – Nachtgefahren: Zombie-Invasion, Blutmond, Kopfgeld-Boss, M12
11. [Timed Events Paket 3](docs/11-events-paket3.md) – Meteorit, Sternschnuppen, Schatzsuche, Spukort, Meta-Erfolge, M13
12. [Zugang von außen](docs/12-zugang-von-aussen.md) – NetherNet, Portfreigaben, öffentliche IPv4
13. [Spawnfackel](docs/13-spawnfackel.md) – roter Schleier, wo nachts Monster spawnen können, M14
14. [Blaupause](docs/14-blaupause.md) – Bereiche speichern und einmal einsetzen, M15
15. [Installation auf einem frischen Server](docs/15-installation.md) – ein Befehl, eigener Seed, M16
16. [Funktionen ein- und ausschalten](docs/16-funktionen-schalten.md) – Packs im Portal, auch reines Vanilla, M17
17. [Wie oft kommen Events?](docs/17-event-haeufigkeit.md) – Schieberegler 1–4 Stunden gemeinsamer Spielzeit, M18
18. [To-dos](docs/TODO.md)

## Grundsätze

- Das Portal läuft als eigener Benutzer `mcportal`, ohne sudo und ohne Shell-Aufrufe aus Benutzereingaben.
- Privilegierte Aktionen nur über polkit für genau benannte systemd-Units.
- Welt, `allowlist.json`, `permissions.json`, `server.properties` werden nie blind überschrieben;
  jede Änderung wird vorher gesichert.
- Jede Änderung an der Minecraft-Installation (M1–M9) ist dokumentiert: was, warum, welche Dateien,
  Sicherung, Rückweg.
