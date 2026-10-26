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
| `/etc/mcportal/config.toml` | Konfiguration, u. a. `pin = ""` für PIN-Schutz |
| `/var/lib/mcportal/audit.jsonl` | Aktionsprotokoll |
| `/var/lib/mcportal/backups/` | Sicherungen (`*_pre_portal_install`, `*_pre_m2_console`, `*_pre_allowlist_*`) |

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
(Log-Zeile „Player Spawned“; vorgemerkt in `/var/lib/mcportal/pending_survival.json`, übersteht Neustarts).

## Server-Update

Tab „Server“ → „Server-Update“. Ablauf, Schutz von Welt/Whitelist/Operatoren, Rollback und
Speicherbedarf: [`../docs/02-update-per-knopfdruck.md`](../docs/02-update-per-knopfdruck.md)

## PIN-Schutz (optional)

In `/etc/mcportal/config.toml` z. B. `pin = "4711"` setzen, dann `sudo systemctl restart mcportal`.
Anschauen bleibt ohne PIN möglich; Start/Stop/Whitelist fragen einmal pro Browser nach der PIN.

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
