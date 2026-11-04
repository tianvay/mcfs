# Minecraft Family Portal

Kleines Web-Portal für den Bedrock-Server im Heimnetz: `http://192.168.178.38:8080`

Phase 1: Dashboard (Status, Version, Laufzeit, letzter Start, letztes Update, Spieler online live),
Start/Stop/Restart, Whitelist anzeigen/hinzufügen/entfernen (mit Sicherung), Aktionsprotokoll.

Analyse und Architektur: [`../docs/01-analyse-und-architektur.md`](../docs/01-analyse-und-architektur.md)

## Aufbau

```text
app/
├── main.py                  API (FastAPI) + Auslieferung der Web-UI, SSE unter /api/events
├── services/minecraft.py    Status, Spieler, Versionen, start/stop/restart
├── services/allowlist.py    Whitelist mit Sicherung vor jeder Änderung
├── audit.py                 Aktionsprotokoll (/var/lib/mcportal/audit.jsonl)
├── adapters/base.py         Schnittstelle zum Minecraft-Server
├── adapters/bedrock/        einzige Stelle mit Bedrock-/systemd-Wissen
└── web/                     HTML/CSS/JS ohne Build-Schritt
deploy/
├── install.sh               Installation S1–S5, M1, M3 (kein Minecraft-Neustart)
├── m2-console.sh            M2: Konsole + sauberer Stop (apply | rollback | status)
└── uninstall.sh             vollständige Entfernung
```

## Installation (auf dem Server)

Code liegt bereits unter `~/mcportal-src` (kopiert vom Windows-PC).

```bash
sudo bash ~/mcportal-src/deploy/install.sh
```

Danach, **wenn niemand spielt**, einmalig (Minecraft ist ca. 30 s weg):

```bash
sudo bash ~/mcportal-src/deploy/m2-console.sh apply
```

## Wo liegt was

| Pfad | Inhalt |
|---|---|
| `/opt/mcportal` | Programm + Python-venv (root, nur lesbar) |
| `/etc/mcportal/config.toml` | Konfiguration, u. a. `password_hash` (Admin-Passwort, nur als Hash) |
| `/var/lib/mcportal/audit.jsonl` | Aktionsprotokoll |
| `/var/lib/mcportal/backups/` | Sicherungen (`*_pre_portal_install`, `*_pre_m2_console`, `*_pre_allowlist_*`) |
| `/var/lib/mcportal/item-icons/` | Item-Bilder für den Tab „Spenden“ (vom Portal einmalig geladen) |

Logs des Portals: `journalctl -u mcportal -f`

## Whitelist-Logik

- Server läuft + Konsole (M2) vorhanden → Änderung über die Server-Konsole (`allowlist add/remove`),
  der Server schreibt seine Datei selbst; das Portal prüft danach die Datei.
- Server gestoppt → das Portal schreibt `allowlist.json` direkt (an Ort und Stelle, Besitzer/Rechte bleiben).
- Server läuft ohne Konsole (vor M2) → Änderungen gesperrt, damit der Server sie nicht überschreibt.
- Vor jeder Änderung: Kopie nach `/var/lib/mcportal/backups/<zeit>_pre_allowlist_<add|remove>/`
  (die letzten 30 werden behalten). Wiederherstellen: Datei bei gestopptem Server zurückkopieren.

## Operator-Status

Knopf ★/☆ je Spieler in der Whitelist. Das Portal sichert `permissions.json`, schreibt sie im
Server-Format und schickt bei laufendem Server `permission reload`. Erst möglich, nachdem ein
Spieler einmal verbunden war (der Server braucht seine XUID).

Wird einem Spieler der Operator-Status entzogen, setzt das Portal seinen Spielmodus auf **Überleben**:
sofort, wenn er online ist (`gamemode survival <Name>` über die Konsole), sonst beim nächsten Betreten
(Log-Zeile „Player Spawned“; vorgemerkt in `/var/lib/mcportal/pending_operator.json`, übersteht Neustarts).

Bei jedem Vergeben/Entziehen bekommt der Spieler eine kurze Chat-Nachricht: „Du bist jetzt Operator.“ bzw.
„Du bist nicht mehr Operator.“ (`tellraw`, ebenfalls sofort oder beim nächsten Betreten).

## Server-Update

Tab „Server“ → „Server-Update“. Ablauf, Schutz von Welt/Whitelist/Operatoren, Rollback und
Speicherbedarf: [`../docs/02-update-per-knopfdruck.md`](../docs/02-update-per-knopfdruck.md)

## Spenden

Tab „Spenden“ (nur Admin): Spieler wählen (nur wer online ist, oder „Alle online“), Item wählen
(Suche oder Kategorien), Menge wählen, „Spenden“. Das Portal schickt `give <Spieler> <item> <Menge>`
und eine Chat-Nachricht („Geschenk vom Admin: 16x Diamant“) über die Server-Konsole; jede Spende
steht im Protokoll (`DONATE`).

- Nur Items aus dem Katalog in `app/services/donate.py` sind möglich (ca. 100, mit deutschem Namen
  und Stapelgröße); höchstens 999 Stück bzw. ein volles Inventar (36 Stapel).
- Die Bilder sind Mojangs Original-Texturen aus dem offiziellen Repository
  [`Mojang/bedrock-samples`](https://github.com/Mojang/bedrock-samples) (feste Version in `ICON_SOURCE`).
  Sie liegen **nicht** in diesem öffentlichen Repository: Das Portal lädt beim Start fehlende Bilder
  nach `/var/lib/mcportal/item-icons/`. Ohne Internet zeigt der Tab farbige Platzhalter.
  Neu laden: Ordner löschen und `systemctl restart mcportal`.

## Wer was sieht (Admin-Anmeldung)

| Bereich | Ohne Anmeldung (Kinder, Gäste im WLAN) | Admin (angemeldet) |
|---|---|---|
| Übersicht: Status, wer online ist, Version, Laufzeit | ✅ | ✅ |
| Statistik, Erfolge | ✅ | ✅ |
| Karte mit Wegpunkten | ✅ | ✅ |
| Seed, „Karte neu zeichnen“ | – | ✅ |
| Whitelist und Operatoren | – | ✅ |
| Events (ansehen, starten, Hinweis auf der Übersicht) | – | ✅ |
| Server: Start/Stop/Neustart/Update, Protokoll | – | ✅ |

Der Schutz sitzt im Server, nicht nur in der Oberfläche: Ohne Anmeldung liefert die API diese
Daten gar nicht aus (401), und der Live-Status enthält nur die freigegebenen Felder
(`PUBLIC_STATUS` in `app/main.py` – neue Felder bleiben verborgen, bis sie dort stehen).

Passwort setzen oder ändern (fragt zweimal, speichert nur einen scrypt-Hash, startet nur das Portal neu):

```bash
sudo bash ~/mcportal-src/deploy/set-password.sh
```

- Ohne Passwort sind die Admin-Bereiche für alle gesperrt.
- Anmeldung unten auf der Seite („🔒 Anmelden“), gilt 30 Tage pro Browser, auch über einen
  Portal-Neustart hinweg (`/var/lib/mcportal/sessions.json`, nur Hashes).
- Nach 5 falschen Passwörtern ist das Gerät 15 Minuten gesperrt; jeder Versuch steht im Protokoll.
- Ein neues Passwort meldet alle Browser ab.
- Kinder-iPads: Safari → `http://192.168.178.38:8080` → Teilen → „Zum Home-Bildschirm“. Kein Konto nötig.

## Rückgängig machen

```bash
sudo bash ~/mcportal-src/deploy/m2-console.sh rollback   # nur M2
sudo bash ~/mcportal-src/deploy/uninstall.sh              # Portal komplett (vorher M2-Rollback)
```

## Entwicklung (lokal, ohne echten Server)

```bash
pip install -r requirements.txt
MCPORTAL_CONFIG=dev-config.toml python -m app     # mit adapter = "fake" in der Konfiguration
python -m unittest discover -s tests -t .
```
