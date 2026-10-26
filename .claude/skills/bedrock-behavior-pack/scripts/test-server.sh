#!/usr/bin/env bash
# Throwaway Bedrock test server for behavior packs - never touches the real installation.
#
#   ssh fred@192.168.178.38 'bash -s -- <pack_dir_on_server> <api-version> [seconds]' < test-server.sh
#
#   api-version 99.0.0  -> the server refuses and lists "Available versions:"
#
# Copies the installed server program (not the world) to ~/bds-test once, starts it with a
# fresh world "PackTest" on other ports (19150/19151), raknet, no LAN visibility and the same
# content-log settings as production; stops it with "stop" after <seconds>.
# Clean up afterwards: rm -rf ~/bds-test  (~600 MB)
set -euo pipefail
[[ "${1:-}" == "--" ]] && shift
PACK="${1:?pack dir}"; API="${2:?api version}"; SECS="${3:-30}"
REAL="$(systemctl show -p WorkingDirectory --value minecraft-bedrock.service)"
T="$HOME/bds-test"
[[ -f "$PACK/manifest.json" ]] || { echo "kein manifest.json in $PACK"; exit 1; }

echo "RAM verfügbar: $(free -m | awk '/^Mem/ {print $7}') MB"
if [[ ! -x "$T/bedrock_server" ]]; then
  mkdir -p "$T"
  rsync -a --exclude=/worlds/ --exclude='/*.zip' --exclude='/*.run' --exclude='/wget-log*' \
        --exclude=/allowlist.json --exclude=/permissions.json "$REAL/" "$T/"
  echo '[]' > "$T/allowlist.json"; echo '[]' > "$T/permissions.json"
  sed -i -e 's/^server-port=.*/server-port=19150/' -e 's/^server-portv6=.*/server-portv6=19151/' \
         -e 's/^enable-lan-visibility=.*/enable-lan-visibility=false/' -e 's/^level-name=.*/level-name=PackTest/' \
         -e 's/^server-name=.*/server-name=PackTest/' -e 's/^transport=.*/transport=raknet/' \
         -e 's/^view-distance=.*/view-distance=5/' -e 's/^max-threads=.*/max-threads=2/' \
         -e 's/^content-log-console-output-enabled=.*/content-log-console-output-enabled=true/' \
         -e 's/^content-log-level=.*/content-log-level=warning/' "$T/server.properties"
fi

# the world entry must carry the manifest's exact version, otherwise the pack is silently not loaded
WORLD_ENTRY="$(python3 -c 'import json,sys; h=json.load(open(sys.argv[1]))["header"]; print(json.dumps([{"pack_id": h["uuid"], "version": h["version"]}]))' "$PACK/manifest.json")"
NAME="$(basename "$PACK")"
W="$T/worlds/PackTest"; mkdir -p "$W/behavior_packs"
rm -rf "$W/behavior_packs/$NAME"; cp -r "$PACK" "$W/behavior_packs/$NAME"
sed -i "s/@SERVER_API@/$API/" "$W/behavior_packs/$NAME/manifest.json"
echo "$WORLD_ENTRY" > "$W/world_behavior_packs.json"

cd "$T"
# show only what matters for a pack: load, scripting errors, the version list, its own lines
(sleep "$SECS"; echo stop; sleep 10) | nice -n 10 ./bedrock_server 2>&1 | awk '
  /Available versions:/                                    { print; list = 1; next }
  list && /^[0-9]/                                         { print; next }
                                                           { list = 0 }
  /BiomeRegistry|FeatureRegistry|\[Structure\]/            { next }
  /\[Scripting\]|mcportal-|Pack Stack|Server started|Quit correctly/ { print }
'
