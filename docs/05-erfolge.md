# Erfolge (Änderung M7)

Stand: 2026-10-26 · Pack `mcportal/minecraft-pack/mcportal_achievements` (getrennt von der Statistik)

## So funktioniert es

- Das Pack zählt pro Spieler selbst mit und speichert den Fortschritt **in der Welt**
  (je Spieler eine „dynamic property“ `mcfs_ach:<Name>`). Er übersteht also Neustarts und Updates
  und gehört zur Welt, nicht zum Portal.
- Wird eine Stufe erreicht:
  - **Einblendung** beim Spieler: „Erfolg!“ + Name, dazu der Level-up-Sound,
  - **Chat-Nachricht an alle**: `[Erfolg] Steve hat »Diamant!« erreicht – Den ersten Diamanten gefunden`,
  - eine Log-Zeile `[mcportal-ach] {"v":1,"unlocked":[…]}` → Portal, Tab „Statistik“
    (Kachel „Erfolge x / 46“, aufklappbare Liste, „Neueste Erfolge“).
- Beim Serverstart schreibt das Pack seinen Katalog ins Log – das Portal kennt so immer die aktuelle Liste.
- Gezählt wird ab der Installation. Erfolgslogik und Katalog: `scripts/catalog.js` (ohne Minecraft-Abhängigkeit,
  getestet mit `node --test …/tests/catalog.test.mjs`).

## Katalog (46 Stufen)

| Bereich | Erfolg (Stufen) | Bedingung |
|---|---|---|
| Bergbau | **Kumpel** → **Bergarbeiter** → **Glück auf!** | 100 / 1.000 / 10.000 Erze abgebaut |
| | **Diamant!** → **Diamantenfieber** → **Ungeschliffen reich** | 1 / 50 / 250 Diamanterze |
| | **Schrott vom Feinsten** | Antiken Schrott abgebaut |
| Ausrüstung | **Strahlend** | komplette Diamantrüstung angelegt |
| | **Unkaputtbar** | komplette Netheriterüstung angelegt |
| Natur | **Grüner Daumen** → **Förster** → **Der Wald ruft** | 10 / 100 / 1.000 Bäume gepflanzt |
| | **Tierfreund** → **Arche Noah** | 10 / 100 Tiere gezüchtet |
| | **Muh-ltitalent** | 25 Kühe gezüchtet |
| Kampf | **Nachtwächter** → **Monsterjäger** → **Albtraum der Albträume** | 10 / 100 / 1.000 Monster besiegt (Tiere zählen nicht) |
| | **Hirn-los glücklich** | 100 Zombies (inkl. Wüstenzombie, Ertrunkener) |
| | **Knochenarbeit** | 50 Skelette |
| | **Sssss-chluss jetzt!** | 50 Creeper |
| | **Drachentöter** | Enderdrache besiegt (alle Spieler im Ende bekommen ihn) |
| | **Wither-sprochen!** | Wither besiegt |
| Missgeschicke | **Anfängerfehler** → **Wiederholungstäter** → **Respawn-Routine** | 1 / 10 / 100-mal gestorben |
| | **Sssssurprise!** | von einem Creeper erwischt |
| | **Heiße Sache** | in Lava gestorben |
| | **Die Schwerkraft gewinnt immer** | an Fallschaden gestorben |
| | **Blubb.** | ertrunken |
| Reisen | **Höllisch heiß** | Nether betreten |
| | **Das Ende vom Lied** | Ende betreten |
| | **Wandervogel** → **Ultramarathon** | 10 / 100 km zu Fuß |
| | **Überflieger** | 10 km mit der Elytra |
| | **Leinen los!** | 5 km mit dem Boot |
| Essen | **Snackpause** → **Vielfraß** | 50 / 500-mal gegessen |
| | **Goldener Biss** | Goldenen Apfel gegessen |
| | **Zombie-Diät** | 10-mal Verrottetes Fleisch |
| Bauen | **Häuslebauer** → **Stein auf Stein** | 1.000 / 10.000 Blöcke gesetzt |
| | **Erdverbunden** | 500 Erdblöcke verbaut |
| Dabeisein | **Stammgast** → **Hier wohn ich jetzt** | 10 / 100 Stunden gespielt |
| | **Erfahrungsschatz** | 5.000 Erfahrungspunkte gesammelt |

Neue Erfolge: in `catalog.js` ergänzen (ggf. Zähler in `main.js`), Tests laufen lassen, Version im
Manifest erhöhen, `world-pack.sh mcportal_achievements apply`. Bereits erreichte Stufen bleiben erhalten.

## Änderung M7

1. **Was:** neuer Ordner `worlds/Bedrock level/behavior_packs/mcportal_achievements/`, ein zusätzlicher
   Eintrag in `world_behavior_packs.json`. Das Pack legt eigene Daten (dynamic properties) in der Welt an.
2. **Warum:** eigene Erfolge mit Nachricht im Spiel.
3. **Dateien:** nur diese zwei; `server.properties` bleibt unverändert (M5 hat die Log-Ausgabe schon eingeschaltet).
4. **Backup:** `~/mcportal-backups/<zeit>_pre_mcportal_achievements/`
5. **Rückgängig:** `bash ~/mcportal-src/deploy/world-pack.sh mcportal_achievements rollback`
   (Pack und Eintrag wieder raus; die gespeicherten Fortschrittsdaten bleiben ungenutzt in der Welt liegen).

## Getestet

- Testserver: alle benutzten Schnittstellen vorhanden (Rüstung, Titel-Einblendung, Sound, Chat,
  Dimensionswechsel, dynamic properties); Pack lädt fehlerfrei, schreibt Katalog und Startzeile;
  Speichern in der Welt funktioniert nach dem Laden (beim Laden selbst nicht – berücksichtigt).
- 6 Node-Tests für Katalog und Erfolgslogik (Stufen, Schwellen, Zuordnung von Erzen, Mobs, Toden, Rüstung).
- Portal: Tests für Katalog, Freischaltungen, keine Doppelungen über Neustarts; Anzeige mit simuliertem Server.
- Nicht getestet: echtes Freischalten im Spiel (Einblendung, Sound, Chat) – das geht erst mit Spielern.
