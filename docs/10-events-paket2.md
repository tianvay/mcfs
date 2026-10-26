# Timed Events – Paket 2: Nachtgefahren (Plan, Änderung M12)

Stand: 2026-10-26 · Status: **installiert** 2026-10-26 16:19 (Portal, Events-Pack 1.1.0, Erfolge-Pack 1.2.0) · baut auf Paket 1 auf (`docs/09-events.md`) ·
nur stabile Script-API, keine Experimente

## Ziel

Drei neue Events für das bestehende Event-Gerüst – Zeitplan, Teilnahme, Portal-Kachel und Countdown funktionieren
wie in Paket 1. Dazu Welle 2 von „Hab ich alles schon gesehen“ und eigene Erfolge.

**Geprüft auf dem Testserver** (Probe-Pack): Tageszeit lesen (`getTimeOfDay`), roter Bildschirm
(`camera.fade`), Wölfe wütend machen (`triggerEvent("minecraft:become_angry")`), Namensschild, Effekte
(Widerstand, Stärke, Extra-Leben: Zombie 20 → 40 Lebenspunkte), Rüstung für Mobs (nur per Befehl `replaceitem` –
die Script-Schnittstelle kann das bei Mobs nicht), Markierung per Tag und Wiederfinden, Dorfbewohner
(`minecraft:villager_v2`), Nebel-Befehl (`fog … push`).

## Nacht-Events: „heute Nacht“

Zombie-Invasion und Blutmond gelten für **die nächste Nacht**:
- Startet das Event am Tag, wird es angekündigt („Heute Nacht greifen Zombies an!“) und **wartet auf die Nacht**.
  Startet es nachts, beginnt es sofort. Es endet bei Sonnenaufgang (eine Minecraft-Nacht ≈ 8 Minuten).
- **Schlafen ist während der Nacht-Events gesperrt** („Heute Nacht schläft niemand!“) – sonst wäre das Event
  mit einem Bett übersprungen.
- Portal-Countdown: erst „beginnt in mm:ss“ (bis zur Nacht), dann „noch mm:ss“ (bis Sonnenaufgang).
- Alle Event-Mobs tragen eine Markierung; was bei Sonnenaufgang noch lebt, verschwindet (auch wenn ein Chunk
  erst später wieder geladen wird). Es bleiben keine wütenden Wölfe oder Bosse dauerhaft in der Welt.

## Die drei Events

### 🧟 Zombie-Invasion
- Bei Einbruch der Nacht sucht das Pack **Dörfer in der Nähe von Spielern** (Dorfbewohner im Umkreis von
  96 Blöcken; Bauwerke selbst kann die Schnittstelle nicht finden). Kein Dorf in der Nähe → die Zombies kommen
  zu den Spielern.
- **Wellen** jede Minute: 3 + 1 je Spieler Zombies (gelegentlich Wüstenzombie oder Zombie-Dorfbewohner),
  24–40 Blöcke vom Dorf entfernt, höchstens 30 gleichzeitig.
- **Bessere Beute** für jeden Zombie, den ein Spieler während der Invasion besiegt: zusätzlich z. B. Eisenbarren,
  Karotten/Kartoffeln, mit kleiner Chance Smaragd, Erfahrungsfläschchen, sehr selten ein Goldener Apfel.
- Vorschlag: **Dorfbewohner sind in der Invasionsnacht geschützt** (Widerstands-Effekt) – auf „Einfach“
  würden Zombies sie sonst töten, und das Handelsdorf der Kinder wäre leer.

### 🌕 Blutmond
- Bei Einbruch der Nacht: kurzer **roter Bildschirm**, Titel „Blutmond!“, Knurren; **rötlicher Nebel** die
  ganze Nacht (wird bei Sonnenaufgang wieder entfernt).
- Alle 90 s erscheint bei jedem Spieler an der Oberfläche ein **Wolfsrudel** (3–5 Wölfe) 20–32 Blöcke entfernt –
  **nur in der Wildnis** (Bau-Register + Naturboden wie bei den Blitzen), nie in Basis oder Dorf; höchstens
  12 Blutmond-Wölfe je Spieler.
- Vorschlag: Die Wölfe sind **wütend** und greifen an. Besiegte Blutmond-Wölfe lassen Knochen fallen.

### 👑 Kopfgeld-Boss
- Ein **benannter Boss** erscheint 40–80 Blöcke von einem zufälligen Spieler entfernt (in der Wildnis), z. B.:
  - „Bernd der Zombiekönig“ – Zombie mit Diamanthelm und Eisenschwert, Widerstand, ≈ 60 Lebenspunkte
  - „Skelett-Sven“ – Skelett mit Goldhelm, schneller, ≈ 50 Lebenspunkte
  - „Spinnen-Susi“ – Spinne, Stärke, ≈ 50 Lebenspunkte
  Helme schützen Zombie und Skelett vor dem Verbrennen am Tag.
- Ankündigung mit Koordinaten; alle 30 s in der Aktionsleiste: „Bernd: 54 Blöcke Richtung Nordwest“.
- **Besiegt** → Kopfgeld fällt auf den Boden (z. B. 3 Diamanten, 5 Smaragde, Goldener Apfel, Erfahrung) und
  Meldung an alle: „Steve hat Bernd den Zombiekönig besiegt!“. **Nach 20 Minuten Spielzeit** entkommt er.

## Erfolge (Erfolge-Pack 1.2.0)

| Erfolg | Bedingung |
|---|---|
| „Hab ich alles schon gesehen II“ | Zombie-Invasion, Blutmond und Kopfgeld-Boss mitgemacht |
| „Hirn-Rissig“ | 20 Zombies während einer Zombie-Invasion besiegt |
| „Wer hat Angst vorm bösen Wolf?“ | 10 Blutmond-Wölfe besiegt |
| „Kopfgeldjäger“ | bei einem besiegten Boss dabei gewesen (Todesstoß oder im Umkreis von 32 Blöcken) |

Die Events zählen auch für Mittendrin/Eventhopper/Partylöwe.

**Meta-Erfolge** (Kategorien Welt / Ressourcen / Mobs / Community): Die Kategorien quer über die Pakete füllen
sich erst mit Paket 3 sinnvoll (Mobs = Paket 2 + Spukort, Welt = Unwetter + Meteorit + Sternschnuppen …).
Vorschlag: jetzt nur **„Gemeinsam stark“** (ein Event mit mindestens 3 Teilnehmern gleichzeitig), die übrigen
Meta-Erfolge mit Paket 3.

## Portal

- Namen/Symbole der neuen Events in der Kachel; Countdown mit Phase („beginnt in …“ / „noch …“).
- Beim Kopfgeld-Boss: Name des Bosses und zuletzt gemeldeter Ort.
- Start-Knöpfe automatisch auch für die neuen Events (kommen aus der Liste des Packs).

## Schritte

| Schritt | Inhalt |
|---|---|
| **N1** | Nacht-Gerüst im Events-Pack: Phasen warten/läuft, Schlafsperre, Aufräumen markierter Mobs; **Blutmond** |
| **N2** | **Zombie-Invasion** (Dorfsuche, Wellen, Beute, Dorfbewohner-Schutz) |
| **N3** | **Kopfgeld-Boss** (Bosse, Hinweise, Kopfgeld, Entkommen) |
| **N4** | Erfolge-Pack 1.2.0 |
| **N5** | Portal: Namen, Phasen-Countdown, Boss-Info |
| **N6** | Installation: `install.sh`, dann Events-Pack 1.1.0 + Erfolge-Pack 1.2.0 mit einem Neustart |

Jeder Schritt mit Node-Tests für die Logik und einem Lauf auf dem Testserver (dort ohne Spieler – Spawns,
Phasen und Aufräumen lassen sich mit Test-Spielerpositionen prüfen, Kämpfe nur im Spiel).

## N1 – gebaut

- **Nacht-Events** (`core.js`: `nightStep`, `isNight` …): Phase `waiting` (Restzeit = bis zur Nacht) → `running`
  (Restzeit = bis Sonnenaufgang) → Ende „dawn“. Geprüft wird jede Sekunde über die Tageszeit. Teilnahme zählt nur
  in der Nacht selbst (`ran`). Der Zustand im Log enthält jetzt `phase`.
- **Schlafsperre:** Bett benutzen wird abgebrochen („Heute Nacht schläft niemand!“), solange ein Nacht-Event
  wartet oder läuft.
- **Event-Mobs** tragen `mcfs_ev` + `mcfs_ev_<art>`; jede Minute und bei jedem Event-Ende werden die entfernt,
  deren Event nicht mehr läuft (auch wenn ihr Chunk beim Ende nicht geladen war). Fremde Mobs werden nie angefasst.
- **Blutmond:** bei Einbruch der Nacht roter Bildschirm + Knurren, rötlicher Nebel (`fog … push
  minecraft:fog_crimson_forest`, bei Sonnenaufgang entfernt), alle 90 s je Spieler an der Oberfläche ein
  Rudel aus 3–5 wütenden Wölfen 20–32 Blöcke entfernt, nur in der Wildnis (gleiche Prüfung wie bei Blitzen),
  höchstens 12 im Umkreis. Besiegte Blutmond-Wölfe lassen 1–2 Knochen fallen; Meldung `kill`/`blood_wolf` an
  das Erfolge-Pack.
- **Getestet:** 13 Node-Tests (neu: Nacht-Phasen, Teilnahme nur nachts, Markierungen, Betten, Rudelgröße).
  Testserver: Start am Tag → wartet (348 s bis zur Nacht) → bei Nacht „running“; Start in der Nacht → sofort;
  Neustart mitten in der Nacht → läuft weiter; Wolfsrudel nur auf Naturboden, Wölfe nach einem Tick wütend
  (verlieren „zähmbar“), bleiben während der Nacht; Sonnenaufgang / Beenden → Ende, alle Blutmond-Wölfe weg.
  Nicht prüfbar ohne Spieler: Nebel, roter Bildschirm, Angriff, Schlafsperre.

## N2 – gebaut

- **Zombie-Invasion:** In der Nacht jede Minute eine Welle. Ziele: für jeden Spieler in der Oberwelt das Dorf
  in seiner Nähe (Mittelpunkt von mind. 3 Dorfbewohnern im Umkreis von 96 Blöcken), sonst der Spieler selbst;
  Ziele näher als 48 Blöcke werden zusammengelegt. Je Ziel 3 + 1 je Spieler dort, höchstens 30 lebende
  Invasions-Zombies; 24–40 Blöcke entfernt, nur außerhalb bebauter Chunks, auf Naturboden, nicht im Wasser
  (sonst würden sie zu Ertrunkenen). 80 % Zombie, 10 % Wüstenzombie, 10 % Zombie-Dorfbewohner.
- **Dorfbewohner geschützt:** Bei jeder Welle bekommen die Dorfbewohner des angegriffenen Dorfs Widerstand V
  (unverwundbar) und Feuerschutz für etwas über eine Minute.
- **Beute:** Jeder Zombie (auch Wüstenzombie, Ertrunkener, Zombie-Dorfbewohner), den ein Spieler in der
  Invasionsnacht besiegt, lässt zusätzlich fallen: 40 % Eisenbarren, je 25 % 1–2 Karotten/Kartoffeln,
  10 % Smaragd, 10 % Erfahrungsfläschchen, 2 % Goldener Apfel. Meldung `kill`/`invasion_zombie` ans Erfolge-Pack.
- **Getestet:** 14 Node-Tests (neu: Wellengröße und Obergrenze, Mob-Auswahl, Beutetabelle, Dorf-Ziele).
  Testserver mit 4 Dorfbewohnern: zwei „Spieler“ im Dorf → ein Ziel, 5 Zombies; nächste Welle +4; alle
  Dorfbewohner geschützt; nicht geladener Ort → keine Zombies; während der Nacht wird nichts aufgeräumt;
  bei Sonnenaufgang Ende und alle Invasions-Zombies weg. Kampf und Beute nur im Spiel prüfbar.

## N3 – gebaut

- **Kopfgeld:** Beim Start (oder sobald jemand in der Oberwelt ist) erscheint ein zufälliger Boss 40–80 Blöcke
  von einem zufälligen Spieler entfernt, nur in der Wildnis und nicht im Wasser: **Bernd der Zombiekönig**
  (Zombie, Diamanthelm, Eisenschwert, Widerstand II, Stärke, 60 LP), **Skelett-Sven** (Goldhelm, Tempo,
  Widerstand, 52 LP), **Spinnen-Susi** (Stärke, Widerstand, 52 LP). Mit Namen verschwinden Mobs nicht von selbst.
- Chatmeldung mit Koordinaten; alle 30 s für jeden in der Oberwelt in der Aktionsleiste „Bernd: 54 Blöcke Richtung
  Nordwesten“ (8 Himmelsrichtungen). Der Ort wird nachgeführt, solange der Boss geladen ist.
- **Besiegt von einem Spieler:** Kopfgeld fällt (3 Diamanten, 5 Smaragde, Goldener Apfel, 5 Erfahrungsfläschchen),
  Titel für alle, „Kopfgeldjäger“ = der Sieger und alle Spieler im Umkreis von 32 Blöcken (Log `bounty`,
  Meldung ans Erfolge-Pack). **Verunglückt** (Lava, Sturz …) → kein Kopfgeld. **Nach 20 Min. Spielzeit** entkommt er.
- Der Zustand im Log enthält beim Kopfgeld `boss` (Name, letzter Ort) für das Portal.
- **Getestet:** 15 Node-Tests (neu: Lebenspunkte-Stufen, Helm gegen Sonne, Himmelsrichtungen, Kopfgeld, Jäger).
  Testserver: Bernd mit 60/60 LP und Effekten, Hinweis „43 Blöcke Richtung Osten“ stimmt mit seinem Ort überein,
  Tod ohne Spieler → Ende ohne Beute, Spinnen-Susi 52/52, nach 20 Min. entkommen und entfernt.
  Im Spiel zu prüfen: Helm/Schwert sichtbar, Kampf, Kopfgeld.

## N4 – gebaut (Erfolge-Pack 1.2.0, Events-Pack 1.1.0)

- Neue Erfolge in der Gruppe „Events“: **Hab ich alles schon gesehen II** (Welle 2: Zombie-Invasion, Blutmond,
  Kopfgeld), **Hirn-Rissig** (20 Zombies in einer einzigen Invasionsnacht – gezählt je Nacht, die beste zählt),
  **Wer hat Angst vorm bösen Wolf?** (10 Blutmond-Wölfe), **Kopfgeldjäger** (beim Sieg über einen Boss dabei),
  **Gemeinsam stark** (ein Event mit mindestens 3 Teilnehmern – erster Meta-Erfolg „Community“).
- Das Erfolge-Pack verarbeitet die neuen Meldungen `kill` (`invasion_zombie`, `blood_wolf`) und `bounty` (Jäger).
- Versionen: Events-Pack 1.0.0 → **1.1.0**, Erfolge-Pack 1.1.0 → **1.2.0**.
- **Getestet:** 8 Node-Tests im Erfolge-Pack (neu: Welle 2, Gemeinsam stark, beste Invasionsnacht, Wölfe, Kopfgeld).
  Testserver mit beiden Packs und nachgestellten Meldungen: Invasion je Nacht gezählt (beste Nacht 3, neue Nacht
  beginnt bei 1), 2 Wölfe, Kopfgeld für beide Jäger, „Gemeinsam stark“ bei 3 Teilnehmern.

## N5 – gebaut (Portal)

- **Eigener Reiter „Events“** (die Übersicht bleibt kurz): laufende Events mit Countdown und Fortschrittsbalken,
  Nacht-Events erst „in mm:ss“ (wartet auf die Nacht), dann bis Sonnenaufgang; beim Kopfgeld Name und letzter
  Ort des Bosses. Automatik an/aus, Start-Knöpfe für alle sechs Events, Verlauf (auch „besiegt“, „verunglückt“,
  „Sonnenaufgang“), wer wie oft mitgemacht hat.
- **Karte „Welt“** im selben Reiter: Wetter (Klar, Regen, Gewitter) und Tageszeit (Morgen 1000, Mittag 6000,
  Abend 12000, Nacht 13000, Mitternacht 18000), jeweils mit Rückfrage. Feste Konsolenbefehle
  (`commands.world_control`, `POST /api/world/{weather|time}`), nur Werte aus der Liste; Protokoll „Wetter“/„Tageszeit“.
- **Übersicht:** nur noch eine Zeile, solange ein Event läuft („🌕 Blutmond 5:22 · 👑 Kopfgeld 14:42“ + Ansehen).
- **Reiter auf dem Handy:** sechs Reiter in zwei Reihen à drei (statt gequetscht oder seitlich zu scrollen).
- **Getestet:** 7 Python-Tests für Events/Welt (neu: nur feste Wetter-/Zeitwerte, nicht bei Server offline,
  neue Events startbar); lokal mit simuliertem Pack auf PC und Handy: Reiter, Phasen-Countdown, Boss-Info,
  Wetter mit Rückfrage und Protokoll, Übersichtszeile.

## N6 – installiert (2026-10-26 16:19)

- `install.sh`, dann `NO_RESTART=1 world-pack.sh mcportal_events apply` und `world-pack.sh mcportal_achievements
  apply` – ein Neustart. Sicherungen: `~/mcportal-backups/2026-10-26_16-18-08_pre_mcportal_events`,
  `…16-18-09_pre_mcportal_achievements`.
- Alle vier Behavior Packs ohne Script-Fehler; das Events-Pack meldet sechs Events, Zeitplan und Bau-Register
  blieben erhalten (nächstes in ca. 172 Online-Minuten, 1 Chunk); 12 Event-Erfolge im Katalog. Startprüfung:
  62 s auf den Port gewartet (TIME-WAIT), dann OK.

## Nachbesserung Events-Pack 1.1.1: Boss leichter zu finden (2026-10-26)

- Anlass: Bei den ersten Kopfgeld-Versuchen wurde der Boss nicht gefunden. Laut Log stand er jedes Mal an der
  Oberfläche (Gras, Y 68–70, 40–80 Blöcke entfernt) – es fehlte die Orientierung: nur ein Hinweis alle 30 s,
  keine Höhe, nichts Sichtbares.
- Jetzt: **Lichtsäule** über dem Boss (aufsteigende End-Stab-Funken, 2–24 Blöcke über ihm, jede Sekunde),
  **Hinweis alle 5 s** mit Höhenunterschied („46 Blöcke Richtung Osten, 8 Blöcke höher“), **Y-Koordinate** in
  Chatmeldung und Portal, Abstand beim Erscheinen **30–60** statt 40–80 Blöcke.
- Getestet: 15 Node-Tests (neu: Höhe im Hinweis, Lichtsäule); Testserver: Partikel angenommen, Y im Zustand,
  Hinweis mit Höhe. Installation: `install.sh` (Portal zeigt Y) und `world-pack.sh mcportal_events apply`.

## Was sich auf dem Server ändert

- Events-Pack 1.0.0 → 1.1.0, Erfolge-Pack 1.1.0 → 1.2.0, neue Portal-Version. Keine Blockänderungen.
- Während der Events: zusätzliche Mobs (nur markierte, werden aufgeräumt), Nebel, Schlafsperre.
- **Rückweg:** `world-pack.sh mcportal_events rollback`, `world-pack.sh mcportal_achievements rollback`,
  Portal per Install-Backup. Einzelne Events lassen sich nicht abschalten, aber Automatik aus genügt.

## Zu entscheiden (Vorschläge in Klammern)

1. Blutmond-Wölfe greifen an? (ja – Knochen als Beute, verschwinden bei Sonnenaufgang)
2. Schlafen während Nacht-Events gesperrt? (ja)
3. Dorfbewohner während der Zombie-Invasion geschützt? (ja)
4. Bosse und Namen (Bernd der Zombiekönig, Skelett-Sven, Spinnen-Susi – gern eigene Ideen)
5. Meta-Erfolge: jetzt nur „Gemeinsam stark“, der Rest mit Paket 3? (ja)
