# Weltkarte im Portal (Plan, Änderung M10)

Stand: 2026-10-26 · Status: **Plan, noch nicht umgesetzt** · eigener Renderer, keine fremde Software

## Ziel

Im Portal eine zoombare Karte der echten Welt von oben, mit allem, was gebaut oder abgebaut wurde.
Darauf eingezeichnet: Wegpunkte (öffentlich/privat, Besitzer) und Spieler (online live, offline letzter
bekannter Ort). Neu gezeichnet wird jede Nacht und auf Knopfdruck.

## Machbarkeit (geprüft an einer Kopie der echten Welt)

| Prüfung | Ergebnis |
|---|---|
| Weltdatenbank lesen (Mojangs LevelDB-Variante, zlib/raw-deflate) | in reinem Python, **1,6 s** für 362 000 Einträge |
| Inhalt | 20 404 Chunks Oberwelt, 2 072 Chunks Nether, kein Ende |
| Testbild Oberwelt (Höhenkarte + ein Block je Spalte, Wassertiefe, Relief) | **23 s** auf dem PC, Dorf, Wege, Gebäude erkennbar |
| Zusatzpakete | keine; Pillow ist im Portal-venv nicht nötig (PNG wird selbst geschrieben) |

Auf dem Laptop (2 Kerne) ist mit etwa 1–2 Minuten für eine vollständige Karte zu rechnen, mit
inkrementellem Zeichnen (K4) danach Sekunden.

## Ablauf eines Kartenlaufs

```text
Portal (mcportal)                          Minecraft-Server
  1. Konsole: save hold            ───►    Speichern pausiert (Spiel läuft normal weiter)
  2. Konsole: save query           ───►    meldet Dateiliste + Längen im Journal
  3. genau diese Dateien/Längen nach /var/lib/mcportal/map/snapshot kopieren
  4. Konsole: save resume          ───►    Speichern läuft weiter   (immer, auch bei Fehlern)
  5. systemctl start mcportal-map.service   (zeichnet aus der Kopie, niedrige Priorität)
  6. Kopie löschen, Kacheln + Index austauschen, Portal zeigt die neue Karte
```

`save hold/query/resume` ist Mojangs vorgesehener Weg für konsistente Kopien einer laufenden Welt.
Die laufende Welt wird **nie** direkt gelesen oder beschrieben.

**Sicherung gegen vergessenes `save resume`:** `resume` steht in einem `finally`, Zeitlimit für Schritt 2–3
von 60 s; zusätzlich schreibt das Portal vor `hold` eine Markierungsdatei und schickt beim eigenen Start
`save resume`, falls die Markierung noch existiert (Portal-Absturz mitten im Kopieren).

## Bausteine

| Baustein | Ort | Inhalt |
|---|---|---|
| LevelDB-Leser | `app/map/leveldb.py` | MANIFEST, `.ldb`-Tabellen, `.log`; nur lesend, neueste Sequenz gewinnt |
| Chunk-Leser | `app/map/chunk.py` | Höhenkarte (Data3D), Subchunks v8/v9 mit Paletten, Biome |
| Renderer | `app/map/render.py` | oberster Block je Spalte, Wasser mit Tiefe, Relief-Schattierung, Nether unter der Decke |
| Farben | `app/map/colors.json` | Durchschnittsfarbe je Block, einmalig erzeugt aus Mojangs offiziellen Texturen (`Mojang/bedrock-samples`) mit `tools/make_colors.py` auf dem PC; der Server lädt nichts herunter |
| Kacheln | `/var/lib/mcportal/map/<dim>/<zoom>/<x>_<z>.png` | 256 × 256 px, Zoom 1 px = 1 Block und Verkleinerungen; geschätzt 20–50 MB |
| Ansicht | `web/map.js` | eigener kleiner Canvas-Viewer (Ziehen, Zoomen, Koordinaten unter der Maus); keine externe Bibliothek, CSP bleibt `'self'` |
| Dienst | `mcportal-map.service` (oneshot) + `mcportal-map.timer` (nachts 04:00) | als Benutzer `mcportal`, `Nice=19`, `IOSchedulingClass=idle`, `CPUQuota=50%`, `MemoryMax=1G`, gleiche Sandbox wie das Portal |
| API | `/api/map` (Index, Stand, Laufstatus), `/api/map/render` (Knopf), `/api/map/tile/...` | Knopf gesperrt, solange ein Lauf aktiv ist oder ein Update läuft |

## Einzeichnungen

- **Wegpunkte:** kommen schon heute über `WaypointsService`; Symbol je Wegpunkt, Farbe öffentlich/privat,
  Tooltip mit Name, Besitzer, Reisen. Gelöschte Wegpunkte (Ruinen) erscheinen nicht.
- **Spieler:** braucht eine kleine Erweiterung des Statistik-Packs (2.1.0): alle 30 s je Online-Spieler
  eine Zeile `{"v":1,"event":"pos","player":…,"dim":…,"x":…,"y":…,"z":…}`. Das Portal zeigt
  Online-Spieler live (SSE) und offline Spieler mit „zuletzt gesehen“. Das ist eine Änderung an der
  Minecraft-Installation und läuft nach dem üblichen Ablauf (Backup → Upgrade → Prüfen, Rückweg über
  `world-pack.sh … rollback`).
- **Weltspawn** als festes Symbol.

## Phasen

| Phase | Inhalt | Eingriff in Minecraft |
|---|---|---|
| **K1** | LevelDB-/Chunk-Leser, Renderer, Kacheln, Viewer, Tab „Karte“, Knopf + Nacht-Timer; Oberwelt und Nether | nur Konsolenbefehle `save hold/query/resume` |
| **K2** | Wegpunkte und Weltspawn auf der Karte | keiner |
| **K3** | Spielerpositionen (Statistik-Pack 2.1.0) | Pack-Upgrade |
| **K4** | inkrementell (nur geänderte Chunks neu), Biom-Färbung von Gras/Laub/Wasser | keiner |

Jede Phase wird zuerst gegen Kopien der echten Welt und den Testserver (`~/bds-test`) geprüft.

## Was sich auf dem Server ändert (K1)

- Neue Dateien unter `/opt/mcportal` (über `install.sh`), Daten unter `/var/lib/mcportal/map`.
- Neue Units `mcportal-map.service` und `mcportal-map.timer`; die polkit-Regel `50-mcportal.rules`
  erlaubt dem Portal zusätzlich genau diesen Unit-Start.
- Keine neuen Ports, keine Pakete, keine Änderungen an Laravel, Webserver oder Minecraft-Dateien.
- **Rückweg:** Timer und Unit deaktivieren, `/var/lib/mcportal/map` löschen, vorherige Portal-Version per
  Install-Backup zurück. Die Welt ist nicht betroffen.

## Offene Punkte

- Schwarze Lücken im Testbild sind Chunks, die noch nie erzeugt wurden; das ist korrekt.
- Blöcke ohne Farbe im Prototyp (u. a. Netherrack, Pilzblöcke, Kürbis, Heu) deckt die Farbtabelle aus K1 ab.
- Speicherplatz pro Lauf kurzfristig +~110 MB für die Weltkopie, danach wieder frei.
