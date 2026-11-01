# Spawnfackel (Änderung M14)

Stand: 2026-11-01 · Packs `mcportal_spawntorch` (Verhalten) + `mcportal_spawntorch_rp` (Grafik)

## Für Spieler

**Spawnfackel craften** (Werkbank): alle 9 Felder mit **Fackeln** füllen → 1 **Spawnfackel** (nicht stapelbar).

**Benutzen:** Die Spawnfackel in die Hand nehmen. Rund um den Spieler (etwa 1 Chunk = 16 Blöcke in jede Richtung,
10 Blöcke nach unten, 6 nach oben) bekommt jeder Block einen **roten Schleier**, auf dem nachts Monster spawnen
könnten. Dort fehlt Licht. Unten in der Leiste steht, wie viele dunkle Stellen es gibt
(„Alles hell genug …“, wenn keine).

- Nur wer die Spawnfackel hält, sieht den Schleier.
- Wird eine Fackel gesetzt, verschwindet das Rot in der Umgebung nach 2–3 Sekunden.
- Nur in der Oberwelt (im Nether und im Ende zählt Licht für die meisten Monster nicht).

## Wann ein Block rot wird

Alle drei Bedingungen zusammen (Regeln in `scripts/core.js`, Tests in `tests/core.test.mjs`):

1. **Boden:** Der Block hat eine volle, feste Oberseite. Nicht rot werden Glas, Laub, untere Stufen (Slabs),
   Treppen, Zäune, Mauern, Truhen, Magma u. Ä.
2. **Platz:** Die zwei Blöcke darüber sind frei – Luft, Gras, Blumen, dünner Schnee. Teppich, Schienen,
   Druckplatten, Knöpfe, Fackeln oder Redstone auf dem Boden machen die Stelle sicher.
3. **Licht:** Kein Fackel-/Lampenlicht erreicht die Stelle (Bedrock: Monster brauchen Blocklicht 0).

Pilzinseln sind ausgenommen. Im Zweifel zeigt die Spawnfackel lieber Rot.

## Technik

- **Licht:** Die stabile Script-API (2.10.0) liefert nur `getLightLevel` = max(Blocklicht, Himmelslicht zur
  aktuellen Uhrzeit) und `getSkyLightLevel` (gemessen: mittags 15, Mitternacht 4).
  - Gesamt > Himmel → Blocklicht vorhanden, sicher.
  - Gesamt = 0 → dunkel.
  - Sonst (tagsüber im Freien) **geschätzt**: Lichtquellen der Umgebung (`getBlocks` mit allen leuchtenden
    Blocktypen) minus Abstand. Wände rechnet die Schätzung nicht ein – hinter einer Mauer neben einer Fackel kann
    tagsüber „hell“ stehen, obwohl es nachts dunkel ist. Unter der Erde und nachts ist der Wert exakt.
- **Scan:** `scripts/scan.js`, als `system.runJob` (eine Spalte pro Schritt, die Tickzeit bleibt frei), höchstens
  alle 2 s je Spieler. Ein Scan dauerte auf dem Testserver ~0,7 s für 256 geladene Spalten.
- **Schleier:** eigener Partikel `mcfs:spawn_veil` (flach, halbdurchsichtig rot, 1,1 s), alle 20 Ticks per
  `player.spawnParticle` nur für diesen Spieler; höchstens 1.500 pro Spieler.
- **Log:** nur die Startzeile `[mcportal-spawntorch] {"v":1,"started":true}`; das Portal bekommt sonst nichts.
- **Symbol und Schleier-Textur:** `mcportal_spawntorch_rp/tools/make_icon.py` (Fackel auf rotem Schleier).

## Geprüft (2026-11-01, Testserver mit Bedrock 1.26.61.1)

- Probe: Lichtwert-API, Partikel nur für einen Spieler, `getBlocks` und `BlockVolume` sind stabil verfügbar.
- Selbsttest (`tests/engine_selftest.js`, nur Testserver): Höhle mit Glas-, Teppich- und Stufenstreifen und einer
  Fackel; Plattform im Freien mittags. Rot genau dort, wo erwartet; keine Script-, Rezept- oder Item-Fehler.
- Installiert am 2026-11-01 und im Spiel bestätigt („funktioniert gut“).

## Installieren / rückgängig

Wenn niemand spielt, auf dem Server:

```bash
sudo NO_RESTART=1 bash ~/mcportal-src/deploy/world-pack.sh mcportal_spawntorch_rp apply
sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_spawntorch apply
```

Rückgängig: `sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_spawntorch rollback` (danach das RP genauso).
Vorhandene Spawnfackeln verschwinden dann aus den Inventaren.
