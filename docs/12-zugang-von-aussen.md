# Zugang von außen (27.–30.10.2026)

Ziel: Freunde spielen von außerhalb des Heimnetzes mit, auf jedem Gerät (PC, Konsole, Handy im Mobilfunknetz),
ohne Bezahldienst. Portal (8080) und Laravel (80) bleiben nur im Heimnetz erreichbar.

## Ergebnis

| Wer | Wie | Geht |
|---|---|---|
| Heimnetz (WLAN/LAN) | wie bisher | ja |
| Freund am PC im Ausland | `<öffentliche IPv4>`, Port 19132 | ja (27.10.) |
| Handy im Mobilfunknetz | `<öffentliche IPv4>`, Port 19132 (das Spielen läuft dann über IPv6) | ja (28.10.) |

## Der Weg dahin – was nicht ging

- **playit.gg:** Der Agent lief, war aber nicht mit dem Konto verbunden („waiting for secret“). Der Tunnel, der mit
  NetherNet funktioniert, kostet Premium. Die kostenlose Variante verlangt `transport=raknet`. RakNet ist mit
  Bedrock 26.60 (27.10.2026) für Spieler abgeschaltet. **Verworfen.** Die Befehle zum Entfernen stehen im
  Chat-Verlauf; ob playit noch installiert ist, entscheidet der Admin.
- **DS-Lite:** Der Vodafone-Kabelanschluss hatte keine eigene IPv4, also wären Portfreigaben nur über IPv6
  gegangen (ohne Switch). → Bei Vodafone **Dual-Stack** beantragt (27.10.), seitdem gibt es eine öffentliche
  IPv4.
- **Alte Freigabe** in der Fritzbox (nur TCP, veraltete IPv6-Interface-ID): vom Admin gelöscht.

## NetherNet und Portfreigaben

Bedrock-Server ab 26.50 nutzen NetherNet (Mojangs `bedrock_server_how_to.html`, Abschnitt „Transport“):

1. **Signalisierung über TCP auf `server-port` (19132)** – HTTP.
2. **Spielverkehr über UDP** auf ausgehandelten Ports. Der Server teilt dem Spieler mit, wohin er senden soll.

Ohne weitere Einstellung nennt der Server nur seine eigenen Adressen (192.168.178.38 und IPv6). Spieler von außen
kommen dann durch Schritt 1, scheitern aber an Schritt 2. Fehlerbilder: am Handy Code „NetherNet“
(`InitialConnection-13`, das Handy fällt zuletzt auf RakNet zurück), am PC Code „Door“ (`InitialConnection-83`).

**`server-udp-ports`** legt die UDP-Ports fest und teilt Spielern eine öffentliche Adresse mit. Drei Fallen:
- Bereiche (`19140-19159`) und Komma-Listen werden **nicht richtig verarbeitet** (Mojira BDS-23108). Es
  funktioniert nur **eine Zeile pro Port mit IP**: `server-udp-ports=<IPv4>:19140:19140`.
- **Höchstens 16 Zeilen** („too many port mappings (max 16)“) → 10 Zeilen, Ports 19140–19149, bei maximal 10
  Spielern.
- Die IP muss eine **Zahl** sein (kein Name), und sie ändert sich, wenn Vodafone eine neue vergibt.

**Mobilfunk:** Handys im Mobilfunknetz haben oft nur IPv6. Den TCP-Schritt zur IPv4-Adresse übersetzt der
Netzbetreiber, den UDP-Spielverkehr kann das Handy aber nur mit einer IPv6-Gegenstelle aufbauen. Der Server bietet
seine öffentliche IPv6 schon von selbst an; es fehlte nur die Freigabe in der Fritzbox. Dafür braucht der Laptop
eine **feste IPv6-Adresse**.

## Einstellungen (Stand 30.10.)

**Fritzbox** (*Internet → Freigaben → Portfreigaben*, Gerät „mcserver“, 192.168.178.38 fest zugewiesen):

| Bezeichnung | Protokoll | Ports | IP-Version |
|---|---|---|---|
| Minecraft TCP | TCP | 19132 | IPv4 |
| Minecraft UDP | UDP | 19140–19149 | IPv4 |
| Minecraft TCP v6 | TCP | 19132 | IPv6 |
| Minecraft UDP v6 | UDP | 19140–19149 | IPv6 |

- IPv6-Interface-ID des Geräts: `::429f:38ff:feca:e91f`.
- Kein „Exposed Host“, keine weiteren IPv6-Öffnungen.
- Nebenbei gesehen: Die Fritzbox-Oberfläche ist per MyFRITZ! aus dem Internet erreichbar (HTTPS). Das hat mit
  Minecraft nichts zu tun; abschalten, falls nicht gebraucht.

**Laptop:**
- **IPv6-Adresse fest**, abgeleitet aus der WLAN-Hardware-Adresse (EUI-64). Sie bleibt gleich, auch wenn
  Vodafone das Präfix wechselt; für ausgehende Verbindungen gibt es weiter wechselnde Datenschutz-Adressen:
  `sudo nmcli connection modify <WLAN> ipv6.addr-gen-mode eui64` und `sudo nmcli connection up <WLAN>`.
  Rückgängig: `default` statt `eui64`.
- **`deploy/mc-public-ip` + Drop-in `30-public-ip.conf`:** Vor jedem Minecraft-Start fragt der Laptop die
  Fritzbox nach der öffentlichen IPv4 (UPnP `GetExternalIPAddress` im Heimnetz: kein fremder Dienst, kein
  Passwort). Dann schreibt er die 10 `server-udp-ports`-Zeilen neu.
  - Antwortet der Router nicht oder liefert keine öffentliche Adresse (z. B. wieder DS-Lite), bleiben die alten
    Zeilen stehen, und der Start wird nie blockiert.
  - Installiert von `install.sh`; Tests in `tests/test_public_ip.py`.
- **`verify.sh`** prüft „Zugang von außen“: Alle UDP-Zeilen müssen die aktuelle öffentliche IPv4 tragen.
- **Neue Welt:** `server-udp-ports` steht bewusst nicht in `provision/server.properties.overrides`, die Zeilen
  schreibt `mc-public-ip` beim ersten Start.

## Für Freunde

Server hinzufügen: Adresse = `<öffentliche IPv4>`, Port `19132`. Die Whitelist gilt weiter, nur wer darauf steht,
kommt hinein.

Offen: ein Name statt der Zahl. Die MyFRITZ!-Adresse zeigt auch auf die IPv6 der Fritzbox selbst (nicht des
Laptops). Ob Clients damit klarkommen, ist nicht getestet.
