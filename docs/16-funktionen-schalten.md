# Funktionen ein- und ausschalten (Änderung M17)

Stand: 2026-11-06 · Portal: Tab „Funktionen“ · `app/services/packs.py`

Jede Erweiterung des Servers lässt sich im Portal einzeln abschalten. Wer alles abschaltet, spielt reines
Minecraft (Vanilla). Statistik und Erfolge können dabei an bleiben, sie bringen keine eigenen Gegenstände mit.

## Bedienung

Tab **Funktionen**, für alle sichtbar:

- **Ohne Anmeldung** (Kinder, Gäste): nur die Funktionen, die gerade laufen, mit Beschreibung. Bei eigenen
  Gegenständen steht das **Rezept** dabei: Werkbank-Raster mit den Bildern der Zutaten, Ergebnis und eine Zeile wie
  „Wegpunkt: 4× Lantern, 4× Stone Brick Wall, 1× Block of Diamond“. Keine Versionen, keine Schalter. Läuft nichts,
  steht dort „Gerade läuft reines Minecraft“.
- **Admin:** alle Funktionen, auch ausgeschaltete, mit Zustand, Version, Schalter und Rezepten:

| Funktion | Packs | Eigene Inhalte | Beim Ausschalten |
|---|---|---|---|
| Statistik | `mcportal_stats` | – | Portal sammelt keine neuen Zahlen; die alten bleiben sichtbar |
| Erfolge | `mcportal_achievements` | – | keine neuen Erfolge; die alten bleiben |
| Wegpunkte | `mcportal_waypoints` + Grafik | Wegpunkt-Item | **Items werden gelöscht** (s. u.), `/warp` geht nicht mehr |
| Events | `mcportal_events` + Grafik | Bosse, Hexen | laufende Events enden, Bosse verschwinden; Events-Tab gesperrt |
| Spawnfackel | `mcportal_spawntorch` + Grafik | Spawnfackel-Item | **Items werden gelöscht** |
| Blaupause | `mcportal_blueprint` + Grafik | Blaupause-Items | **Items werden gelöscht** |

- **Wirksam nach dem Neustart.** Bedrock liest die Pack-Listen nur beim Start. Das Portal zeigt „⏳ aus nach
  Neustart“ bzw. „⏳ an nach Neustart“ und einen Knopf „Jetzt neu starten“. Der Neustart geht wie immer: mit
  Rückfrage, wer gerade online ist, wird getrennt.
- **Warnung vor dem Ausschalten** bei Funktionen mit eigenen Gegenständen: Minecraft löscht unbekannte Items
  dauerhaft, sobald es sie lädt (Inventar beim Betreten, Truhen beim Laden des Chunks). Beim Wiedereinschalten
  kommen sie **nicht** zurück. Was das Pack in der Welt gespeichert hat (z. B. die Liste der Wegpunkte, gespeicherte
  Blaupausen), bleibt erhalten.
- **Zustände:** „✓ an“, „aus“, „⏳ an/aus nach Neustart“, „✗ nicht gestartet“ (eingeschaltet, aber beim letzten
  Start nicht im „Pack Stack“ – Log ansehen). Läuft der Server nicht, zeigt das Portal nur an/aus.
- Ist das Events-Pack aus, **verschwindet der Events-Tab** samt „Blockänderungen rückgängig“ (API: 409). Wetter
  und Tageszeit haben einen eigenen Tab **Welt** (nur Admin), das sind normale Befehle ohne Pack.

### Rezepte und Bilder

- Die Rezepte liest das Portal aus `recipes/*.json` der Behavior Packs in der Welt (geformt und ungeformt), die
  Namen und Bilder der eigenen Items aus `items/*.json` und `textures/item_texture.json` der Grafik-Packs. Neue
  Rezepte erscheinen also von selbst.
- Bilder der Minecraft-Zutaten und ihre (englischen) Namen kommen wie im Tab „Spenden“ aus Mojangs Repository
  (`/api/donate/icons/…`). Bilder der eigenen Items liefert `/api/features/icons/<ns>.<item>.png`, aber nur für
  Funktionen, die laufen, und nur Dateien innerhalb des Pack-Ordners. Fehlt ein Bild, steht der Name im Feld.

## Wie es funktioniert

- Eine **Funktion** ist ein Behavior Pack samt den Resource Packs, von denen es laut `manifest.json` abhängt. Das
  Portal liest dafür die Ordner `behavior_packs/` und `resource_packs/` der Welt. Nichts ist fest verdrahtet, neue
  Packs erscheinen von selbst.
- **Ausschalten** entfernt die Einträge aus `world_behavior_packs.json` und `world_resource_packs.json`.
  **Einschalten** hängt sie mit der installierten Version wieder an. Die Pack-Ordner bleiben immer liegen.
- Geschrieben wird **in place**, so bleiben Besitzer (`minecraft`) und ACL gleich. Vorher landet eine Sicherung
  beider Dateien in `/var/lib/mcportal/backups/packs/<zeit>/` (die letzten 20). Schlägt das Schreiben fehl,
  spielt das Portal die Sicherung sofort zurück.
- **Was läuft**, liest das Portal aus den „Pack Stack“-Zeilen, die Bedrock bei jedem Start ins Log schreibt (mit
  UUID). Wann zuletzt geschaltet wurde, steht in `/var/lib/mcportal/packs.json`. So unterscheidet das Portal
  „wartet auf Neustart“ von „nicht gestartet“.
- Jede Änderung steht im Protokoll (`PACK_ON`/`PACK_OFF`).
- Während eines Updates oder Neustarts lehnt das Portal das Schalten ab (409).

## Zusammenspiel mit den Scripts

- **`deploy/install.sh`** gibt dem Portal `rw` auf die beiden Pack-Listen (ACL, wie bei `allowlist.json`). Fehlt
  `world_resource_packs.json`, wird sie leer für `minecraft` angelegt. `setup.sh --install` bekommt das über
  install.sh automatisch.
- **`provision/verify.sh`** meldet ein ausgeschaltetes Pack als HINWEIS, nicht als Fehler, und prüft die
  Schreibrechte des Portals auf die Pack-Listen.
- **`deploy/world-pack.sh apply`** aktualisiert bei einem ausgeschalteten Pack nur die Dateien. Es bleibt aus,
  ohne Neustart. Einschalten geht dann im Portal.
- Ein **Update-Rollback** stellt die Welt mitsamt ACLs wieder her (`tar --acls`).
- Neue Server (`setup.sh --install`) starten mit **allen** Funktionen an (`provision/packs.list`).

## Geprüft

Am 2026-11-06 in einer Wegwerf-VM (frisches Ubuntu 24.04, WSL2), nach `setup.sh --install` mit der README-Zeile;
nicht auf dem Laptop:

- `install.sh` vergibt die ACL, `verify.sh` meldet „Portal schaltet Funktionen“ OK.
- Wegpunkte, Events, Spawnfackel und Blaupause ausgeschaltet. `world_resource_packs.json` ist danach `[]`, Besitzer
  `minecraft` und ACL `mcportal:rw` bleiben. Nach dem Neustart stehen nur noch Statistik und Erfolge im „Pack Stack“,
  keine Script-Fehler. `verify.sh` meldet die vier als HINWEIS, die Spielregeln bleiben erhalten.
- Event starten bei ausgeschalteten Events: 409.
- `world-pack.sh mcportal_spawntorch apply` bei ausgeschalteter Spawnfackel: Dateien aktualisiert, bleibt aus,
  kein Neustart.
- Spawnfackel wieder eingeschaltet: „⏳ an nach Neustart“, nach dem Neustart „✓ an“. Das Protokoll zeigt alle
  `PACK_OFF`/`PACK_ON`.
- Oberfläche lokal mit dem Fake-Server: Warndialog, Zustände, „Jetzt neu starten“, Handy-Breite. Ohne Anmeldung
  nur Übersicht, Statistik, Karte, Funktionen. Admin-APIs antworten mit 401, die Funktionen-Liste zeigt nur
  Laufendes mit Rezepten und allen Bildern. Nach Events aus + Neustart ist der Events-Tab weg, und das Bild eines
  ausgeschalteten Items gibt 404.
- Unit-Tests `tests/test_packs.py` (15), die ganze Suite läuft durch.

## Änderung M17

1. **Was:** Neuer Portal-Dienst `app/services/packs.py` mit `GET /api/packs` und `PUT /api/packs/{funktion}`
   (nur Admin) sowie `GET /api/features` und `/api/features/icons/…` (für alle: was läuft, mit Rezepten), dazu
   der Tab „Funktionen“ (`app/web/packs.js`) und der Tab „Welt“ für Wetter/Tageszeit und das Feld `packs` im öffentlichen Status
   (welche Funktionen aus sind, ob ein Neustart nötig ist). `ServerFiles` liest und schreibt die Pack-Listen der
   Welt. Events-Endpunkte geben 409 zurück, wenn das Events-Pack aus ist. `install.sh` vergibt die ACL,
   `verify.sh` und `world-pack.sh` beachten ausgeschaltete Packs.
2. **Warum:** Andere Nutzer sollen auch reines Minecraft spielen können, ohne eigene Items, aber mit Statistik
   und Erfolgen.
3. **Dateien auf dem Server:** ACL `u:mcportal:rw` auf `worlds/<Welt>/world_behavior_packs.json` und
   `world_resource_packs.json` (steht in `/var/lib/mcportal/acl-added.txt`, `uninstall.sh` nimmt sie wieder
   weg). Neu: `/var/lib/mcportal/packs.json`, `/var/lib/mcportal/backups/packs/`.
4. **Backup:** vor jedem Schalten automatisch (s. o.). `install.sh` legt wie immer
   `/var/lib/mcportal/backups/<zeit>_pre_portal_install/` an.
5. **Rückgängig:** einschalten bzw. ausschalten im Portal. Von Hand: die Sicherung aus
   `/var/lib/mcportal/backups/packs/<zeit>/` zurückkopieren (`cat sicherung > datei`, damit die ACL bleibt) und
   Minecraft neu starten.

Auf dem Laptop installieren (danach im Portal neu laden):

```bash
sudo bash ~/mcportal-src/deploy/install.sh
```
