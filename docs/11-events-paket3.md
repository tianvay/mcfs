# Timed Events – Paket 3: Die Welt verändert sich (Plan, Änderung M13)

Stand: 2026-10-26 · Status: **installiert** 2026-10-26 18:51 (Portal, Events-Pack 1.3.0, Erfolge-Pack 1.3.0) · baut auf Paket 1 und 2 auf · nur stabile
Script-API, keine Experimente

## Ziel

Vier Events, von denen zwei **Blöcke in der Welt verändern** – deshalb zuerst eine Bestandsaufnahme der
vorhandenen Bauten und ein Rückgängig-Protokoll. Dazu Welle 3 von „Hab ich alles schon gesehen“ und die
Meta-Erfolge je Kategorie.

## Grundlage: Bauten sicher erkennen (vor allem anderen)

Das Bau-Register kennt seit dem 26.10. jeden Chunk, in dem ein Spieler etwas gesetzt hat – ältere Bauten nicht.
- **Bestandsaufnahme aus der Karte:** Der Karten-Leser liest beim Zeichnen ohnehin alle Chunks. Er markiert
  zusätzlich jeden Chunk, dessen Blöcke nicht nur natürlich sind (Bretter, Glas, Wolle, Truhen, Fackeln, Betten,
  Türen, Schienen, Zäune …). Das trifft auch Dörfer und Minenschächte – gewollt, dort soll kein Meteor einschlagen.
- Das Portal spielt diese Chunks nach jedem Kartenlauf über feste Konsolenbefehle ins Register des Events-Packs
  ein (`scriptevent mcfs:event register o12,-3;o12,-2;…`, in kleinen Paketen). Danach kennt das Register auch
  alle alten Bauten und bleibt mit dem nächtlichen Kartenlauf aktuell.
- **Rückgängig-Protokoll:** Jeder Block, den ein Event verändert, wird mit seinem vorherigen Zustand gespeichert.
  `scriptevent mcfs:event undo <id>` (im Portal ein Knopf am Event im Verlauf) stellt alles wieder her.

## Die vier Events

### ☄️ Meteorit
- Ankündigung „Ein Meteor nähert sich!“ mit 30 Sekunden Countdown und den Koordinaten (X/Y/Z).
- Ziel: 40–120 Blöcke von einem Spieler, **Chunk nicht im Register, auch kein Nachbar-Chunk**, die ganze
  Einschlagfläche natürlicher Boden.
- Einschlag: Feuer- und Funkenspur vom Himmel, Knall, Kamerawackeln für Spieler in der Nähe – **ohne echte
  Explosion**. Danach eine flache Mulde (Radius ≈ 5, 2–3 Blöcke tief) mit einer Schicht aus **Netherrack**,
  **Amethyst** (Blöcke und Kristalle) und **3–5 Diamanterzen**; kurz brennt es auf dem Netherrack.
- Ersetzt werden **nur natürliche Blöcke** (Gras, Erde, Stein, Sand, Kies, Schnee …), nie etwas anderes.
- Das Event läuft 30 Minuten (Teilnahme wie gewohnt); der Krater bleibt.

### 🌠 Sternschnuppen-Nacht (friedlich)
- Die nächste Nacht: alle 15–30 Sekunden zieht eine Sternschnuppe (Funkenspur) über den Himmel.
- Ab und zu fällt ein **Sternenstück** 10–30 Blöcke neben einem Spieler: Lichtsäule wie beim Boss, darin als
  Gegenstand Glowstone-Staub, Erfahrungsfläschchen, Lapis, selten ein Diamant oder Netherite-Schrott.
- Keine Blockänderungen.

### 🗺️ Schatzsuche
- Eine Truhe wird 150–400 Blöcke entfernt **3 Blöcke unter der Oberfläche** vergraben (nur unberührter Boden,
  Rückgängig-Protokoll). Hinweise alle 5 s: Richtung und „wärmer/kälter“; ab 10 Blöcken Funkeln über dem Versteck.
- Wer die Truhe zuerst öffnet, findet den Schatz (Diamanten, Smaragde, Goldbarren, ein verzaubertes Buch …),
  Meldung an alle. Nicht gefunden nach 30 Minuten Spielzeit → die Stelle wird wieder wie vorher.

### 👻 Spukort (Nacht)
- Ein Dorf in der Nähe eines Spielers (sonst ein Ort in der Wildnis) wird für eine Nacht verflucht:
  Seelensand-Nebel, Glockenläuten, Seelenfeuer-Funken, Skelette und Zombies kommen in Wellen; die Dorfbewohner
  sind geschützt wie bei der Invasion.
- Ziel: **15 Spuk-Monster besiegen** → „Der Fluch ist gebrochen!“, über dem Dorfplatz erscheint Beute
  (als Gegenstände, keine Truhe). Sonst endet der Spuk bei Sonnenaufgang.

## Erfolge (Erfolge-Pack 1.3.0)

| Erfolg | Bedingung |
|---|---|
| „Hab ich alles schon gesehen III“ | Meteorit, Sternschnuppen-Nacht, Schatzsuche und Spukort mitgemacht |
| „Volltreffer“ | beim Meteoriteneinschlag im Umkreis von 32 Blöcken gewesen |
| „Sterntaler“ | 10 Sternenstücke aufgesammelt |
| „Schatzsucher“ | als Erste/r den Schatz gefunden |
| „Geisterjäger“ | beim Brechen eines Fluchs dabei gewesen |

**Meta-Erfolge** (Kategorie = alle Events dieser Art mitgemacht):

| Erfolg | Kategorie | Events |
|---|---|---|
| „Wetterfest und Weltenbummler“ | Welt | Unwetter, Meteorit, Sternschnuppen-Nacht |
| „Schatzkammer“ | Ressourcen | Mining Rush, Glückstag, Schatzsuche |
| „Nachtwache“ | Mobs | Blutmond, Zombie-Invasion, Kopfgeld, Spukort |
| „Unzertrennlich“ | Community | 10 Events mit mindestens 3 Teilnehmern (Stufe 2 zu „Gemeinsam stark“) |

## Schritte

| Schritt | Inhalt |
|---|---|
| **W1** | Bestandsaufnahme alter Bauten (Karten-Leser + Portal → Register), Rückgängig-Protokoll |
| **W2** | ☄️ Meteorit |
| **W3** | 🌠 Sternschnuppen-Nacht |
| **W4** | 🗺️ Schatzsuche |
| **W5** | 👻 Spukort |
| **W6** | Erfolge-Pack 1.3.0 (Welle 3, Meta-Erfolge) |
| **W7** | Portal (Namen, Meteor-/Schatz-Ort, Rückgängig-Knopf) und Installation |

Aufwand: ≈ 4–5 Tage. Jeder Schritt mit Node-Tests und Testserver; die Blockänderungen prüfe ich dort
zusätzlich mit einem Vorher/Nachher-Vergleich und dem Rückgängig-Befehl.

## W1 – gebaut

- **Karten-Leser** (`app/map/natural.py`, `render.py`): Ein Chunk gilt als bebaut, wenn in den Abschnitten von
  8 Blöcken unter der niedrigsten bis zur höchsten Oberfläche ein nicht natürlicher Block vorkommt. Natürlich
  sind Gelände, Erze, Pflanzen, Bäume, Erzadern, Felsbrocken, Endstein usw.; unbekannte Blöcke zählen als bebaut.
  Ergebnis nach jedem Kartenlauf: `/var/lib/mcportal/map/built_chunks.json`. Echte Welt (Kopie): **1.053 bebaute
  Chunks in der Oberwelt** (Dörfer, eure Bauten, Ruinen) + 34 im Ende (Endstädte); +12 s Zeichenzeit.
- **Abgleich:** Nach jedem erfolgreichen Kartenlauf schickt das Portal die neuen Chunks über feste
  Konsolenbefehle (`scriptevent mcfs:event register …`, je 100) ans Events-Pack; schon gesendete merkt es sich.
  Ist der Server gerade nicht erreichbar, holt der nächste Kartenlauf das nach.
- **Events-Pack:** nimmt `register` an (nur gültige Chunk-Schlüssel, höchstens 200 je Befehl) und führt ein
  **Rückgängig-Protokoll** (`changeBlocks` / `undo <id>`): jeder von einem Event geänderte Block mit vorherigem
  Zustand; Rückgängig stellt nur Blöcke wieder her, die noch so sind, wie das Event sie hinterlassen hat.
- **Portal:** Reiter Events zeigt „🛡️ Geschützt: … Chunks mit Bauten“.
- **Getestet:** 17 Node-Tests (neu: register/undo-Befehle), Python-Tests (Erkennung im Karten-Leser, natürliche
  Blöcke, Abgleich in 100er-Paketen, nur neue, nicht bei Server offline). Testserver: Import (doppelte
  übersprungen, ungültige abgelehnt), importierter Chunk schützt vor Blitz, Rückgängig 8 von 9 Blöcken (einer war
  „von einem Spieler“ verändert und bleibt). Lokal: Kartenlauf → 1.087 Chunks übergeben.

## W2 – gebaut (Meteorit)

- **Ziel:** 40–120 Blöcke von einem zufälligen Spieler in der Oberwelt; der Einschlag-Chunk und alle 8 Nachbarn
  nicht im Bau-Register; jede Säule im Umkreis von 6 Blöcken echter Boden (kein Laub, kein Wasser) und höchstens
  3 Blöcke Höhenunterschied. Je Sekunde 10 Versuche; nach 2 Minuten ohne passenden Ort „verglüht“ der Meteor.
- **Ablauf:** Titel „Meteor im Anflug!“ + Chat mit X/Y/Z, Countdown 30 s (alle 5 s in der Aktionsleiste), in den
  letzten Sekunden Feuerspur vom Himmel, dann großer Explosions-Effekt, Knall, Kamerawackeln bis 64 Blöcke –
  **keine echte Explosion, kein Feuer** (Lava- und Rauchpartikel 20 s lang).
- **Krater** (`planCrater`): Mulde Radius 5, Mitte 3 tief; Boden aus Netherrack und ~25 % Amethyst (teils mit
  Kristallen), 3–5 Diamanterze in der tiefen Mitte, Netherrack-Spritzer am Rand. Verändert werden nur Blöcke, die
  die Welt selbst erzeugt hat (`isMeteorReplaceable`). Jeder Block steht im Rückgängig-Protokoll `meteor-<n>`.
- Danach gelten Einschlag-Chunk und Nachbarn als bebaut (kein zweiter Meteor, kein Schatz dort); sofort gespeichert.
- Wer beim Einschlag im Umkreis von 32 Blöcken war → Meldung `meteor_hit` (Erfolg „Volltreffer“, W6).
- **Rückgängig** nur, wenn der ganze Bereich geladen ist (jemand in der Nähe); sonst Hinweis, Protokoll bleibt.
- **Getestet:** 18 Node-Tests (neu: Krater-Profil, Materialien, 3–5 Diamanten, ersetzbare Blöcke, Boden-Prüfung,
  Pflanzen/Schnee). Testserver: Krater mit 215 Blöcken (60 Netherrack, 20 Amethyst, 11 Kristalle, 3 Diamanterze);
  nach Neustart Register erhalten; Rückgängig bei nicht geladenem Bereich abgelehnt, danach alle 215 zurück.
  Zwei Fehler dabei gefunden und behoben (Rückgängig löschte sein Protokoll bei ungeladenem Bereich; Register
  wurde nach dem Einschlag erst nach 30 s gespeichert).

## W3 – gebaut (Sternschnuppen-Nacht)

- Nacht-Event (wartet auf die Nacht, endet bei Sonnenaufgang, Schlafsperre wie die anderen).
- Alle 15–30 s eine **Sternschnuppe** über jedem Spieler in der Oberwelt: Lichtspur 30–50 Blöcke lang, 45–65
  Blöcke über ihm, in einer halben Sekunde gezeichnet.
- Je Spieler alle 1–2 Minuten (erstes nach 30 s) ein **Sternenstück**: fällt mit Lichtspur 10–30 Blöcke entfernt
  auf echten Boden, kleiner Knall, bleibt in einer Lichtsäule liegen. Inhalt: Glowstone-Staub 40 %,
  Erfahrungsfläschchen 30 %, Lapis 15 %, Diamant 10 %, Netherite-Schrott 5 % (100.000 Würfe nachgezählt).
- Aufgesammelt: Wer beim Verschwinden höchstens 3 Blöcke daneben stand, bekommt es angerechnet (Log `star`,
  Meldung ans Erfolge-Pack für „Sterntaler“). Liegen gebliebene Stücke bleiben nach dem Event Beute.
- **Getestet:** 19 Node-Tests (neu: Beute, Bahnen, Linienpunkte). Testserver: wartet am Tag, startet bei Nacht,
  3 Sternenstücke 12–30 Blöcke entfernt, verfolgt; Ende bei Sonnenaufgang. Aufsammeln nur im Spiel prüfbar.

## W4 – gebaut (Schatzsuche)

- **Ort:** 150–400 Blöcke von einem zufälligen Spieler, Chunk und Nachbarn nicht im Bau-Register. Festgelegt beim
  Start (das Register braucht keinen geladenen Bereich), **vergraben erst, wenn jemand in die Nähe kommt** und der
  Bereich geladen ist: Truhe 3 Blöcke unter echtem Boden, alle Blöcke darüber natürlich; passt die Stelle nicht,
  wird bis 8 Blöcke daneben gesucht, sonst ein neuer Ort in der Nähe.
- **Inhalt:** 2–4 Diamanten, 4–8 Smaragde, 3–6 Goldbarren, 4–8 Erfahrungsfläschchen und eins von Goldener Apfel,
  Namensschild, Sattel, Totem der Unsterblichkeit – zufällig in der Truhe verteilt.
- **Hinweise** alle 5 s: Himmelsrichtung, grobe Entfernung („noch weit weg“ … „ganz nah“ … „direkt hier – grabt
  nach!“) und „wärmer“/„kälter“ gegenüber dem letzten Hinweis; ab 16 Blöcken Funkeln über der Stelle.
- **Gefunden** = Truhe als Erste/r geöffnet (oder ausgegraben): Titel für alle, Log `treasure`, Meldung
  `treasure_found` (Erfolg „Schatzsucher“). Die Truhe bleibt dann.
- **Nicht gefunden** nach 30 Min. Spielzeit (oder beendet): Truhe samt Inhalt weg, Boden wie vorher
  (Rückgängig-Protokoll). Ist der Bereich nicht geladen, wird es jede Minute erneut versucht, bis es klappt.
- **Getestet:** 20 Node-Tests (neu: Beute, Entfernungsstufen, wärmer/kälter). Testserver: Truhe 3 unter der
  Oberfläche mit 5 Beute-Stapeln, Hinweis „Richtung Osten, nah“, beim Beenden Truhe weg und Boden zurück.
  Öffnen durch einen Spieler nur im Spiel prüfbar.

## W5 – gebaut (Spukort)

- Nacht-Event. Bei Einbruch der Nacht: das Dorf bei einem zufälligen Spieler (≥ 3 Dorfbewohner im Umkreis von
  96 Blöcken, Mittelpunkt), sonst der Ort des Spielers. Chatmeldung mit X/Z und dem Ziel „15 Spukgestalten“.
- Im Spukgebiet (48 Blöcke): **Seelensand-Nebel** (`fog_soulsand_valley`, beim Verlassen und am Ende entfernt),
  Seelen-Funken, alle 20 s eine tiefe Glocke. **Kein Dunkelheits-Effekt** (wie besprochen).
- Alle 45 s eine Welle (erste nach 10 s), solange jemand im Umkreis von 96 Blöcken ist: 3 + 1 je Spieler im
  Gebiet, höchstens 20 gleichzeitig; Skelette 50 %, Zombies 40 %, Eiswanderer 10 %; 16–32 Blöcke vom Platz, nicht
  in bebauten Chunks; Dorfbewohner geschützt wie bei der Invasion.
- Jede von einem Spieler besiegte Spukgestalt zählt (Aktionsleiste „Fluch: 7 / 15“). Bei 15: **„Der Fluch ist
  gebrochen!“**, Belohnung auf dem Platz (3–6 Smaragde, 4–8 Eisen, 4–8 Erfahrungsfläschchen, Goldener Apfel,
  Amethyst- oder Echo-Splitter), Meldung `curse_broken` an alle im Gebiet (Erfolg „Geisterjäger“), Spuk endet,
  übrige Spukgestalten verschwinden. Sonst endet er bei Sonnenaufgang.
- **Getestet:** 21 Node-Tests (neu: Mob-Auswahl, Wellen, Belohnung). Testserver: Welle mit 4 Spukgestalten,
  15 Siege → Fluch gebrochen, Belohnung auf dem Platz, alle Spukgestalten weg; ohne Siege Ende bei Sonnenaufgang.
  Nebel, Glocke und Kämpfe nur im Spiel prüfbar.

## W6 – gebaut (Erfolge-Pack 1.3.0, Events-Pack 1.3.0)

- **Welle 3** „Hab ich alles schon gesehen III“ (Meteorit, Sternschnuppen-Nacht, Schatzsuche, Spukort).
- **Spezial:** Volltreffer (beim Einschlag im Umkreis von 32 Blöcken), Sterntaler (10 Sternenstücke),
  Schatzsucher (als Erste/r gefunden), Geisterjäger (beim Brechen eines Fluchs dabei).
- **Meta-Erfolge** je Kategorie (`EVENT_CATEGORIES`, gleiche Einteilung wie `TYPES[…].category` im Events-Pack):
  Wetterfest und Weltenbummler (Welt: Unwetter, Meteorit, Sternschnuppen), Schatzkammer (Ressourcen: Mining Rush,
  Glückstag, Schatzsuche), Nachtwache (Mobs: Blutmond, Zombie-Invasion, Kopfgeld, Spukort); Community:
  „Gemeinsam stark“ bekommt Stufe 2 **Unzertrennlich** (10 Events mit mindestens 3 Teilnehmern).
- Test sichert: jede Event-Art steht in genau einer Kategorie und einer Welle.
- **Getestet:** 9 Node-Tests im Erfolge-Pack; Testserver mit allen drei Packs und nachgestellten Meldungen: alle
  Zähler kommen an (Welle 3 = 4, Kategorie Welt = 3, Sterne, Schatz, Fluch, Volltreffer).

## W7 – gebaut (Portal)

- Reiter Events kennt die vier neuen Events (☄️ Meteorit, 🌠 Sternschnuppen, 🗺️ Schatzsuche, 👻 Spukort) mit
  Details: Meteor-Ort und ob er eingeschlagen ist, Schatz „wird vergraben … / vergraben / gefunden“ (ohne Ort –
  sonst wäre es keine Suche), Spukort mit Ort und „Fluch 6 / 15“. Verlauf zeigt auch „gefunden“, „Fluch
  gebrochen“, „verglüht“.
- **Blockänderungen** (Karte „Welt“): jede Rückgängig-ID, die das Events-Pack meldet, mit Knopf „Rückgängig“
  (Rückfrage). Das Portal nimmt nur IDs aus dieser Liste an (`POST /api/gameevents/undo`, Befehl
  `commands.event_undo`); Protokoll „Event rückgängig“.
- **Getestet:** Python-Tests (Rückgängig nur für gemeldete IDs, ungültige abgelehnt, neue Events startbar);
  lokal im Browser auf PC und Handy: Details der neuen Events, Rückgängig mit Rückfrage und Protokoll.

## Installation (W7)

1. `install.sh` (Portal).
2. `NO_RESTART=1 world-pack.sh mcportal_events apply` und `world-pack.sh mcportal_achievements apply`
   (Events-Pack 1.3.0, Erfolge-Pack 1.3.0, ein Neustart).
3. **Sofort danach einen Kartenlauf** starten: Er liefert die Bestandsaufnahme der alten Bauten an das neue
   Events-Pack – bevor ein automatischer Meteorit oder Schatz kommen kann.

## Installiert (2026-10-26 18:51)

- Sicherungen: `~/mcportal-backups/2026-10-26_18-51-09_pre_mcportal_events` und `…_pre_mcportal_achievements`.
- Alle vier Behavior Packs ohne Script-/Inhaltsfehler; Startprüfung nach 4 s OK; Portal sieht zehn Events.
- Kartenlauf direkt danach (96 s): 1.087 Chunks mit Bauten in 11 Paketen ans Events-Pack übergeben,
  Bau-Register von 1 auf **1.087** Chunks. Ab jetzt hält es jeder nächtliche Kartenlauf aktuell.

## Nachtrag: Creeper-Chaos, Hexenzirkel, dichterer Spuk-Nebel (Events-Pack 1.4.0, Erfolge-Pack 1.4.0, Grafik-Pack 1.1.0)

- **Spuk-Nebel:** eigener Nebel `mcfs:haunt` im Grafik-Pack (`fogs/mcfs_haunt_fog_setting.json`): Sicht nur noch
  ≈ 20 Blöcke, violett-grau – die eingebauten Minecraft-Nebel lassen sich nicht verdichten. Reicht jetzt **96**
  statt 48 Blöcke weit (das Spukgebiet für Wellen und Belohnung bleibt 48).
- **💥 Creeper-Chaos** (Nacht): alle 30 s je Spieler an der Oberfläche 2–4 Creeper 16–28 Blöcke entfernt, nur in
  der Wildnis, höchstens 16 im Umkreis; ~20 % **geladen** (`minecraft:become_charged`). **Explosionen der
  Event-Creeper zerstören keine Blöcke** (`beforeEvents.explosion` → keine Blöcke), Schaden an Spielern bleibt.
  Geladener Creeper besiegt → 1 Diamant.
- **🧙 Hexenzirkel** (Nacht): 3–5 eigene Hexen `mcfs:coven_witch` (Vanilla-Hexe, 1,15-fach, grün getönt,
  verschwinden nicht von selbst) im Kreis 40–80 Blöcke von einem Spieler; Funkensäule, Hinweise alle 5 s
  („Hexenzirkel (3 übrig): …“). Alle besiegt → Netherwarze, Enderperlen, Glowstone, Redstone, Erfahrung; ohne
  Spieler-Beteiligung keine Belohnung.
- **Erfolge 1.4.0:** Hab ich alles schon gesehen IV (beide), Knallhart (10 Chaos-Creeper), Entschärft (geladenen
  Creeper besiegt), Hexenmeister (Zirkel gesprengt); Mob-Kategorie mit zwei Stufen: Nachtwache (4 verschiedene
  Mob-Events), **Herr der Nacht** (alle 6).
- `tools/make_bosses.py` erzeugt jetzt alle eigenen Mobs (drei Bosse + Hexe).
- **Getestet:** 22 + 10 Node-Tests, Python-Tests. Testserver: Creeper-Gruppen bis zur Obergrenze, geladene haben
  `is_charged`, Explosion lässt den Boden heil; Zirkel mit `mcfs:coven_witch` in 1,15-facher Größe, Ende ohne
  Spieler ohne Belohnung. Portal lokal. Nebel-Dichte nur im Spiel sichtbar.

## Was sich auf dem Server ändert

- Events-Pack 1.3.0, Erfolge-Pack 1.3.0, Portal (Karten-Leser, Register-Abgleich, Knöpfe).
- **Erstmals dauerhafte Blockänderungen** (Meteor-Krater; Schatz-Truhe nur vorübergehend) – jeweils mit
  Rückgängig-Protokoll, nur auf natürlichem Boden fernab aller bekannten Bauten.
- Rückweg wie immer per `world-pack.sh … rollback`; Krater per Rückgängig-Knopf.

## Zu entscheiden (Vorschläge in Klammern)

1. Meteor-Größe: Radius ≈ 5, 2–3 tief, 3–5 Diamanterze? (ja)
2. Der Krater bleibt dauerhaft (Rückgängig nur bei Bedarf)? (ja)
3. Schatz-Truhe vergraben (vorübergehende Blockänderung) statt nur Gegenstände? (ja)
4. Spukort mit leichtem Dunkelheits-Effekt für Spieler im Spukgebiet – oder für die Kinder zu gruselig? (ohne
   Dunkelheit, nur Nebel und Geräusche)
5. Namen der Meta-Erfolge (wie oben – gern eigene Ideen)
