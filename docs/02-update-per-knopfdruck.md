# Server-Update per Knopfdruck (Änderung M4)

Stand: 2026-10-25

## Ablauf

```text
Vorbereitung          Platz prüfen (≥ 1,5 GB frei), aktuelle Version bekannt
Download              nur https://www.minecraft.net/bedrockdedicatedserver/bin-linux/…
Download prüfen       Zip intakt (CRC aller Dateien), keine ../-Pfade, keine Links,
                      bedrock_server + server.properties + Packs vorhanden
Spieler informieren   nur wenn jemand online ist: Chat-Nachricht, 15 s warten
Server stoppen        sauber über "stop" (M2)
Backup erstellen      komplettes Serververzeichnis als tar.gz (~190 MB),
                      ohne alte Zips/Installer; Prüfsummen der geschützten Dateien
Dateien aktualisieren Hilfsprogramm kopiert die neue Version (s. u.)
Whitelist & Op prüfen allowlist.json, permissions.json, server.properties
                      müssen byte-gleich sein – sonst Rollback
Server starten
Serverstatus prüfen   "Server started." mit der neuen Version innerhalb 180 s
```

Download und Prüfung laufen, während der Server noch läuft – der Server ist nur
für Stop → Start offline (ca. 1–2 Minuten).

**Bei einem Fehler nach dem Kopieren:** Server stoppen → Backup zurückspielen →
alte Version starten. Der fehlgeschlagene Stand wird nicht gelöscht, sondern nach
`…/bedrock-server-1.21.51.02.failed-<zeit>/` verschoben (kann danach von Hand gelöscht werden).

**Bei einem Fehler vorher** (Download, Prüfung, Backup): Es wurde nichts verändert,
der Server läuft weiter bzw. wird wieder gestartet.

## Was ein Update nie verändert

| Datei/Ordner | Verhalten |
|---|---|
| `worlds/` | nie angefasst |
| `allowlist.json`, `permissions.json`, `server.properties` | nie überschrieben, nach dem Update byte-genau geprüft |
| `whitelist.json`, `packetlimitconfig.json`, `config/` | nie überschrieben (nur angelegt, falls sie fehlen) |
| eigene Dateien/Ordner (z. B. `development_*`) | bleiben, das Update löscht nichts |

## Speicherplatz

- Während des Updates kurzzeitig: Download 95 MB + entpackt 320 MB (wird danach gelöscht).
- Dauerhaft: **nur das letzte Update-Backup (~190 MB)**. Ältere werden nach einem
  erfolgreichen Update entfernt (`update_backups_keep = 1` in `/etc/mcportal/config.toml`).
- Keine automatischen/nächtlichen Backups (bewusst, Speicher ist knapp).
- Platz-Tipp: Im Serververzeichnis liegen noch `bedrock-server.zip` (95 MB) und
  `xampp-linux-x64-8.2.12-0-installer.run` (160 MB) – beide werden vom Server nicht gebraucht.

## Änderung M4 am System

1. **Was wird geändert?**
   - neues Hilfsprogramm `/opt/mcportal/bin/mcportal-update-helper` (root-eigen, für das Portal nicht änderbar)
   - zwei systemd-Units `mcportal-update-apply.service` und `mcportal-update-rollback.service`
   - polkit-Regel erweitert: `mcportal` darf diese zwei Units *starten* (sonst nichts zusätzlich)
2. **Warum?** Die Serverdateien gehören `fred`; das Portal darf sie absichtlich nicht
   ändern. Das Hilfsprogramm läuft **als `fred` (nicht als root)**, in einer Sandbox, die nur
   `/home/fred/Downloads` beschreiben darf, und kann genau zwei Dinge: vorbereitete
   Version einspielen / letztes Update-Backup zurückspielen. Es nimmt vom Portal keine
   Parameter außer dieser festen Aktion an und verweigert, solange Minecraft läuft.
3. **Betroffene Dateien:** die drei oben genannten + `/etc/polkit-1/rules.d/50-mcportal.rules`.
   Am Minecraft-Server selbst ändert die Installation nichts.
4. **Backup:** install.sh sichert wie bisher vor jeder Installation (`*_pre_portal_install`,
   die letzten zwei werden behalten).
5. **Rückgängig:** `sudo bash ~/mcportal-src/deploy/uninstall.sh` entfernt alles;
   nur M4: die zwei Unit-Dateien und `/opt/mcportal/bin` löschen, `systemctl daemon-reload`
   und in `50-mcportal.rules` den Block für `mcportal-update-*` entfernen.

## Getestet

- 19 Unit-Tests (u. a. Download-Adresse, Zip mit `../`, absoluten Pfaden, Links,
  fehlendem Server, kaputter Prüfsumme, HTML statt Zip).
- Ablauf komplett mit simuliertem Server: Erfolg (10 Schritte) und Fehlerfall
  (neue Version startet nicht → automatischer Rollback, alte Version läuft wieder).
- Hilfsprogramm auf dem echten Server in einer Testumgebung mit dem echten Mojang-Zip:
  geschützte Dateien, Welt und eigene Packs byte-gleich; Rollback stellt exakt den
  alten Stand her; Ordner, Rechte und ACLs bleiben; verweigert bei laufendem Minecraft.
