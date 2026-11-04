# Installation auf einem frischen Server (Änderung M16)

Stand: 2026-11-02 · `provision/setup.sh --install` · getestet auf Ubuntu 24.04 LTS

Mit einem Befehl wird ein frisch installierter Ubuntu-Server zum Familienserver, so wie er hier läuft. Dazu gehören
der Bedrock-Server als Dienst, das Portal, die Startprüfung, die Konsole, die Karte, der Zugang von außen, alle Packs
und die Spielregeln. Die Welt entsteht neu, wahlweise mit eigenem Seed.

## Voraussetzungen

- **Ubuntu 24.04 LTS oder neuer** (Server oder Desktop, 64 Bit x86). Ältere Versionen haben ein polkit ohne
  JavaScript-Regeln, dann gehen die Knöpfe im Portal nicht.
- Ein Benutzer mit `sudo`, Internet (minecraft.net, Ubuntu-Paketquellen, PyPI), etwa 3 GB frei unter `/opt`.
- `git` (ist bei Ubuntu Server dabei; sonst installiert der Befehl unten es mit).

## Installieren

Mit eigenem Seed (hier `123456789` durch den gewünschten ersetzen):

```bash
sudo apt-get update && sudo apt-get install -y git && git clone https://github.com/tianvay/mcfs.git ~/mcfs && sudo bash ~/mcfs/mcportal/provision/setup.sh --install --seed 123456789
```

Ohne `--seed` fragt das Script nach dem Seed, Enter heißt zufällig. Ohne Terminal (z. B. über ein Script) gibt es
ohne Nachfrage einen zufälligen Seed:

```bash
sudo apt-get update && sudo apt-get install -y git && git clone https://github.com/tianvay/mcfs.git ~/mcfs && sudo bash ~/mcfs/mcportal/provision/setup.sh --install
```

Weitere Angaben, alle freiwillig:

| Angabe | Wirkung |
|---|---|
| `--seed <seed>` | Seed der neuen Welt: Zahl (z. B. `-1234567890`) oder Wort (Buchstaben, Ziffern, `_`, bis 30 Zeichen). `--seed ""` = zufällig ohne Nachfrage |
| `--name "<Name>"` | Servername in der Serverliste (Standard `Family Server`) |
| `--conf <Datei>` | eigene Einstellungen statt `/etc/mcportal/server.conf` (Vorlage: `mcportal/provision/server.conf.example`) |

Am Ende fragt das Script nach dem **Admin-Passwort fürs Portal**. Ohne Passwort sind Whitelist, Events und die
Server-Seite gesperrt. Später setzen:

```bash
sudo bash ~/mcfs/mcportal/deploy/set-password.sh
```

Danach ist das Portal unter `http://<IP des Servers>:8080` erreichbar, nur aus dem Heimnetz. Minecraft läuft auf Port
19132.

## Was der Befehl macht

| Schritt | Was | Baustein |
|---|---|---|
| 1 | Pakete: `python3-venv`, `acl`, `curl`, `polkitd`, `libcurl` (nur fehlende) | neu |
| 2 | `/etc/mcportal/server.conf` aus der Vorlage, Seed und Name eintragen | neu |
| 3–7 | Prüfungen, Benutzer `minecraft`, neuester Bedrock-Server nach `/opt/minecraft/bedrock`, `server.properties`, alle Packs aus `provision/packs.list` in die Welt (vor dem ersten Start) | wie `--prepare` |
| 8 | `minecraft-bedrock.service` (Sandbox), Konsole (`.socket`, `10-portal.conf`), Router für die öffentliche IP (`31-router.conf`) | wie `--switch` |
| 9 | `deploy/install.sh`: Portal, Startprüfung, öffentliche IP, Update-Knopf, polkit, Firewall fürs Portal | unverändert |
| 10 | Firewall (nur wenn `ufw` aktiv ist): 19132, 19133 und 19140–19149/udp; kein Ruhezustand (`no-suspend.sh`), kein WLAN-Stromsparen (`wifi-no-powersave.sh`) | neu / unverändert |
| 11 | Erster Start, die Welt entsteht. Danach Seed anzeigen, Spielregeln aus `gamerules.list` setzen | wie `--switch` |
| 12 | Rechte prüfen, dann `verify.sh`: Dienste, Port, jedes Pack mit Version und Startzeile, keine Script-Fehler, Portal, Update-Prüfung | unverändert |

Einen Probestart mit Kopie wie bei `--prepare` gibt es hier nicht. Es läuft noch kein Server, den man schützen
müsste. Der echte Start wird genauso geprüft.

**Packs:** Statistik, Wegpunkte, Events, Erfolge, Spawnfackel, Blaupause (Verhalten) sowie Wegpunkte-, Events-,
Spawnfackel- und Blaupause-Grafik. Die Blaupause steht jetzt auch in `packs.list`, also prüft `verify.sh` sie auch
auf dem echten Server.

**`server.properties`:** Mojangs Datei plus `provision/server.properties.overrides`, darunter `allow-cheats=true`,
`content-log-console-output-enabled=true`, `content-log-level=warning` und `texturepack-required=true`. Dazu kommen
Name, Welt, Seed, Spielmodus und Ports aus `server.conf`.

**Zugang von außen:** `mc-public-ip` fragt vor jedem Start den Router (UPnP) nach der öffentlichen IPv4. Beim
Installieren wird dafür das Standard-Gateway eingetragen (`31-router.conf`). Das klappt mit einer Fritzbox. Bei
anderen Routern meldet `verify.sh` nur einen Hinweis. Die Portfreigaben (TCP+UDP 19132, UDP 19140–19149) richtet
man im Router von Hand ein, siehe [Zugang von außen](12-zugang-von-aussen.md).

## Was nicht mitkommt

- **Whitelist und Operatoren:** Die neue Welt startet leer. Spieler trägt man im Portal ein.
- **Die Welt dieses Servers:** Ein Umzug wäre ein eigener Schritt.
- **Laravel/XAMPP:** gehört nicht zum Minecraft-Server.

## Erneut ausführen

Der Befehl darf noch einmal laufen, z. B. nach einem Abbruch:

```bash
sudo bash ~/mcfs/mcportal/provision/setup.sh --install
```

Eine Welt, die es schon gibt, bleibt samt Packs unverändert. Ein Seed ändert dann nichts mehr. Läuft der Server,
wird er nicht neu gestartet. Steht die Unit auf einem anderen Ordner (alte Installation), bricht `--install` ab. Für
diesen Fall gibt es `--prepare`/`--switch` ([Reproduzierbarer Aufbau](04-reproduzierbarer-aufbau.md)).

Packs ändern oder neue Pack-Versionen einspielen geht danach wie gewohnt, nur mit dem Pfad `~/mcfs/mcportal`:

```bash
sudo bash ~/mcfs/mcportal/deploy/world-pack.sh mcportal_blueprint status
```

## Geprüft

Getestet am 2026-11-02 in einer Wegwerf-VM mit frischem Ubuntu 24.04 LTS (WSL2 mit systemd), nicht auf dem echten
Server:

- **Erster Lauf mit `--seed 424242`, ohne Terminal:** Bedrock 1.26.61.1 geladen, alle 10 Packs eingesetzt. Die
  Startprüfung war nach 2 s OK, der Seed der Welt laut `level.dat` ist 424242, die drei Spielregeln sind gesetzt.
  `verify.sh` meldet alles OK: alle 6 Verhaltens-Packs mit ihrer Startzeile, keine Script-Fehler, Portal, Update-
  Prüfung, Rechte. Beim Zugang von außen kommt nur der Hinweis, weil die VM keinen UPnP-Router hat.
- **Zweiter Lauf auf derselben VM (`--seed 999`):** Er warnt, dass der Seed nichts mehr ändert, und lässt Welt und
  Packs stehen. Es gibt keinen Neustart, alles bleibt OK, Exit 0.
- **Neue VM, interaktiv:** Der Seed wird abgefragt, Eingabe `Mein_Seed`. Bedrock macht daraus den Seed 133264563.
  Danach wird das Admin-Passwort abgefragt. Die Anmeldung im Portal klappt, und das Portal zeigt den Seed, die
  Konsole und die Whitelist. Der Kartenlauf läuft ohne Fehler durch. Bei einer Welt, die noch niemand betreten hat,
  ist die Karte leer.
- Das Portal ist von einem anderen Rechner aus erreichbar (`http://<VM-IP>:8080`).
- Unit-Tests `provision/tests` (11) und `tests/test_public_ip`, `test_release`, `test_leveldat` (17) laufen durch.

Nebenbei behoben: Seit der Admin-Anmeldung (30.10.) zeigt `/api/status` ohne Anmeldung keine Whitelist- und
Konsolen-Felder mehr. Die Schlussprüfung von `install.sh` brach deshalb mit einem Traceback ab (nur die Anzeige).
`verify.sh` meldete das Portal und die Update-Prüfung als Fehler. Beide nutzen jetzt nur noch die öffentlichen
Felder, die Update-Prüfung läuft direkt über das Release-Modul des Portals.

## Änderung M16

1. **Was:** `provision/setup.sh` bekommt den Modus `--install [--seed] [--name]`. `provision/packs.list` enthält
   jetzt auch die Blaupause. `provision/verify.sh` nimmt den Router aus der Unit (`MC_ROUTER`) statt fest
   `192.168.178.1` und gibt nur einen Hinweis statt eines Fehlers, wenn der Router keine öffentliche IPv4 nennt.
   `verify.sh` und `deploy/install.sh` lesen vom Portal nur noch die Felder, die man ohne Anmeldung sieht.
2. **Warum:** Andere sollen den Server mit einem Befehl genauso aufsetzen können, mit eigener Welt.
3. **Dateien auf dem echten Server:** keine. `--install` bricht dort ab, weil auf dem echten Server schon eine
   Unit für einen anderen Ordner existiert. Wenn man dort `~/mcportal-src` aktualisiert, ändert sich nur das
   Prüfen: `verify.sh` prüft dann auch die Blaupause, nimmt weiter `192.168.178.1` als Router und meldet das Portal
   wieder grün.
4. **Backup:** nicht nötig, auf einem frischen Server gibt es nichts zu sichern. `install.sh` legt wie immer
   `/var/lib/mcportal/backups/<zeit>_pre_portal_install/` an.
5. **Rückgängig:** Ubuntu neu aufsetzen. `--install` ist für einen frischen Server gedacht und ändert nichts an
   einem bestehenden.
