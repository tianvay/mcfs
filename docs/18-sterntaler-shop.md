# Sterntaler und Shop (Änderung M19)

Stand: 2026-11-11 (Version 1.0.0) · Packs `mcportal_shop` (Verhalten) + `mcportal_shop_rp` (Grafik) ·
Portal: Tab „Sterntaler“

Wer bei den Events mitmacht, verdient **Sterntaler**. Im Spiel kauft man damit vier besondere Werkzeuge. Das Portal
zeigt für alle die Kontostände und das Angebot, der Admin sieht zusätzlich jede Buchung.

## Verdienen

| Anlass | Sterntaler |
|---|---|
| Bei einem Event dabei sein (Regel des Events-Packs: lange genug online) | 5 |
| Kopfgeld-Boss besiegt (alle Jäger in der Nähe) | +5 |
| Schatz gefunden | +5 |
| Hexenzirkel gesprengt, Fluch gebrochen (alle Beteiligten) | +3 |
| Meteoriteneinschlag miterlebt | +2 |
| Blitz im Unwetter überlebt | +2 |
| Sternstück aufgesammelt | +1 |

Im Chat steht dann z. B. `[Sterntaler] +5 Event mitgemacht – Kontostand 25. Einkaufen mit /shop`. Wer beim Ende
eines Events schon offline ist, bekommt die Sterntaler trotzdem.

**Startguthaben:** Für jede Teilnahme, die das Portal aus der Zeit vor dem Shop kennt (die letzten 100 Events), gibt
es einmalig 5 Sterntaler. Das Portal schickt das von selbst, sobald das Pack zum ersten Mal läuft.

## Ausgeben: `/shop`

`/shop` in den Chat tippen. Das Menü zeigt den Kontostand und das Angebot; ein Klick auf einen Gegenstand zeigt
Beschreibung und Preis, „Kaufen“ bucht ab und legt ihn ins Inventar (ist es voll, liegt er vor den Füßen).
Kein Preis liegt über 4 Event-Teilnahmen.

| Gegenstand | Preis | Was er kann |
|---|---|---|
| **Bergbrecher** | 20 | Spitzhacke (Diamant-Stufe). Baut um den Zielblock 3 × 3 × 3 ab – aber nur natürliches Gestein und Erze (Stein, Tiefenschiefer, Granit, Netherrack, Sandstein, Terrakotta, alle Erze …). Bruchstein, Ziegel, Öfen, Truhen und alles andere Gebaute bleibt stehen. **Schleichen: nur ein Block.** Hält 3000 Blöcke. |
| **Holzfäller-Axt** | 15 | Fällt den ganzen Baum (bis 96 Stämme) mit einem Schlag. Nur echte Bäume: Stämme ohne Laub daneben (Blockhütte, Zaunpfosten) bleiben stehen. Was unter dem Schlag liegt, bleibt auch. **Schleichen: nur ein Block.** Hält 2000 Stämme. |
| **Magnet-Amulett** | 20 | Zieht herumliegende Gegenstände aus 8 Blöcken an, solange es in der Schnellleiste oder Zweithand liegt. Was man wegwirft, bleibt 2 Sekunden liegen. **Schleichen: Pause.** Nutzt sich nicht ab. |
| **Ernte-Sichel** | 15 | Rechtsklick auf ein Feld: reife Feldfrüchte in 3 × 3 (Weizen, Karotten, Kartoffeln, Rote Bete, Netherwarzen) werden geerntet und sofort neu gepflanzt. Unreifes bleibt. Hält 1000 Ernten. |

Die Werkzeuge kann man nicht herstellen, nur kaufen. Sie lassen sich nicht verzaubern oder reparieren; ist eines
abgenutzt, kauft man ein neues.

## Im Portal

- **Tab „Sterntaler“ (für alle):** Rangliste mit Kontostand, insgesamt verdient, ausgegeben und gekauft; das Angebot
  mit Bildern und Preisen; die Tabelle, wofür es Sterntaler gibt.
- **Nur Admin, im selben Tab:** „Gutschreiben oder abziehen“ (Spieler, Betrag −999 bis 999; ein Konto fällt nie
  unter 0) und das **Kontobuch** mit den letzten 100 Buchungen (Zeit, Spieler, Grund, Betrag, Kontostand danach).
  Dort steht auch, wer welches Startguthaben bekommen hat.
- **Tab „Statistik“:** Kachel „Sterntaler“ bei jedem Spieler.
- **Tab „Funktionen“:** „Sterntaler“ ist eine Erweiterung wie die anderen, mit Schalter für den Admin. Ausgeschaltet
  (nach dem Neustart) gibt es keine Sterntaler mehr, kein `/shop`, der Tab und die Kacheln verschwinden.
  **Die gekauften Werkzeuge löscht Minecraft dann dauerhaft** (eigene Gegenstände ohne Pack) – das Portal warnt
  davor. Die Kontostände bleiben in der Welt und sind nach dem Einschalten wieder da.
- Protokoll: `STERNTALER` (Gutschrift/Abzug von Hand).

An der Server-Konsole geht dasselbe mit `scriptevent mcfs:shop grant <+/-Betrag> <Name>`;
`scriptevent mcfs:shop balances` schreibt alle Kontostände ins Log. Im Spiel getippt wirken die Befehle nicht, auch
nicht für Operatoren.

## Wie es funktioniert

- **Pack** `minecraft-pack/mcportal_shop`:
  - `scripts/core.js` – Regeln ohne Minecraft-API: Angebot und Preise (`ITEMS`), Beträge (`REWARDS`), was eine
    Nachricht des Events-Packs wert ist (`rewardsFor`), Konto (`book`), Konsolenbefehle, welche Blöcke der
    Bergbrecher mitnimmt (`isCubeBlock`), Baum-Suche (`treeLogs`), reife Feldfrüchte.
  - `scripts/work.js` – was die Werkzeuge in der Welt tun (`breakCube`, `fellTree`, `harvest`). Abgebaut wird mit
    `setblock … destroy`, also mit den Drops des Spiels.
  - `scripts/main.js` – Konten (Dynamic Property `mcfs_shop:<Name>` in der Welt, übersteht Neustarts), `/shop`
    mit Menü (`@minecraft/server-ui`), Abnutzung, Magnet.
  - `items/*.json` – die vier Gegenstände; Bilder im Grafik-Pack (`mcportal_shop_rp/tools/make_icon.py`).
- **Verbindung zu den Events:** Das Events-Pack meldet schon bisher jedem Pack, was passiert
  (`system.sendScriptEvent("mcfs:event_news", …)`, davon leben die Event-Erfolge). Das Shop-Pack hört dieselben
  Nachrichten. Am Events-Pack ändert sich nichts. Ohne Events-Pack gibt es keine neuen Sterntaler, einkaufen
  geht weiter.
- **Nur Skripte und die Konsole** können Sterntaler buchen. Ein `/scriptevent` von einem Spieler wird ignoriert.
- **Log für das Portal:** `[mcportal-shop] {"v":1,"event":"booking","player":…,"delta":…,"reason":…,"detail":…,
  "balance":…,"earned":…}`; bei jedem Start zusätzlich `catalog` (Angebot, Beträge) und `balances` (alle Konten).
  Die Welt hat recht: Hat das Portal etwas verpasst, stimmt der Kontostand nach dem nächsten Serverstart wieder.
- **Portal:** `app/services/sterntaler.py` (Datei `/var/lib/mcportal/sterntaler.json`), `GET /api/sterntaler` (für
  alle; Kontobuch nur mit Anmeldung), `POST /api/sterntaler/grant` (Admin, nur wenn das Pack an ist). Die beiden
  Konsolenbefehle entstehen fest in `commands.shop_grant()`/`shop_seed()` – geprüfte Zahl, geprüfter Gamertag.
  Web: `app/web/sterntaler.js`, `index.html`, `app.css`, Kachel in `app.js`, Angebot im Funktionen-Tab (`packs.js`).
- **Startguthaben:** Beim ersten „gestartet“ des Packs hält das Portal fest, wer nach seiner Event-Geschichte wie
  viel bekommt (nur Events, die vorher endeten), und schickt `seed <Betrag> <Name>`. Das Pack bucht pro Spieler nur
  einmal und bestätigt jede Anfrage im Log; Unbestätigtes schickt das Portal später noch einmal.

### Bekannte Grenzen

- **Mining Rush** verdoppelt nur den Block, den man selbst abbaut, nicht die 26 daneben. Glück und Behutsamkeit
  gibt es für die Werkzeuge nicht.
- **Statistik und Erfolge** zählen nur den selbst abgebauten Block (die übrigen baut das Pack ab).
- Die Ernte-Sichel pflanzt nach, ohne Saatgut abzuziehen.
- Der Magnet zieht auch, was andere Spieler in der Nähe fallen lassen.

## Geprüft

- `node --test minecraft-pack/mcportal_shop/tests/core.test.mjs` (11 Tests): Beträge und Preise (nichts über
  4 Teilnahmen), Nachrichten → Buchungen, Konto nie unter 0, Konsolenbefehle, Bergbrecher-Blöcke, Baum/kein Baum,
  reife Feldfrüchte, Abnutzung.
- **Testserver** (Wegwerf-Welt, `tests/engine_selftest.js`, API 2.10.0, 11.11.): Pack lädt ohne Fehler, alle vier
  Gegenstände existieren mit Haltbarkeit und Werkzeug-Tags. Bergbrecher: aus einem 3 × 3 × 3-Würfel mit Diamanterz,
  Bruchstein und Truhe gehen 24 Blöcke (23 Bruchstein + 1 Diamant fallen), Truhe und Bruchstein bleiben. Axt: 4
  Stämme über dem Schlag fallen, Stämme ohne Laub bleiben. Sichel: 3 reife geerntet und neu gepflanzt, der junge
  Weizen bleibt. Buchungen, doppeltes Startguthaben (nur einmal), Abzug nie unter 0, `@a` abgelehnt.
- `tests/test_sterntaler.py` (12 Tests): Buchungen, Käufe, kein doppeltes Zählen über einen Portal-Neustart,
  Startguthaben (einmal, wartet auf den Server), Gutschreiben mit Grenzen, nur feste Konsolenbefehle.
  `tests/test_packs.py`: sieben Schalter, Bilder der Shop-Gegenstände.
- Portal lokal mit dem Fake-Server: Tab, Rangliste, Kontobuch, Gutschreiben, Kachel, Aus-/Einschalten.
- **Noch nicht geprüft – geht nur mit Spielern** (auf dem Testserver kann niemand beitreten): `/shop`-Menü,
  Abbaugeschwindigkeit und Drops des selbst abgebauten Blocks mit Bergbrecher und Axt, Abnutzung, Magnet in der
  Zweithand, Sichel per Rechtsklick. Falls das Spiel den Bergbrecher für den Zielblock nicht als Diamantspitzhacke
  anerkennt, lässt das Pack den Block ersatzweise selbst fallen und schreibt einmal `"event":"hedge"` ins Log.

## Änderung M19

1. **Was:** neue Packs `mcportal_shop` (Verhalten) + `mcportal_shop_rp` (Grafik), je ein Eintrag in
   `world_behavior_packs.json`/`world_resource_packs.json`; Portal mit Tab „Sterntaler“. `provision/packs.list`
   enthält beide, neue Server bekommen sie mit `setup.sh --install`.
2. **Warum:** Mitmachen bei Events soll sich lohnen und etwas zum Sparen geben.
3. **Dateien auf dem Server:** `worlds/<Welt>/behavior_packs/mcportal_shop`, `worlds/<Welt>/resource_packs/mcportal_shop_rp`,
   die beiden Pack-Listen der Welt, Portal unter `/opt/mcportal/app`, neu `/var/lib/mcportal/sterntaler.json`.
   Keine neuen Rechte, keine neue Unit, kein neues Systempaket, keine Spielregel, kein `server.properties`-Wert.
   Spieler laden das Grafik-Pack beim Betreten einmal herunter (wie bei Wegpunkten und Blaupause).
4. **Backup:** `world-pack.sh` legt `<Home des Minecraft-Nutzers>/mcportal-backups/<zeit>_pre_mcportal_shop*/` an,
   `install.sh` `/var/lib/mcportal/backups/<zeit>_pre_portal_install/`.
5. **Rückgängig:** im Portal ausschalten (Tab „Funktionen“) oder
   `sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_shop rollback` (danach das Grafik-Pack genauso).
   Gekaufte Werkzeuge verschwinden dann; die Kontostände bleiben als ungenutzter Eintrag in der Welt.

Auf dem Laptop installieren, wenn niemand spielt (erst das Portal, dann die Packs mit einem Neustart):

```bash
sudo bash ~/mcportal-src/deploy/install.sh
```

```bash
sudo NO_RESTART=1 bash ~/mcportal-src/deploy/world-pack.sh mcportal_shop_rp apply
```

```bash
sudo bash ~/mcportal-src/deploy/world-pack.sh mcportal_shop apply
```
