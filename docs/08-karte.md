# Weltkarte im Portal (Änderung M10)

Stand: 2026-10-26 · Status: **K1 gebaut** (Karte, Knopf, nachts), K2–K4 offen · eigener Renderer, keine fremde Software

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

## K1 – so ist es gebaut

- Tab **„Karte“**: Oberwelt und Ende umschaltbar (der Nether wird bewusst nicht gezeichnet – von oben sieht man
  nur seine Grundgesteindecke); ziehen, Mausrad/Pinch, ＋/－, ⭐ = zurück zum Spawn;
  unten links Koordinaten unter der Maus. Darunter Stand, nächstes Neuzeichnen, **Seed** (aus der Übersicht
  hierher verschoben) und der Knopf **„Jetzt neu zeichnen“**.
- Gemessen auf dem Laptop (echte Welt, damals noch mit Nether: 20 404 + 1 404 + 666 Chunks): **106 s**, **200 MB RAM**,
  **5 MB Kacheln**; ohne Nether am PC 28 statt 33 s.
- Abweichung vom Plan: Statt eigener systemd-Unit und Timer startet das Portal den Renderer selbst als
  Kindprozess (`nice 19`, `ionice -c3`, Speichergrenze 1,5 GB) und plant den Nachtlauf (04:00) selbst.
  Dadurch braucht es **keine** neue Unit, keine polkit-Änderung und keine Änderung an `install.sh`.
- Läuft das Portal um 04:00 nicht, entfällt der Nachtlauf; der Knopf geht immer.
- Ist der Server gestoppt, wird ohne `save hold` kopiert (die Dateien sind dann ruhig).
- Protokoll: Eintrag „Karte gezeichnet“ (Erfolg oder Fehler) im Server-Tab.

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
| Renderer | `app/map/render.py` | oberster Block je Spalte, Wasser mit Tiefe, Relief-Schattierung; Oberwelt und Ende |
| Farben | `app/map/colors.json` | 1 334 Blöcke, Durchschnittsfarbe der Oberseite aus Mojangs offiziellen Texturen (`Mojang/bedrock-samples` 1.26.50.4) mit `tools/make_colors.py` auf dem PC; der Server lädt nichts herunter |
| Kacheln | `/var/lib/mcportal/map/build-<zeit>/<dim>/<stufe>/<x>_<z>.png` | 256 × 256 px, Stufe 0 = 1 px je Block, jede Stufe halbiert; `current.json` zeigt auf den gültigen Stand, alte Stände werden gelöscht |
| Ansicht | `web/map.js` | eigener kleiner Canvas-Viewer (Ziehen, Zoomen, Koordinaten unter der Maus); keine externe Bibliothek, CSP bleibt `'self'` |
| Ablauf | `app/services/map.py` | Kopie, Kindprozess `python -m app.map.render` (nice 19, idle-I/O, 1,5 GB), Nachtlauf 04:00 |
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

- Neue Portal-Dateien unter `/opt/mcportal/app` (über `install.sh`, wie jede Portal-Änderung), Daten unter
  `/var/lib/mcportal/map`.
- Minecraft: nur die Konsolenbefehle `save hold` / `save query` / `save resume` während des Kopierens
  (wenige Sekunden). Keine Datei des Servers oder der Welt wird geschrieben.
- Keine neuen Ports, Pakete, Units oder Rechte; keine Änderungen an Laravel oder am Webserver.
- **Sicherung gegen hängendes `save hold`:** `save resume` im `finally`; Markierungsdatei
  `/var/lib/mcportal/map/save-hold.active` → beim nächsten Portal-Start wird `save resume` nachgeholt.
- **Rückweg:** vorherige Portal-Version per Install-Backup zurück, `/var/lib/mcportal/map` löschen.
  Die Welt ist nicht betroffen.

## Offene Punkte

- Schwarze Lücken im Testbild sind Chunks, die noch nie erzeugt wurden; das ist korrekt.
- Blöcke ohne Farbe im Prototyp (u. a. Netherrack, Pilzblöcke, Kürbis, Heu) deckt die Farbtabelle aus K1 ab.
- Speicherplatz pro Lauf kurzfristig +~110 MB für die Weltkopie, danach wieder frei.
