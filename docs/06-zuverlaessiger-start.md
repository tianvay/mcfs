# Zuverlässiger Start (Änderung M8) und Cheats

Stand: 2026-10-26

## Problem

Am 26.10. kam zweimal nach einem Neustart niemand auf den Server. Um 07:09 lief der Server, war
beim Xbox-Verbindungsdienst angemeldet, hatte aber den Spieler-Port **19132 nicht geöffnet** – im Log
fehlte „Accepting clients on [::]:19132“, eine Fehlermeldung gab es nicht.

Wahrscheinliche Ursache: Nach dem Abmelden von Spielern hält Linux Port 19132 noch bis zu 60 s
im Zustand TIME-WAIT (auf dem Laptop nach Beitritten beobachtet: 4 Verbindungen). Startet der Server
in diesem Zeitfenster neu, öffnet er den Port stillschweigend nicht.

(Der erste Vorfall um 06:33 – Port offen, Beitritt trotzdem nicht möglich – ist damit nicht sicher
erklärt; die Nachprüfung unten erkennt aber auch einen fehlenden Verbindungsdienst.)

## Lösung: ein Start zählt erst, wenn Spieler wirklich beitreten können

`/opt/mcportal/bin/mc-start-check`, eingebunden über
`/etc/systemd/system/minecraft-bedrock.service.d/20-startcheck.conf` – gilt damit für **jeden** Start
(Portal-Knopf, Update, Systemstart, Pack-Installation):

| Phase | Was passiert |
|---|---|
| vor dem Start | warten, bis Port 19132/19133 komplett frei ist (alle Zustände, max. 120 s) |
| nach dem Start | warten (max. 150 s), bis alle drei erfüllt sind: Port 19132 lauscht, beim Xbox-Verbindungsdienst angemeldet, „Server started.“ |
| Prüfung scheitert | Server sauber über `stop` beenden (Welt wird gespeichert), systemd startet nach 15 s neu |
| Grenze | höchstens 4 Versuche in 15 Minuten, dann bleibt der Dienst gestoppt (keine Endlosschleife) |

Das Portal wartet bei Start/Neustart auf diese Neuversuche, statt sofort „fehlgeschlagen“ zu melden.
Ein Neustart dauert dadurch manchmal etwas länger (typisch 10–20 s, nach Spieler-Abmeldungen bis ~1 min).

Getestet: das Prüfprogramm gegen den laufenden Server (Port erkannt, Verbindungsdienst erkannt),
das Warten bei belegtem Port, und auf dem Laptop mit einem Wegwerf-Dienst, dass systemd nach einer
gescheiterten Nachprüfung automatisch neu startet.

### Änderung M8

1. **Was:** neues Programm `/opt/mcportal/bin/mc-start-check`, neue Datei
   `minecraft-bedrock.service.d/20-startcheck.conf` (Original-Unit unverändert).
2. **Warum:** siehe oben.
3. **Dateien:** nur diese zwei; installiert von `install.sh`.
4. **Backup:** nicht nötig – es wird nur eine neue Datei angelegt.
5. **Rückgängig:** `sudo rm /etc/systemd/system/minecraft-bedrock.service.d/20-startcheck.conf && sudo systemctl daemon-reload`

## Cheats (`allow-cheats=true`, 2026-10-26)

- Geändert: eine Zeile in `server.properties` (`false` → `true`), Sicherung in
  `~/mcportal-backups/2026-10-26_07-17-20_pre_allow_cheats/`, wirksam ab dem nächsten Start.
- Operatoren können damit Befehle nutzen (`/gamemode`, `/give`, `/tp`, `/time` …), Mitglieder nicht.
- **Bleibt bei Updates erhalten:** `server.properties` wird vom Update-Knopf nie überschrieben und nach
  dem Update byte-genau geprüft (wie `allowlist.json` und `permissions.json`), siehe
  [02-update-per-knopfdruck.md](02-update-per-knopfdruck.md).
- Vermutlich war es früher schon einmal `true`: Das Handupdate vom 20.09. hat Mojangs Zip über die
  Installation entpackt und dabei `server.properties` mit dem Standard überschrieben.
- Reproduzierbarer Aufbau: `allow-cheats=true` gehört zu den Abweichungen vom Mojang-Standard
  (`provision/server.properties.overrides`, siehe [04-reproduzierbarer-aufbau.md](04-reproduzierbarer-aufbau.md)).
