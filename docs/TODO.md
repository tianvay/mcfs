# To-do – Minecraft Family Portal

Stand: 2026-11-03 (mit dem Server abgeglichen: Log, sudo-Verlauf, Prüfsummen von `/opt/mcportal/app` und
`~/mcportal-src`)

## Offen

### Im Spiel ansehen

- [ ] **Statistik 2.0.1** (Essen vollständig, `docs/03-block-statistik.md`): auf dem Laptop installieren, dann ein Steak
      essen und im Tab „Statistik“ nachsehen.
- [ ] **Funktionen ein/aus (M17)** (`docs/16-funktionen-schalten.md`): auf dem Laptop `sudo bash ~/mcportal-src/deploy/install.sh`,
      dann im Portal z. B. die Spawnfackel aus- und wieder einschalten (Neustart) und im Spiel prüfen.
- [ ] **Blaupause (M15)** (installiert 02.11. 18:29, Pack startet ohne Fehler; `docs/14-blaupause.md`): Craften,
      Markieren mit Umriss, Namensfenster, Einsetzen in alle Richtungen, Kopieren über die Werkbank (wird der
      Platzhalter zu zwei Blaupausen?), Schleichen + Benutzen.
- [ ] **Spawnfackel 1.1.0** (installiert 02.11. 10:00): Schleier bei umgedrehten Treppen, 1 Block hohen Lücken,
      im Tiefen Dunkel stimmig?
- [ ] **Events – Aussehen und Wirkung.** Laut Log sind alle Events schon mit Spielern gelaufen außer **Glückstag** und
      **Creeper-Chaos** (liefen nur, als niemand online war). Keine Script-Fehler. Offen ist nur noch, ob alles so
      aussieht und wirkt wie gedacht: Titel/Chat/Sound, Unwetter mit Blitzen (nicht bei Bauten), Erze doppelt beim
      Mining Rush, Blutmond (Nebel, roter Bildschirm, Wölfe, Schlafsperre), Zombie-Wellen am Dorf, Lichtsäule beim
      Kopfgeld, Meteor-Krater, Sternenstücke, Schatztruhe, Spukort, Hexenzirkel, Spuk-Nebel.
- [ ] **Boss-Aussehen**: Bosse 1,5-fach groß und eingefärbt (Bernd violett, Sven gold, Susi rot).
- [ ] **Statistik 2.0** im Tab „Statistik“ durchsehen (Tode, Mobs, Essen, XP, Setzlinge, Züchten, Strecke, Spielzeit) –
      die Daten kommen an; Auffälligkeiten melden.
- [ ] Wegpunkte: Teleport in den Nether/ins Ende, Diamant abbauen, Xbox (Grafik-Download); Ruinen ansehen (einen
      Wegpunkt löschen); „Dorf“ ggf. mit `/warp public Dorf` freigeben.
- [ ] Operator-Nachrichten ausprobieren (Vergeben/Entziehen, online und offline); bekommt ein Spieler, der gerade
      online ist, die Rechte durch `permission reload` sofort?

### Zugang und Aufräumen

- [ ] Zugang von außen: ein **Name statt der Zahl** für Freunde (MyFRITZ!-Adresse zeigt auch auf die IPv6 der
      Fritzbox – testen oder einen Namen nur mit IPv4 einrichten).
- [ ] **Aufräumen** (die neue Welt läuft seit 30.10. ohne Probleme): Testinstallation
      `~/Downloads/bedrock-server-1.21.51.02` (darin liegen auch `bedrock-server.zip` und der XAMPP-Installer),
      `/var/lib/mcportal/archive/*_testphase`, `/var/backups/mcportal-switch/*` (danach ist kein `--switch-back` mehr
      möglich). Platz ist genug (79 GB frei), es eilt also nicht.
- [ ] Kosmetik: Beim Beenden des Portals kann die gerade laufende Statusabfrage einen Fehler protokollieren
      („status poll failed … SIGTERM“, `app/services/minecraft.py`) – seit 30.10. nicht mehr aufgetreten, aber nicht behoben.

### Beobachten / warten

- [ ] **WLAN-Aussetzer** (2026-11-04 13:23–13:40, schon einmal am 02.11. 23:49): Der Realtek-Treiber rtw88 hat die
      Verbindung zum Router verloren, Minecraft lief weiter. Gegenmittel `deploy/wifi-no-powersave.sh apply`
      (WLAN-Stromsparen aus). Wenn es trotzdem wieder passiert: LAN-Kabel an `eno1` anschließen.
- [ ] **Sunny** kann erst Operator werden, nachdem Sunny einmal verbunden war (bis 03.11. noch nie im Log).
- [ ] **Beitritt nach Neustart gescheitert** (2026-10-26, seitdem nicht wieder). Falls es wieder passiert:
      Zeitpunkt notieren, Server über das Portal neu starten, Bescheid geben. Diagnose: `~/mcportal-backups/diagnose-06-41/`.
- [ ] **Chatlog im Portal** (nur Nachrichten an alle): wartet, bis Mojang `world.afterEvents.chatSend` aus dem
      Beta-Stadium holt (Stand 26.10.: nur in `@minecraft/server` 2.11.0-beta). Bei jedem Server-Update prüfen.
- [ ] Bei Bedrock-Updates prüfen, ob `server-udp-ports` weiterhin eine Zeile pro Port braucht (Mojira BDS-23108).
- [ ] Nach größeren Minecraft-Updates: `tools/make_bosses.py` neu laufen lassen (Bosse folgen dem Vanilla-Verhalten).

### Später / Ideen

- [ ] Weitere Mob-Events (Liste vom 26.10.): Knochensturm (Skelette, „Knochenbrecher“), Spinnennacht
      („Arachnophobie“), Untotenarmee (Zombies+Skelette+Ertrunkene, „Letzte Bastion“), Wilde Jagd („Jäger oder
      Gejagter“), Tierwanderung („Tierfreund“), Elite-Mob („Bosskiller“), Der eine Zombie („David gegen Goliath“),
      Königin der Nacht (große Spinne + kleine, „Arachnidenjäger“), Geisterstunde (unsichtbare Gegner, „Ich habe
      nichts gesehen“).
- [ ] Karte K3 Spielerpositionen (Statistik-Pack 2.1.0) · K4 nur Geändertes neu zeichnen, Biom-Färbung
      (Plan: `docs/08-karte.md`).
- [ ] Welt-Umzug auf einen neuen Server (`setup.sh --install` startet immer mit neuer Welt).
- [ ] **Web-Konsole** und **Log-Ansicht**.

## Erledigt

- [x] `~/mcportal-src` auf den Stand von M16 gebracht (Git-Stand mit LF, alle 161 Dateien identisch; Sicherung vorher:
      `~/mcportal-backups/mcportal-src-2026-11-03_pre_m16.tgz`); `verify.sh` danach: alles in Ordnung (Dienste,
      Zugang von außen 10/10, Spielregeln, alle 10 Packs inkl. Spawnfackel 1.1.0 und Blaupause 1.0.0, Portal, Rechte)
      (2026-11-03)
- [x] Abgleich mit dem Server (2026-11-03): Admin-Anmeldung ausgerollt (`set-password.sh` + `install.sh` am 30.10.),
      Karten-Fix für neue Welten und Whitelist-XUID aus dem Log sind im Portal (`install.sh` 01.11. 18:31; installierter
      Code = aktueller Stand), Spawnfackel 1.1.0 (02.11. 10:00) und Blaupause (02.11. 18:29) installiert, Packs werden
      mit sudo installiert, Karten-Nachtlauf läuft jede Nacht um 04:00, playit ist nicht mehr installiert, die neue Welt
      läuft (Wegpunkte, Events, Erfolge, Statistik melden sich im Log, keine Script-Fehler)
- [x] Zombie-Bernd sichtbar (Events-Pack 1.4.1 + Grafik-Pack 1.1.1, im Spiel bestätigt) (2026-10-27)
- [x] Neue Welt im Spiel: Beitreten klappt; erste Karte gezeichnet (349 Chunks Oberwelt) (2026-10-30)
- [x] Reproduzierbarer Aufbau – Umstieg auf die neue Welt („Family and Friends“, Welt „FAF“,
      `/opt/minecraft/bedrock`, Benutzer `minecraft`, kein PvP, Whitelist ohne Operatoren), `docs/04-reproduzierbarer-aufbau.md` (R6) (2026-10-30)
- [x] `install.sh` mit `mc-public-ip`: läuft vor jedem Start, Startprüfung OK nach 4 s; `verify.sh`: Zugang von außen 10/10 (2026-10-30)
- [x] Bedrock 26.60 per Update-Knopf: 27.10. → 1.26.60.6, 30.10. → 1.26.61.1; Zugang von außen (IPv4 + Mobilfunk) am 28.10. bestätigt
- [x] Spawnfackel (M14) installiert und im Spiel bestätigt; `world-pack.sh` startet mit sudo jetzt über systemd neu (Portal-Neustart braucht seit der Admin-Anmeldung ein Login) (2026-11-01)
- [x] Timed Events Paket 3 installiert (Events-Pack 1.3.0, Erfolge-Pack 1.3.0 mit Meta-Erfolgen); Bau-Register mit 1.087 Chunks aus der Karte (2026-10-26 18:53)
- [x] Events-Pack 1.1.2 installiert: verschwundener Boss kommt zurück, Spawns nur auf echtem Boden (2026-10-26)
- [x] Events-Pack 1.1.1 installiert: Boss mit Lichtsäule, Hinweis alle 5 s mit Höhe, Y-Koordinate (2026-10-26 16:33)
- [x] Timed Events Paket 2 installiert: Portal (Reiter Events, Wetter/Zeit), Events-Pack 1.1.0, Erfolge-Pack 1.2.0 (2026-10-26 16:19)
- [x] Timed Events Paket 1 installiert: Portal, Events-Pack 1.0.0, Erfolge-Pack 1.1.0, alle ohne Script-Fehler (2026-10-26 15:34)
- [x] Wegpunkte 1.4.0 im Spiel bestätigt: Diamant geschützt, Bearbeiten per Antippen (2026-10-26)
- [x] Wegpunkte 1.4.0 installiert (Diamant geschützt, Bearbeiten per Antippen), startet ohne Script-Fehler (2026-10-26 13:10)
- [x] Karte K2 installiert: Wegpunkte + Weltspawn auf der Karte, Marker auf der Blockmitte (2026-10-26)
- [x] Karte K1 installiert, erster echter Lauf: Welt 0,65 s angehalten, 91 s gesamt, Oberwelt + Ende (2026-10-26 12:14)

- [x] Karte K1 gebaut und gegen eine Kopie der echten Welt getestet (Laptop: 106 s, 200 MB, 5 MB Kacheln) (2026-10-26)

- [x] Feste IP 192.168.178.38 in der FRITZ!Box zugewiesen (2026-10-25)
- [x] Korrektur „Update verfügbar“-Hinweis + Portal mit Statistik installiert (2026-10-25)
- [x] M5 Statistik-Pack in der Welt installiert, Pack meldet sich (2026-10-25 21:19)
- [x] M6 Statistik-Pack 2.0 in der Welt installiert, meldet sich ohne Script-Fehler (2026-10-26 06:33)
- [x] Wegpunkte im Portal: Portal + Pack 1.3.0 installiert, Liste kommt an (2026-10-26 11:13)
- [x] Wegpunkte 1.2.0 (Ruinen) installiert (2026-10-26 09:16)
- [x] Wegpunkte 1.1.0 (öffentlich/privat) installiert (2026-10-26 09:08)
- [x] Wegpunkte im Spiel bestätigt: craften, setzen, Name, `/warp` (Kurzform funktioniert) (2026-10-26)
- [x] M9 Wegpunkte + Grafik-Pack installiert, `texturepack-required=true`; drei Packs ohne Script-Fehler (2026-10-26 08:40)
- [x] Portal mit Operator-Nachrichten installiert (2026-10-26)
- [x] „Operator entziehen → Überleben“ im Spiel bestätigt (2026-10-26)
- [x] Ruhezustand abgeschaltet (no-suspend.sh): logind ignoriert den Deckel, Suspend gesperrt (2026-10-26)
- [x] Portal mit „Operator entziehen → Überleben“ installiert (2026-10-26)
- [x] Neustart-Test (`sudo reboot`): alle Dienste kommen von selbst, Startprüfung OK, WLAN ohne Anmeldung –
      aber Ruhezustand wegen geschlossenem Deckel gefunden (2026-10-26)
- [x] Erfolge im Spiel ausgelöst: „Anfängerfehler“, „Die Schwerkraft gewinnt immer“ (2026-10-26 07:54)
- [x] Cheats im Spiel bestätigt: `/gamemode survival` funktioniert, Beitritt nach M8-Neustart ok (2026-10-26)
- [x] M8 Startprüfung installiert; erster Neustart damit: 48 s auf TIME-WAIT gewartet, dann Port offen (2026-10-26 07:50)
- [x] `allow-cheats=true` gesetzt (wirksam ab nächstem Start), bleibt bei Updates erhalten (2026-10-26)
- [x] M7 Erfolgs-Pack 1.0 in der Welt installiert, beide Packs ohne Script-Fehler (2026-10-26 07:07)
- [x] Statistik im Spiel bestätigt: gesetzte/abgebaute Blöcke erscheinen im Tab „Statistik“ (2026-10-25)
- [x] Windows-PC: Maus/Controller in Minecraft gingen nicht (GameInput-Dienst hing) – per Neustart behoben (2026-10-25)
- [x] Phase 1: Dashboard, Start/Stop/Restart, Whitelist, Protokoll
- [x] M2: Konsole und sauberer Stopp
- [x] Operator-Status in der Whitelist
- [x] Update per Knopfdruck (M4); erstes Update auf 1.26.52.3
