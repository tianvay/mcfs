# Timed Events – Paket 1 (Plan, Änderung M11)

Stand: 2026-10-26 · Status: **E1 + E2 gebaut** (Grundgerüst, Bau-Register, Unwetter, Mining Rush, Glückstag), E3–E5 offen · nur stabile Script-API (`@minecraft/server` 2.10.0), keine Experimente

## Ziel

Zufällige Ereignisse beleben den Server. Je mehr Spieler online sind, desto häufiger; höchstens eins pro Stunde
(bei vollem Server). Paket 1 bringt das Grundgerüst, das Bau-Register, die Portal-Kachel „Events“, drei Events
und Erfolge dafür. Pakete 2 und 3 (Nachtgefahren, Welt verändert sich) stehen in `docs/TODO.md`.

## Die drei Events

| Event | Dauer | Wirkung |
|---|---|---|
| 💎 **Mining Rush** | 2 Std. | Was ein Erz beim Abbauen tatsächlich fallen lässt, kommt noch einmal dazu – Glück (Fortune) wird also mit verdoppelt. Mit Behutsamkeit (Silk Touch) keine Verdopplung (sonst ließen sich Erzblöcke vermehren). |
| 🌧️ **Unwetter** | 2 Tag-Nacht-Wechsel (40 Min.) | Gewitter in der Oberwelt; zusätzlich alle 20–60 s ein Blitz 16–64 Blöcke neben einem zufälligen Spieler – **nur in Chunks ohne Spielerbauten** (Bau-Register) und nie näher als 24 Blöcke an Wegpunkten/Spawn. Danach klart es auf. |
| 🍀 **Glückstag** | 2 Std. | Jede gewonnene Erfahrung zählt doppelt (Monster, Erze, Züchten, Angeln, Öfen …). Ausgaben (Verzaubern, Amboss) werden nicht verdoppelt. |

**Technik:** Mining Rush merkt sich jeden abgebauten Erzblock einen Tick lang und verdoppelt die Item-Drops, die
genau dort erscheinen (`entitySpawn`). Glückstag schaut alle 5 Ticks auf die Erfahrung jedes Spielers
(`getTotalXp`) und gibt jeden Zuwachs noch einmal dazu. Unwetter nutzt `setWeather` und `spawnEntity("lightning_bolt")`.

**Ankündigung** (im Spiel; Emojis kann Minecraft dort nicht darstellen, nur Farben):
Titel + Untertitel für alle („§bMining Rush!“ – „2 Stunden doppelte Erze“), Chatzeile, passender Sound;
zwischendurch die Restzeit in der Aktionsleiste; am Ende „Mining Rush ist vorbei“.

## Wann kommt ein Event?

- Die Uhr läuft **nur, solange jemand online ist**. Pro Minute sammelt der Server „Event-Guthaben“ –
  umso mehr, je mehr Spieler online sind. Bei 1,0 startet ein zufälliges Event (nach 0–10 Min. Zufallsverzug).
- **Nie öfter als eines pro Stunde.**
- Vorschlag (im Pack als Tabelle, leicht änderbar):

  | Spieler online | 1 | 2 | 3 | 4 | 5 | 6–7 | 8–10 |
  |---|---|---|---|---|---|---|---|
  | etwa alle … Minuten Spielzeit | 180 | 150 | 120 | 105 | 90 | 75 | 60 |

  Bei 3 Kindern also ungefähr alle 2 Stunden gemeinsamer Spielzeit, bei vollem Server (10) stündlich.
- Auswahl zufällig, aber nie zweimal hintereinander dasselbe. Verschiedene Events dürfen sich überlappen
  (z. B. Unwetter während Mining Rush), dasselbe Event nie doppelt.
- **Restzeiten laufen nur, solange jemand online ist** – loggen sich alle aus, pausiert das Event und geht beim
  nächsten Einloggen weiter. Alles übersteht Neustarts.

## Bau-Register (Grundlage für Paket 3)

- Ab Installation merkt sich das Event-Pack jeden **Chunk, in dem ein Spieler einen Block setzt**
  (nur Chunk-Koordinaten je Dimension, wenige KB). Dazu automatisch die Chunks rund um Wegpunkte und Spawn.
- Paket 1 nutzt es für die Blitze; Paket 3 (Meteorit, Spukort) später für „niemals Spielerbauten anfassen“.
- **Ältere Bauten** (vor dem Register) kennt es nicht. Vorschlag für Paket 3: eine einmalige Bestandsaufnahme aus
  der Karte – der Karten-Leser findet Chunks mit „künstlichen“ Blöcken (Bretter, Glas, Ziegel, Wolle, Truhen …)
  und spielt sie über die Konsole ins Register ein.

## Erfolge (Erfolge-Pack 1.1.0)

| Erfolg | Bedingung |
|---|---|
| „Mittendrin statt nur dabei“ | 5 Events mitgemacht |
| „Eventhopper“ | 20 Events mitgemacht |
| „Partylöwe“ | 50 Events mitgemacht |
| „Hab ich alles schon gesehen“ – **Stufe 1** | jedes Event aus Paket 1 mindestens einmal mitgemacht (Mining Rush, Unwetter, Glückstag) |
| „Goldrausch“ | 100 Erze während eines Mining Rush abgebaut |
| „Glückspilz“ | 1.000 Erfahrungspunkte an Glückstagen gesammelt |
| „Geistesblitz“ | während eines Unwetters von einem Blitz getroffen worden und überlebt |

**Mitgemacht** heißt: mindestens 5 Minuten online, während das Event lief (bei kürzeren Events: bis zum Ende).
Das Event-Pack meldet das beim Ende per `system.sendScriptEvent("mcfs:event", …)`; das Erfolge-Pack hört darauf
(`scriptEventReceive`, stabil).

**„Hab ich alles schon gesehen“ in Wellen:** Jedes Event-Paket bringt eine eigene Stufe mit genau seinen Events
(Stufe 2 = Paket 2, Stufe 3 = Paket 3). So ändert sich eine einmal erreichte Stufe nie nachträglich, und neue
Events machen keinen alten Erfolg ungültig. Im Katalog hängt jede Stufe an einer festen Liste von Event-Arten.

## Portal: Kachel „Events“ in der Übersicht

- Laufende Events mit Restzeit; „automatische Events: an/aus“; ungefähr wann das nächste kommen kann.
- Verlauf der letzten Events (Art, Start, Dauer, wer mitgemacht hat).
- **Knöpfe** (nur mit PIN-Freigabe, falls aktiviert): jedes Event starten, laufendes beenden, Automatik an/aus.
  Das Portal schickt dafür feste Befehle über die Server-Konsole – `scriptevent mcfs:event start mining_rush`
  usw., nur Werte aus einer festen Liste, keine freien Eingaben. Damit lässt sich jedes Event auch gezielt testen.
- Daten wie bisher aus dem Log: Das Pack schreibt `[mcportal-events] {"v":1,"event":"started"|"ended"|"state",…}`;
  neuer Dienst `app/services/events.py`, Daten in `/var/lib/mcportal/events.json`.

## Schritte

| Schritt | Inhalt | Test |
|---|---|---|
| **E1** | Neues Pack `mcportal_events`: Zeitplan, Bau-Register, Ankündigungen, Log-Zeilen, Steuerung per `scriptevent`; Event **Unwetter** | Node-Tests (Zeitplan, Auswahl, Register, Blitz-Ziele); Testserver: Start/Ende per Konsole, Wetter, Blitze, Neustart mitten im Event |
| **E2** | **Mining Rush** und **Glückstag** | Node-Tests; Testserver: Start/Ende, Restzeit pausiert ohne Spieler. Die Verdopplung selbst braucht einen echten Spieler → im Spiel prüfen |
| **E3** | Erfolge-Pack 1.1.0 mit den Event-Erfolgen | Node-Tests (Katalog); Testserver: Teilnahme-Meldung kommt im Erfolge-Pack an |
| **E4** | Portal: Dienst, Kachel, Knöpfe, Befehle | Python-Tests; lokal mit simuliertem Server |
| **E5** | Installation: `install.sh` (Portal), dann beide Packs mit **einem** Neustart, wenn niemand spielt; danach jedes Event einmal über das Portal starten und im Spiel ansehen | |

Nach jedem Schritt zeige ich das Ergebnis; installiert wird erst in E5 (mit deinem Okay).

## E1 – gebaut

- Pack `mcportal/minecraft-pack/mcportal_events` (1.0.0): `scripts/core.js` (reine Logik), `scripts/main.js`.
- **Steuerung** (Konsole, Portal, Operatoren im Spiel): `/scriptevent mcfs:event start storm` · `stop storm` ·
  `auto on` / `auto off` · `state`. Nur diese Wörter und Event-Arten aus der festen Liste werden angenommen.
- **Log** `[mcportal-events]`: `started` (type, by, duration), `ended` (type, by, ran, participants), `state`
  (auto, online, laufende Events mit Restzeit, `next_in` in Online-Minuten, last, register = Anzahl Chunks,
  types = verfügbare Events; beim Start, bei jeder Änderung und alle 10 Online-Minuten), `lightning_survived`.
- **Andere Packs** bekommen dasselbe per `system.sendScriptEvent("mcfs:event_news", …)` (für die Erfolge in E3).
- **Speicher:** Zustand in `mcfs_ev:state`, Bau-Register in `mcfs_ev_reg:0…n` (je ≤ 30.000 Zeichen).
- **Blitze:** alle 20–60 s neben einem zufälligen Spieler in der Oberwelt, nur wenn der Chunk nicht im Register ist
  **und** eine 7 × 7-Fläche ringsum nur natürlichen Boden hat (Gras, Erde, Sand, Stein, Laub, Blumen, Wasser …) –
  das schützt auch Bauten von vor dem Register (Dächer, Wege, Felder, Laternen = kein Blitz).
- **Getestet:** 8 Node-Tests (Häufigkeit je Spielerzahl, höchstens 1/Std., Pause ohne Spieler, Zufallsverzug,
  Auswahl, Teilnahme, Steuerbefehle, Register-Speicherung, natürlicher Boden). Testserver mit simulierten
  Online-Minuten (nur über die Konsole möglich: `scriptevent mcfs:event test minute <n> <spieler>`):
  Start/Doppelstart/unbekanntes Event, Blitz auf Naturboden, Automatik aus/an, **Neustart mitten im Unwetter**
  (Restzeit und „aus“ blieben erhalten), Ende nach Zeit mit Teilnehmern, automatischer Start, Stopp.
  Im Spiel noch zu sehen: Titel/Chat/Sound, Gewitter, Blitze, Restzeit in der Aktionsleiste.

## E2 – gebaut

- **Mining Rush:** Einen Tick nach dem Abbau eines Erzes werden die dort gerade erschienenen Drops kopiert.
  Verdoppelt wird nur der **echte Drop des Erzes** (Eisenerz → Roheisen, Diamanterz → Diamant, Lapis, Redstone,
  Kupfer, Gold, Kohle, Smaragd, Quarz, Goldnugget) – mit Glück also entsprechend mehr. **Nicht** verdoppelt:
  das Erz selbst (Behutsamkeit), antiker Schrott, und Gegenstände, die schon vorher dort lagen oder
  absichtlich danebengeworfen wurden (Schlupfloch geschlossen: nur Items, die im selben Tick entstanden, und nur
  die zum Erz passende Sorte). Kleiner grüner Funken-Effekt bei jeder Verdopplung.
- **Glückstag:** Alle 5 Ticks wird der Erfahrungszuwachs jedes Spielers seit dem letzten Blick noch einmal
  gegeben. Verluste (Verzaubern, Amboss, Tod) und der Stand beim Einloggen werden nicht verdoppelt.
- Jede Event-Art hat eine **Kategorie** (welt, ressourcen, mobs, community) – Grundlage für spätere Meta-Erfolge.
- **Getestet:** 11 Node-Tests (neu: welche Erze, welcher Drop, XP-Zuwachs, Kategorien). Testserver: ohne
  Mining Rush wird nichts verdoppelt; mit Mining Rush genau der Roheisen-Drop – Eisenerz-Block, danebengeworfener
  Diamant und älterer Smaragd bleiben einfach, zweiter Durchlauf verdoppelt nichts mehr; alle drei Events
  gleichzeitig, Unwetter endet nach 40 Min., Glückstag per Befehl beendet.
  **Im Spiel zu prüfen:** echter Erzabbau (auch mit Glück), Glückstag-Erfahrung.

## Was sich auf dem Server ändert

- Neues Behavior Pack `mcportal_events` in der Welt, Erfolge-Pack 1.0.0 → 1.1.0, neue Portal-Version.
- Welt: Wetter und Blitze während eines Unwetters (Blitze können wie in Vanilla Feuer legen und Mobs
  verwandeln – aber nur fernab von Spielerbauten). Sonst keine Blockänderungen in Paket 1.
- **Rückweg:** `world-pack.sh mcportal_events rollback` und `world-pack.sh mcportal_achievements rollback`
  (Backup vor jeder Änderung), Portal per Install-Backup. Abschalten ohne Rückbau: Automatik im Portal aus.

## Zu entscheiden (Vorschläge in Klammern)

1. Häufigkeit (Tabelle oben).
2. Dürfen sich verschiedene Events überlappen? (ja)
3. Antiker Schrott im Mining Rush verdoppeln? (nein – Netherite soll selten bleiben)
4. Restzeit pausiert, wenn niemand online ist? (ja)
