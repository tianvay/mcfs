# Shared by provision/setup.sh, verify.sh and import-players.sh (sourced, not run).
# shellcheck shell=bash

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
PACKS_SRC="$REPO/minecraft-pack"
UNIT=minecraft-bedrock.service

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '    \033[1;33mWARNUNG: %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mFEHLER: %s\033[0m\n' "$*" >&2; exit 1; }

# load_conf [FILE]: --conf FILE, else /etc/mcportal/server.conf, else the example (placeholder names).
# Sets CONF, WORLD_NAME, MC_USER, MC_DIR, MC_HOME, PORT_V4, PORT_V6 - checked by properties.py.
load_conf() {
  CONF="${1:-}"
  if [[ -z "$CONF" ]]; then
    CONF=/etc/mcportal/server.conf
    [[ -f "$CONF" ]] || CONF="$HERE/server.conf.example"
  fi
  [[ -f "$CONF" ]] || fail "Einstellungen nicht gefunden: $CONF"
  local lines key value
  lines="$(python3 -I "$HERE/properties.py" conf "$CONF")" || fail "Einstellungen ungültig: $CONF"
  while IFS='=' read -r key value; do
    case "$key" in
      WORLD_NAME|MC_USER|MC_DIR|PORT_V4|PORT_V6) printf -v "$key" '%s' "$value" ;;
    esac
  done <<<"$lines"
  MC_HOME="$(dirname "$MC_DIR")"
}

conf_is_example() { [[ "$CONF" == "$HERE/server.conf.example" ]]; }

# manifest <manifest.json> name|uuid|version
manifest() {
  python3 -I -c 'import json,sys; h=json.load(open(sys.argv[1]))["header"]; print(h[sys.argv[2]] if sys.argv[2] != "version" else ".".join(map(str, h["version"])))' "$1" "$2"
}

# pack_lines: "<kind> <pack>" for every entry in packs.list, checked
pack_lines() {
  local kind pack n=0
  while read -r kind pack; do
    [[ -z "$kind" || "$kind" == \#* ]] && continue
    [[ "$kind" =~ ^(behavior|resource)$ && "$pack" =~ ^[a-z0-9_]+$ && -f "$PACKS_SRC/$pack/manifest.json" ]] \
      || fail "packs.list: ungültige Zeile '$kind $pack'"
    printf '%s %s\n' "$kind" "$pack"
    n=$((n + 1))
  done < "$HERE/packs.list"
  (( n > 0 )) || fail "packs.list ist leer"
}

# pack_log_patterns <pack dir>: what a started server logs for this behavior pack (one grep pattern per line):
# its "Pack Stack" entry with the exact version, and the startup line of its script (if it has one)
pack_log_patterns() {
  local dir="$1" tag
  printf '%s\n' "$(manifest "$dir/manifest.json" name).*version: $(manifest "$dir/manifest.json" version)"
  if [[ -f "$dir/scripts/main.js" ]]; then
    tag="$(grep -om1 '\[mcportal-[a-z]*\]' "$dir/scripts/main.js" || true)"
    [[ -n "$tag" ]] && printf '%s\n' "\\$tag {\"v\":[0-9]*,\"started\":true}"
  fi
  return 0
}

# script/content errors in a server log on stdin (our own tagged report lines are not errors)
log_errors() {
  grep -aE '\[Scripting\]|ERROR|\[Json|\[Item|\[Texture|\[Recipes\]' | grep -av 'mcportal-[a-z]*\]' || true
}
