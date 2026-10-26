# Timed Events – Paket 3: Die Welt verändert sich (Plan, Änderung M13)

Stand: 2026-10-26 · Status: **Plan, noch nicht umgesetzt** · baut auf Paket 1 und 2 auf · nur stabile
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
