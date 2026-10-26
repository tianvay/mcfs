# Block-Statistik (Änderung M5)

Stand: 2026-10-25

## So funktioniert es

```text
Spieler setzt/baut Block ab
  → Statistik-Pack in der Welt (Script, stabile API @minecraft/server 2.10.0)
  → alle 20 s eine Zeile ins Server-Log:  [WARN] [Scripting] [mcportal-stats] {...}
  → Portal liest das Journal, addiert in /var/lib/mcportal/stats.json
  → Tab „Statistik“: pro Spieler gesetzt/abgebaut + häufigste Blöcke (live)
```

- Gezählt wird erst ab der Installation; frühere Bauten lassen sich nicht ermitteln.
- Für Spieler unsichtbar, kein Download nötig, keine Experimente in der Welt.
- Doppelzählung ausgeschlossen (Cursor über Zeitstempel + Zeilen-Hash, auch nach Portal-Neustart).
- Läuft das Portal nicht, holt es die Zeilen beim nächsten Start aus dem Journal nach.
- Bei einem Absturz von Minecraft gehen höchstens die letzten 20 Sekunden verloren.

## Änderung M5

1. **Was wird geändert?**
   - neuer Ordner `worlds/Bedrock level/behavior_packs/mcportal_stats/`
   - `worlds/Bedrock level/world_behavior_packs.json`: ein Eintrag (vorher `[]`)
   - `server.properties`: `content-log-console-output-enabled=false → true`,
     `content-log-level=info → warning`
2. **Warum?** Bedrock protokolliert Blöcke nicht selbst; das Script zählt sie. Seine Ausgabe
   erscheint nur mit eingeschalteter Content-Log-Ausgabe im Log. Level „warning“ lässt die
   Statistik-Zeilen durch, hält aber Info-Meldungen von Inhalten aus dem Log heraus.
3. **Betroffene Dateien:** die drei oben genannten. Sonst nichts – im Probelauf geprüft.
4. **Backup:** `~/mcportal-backups/<zeit>_pre_m5/` (server.properties, world_behavior_packs.json,
   Liste der Packs).
5. **Rückgängig:** `bash ~/mcportal-src/deploy/m5-stats-pack.sh rollback` – stellt beide Dateien
   exakt wieder her, verschiebt das Pack in die Sicherung und startet Minecraft neu.

Erfordert einen Minecraft-Neustart (~10 s), kein sudo.

## Getestet

- Eigener Testserver (gleiche Bedrock-Version 1.26.52.3, frische Testwelt, andere Ports):
  verfügbare Script-API-Versionen ermittelt (stabil: 1.19.0, 2.10.0), Pack lädt fehlerfrei,
  beide Block-Ereignisse lassen sich abonnieren, Ausgabe-Format bestätigt, Einfluss der
  Log-Einstellungen geprüft (mit `false` erscheint nichts; `warning` + `console.warn` funktioniert).
- 22 Unit-Tests, u. a. keine Doppelzählung über Portal-Neustarts.
- Oberfläche mit simuliertem Server (Live-Aktualisierung, deutsche Blocknamen).
- **Nicht getestet:** echtes Setzen/Abbauen durch einen Spieler – dafür muss jemand
  auf dem echten Server ein paar Blöcke setzen.

## Hinweis zu Server-Updates

Das Pack liegt in der Welt und wird von Updates nicht angefasst. Mojang hält ältere stabile
Script-API-Versionen meist verfügbar (1.19.0 ist z. B. noch da). Falls eine neue Version 2.10.0
nicht mehr anbietet, zeigt das Server-Log einen Scripting-Fehler, die Statistik pausiert, das Spiel
läuft normal weiter; dann muss nur die Versionsnummer im Pack angepasst werden.
