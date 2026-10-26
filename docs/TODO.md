# To-do – Minecraft Family Portal

Stand: 2026-10-25

## Offen

- [ ] **Ruhezustand abschalten** (sudo, siehe `docs/06-zuverlaessiger-start.md`): Nach dem Hochfahren mit
      geschlossenem Deckel geht der Laptop sonst sofort schlafen – Server 7 Minuten weg beim Test.
- [ ] **install.sh** für „Operator entziehen → Überleben“; danach im Spiel testen.
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

- [x] Feste IP 192.168.178.38 in der FRITZ!Box zugewiesen (2026-10-25)
- [x] Korrektur „Update verfügbar“-Hinweis + Portal mit Statistik installiert (2026-10-25)
- [x] M5 Statistik-Pack in der Welt installiert, Pack meldet sich (2026-10-25 21:19)
- [x] M6 Statistik-Pack 2.0 in der Welt installiert, meldet sich ohne Script-Fehler (2026-10-26 06:33)
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
