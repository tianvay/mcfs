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

Danach fragt ein Fenster: **„Wie soll dieser Wegpunkt heißen?“** Wird es geschlossen, heißt der Wegpunkt
„Wegpunkt 1“ (2, 3 …) und lässt sich umbenennen.

**Befehle** (für alle; ob `/warp` oder nur `/mcfs:warp` funktioniert, zeigt der erste Test im Spiel):

| Befehl | Was |
|---|---|
| `/warp Zuhause` | zum Wegpunkt reisen – von überall, auch zwischen Oberwelt, Nether und Ende |
| `/warp list` | alle Wegpunkte mit Ort und Besitzer |
| `/warp delete Zuhause` | eigenen Wegpunkt löschen (Operatoren: jeden); das Bauwerk bleibt stehen |
| `/warp rename Zuhause Burg` | eigenen Wegpunkt umbenennen |
| `/warp set Zuhause` | **nur Operatoren:** Wegpunkt ohne Bauwerk an der aktuellen Position |
| `/warp` | Hilfe |

Namen mit Leerzeichen in Anführungszeichen: `/warp "Mein Haus"`. Namen sind eindeutig (Groß-/Kleinschreibung egal),
höchstens 24 Zeichen; Befehlswörter (list, set …) sind keine Namen.

**Abbauen:** Wer den Diamantblock abbaut, entfernt den Wegpunkt (Meldung an alle) und bekommt den Diamantblock
zurück. **Explosionen** (Creeper, TNT) beschädigen Wegpunkt-Bauwerke nicht.

## Technik

- Gespeichert in der Welt: je Wegpunkt eine „dynamic property“ `mcfs_wp:<name>` mit Name, Koordinaten
  (Diamantblock), Dimension, Besitzer, Datum, Bauwerk ja/nein. Übersteht Neustarts und Updates.
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
- **Nicht getestet** (nur mit Spieler möglich): Craften, Setzen per Item, Namensdialog, `/warp` als Kurzform,
  Teleport, Abbauen, Explosionsschutz.
