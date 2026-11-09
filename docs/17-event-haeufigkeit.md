# Wie oft kommen Events? (Änderung M18)

Stand: 2026-11-09 · Events-Pack 1.5.0 · Portal: Tab „Events“ (nur Admin)

Events kamen zu selten: Der Abstand hing an der Zahl der Spieler (180 Minuten bei 1 Spieler, 150 bei 2,
120 bei 3 …). Bei zwei, drei Kindern hieß das: ein Event alle zweieinhalb Stunden. Jetzt stellt der Admin den
Abstand selbst ein.

## Bedienung

Im Tab **Events** steht unter der Überschrift ein Schieberegler:

> Automatisch ein Event alle **1 Std. 30 Min.** gemeinsamer Spielzeit

- Bereich **1 bis 4 Stunden** in Viertelstunden-Schritten. **Standard: 90 Minuten.**
- „Gemeinsame Spielzeit“ heißt: Die Uhr läuft, solange **mindestens ein** Spieler online ist. Wie viele es sind,
  spielt keine Rolle mehr.
- Gesendet wird beim Loslassen. Das Portal zeigt „Events alle … gemeinsamer Spielzeit“, kurz danach passt sich
  „Nächstes Event in ca. …“ an.
- Das schon gesammelte Guthaben bleibt. Wer den Abstand verkürzt, holt das nächste Event also sofort näher heran
  (halb voll bei 2 Stunden = noch 1 Stunde; auf 1 Stunde gestellt = noch 30 Minuten).
- Unverändert: höchstens **ein** automatisches Event pro Stunde, 0–10 Minuten Zufallsverzug, Automatik an/aus,
  Events von Hand starten.
- Ist die Automatik aus, ist der Regler blass. Der Wert gilt, sobald sie wieder an ist.
- Läuft noch ein Events-Pack vor 1.5.0, steht statt des Reglers ein Hinweis: Das alte Pack meldet keinen
  Abstand, also muss erst `world-pack.sh mcportal_events apply` laufen.

Im Spiel bzw. an der Konsole geht dasselbe mit `/scriptevent mcfs:event every <60–240>` (Operatoren, Konsole).

## Wie es funktioniert

- **Pack** (`minecraft-pack/mcportal_events`): `schedule.every` in der Welt (Dynamic Property, übersteht
  Neustarts). `intervalMinutes(schedule)` liefert den Wert, alte oder kaputte Werte fallen auf 90 zurück. Ältere
  Welten ohne den Wert laufen also nach dem Update mit 90 Minuten. Die State-Zeile im Log hat das neue Feld
  `every`. Der Befehl `every <n>` nimmt nur ganze Zahlen von 60 bis 240 an.
- **Portal:** `POST /api/gameevents/every` mit `{"minutes": n}`, nur Admin, nur wenn das Events-Pack an ist,
  der Server läuft und die Konsole erreichbar ist. Der Konsolenbefehl entsteht fest in
  `commands.event_every()` (Zahl wird geprüft, kein freier Text). Protokoll: `EVENT_EVERY`.
  `GET /api/gameevents` liefert `every` und `every_range`.
- **Web:** `app/web/events.js` (`renderEvery`), `index.html`, `app.css`.
- **Tests:** `tests/core.test.mjs` (Abstand, Schätzung, Befehl), `tests/test_events.py` (Grenzen, nur feste Befehle,
  Server aus).

## Änderung M18

1. **Was:** Events-Pack 1.5.0 mit einstellbarem Abstand statt Tabelle nach Spielerzahl; Portal-Endpunkt
   `POST /api/gameevents/every` und Schieberegler im Events-Tab.
2. **Warum:** Events kamen bei wenigen Spielern zu selten; der Admin soll die Häufigkeit selbst wählen.
3. **Dateien auf dem Server:** Pack-Ordner `worlds/<Welt>/behavior_packs/mcportal_events` (neue Version in
   `world_behavior_packs.json`), Portal unter `/opt/mcportal/app`. Keine neuen Rechte, keine neue Unit, kein neues
   Systempaket. Neue Server bekommen beides über `setup.sh --install` wie bisher.
4. **Backup:** `world-pack.sh mcportal_events apply` sichert Pack-Ordner und Pack-Liste vorher, `install.sh` legt
   `/var/lib/mcportal/backups/<zeit>_pre_portal_install/` an.
5. **Rückgängig:** Regler zurück auf den alten Wert (bei 2–3 Spielern entsprach das etwa 120–150 Minuten). Ganz
   zurück: `sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_events rollback`; das alte Pack ignoriert den
   gespeicherten Wert `every`.

Auf dem Laptop installieren (Portal, dann das Pack mit Neustart des Servers):

```bash
sudo bash ~/mcportal-src/deploy/install.sh
```

```bash
sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_events apply
```
