# Reproduzierbarer Aufbau – Plan für den echten Server

Stand: 2026-10-26 · Entscheidungen: **derselbe Laptop**, **neue Welt**, **sauberer Aufbau unter `/opt/minecraft`**

## Ziel

Ein Befehl richtet den kompletten Server so ein, wie er in der Testphase entstanden ist –
auf diesem Laptop zum Start des echten Servers, und genauso auf jedem frischen Ubuntu/Linux Mint.
Alles Wissen aus der Testphase (M1–M5, die Fehler beim ersten Update, Log-Einstellungen …)
steckt in Scripts, nicht in Handarbeit.

## Was heute nicht reproduzierbar ist

| Heute (Testphase) | Problem |
|---|---|
| Server von Hand in `~/Downloads/bedrock-server-1.21.51.02` entpackt (Ordner 777, Teile gehörten root) | genau das hat das erste Update scheitern lassen |
| systemd-Unit von Hand geschrieben, nicht im Repo | geht beim Neuaufsetzen verloren |
| Läuft als `fred` | Minecraft hätte Zugriff auf alles von fred (inkl. Laravel-Projekt) |
| M1–M5 nacheinander von Hand ausgeführt, dazu manuelle Korrekturen (chown, chmod) | Reihenfolge und Korrekturen stehen nur im Chatverlauf |
| `server.properties` | weicht nur in 2 Zeilen (M5) vom Mojang-Standard ab – gut, aber nirgends festgehalten |

## Ziel-Aufbau

```text
/opt/minecraft/                      Benutzer "minecraft" (Systembenutzer, keine Anmeldung)
└── bedrock/                         Serverprogramm + Welt + Konfiguration (750, nur minecraft)
    ├── worlds/<Weltname>/           neue Welt, Statistik-Pack von Anfang an drin
    ├── server.properties            Mojang-Standard + Abweichungen aus dem Repo
    ├── allowlist.json, permissions.json   (personenbezogen – nie im Repo)
/etc/systemd/system/minecraft-bedrock.service   aus dem Repo, mit Sandbox
            + .socket / .service.d/10-portal.conf  (Konsole, sauberer Stopp – M2)
/opt/mcportal, /var/lib/mcportal, /etc/mcportal  Portal wie heute
```

Der Unit-Name bleibt `minecraft-bedrock.service` – Portal, polkit-Regel und Scripts funktionieren unverändert.

## Neue Dateien im Repo

```text
provision/
├── server.conf.example          Einstellungen: Weltname, Servername, Benutzer, Pfade, LAN, Port
├── server.properties.overrides  nur die Abweichungen vom Mojang-Standard
├── minecraft-bedrock.service.in Unit (User=minecraft, Sandbox, Restart=on-failure)
├── setup.sh                     alles in einem, idempotent (mehrfach ausführbar)
├── import-players.sh            Whitelist + Operatoren aus einer bestehenden Installation übernehmen
└── verify.sh                    Abnahmetest: Dienste, Ports, Konsole, Portal, Statistik-Pack, Laravel
```

`setup.sh` macht der Reihe nach:

1. **Prüfen**: Ports frei bzw. von der eigenen Installation belegt, Speicher, Laravel-Antwort merken.
2. **Benutzer und Ordner**: `minecraft`, `/opt/minecraft/bedrock` mit sauberen Rechten (nichts 777, nichts root).
3. **Serverprogramm**: neueste offizielle Version mit derselben Prüfung wie der Update-Knopf
   (nur minecraft.net, Zip-Prüfung, keine `../`-Pfade).
4. **Konfiguration**: `server.properties` aus dem Zip + Abweichungen aus dem Repo (Weltname, Servername, Content-Log).
5. **Statistik-Pack** in die neue Welt (M5), bevor sie das erste Mal startet – kein Extra-Neustart.
6. **systemd**: Unit + Konsole (M2) installieren.
7. **Portal**: das bestehende `install.sh` (S1–S5, M3, M4) – zeigt automatisch auf den neuen Ordner.
8. **Start + `verify.sh`**.

Personenbezogene Daten (Whitelist, Operatoren) kommen nie ins öffentliche Repo:
`import-players.sh` übernimmt sie aus der Testinstallation; alternativ trägt man sie im Portal ein.

## Umstieg am Stichtag (auf diesem Laptop)

```text
Vorher (Tage davor, ohne Ausfall):
  setup.sh --prepare     neues Programm, Konfiguration, Welt-Ordner in /opt/minecraft vorbereiten,
                         einmal mit anderen Ports probestarten (wie der Testserver) und wieder stoppen

Stichtag (ca. 5 Minuten Ausfall):
  1. Testserver stoppen, Testinstallation komplett archivieren (bleibt liegen, wird nicht gelöscht)
  2. setup.sh            Unit auf /opt/minecraft umstellen, Portal neu ausrichten
  3. import-players.sh   Whitelist + Operatoren aus der Testinstallation
  4. Portal-Daten der Testphase archivieren (Statistik, Versionshistorie) – Neustart bei 0
  5. verify.sh
Rückweg: alte Unit-Datei zurück, daemon-reload, Start – die Testinstallation ist ja unverändert da.
```

## Was ich dafür an bestehenden Scripts anpasse

- `install.sh` / `m2-console.sh` / Update-Helfer: funktionieren schon mit jedem Pfad und Benutzer aus der Unit;
  nur Kleinigkeiten (z. B. `m5-stats-pack.sh` muss auch als `sudo -u minecraft` laufen).
- Portal: Sandbox-Pfade kommen schon aus der Unit; keine Codeänderung erwartet.

## Wie ich es teste, ohne den laufenden Server zu stören

- `setup.sh --prepare` komplett auf dem Laptop (eigener Ordner, Probestart auf anderen Ports) – der
  Testserver läuft weiter.
- Den eigentlichen Umstieg kann man nur am Stichtag ausführen; dafür gibt es den Rückweg oben.
- Optional: Probelauf auf einem frischen Linux (z. B. VM/zweiter Rechner), falls verfügbar.

## Offene Fragen für später

- Name der neuen Welt und Servername (Anzeige im Spiel).
- Sollen beim Start des echten Servers alle heutigen Whitelist-Einträge übernommen werden?
- Termin für den Umstieg.
