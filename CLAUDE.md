# mcfs – Hinweise für Claude

- Antworten an den Nutzer auf Deutsch.
- **Denke stets daran, die README und die Installation aktuell zu halten.** Jede neue Funktion, jedes neue Pack,
  Script, jede Unit, jedes Systempaket oder jeder neue Rechte-Schritt gehört in derselben Änderung auch in die
  Ein-Zeilen-Installation (`mcportal/provision/setup.sh --install`, `provision/packs.list`, `gamerules.list`,
  `server.properties.overrides`, `deploy/install.sh`) und in `README.md` sowie `docs/15-installation.md`.
  Ein frischer Ubuntu-Server muss mit dem Befehl aus der README genau so laufen wie der Familienserver.
- Nur für den Laptop (bleibt aus der Installation draußen): WLAN-Stromsparen (`deploy/wifi-no-powersave.sh`),
  feste IP, Portfreigaben in der Fritzbox.
- Dateien für den Server mit LF-Zeilenenden schreiben (`.gitattributes`).
- Jede Änderung an der Minecraft-Installation bekommt eine Nummer (M1, M2, …) und eine Seite unter `docs/`:
  was, warum, welche Dateien, Sicherung, Rückweg.
