# Wegpunkte / Warps (Änderung M9)

Stand: 2026-10-26 · Packs `mcportal_waypoints` (Verhalten) + `mcportal_waypoints_rp` (Grafik)

## Für Spieler

**Wegpunkt craften** (Werkbank):

```text
[ Laterne      ] [ Steinziegelmauer ] [ Laterne      ]
[ Steinziegelm.] [ Diamantblock     ] [ Steinziegelm.]
[ Laterne      ] [ Steinziegelmauer ] [ Laterne      ]
```

→ Item **„Wegpunkt“** (leuchtet, bis zu 16 stapelbar).

**Aufstellen:** Das Item von oben auf den Boden setzen. Es braucht 3 × 3 Blöcke Fläche und 4 Blöcke Höhe frei
(Gras, Blumen, Schnee werden ersetzt). Es entsteht:

```text
Boden (3 × 3):      Darüber an den 4 Ecken:
S S S               Steinziegelmauer (2 hoch) + Laterne obendrauf
S D S
S S S               S = Steinziegel, D = der Diamantblock aus dem Rezept
```

Danach fragt ein Fenster: **„Wie soll dieser Wegpunkt heißen?“**, darunter der Schalter **„Öffentlich“**
(standardmäßig aus). Wird das Fenster geschlossen, heißt der Wegpunkt „Wegpunkt 1“ (2, 3 …), ist privat und
lässt sich umbenennen.

**Bearbeiten** (seit 1.4.0): Den **Diamantblock antippen** (PC: Rechtsklick, Xbox: LT, Tablet: antippen) öffnet
für Besitzer und Operatoren wieder das Fenster – Name und „Öffentlich“ sind vorausgefüllt. Andere Spieler sehen
nur, wem der Wegpunkt gehört.

**Privat oder öffentlich** (seit Version 1.1.0):

| | Wer darf hinreisen und sieht ihn in `/warp list` |
|---|---|
| privat (Standard) | nur der Besitzer |
| öffentlich | alle Spieler |
| Operatoren | dürfen immer alle Wegpunkte sehen und benutzen |

Wegpunkte von vor 1.1.0 (z. B. „Dorf“) gelten als privat; freigeben mit `/warp public Dorf`.

**Befehle** (für alle; die Kurzform `/warp` funktioniert, im Spiel bestätigt):

| Befehl | Was |
|---|---|
| `/warp Zuhause` | zum Wegpunkt reisen – von überall, auch zwischen Oberwelt, Nether und Ende |
| `/warp list` | alle Wegpunkte, die man benutzen darf – mit Ort, Besitzer, öffentlich/privat |
| `/warp delete Zuhause` | eigenen Wegpunkt löschen (Operatoren: jeden); das Bauwerk wird zur Ruine (siehe unten) |
| `/warp rename Zuhause Burg` | eigenen Wegpunkt umbenennen (oder Diamantblock antippen) |
| `/warp public Zuhause` / `/warp private Zuhause` | eigenen Wegpunkt für alle freigeben / wieder privat machen |
| `/warp set Zuhause` | **nur Operatoren:** Wegpunkt ohne Bauwerk an der aktuellen Position |
| `/warp` | Hilfe |

Namen mit Leerzeichen in Anführungszeichen: `/warp "Mein Haus"`, `/warp rename "Wegpunkt 1" Baumhaus`. Fehlen die
Anführungszeichen, schlägt das Spiel den richtigen Befehl vor (seit 1.4.0). Namen sind eindeutig
(Groß-/Kleinschreibung egal), höchstens 24 Zeichen; Befehlswörter (list, set …) sind keine Namen.

**Abbauen geht nicht** (seit 1.4.0): Der Diamantblock eines Wegpunkts lässt sich nicht abbauen – auch nicht im
Kreativmodus oder als Operator. Entfernen nur mit `/warp delete <Name>`; der Diamant wird dabei zu Kohle und ist
**absichtlich verbraucht**. (Bis 1.3.0 entfernte Abbauen den Wegpunkt und gab den Diamanten zurück.) Die übrigen
Blöcke des Bauwerks (Steinziegel, Mauern, Laternen) lassen sich weiter abbauen.

**Ruine** (seit 1.2.0): Ein entfernter Wegpunkt bleibt als Ruine stehen, damit man sieht, dass hier einer war:

| | Mitte | Laternen |
|---|---|---|
| `/warp delete` | Diamantblock → **Kohleblock** (der Diamant ist damit weg) | → **Kupferlaternen** (laufen mit der Zeit grün an) |
| Diamant abgebaut (nur bis 1.3.0) | bleibt leer | → Kupferlaternen |

Nur Originalblöcke werden ersetzt. Ist der Bereich beim Löschen nicht geladen (niemand in der Nähe),
wird der Umbau vorgemerkt und erledigt, sobald jemand vorbeikommt – außer dort steht inzwischen ein neuer Wegpunkt. **Explosionen** (Creeper, TNT) beschädigen Wegpunkt-Bauwerke nicht.

## Technik

- Gespeichert in der Welt: je Wegpunkt eine „dynamic property“ `mcfs_wp:<name>` mit Name, Koordinaten
  (Diamantblock), Dimension, Besitzer, Datum, Bauwerk ja/nein, öffentlich ja/nein. Übersteht Neustarts und Updates.
- Befehl: eigener Befehl `mcfs:warp` (Berechtigung „alle“), Operator-Prüfung über `playerPermissionLevel`.
- Namensdialog: `@minecraft/server-ui` 2.2.0 (stabil). Ist der Spieler gerade in einem anderen Menü,
  wird es bis zu 15-mal erneut versucht.
- Log-Zeilen `[mcportal-warp] {"v":1,"event":"created|renamed|deleted|destroyed|teleport",…}` – für eine
  spätere Wegpunkt-Ansicht im Portal.
- Reine Logik (Namen, Befehle, Bauplan) in `scripts/core.js` mit Node-Tests; Bauen/Prüfen in `scripts/structure.js`.
- Item-Bild: 16 × 16, erzeugt von `mcportal_waypoints_rp/tools/make_icon.py` (Wegpunkt von oben).

## Änderung M9

1. **Was:**
   - neues Behavior Pack `worlds/Bedrock level/behavior_packs/mcportal_waypoints/` (+ Eintrag in `world_behavior_packs.json`)
   - neues Resource Pack `worlds/Bedrock level/resource_packs/mcportal_waypoints_rp/` (+ `world_resource_packs.json`, wird neu angelegt)
   - `server.properties`: `texturepack-required=false` → `true` (Spieler laden das kleine Grafik-Pack beim Beitreten)
2. **Warum:** Wegpunkte mit Rezept, Bauwerk, Namen und `/warp`; ohne Grafik-Pack wäre das Item kariert.
3. **Dateien:** nur die genannten.
4. **Backup:** `~/mcportal-backups/<zeit>_pre_mcportal_waypoints*/` und für `server.properties` `…_pre_texturepack_required/`.
5. **Rückgängig:** `world-pack.sh mcportal_waypoints rollback`, `world-pack.sh mcportal_waypoints_rp rollback`,
   Zeile in `server.properties` zurück. Gespeicherte Wegpunkte bleiben ungenutzt in der Welt; Bauwerke bleiben stehen.

Installation (ein Neustart):

```bash
NO_RESTART=1 bash ~/mcportal-src/deploy/world-pack.sh mcportal_waypoints_rp apply
bash ~/mcportal-src/deploy/world-pack.sh mcportal_waypoints apply
```

## Getestet

- Testserver: alle Schnittstellen vorhanden (eigene Befehle, Formular, Item, Rezept, Blöcke, Teleport mit Dimension,
  Explosionsfilter, Operator-Erkennung); beide Packs laden zusammen ohne Fehler; Befehl registriert.
- **Bauwerk in der echten Engine** (Selbsttest per Konsole): alle 21 Blöcke korrekt, Mauern als Säulen,
  Laternen stehend; zweiter Wegpunkt an derselben Stelle abgelehnt.
- 5 Node-Tests: Namen (gültig, doppelt, reserviert), Befehle, Bauplan, Ankunftsort, Liste.
- **Im Spiel bestätigt** (2026-10-26): Craften, Setzen per Item, Namensdialog, `/warp` als Kurzform, Teleport.
- Noch nicht im Spiel geprüft: Teleport zwischen Dimensionen, Abbauen, Explosionsschutz.

## Version 1.1.0: öffentliche Wegpunkte (2026-10-26)

- Schalter „Öffentlich“ im Namensdialog, `/warp public|private <Name>`, Zugriffsprüfung beim Reisen, gefilterte Liste.
- Getestet: 6 Node-Tests (u. a. Zugriffsregeln, Liste je Spieler); **mit einer Kopie der echten Welt** auf dem
  Testserver: beide vorhandenen Wegpunkte gelesen, „Dorf“ für Besitzer ja / Fremde nein / Operatoren ja,
  nach dem Freigeben auch für Fremde ja; Liste je Spieler korrekt.
- Installation: `bash ~/mcportal-src/deploy/world-pack.sh mcportal_waypoints apply` (Upgrade 1.0.0 → 1.1.0, ein Neustart).

## Version 1.2.0: Ruinen (2026-10-26)

- Beim Löschen: Diamantblock → Kohleblock, Laternen → Kupferlaternen; beim Abbauen des Diamanten nur die Laternen.
- Getestet in der echten Engine (Testserver): beide Fälle Block für Block, umgebaute Laterne bleibt unangetastet,
  nicht geladener Bereich wird vorgemerkt; 7 Node-Tests.
- Installation: `bash ~/mcportal-src/deploy/world-pack.sh mcportal_waypoints apply` (ein Neustart).

## Version 1.3.0: Anzeige im Portal (2026-10-26)

- Das Pack schreibt nach jeder Änderung und beim Start die **vollständige Liste** aller Wegpunkte ins Log
  (`{"event":"list","waypoints":[…]}`: Name, Besitzer, Dimension, Koordinaten, öffentlich, Bauwerk, Datum).
- Das Portal (`app/services/waypoints.py`, `/var/lib/mcportal/waypoints.json`) übernimmt die neueste Liste und
  zählt aus den `teleport`-Ereignissen, wie oft und von wem zu jedem Wegpunkt gereist wurde (folgt Umbenennungen).
- Tab „Statistik“: je Spieler Kachel **„📍 Wegpunkte“** und aufklappbare Liste – mit Ort, öffentlich/privat,
  „ohne Bauwerk“, Anzahl Reisen und letzter Reise. **Admin-Ansicht: zeigt auch private Wegpunkte**
  (das Portal nutzt nur der Admin).
- Getestet: 3 Python-Tests (Liste je Besitzer, Reisen über Umbenennung und Portal-Neustart, Löschen);
  Anzeige mit simuliertem Server; Pack 1.3.0 mit einer Kopie der echten Welt – Liste mit beiden Wegpunkten im Log.
- Installation: zuerst `install.sh` (Portal), dann `world-pack.sh mcportal_waypoints apply` – so ist das Portal
  bereit, wenn das Pack beim Neustart die Liste schreibt.

## Version 1.4.0: Diamant geschützt, Bearbeiten per Antippen (2026-10-26)

- Anlass: Ein Wegpunkt blieb „Wegpunkt 1“, weil `/warp rename Wegpunkt 1` ohne Anführungszeichen nicht ging.
- **Diamantblock antippen** → Fenster „Wegpunkt bearbeiten“ (Name, Öffentlich) für Besitzer und Operatoren;
  andere bekommen eine Info. Auf den Diamanten kann dabei nichts gesetzt werden (dort kommt man an).
- **Diamantblock nicht abbaubar** (`beforeEvents.playerBreakBlock` abgebrochen, mit Hinweis auf `/warp delete`).
  Bekannte Lücke: Ein Kolben könnte den Diamanten noch verschieben (dafür gibt es kein abbrechbares Ereignis).
- **Hinweis bei fehlenden Anführungszeichen:** Ergeben die einzeln angekommenen Wörter einen vorhandenen Namen,
  antwortet das Spiel mit dem richtigen Befehl, z. B. `/warp rename "Wegpunkt 1" <neuer Name>`.
- Getestet: 8 Node-Tests (neu: Hinweis-Logik); Testserver lädt 1.4.0 ohne Script-Fehler. Antippen und
  Abbau-Schutz brauchen einen echten Spieler – im Spiel prüfen.
- Installation: `bash ~/mcportal-src/deploy/world-pack.sh mcportal_waypoints apply` (ein Neustart, Backup davor).
