# To-do – Minecraft Family Portal

Stand: 2026-10-26

## Offen

- [ ] **Creeper-Chaos, Hexenzirkel, Spuk-Nebel im Spiel ansehen** (installiert 26.10. 21:18: Events-Pack 1.4.0,
      Erfolge-Pack 1.4.0, Grafik-Pack 1.1.0).
- [ ] Weitere Mob-Event-Ideen (Liste vom 26.10.): Knochensturm (Skelette, „Knochenbrecher“), Spinnennacht
      („Arachnophobie“), Untotenarmee (Zombies+Skelette+Ertrunkene, „Letzte Bastion“), Wilde Jagd („Jäger oder
      Gejagter“), Tierwanderung („Tierfreund“), Elite-Mob („Bosskiller“), Der eine Zombie („David gegen Goliath“),
      Königin der Nacht (große Spinne + kleine, „Arachnidenjäger“), Geisterstunde (unsichtbare Gegner, „Ich habe
      nichts gesehen“).
- [ ] **Events im Spiel prüfen** (über die Kachel „Events“ starten): Titel/Chat/Sound, Unwetter mit Blitzen
      (nicht bei Bauten), Mining Rush (Erze doppelt, mit Glück; Silk Touch einfach), Glückstag (Erfahrung doppelt),
      Restzeit in der Aktionsleiste, Erfolge „Mittendrin…“ usw. nach dem 5. Event.
- [ ] **Paket 2 im Spiel prüfen** (Reiter „Events“): Blutmond (Nebel, roter Bildschirm, Wölfe greifen an,
      Schlafsperre), Zombie-Invasion (Wellen am Dorf, Dorfbewohner bleiben heil, Extra-Beute), Kopfgeld (Lichtsäule von
      weitem sichtbar? Helm/Schwert, Hinweise mit Höhe, Kopfgeld). Wetter-/Tageszeit-Knöpfe ausprobieren.
- [ ] **Paket 3 im Spiel prüfen** (Reiter Events): Meteorit (Countdown, Feuerspur, Krater mit Diamanten; nicht bei
      Bauten), Sternschnuppen (Spuren am Himmel, Sternenstücke aufsammeln), Schatzsuche (Hinweise, Truhe öffnen),
      Spukort (Nebel, Glocke, Fluch brechen). Erfolge: Welle III, Volltreffer, Sterntaler, Schatzsucher, Geisterjäger,
      Meta-Erfolge.
- [ ] **Boss-Aussehen im Spiel ansehen** (installiert 26.10. 16:57): Bosse 1,5-fach groß und eingefärbt
      (Bernd violett, Sven gold, Susi rot).
- [ ] Nach größeren Minecraft-Updates: `tools/make_bosses.py` neu laufen lassen (Bosse folgen dem Vanilla-Verhalten).
- [ ] **Chatlog im Portal** (eigener Punkt in der Übersicht, nur Nachrichten an alle – keine `/tell`, keine Befehle):
      warten, bis Mojang das Chat-Ereignis (`world.afterEvents.chatSend`) aus dem Beta-Stadium holt. Stand 2026-10-26:
      nur in `@minecraft/server` 2.11.0-beta; stabil ist 2.10.0 ohne Chat; der Server-Log enthält keinen Chat.
      Bei jedem Server-Update prüfen (Probe-Pack wie in der Sitzung vom 26.10., Testserver).
- [ ] Prüfen, ob der Karten-Nachtlauf am 27.10. um 04:00 kam (Protokoll im Server-Tab).
- [ ] Später, nicht dringend: Karte K3 Spielerpositionen (Statistik-Pack 2.1.0) · K4 nur Geändertes neu
      zeichnen, Biom-Färbung (Plan: `docs/08-karte.md`).

- [ ] Ruinen im Spiel ansehen: einen Wegpunkt löschen (Kohleblock, Kupferlaternen).
- [ ] „Dorf“ ggf. mit `/warp public Dorf` freigeben; Schalter „Öffentlich“ beim nächsten Setzen ausprobieren.
- [ ] Wegpunkte noch ausprobieren: Teleport in den Nether/ins Ende, Diamant abbauen, Xbox (Grafik-Download).
- [ ] Operator-Nachrichten im Spiel ausprobieren (Vergeben/Entziehen, online und offline).
- [ ] Kosmetik: Beim Beenden des Portals protokolliert die gerade laufende Statusabfrage einen Fehler
      („status poll failed … SIGTERM“) – beim Herunterfahren nicht mehr als Fehler loggen.
- [ ] **Beobachten: Beitritt nach Neustart gescheitert** (2026-10-26). Nach dem Neustart fürs Pack-Upgrade
      (06:33) kam niemand mehr auf den Server (PC und Xbox: `InitialConnection-145`, `NetherNet:2193`); im
      Server-Log kam kein Versuch an. Ein weiterer Neustart (06:42) hat es behoben, mit Pack 2.0. Ursache
      unklar: Die Verbindungen zu Microsofts Verbindungsdienst stehen auch im Normalbetrieb nach ~2 min auf
      CLOSE-WAIT, das war es also nicht. Diagnose: `~/mcportal-backups/diagnose-06-41/`. Falls es wieder
      passiert: Zeitpunkt notieren, Server über das Portal neu starten, Bescheid geben.
- [ ] **Statistik 2.0 im Spiel prüfen**: Tode, Mobs, Essen, XP, Setzlinge, Züchten, Strecke (Boot/Elytra …), Spielzeit –
      nach dem nächsten Spielen im Tab „Statistik“ ansehen; Auffälligkeiten melden.
- [ ] Optional **Platz schaffen** im Serverordner: `bedrock-server.zip` (95 MB) und
      `xampp-linux-x64-8.2.12-0-installer.run` (160 MB) braucht der Server nicht.
- [ ] **Sunny** kann erst Operator werden, nachdem Sunny einmal verbunden war.
- [ ] **Reproduzierbarer Aufbau** für den echten Server (Plan: `docs/04-reproduzierbarer-aufbau.md`):
      `provision/setup.sh`, `import-players.sh`, `verify.sh`; Umstieg auf `/opt/minecraft` am Stichtag.
- [ ] Später: **Web-Konsole** und **Log-Ansicht**.
- [ ] Prüfen, ob ein Spieler, der gerade online ist, Operator-Rechte durch `permission reload` sofort bekommt.

## Erledigt

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
