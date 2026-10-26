# Timed Events – Paket 2: Nachtgefahren (Plan, Änderung M12)

Stand: 2026-10-26 · Status: **N1 gebaut** (Nacht-Gerüst, Blutmond), N2–N6 offen · baut auf Paket 1 auf (`docs/09-events.md`) ·
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
