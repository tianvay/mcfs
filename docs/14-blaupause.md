# Blaupause (Änderung M15)

Stand: 2026-11-02 (Version 1.0.0) · Packs `mcportal_blueprint` (Verhalten) + `mcportal_blueprint_rp` (Grafik)

## Für Spieler

**Blaupause craften** (Werkbank):

```text
[ Diamant  ] [ Smaragd ] [ Diamant  ]
[ Smaragd  ] [ Papier  ] [ Smaragd  ]
[ Diamant  ] [ Smaragd ] [ Diamant  ]
```

→ **Blaupause** (leer, bis zu 16 stapelbar).

**Bereich speichern:**

1. Blaupause in die Hand, **Rechtsklick auf einen Block** (PC: Rechtsklick, Xbox: LT, Tablet: antippen) → Ecke 1.
   Das Item wird zu **„Blaupause – Ecke 2 wählen“** (gelbe Ecke im Bild).
2. Beim Umherschauen zeigt ein hellblauer Umriss den Bereich, unten steht die Größe. Höchstens
   **32 × 32 × 32 Blöcke**; ist er größer, wird der Umriss rot.
3. **Rechtsklick auf die gegenüberliegende Ecke** → gespeichert. Ein Fenster fragt nach dem Namen
   (z. B. „Stadtmauer“, sonst „Bauplan 1“). Das Item heißt dann **„Blaupause: Stadtmauer“** (Mauer im Bild, glänzt).

Neu anfangen, solange erst Ecke 1 gesetzt ist: **Schleichen + Benutzen in die Luft**.

**Einsetzen:** Die gefüllte Blaupause halten. Der Umriss zeigt, wo der Bau landet, gedreht in Blickrichtung.

- Was beim Speichern **vorne links unten** war, kommt an den angeklickten Platz. Auf den Boden geklickt heißt das:
  direkt darauf.
- Der Bau steht vor dem Spieler und erstreckt sich nach rechts. Für eine Stadtmauer: ein Stück einsetzen, dann
  neben dessen Ende klicken und das nächste setzen.
- Der ganze Bereich muss frei sein. Erlaubt sind Luft, Gras, Blumen, Schnee, Laub am Boden und Wasser. Sonst
  sagt eine Meldung, welcher Block wo im Weg ist. Niemand darf im Bauplatz stehen.
- **Rechtsklick** setzt ein. Danach ist die Blaupause **verbraucht**, auch im Kreativmodus.

**Kopieren** (Werkbank): die gefüllte Blaupause statt des Papiers in die Mitte legen, außen wieder 4 Diamanten und
4 Smaragde → **2 Blaupausen** mit demselben Bauplan. Jede weitere Kopie kostet also 4 Diamanten und 4 Smaragde.
Das Ergebnis heißt kurz „Blaupause (Kopie)“ und wird im Inventar nach einem Moment zu zwei
„Blaupause: <Name>“.

## Was nicht mitkopiert wird

Regeln in `scripts/core.js` (`blockRule`), Tests in `tests/core.test.mjs`. Beim Speichern steht in der Meldung,
was weggelassen wurde (z. B. „Nicht mitkopiert: 4 × diamond block, 2 × iron ore“).

| Was | Wird zu |
|---|---|
| **Wertvoll:** Netherit-, Diamant-, Smaragd-, Gold-, Eisen-, Lapis-, Kohleblock, Rohgold/-eisen/-kupferblock, antiker Schrott, Amethystblock, knospender Amethyst, Obsidian, weinender Obsidian, Schwamm (auch nass), Seelaterne, Glowstone, Kupfer als ganzer Block (auch angelaufen, gewachst, geschnitten, gemeißelt) | Luft |
| **Wertvoll (Gegenstände als Block):** Leuchtfeuer, Aquisator, Leitstein, schwerer Kern, Zaubertisch, Amboss (alle Stufen), Witherskelettschädel, Drachenkopf, Drachenei | Luft |
| **Erze** (Stein, Tiefenschiefer, Nether), vergoldeter Schwarzstein | Stein / Tiefenschiefer / Netherrack / Schwarzstein (die Mauer bekommt kein Loch) |
| **Nicht beschaffbar / Technik:** Grundgestein, verstärkter Tiefenschiefer, Portale und Endportalrahmen, Spawner, Tresore, seltsamer Sand/Kies, Befehls- und Konstruktionsblöcke, Barriere, Lichtblock, Erlauben/Verbieten/Grenze, eigene `mcfs:`-Blöcke | Luft |
| **Behälter:** Truhe, Redstone-Truhe, Endertruhe, Fass, alle Shulkerkisten, Kupfertruhen | Luft |
| **Halten Items, aber ein Skript kann den Inhalt nicht prüfen:** Crafter, gemeißeltes Bücherregal, verzierter Krug, Rahmen (auch leuchtend), Lagerfeuer (beide), Regale | Luft |

**Bleibt, aber garantiert leer:** Trichter, Spender, Werfer, Öfen (alle drei), Braustand, Lesepult, Plattenspieler.
Das sind genau die Blöcke, deren Inhalt ein Skript sehen kann. Nur bei ihnen lässt sich nachweisen, dass sie leer
ankommen. Grundregel: Alles, worin Items liegen können, ist in der Blaupause leer gespeichert. Geht das nicht
nachweisbar, wird Luft gespeichert. Drei Sicherungen:

1. Beim Speichern wird jeder dieser Blöcke in der Blaupause geleert.
2. Hat ein Block, der nicht auf der Liste steht, trotzdem ein Inventar (z. B. ein neuer Block nach einem
   Minecraft-Update), wird er ebenfalls geleert.
3. Nach dem Einsetzen leert das Pack alle eingesetzten Behälter noch einmal. Läge doch etwas darin, steht ein
   `error` im Log.

**Bleibt:** alles andere, auch **Redstone-Blöcke**, Kupferstufen, -treppen, -gitter, -lampen, -türen, Kolben,
Beobachter, Wasser, Lava.

**Kreaturen und Gegenstände** (Tiere, Rüstungsständer, Loren, liegende Items) werden nie mitkopiert. Bündel
können nur in Behältern liegen, und deren Inhalt fällt immer weg.

## Technik

- **Speichern:** `world.structureManager.createFromWorld` (zuerst im Speicher, ohne Kreaturen). Dann wird jeder
  Block mit `Structure.setBlockPermutation` geprüft und ersetzt, danach kommt `saveToWorld`. Das läuft als
  `system.runJob` mit 256 Blöcken je Schritt; 16 × 32 × 16 Blöcke dauerten auf dem Testserver 0,6–0,8 s.
- **Behälter:** Eine Struktur speichert den Inhalt von Behältern mit (gemessen: Ohne Leeren kam jeder Trichter, Ofen
  usw. mit Item wieder an). Einen Behälter „leert“ man, indem man denselben Block noch einmal setzt. Der Eintrag
  `emptied` merkt sich die Stellen, damit nach dem Einsetzen dort noch einmal `container.clearAll()` läuft.
- **Gespeichert** in der Welt: Struktur `mcfs:bp_<n>` und die dynamic property `mcfs_bp:<n>` mit Name, Besitzer,
  Größe, Blickrichtung beim Speichern, weggelassenen Blöcken und `refs` (Anzahl der gefüllten Blaupausen). Wird die
  letzte eingesetzt, löscht das Pack Struktur und Eintrag. Die Blaupause selbst trägt nur die Struktur-ID
  (dynamic property am Item; geht nur bei nicht stapelbaren Items).
- **Drehen:** `structureManager.place` mit `Rotate90/180/270`. Rotate90 dreht im Uhrzeigersinn: (x, z) →
  (Tiefe − 1 − z, x), auf dem Testserver gemessen. Die Lage (`placement` in `core.js`) ist so berechnet, dass die
  Ecke „vorne links unten“ auf dem angeklickten Block landet.
- **Kopien:** Ein Rezept-Ergebnis kann keine Daten tragen. Das Rezept liefert darum 2 × `mcfs:blueprint_copy`
  (Platzhalter). Alle 5 Ticks zählt das Pack die gefüllten Blaupausen im Inventar (auch die am Mauszeiger). Ist eine
  verschwunden, z. B. ins Crafting-Feld, wird sie gemerkt (bis 10 Minuten). Taucht ein Platzhalter auf, bekommt er
  den zuletzt verschwundenen Bauplan. Findet sich in 3 s keiner (z. B. Kopie aus einem Crafter-Block), werden es leere
  Blaupausen.
- **Umriss:** eigene Partikel `mcfs:blueprint_dot` (hellblau) und `mcfs:blueprint_dot_red` (zu groß), alle 10 Ticks
  nur für den haltenden Spieler, auf den Kanten des Bereichs.
- **Log:** `[mcportal-blueprint] {"v":1,"event":"saved|placed|copied|copy_unresolved|error",…}` und die
  Startzeile. Das Portal wertet noch nichts davon aus.
- **Bilder:** `mcportal_blueprint_rp/tools/make_icon.py`.

## Geprüft (2026-11-02, Testserver, Script-API 2.10.0)

- Probe: `structureManager`, `Structure.get/setBlockPermutation`, `saveToWorld`, `place` mit Drehung, dynamic
  properties an nicht stapelbaren Items, Lore, `PlayerCursorInventoryComponent` sind stabil verfügbar. Grenze der
  Engine: 64 × 384 × 64.
- Selbsttest (`tests/engine_selftest.js`): Ein Teststück 4 × 3 × 2 enthält 18 verschiedene Blöcke, darunter eine Truhe
  mit Diamanten, einen Trichter mit Eisen, einen Diamantblock, Erze, Obsidian und Kupfer. Es wurde gespeichert und in
  alle vier Richtungen eingesetzt. Jeder Block lag genau dort, wo `placement`/`placedCell` es vorhersagen. Die
  weggelassenen Blöcke waren Luft bzw. Stein, der Trichter war leer, die Treppe mitgedreht. Die Platzprüfung lehnt
  einen belegten Platz ab und nimmt einen freien an. Keine Script-, Rezept- oder Item-Fehler.
- Behälter-Test: 19 Blöcke, die Items halten können, je mit einem Item gefüllt. Eine rohe Struktur kopierte bei allen
  mit Inventar das Item mit. Über die Blaupause kamen alle 9 geleerten Blöcke mit 0 Items an, die zweite Leerung
  fand nichts mehr. Truhe, Fass, Crafter, Bücherregal, Krug, Lagerfeuer und Regal waren Luft.
- 15 Node-Tests: Sperrliste, Erze, Behälter, Größe, Blickrichtung, Ankerecke, alle Drehungen, Kopien-Zuordnung.
- **Noch nicht im Spiel geprüft:** Craften (auch die Kopie mit der gefüllten Blaupause als Zutat), Markieren,
  Umriss, Namensfenster, Einsetzen, „Schleichen + Benutzen“, Zuordnung der Kopie über das Crafting-Feld.

## Änderung M15

1. **Was:** neue Packs `mcportal_blueprint` (Verhalten) + `mcportal_blueprint_rp` (Grafik), je ein Eintrag in
   `world_behavior_packs.json` / `world_resource_packs.json`.
2. **Warum:** wiederkehrende Bauten (Mauern, Redstone-Schaltungen, Waldstücke) teuer, aber einfach vervielfältigen.
3. **Dateien:** nur die genannten; `server.properties` bleibt (das Grafik-Pack ist seit M9 Pflicht).
4. **Backup:** `world-pack.sh` legt `<Home des Minecraft-Nutzers>/mcportal-backups/<zeit>_pre_mcportal_blueprint*/` an.
5. **Rückgängig:** siehe unten. Gespeicherte Baupläne bleiben ungenutzt in der Welt, Blaupausen verschwinden aus
   den Inventaren. Eingesetzte Bauten bleiben stehen.

## Installieren / rückgängig

Wenn niemand spielt, auf dem Server (ein Neustart):

```bash
sudo NO_RESTART=1 bash ~/mcportal-src/deploy/world-pack.sh mcportal_blueprint_rp apply
```

```bash
sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_blueprint apply
```

Rückgängig: `sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_blueprint rollback` (danach das RP genauso).
