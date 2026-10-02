#!/usr/bin/env bash
# Headless boot of the pack in .run/server. Exit 0 iff the server reached "Done" with no KubeJS errors, no recipe parse errors
# (logs/latest.log must exist), every shipped config/ file loaded unchanged (tools/check_configs.py) and no FTB Quests errors.
# tools/server_boot.sh --check [RUN_DIR] runs only those post-boot checks, on the logs a boot already left in RUN_DIR (default
# .run/server), without booting.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NEO=21.1.250
RUN="$ROOT/.run/server"

# The post-boot checks, run in the server directory $1 (absolute). Each failure prints its label and exits 1.
post_boot_checks() {
  cd "$1"
  grep -E 'Done \(|Failed to load datapacks|Failed to start the minecraft server|Missing or unsupported mandatory|Requested by' console.log || true
  if ! grep -q 'Done (' console.log; then echo "BOOT FAILED"; exit 1; fi
  # The checks below grep these files, and a grep that cannot read its file matches nothing: a missing log would pass them.
  # (Each `grep | head -40` below ends in `|| true`: under pipefail a grep that head cut off exits 141, and set -e would
  # then end the script with 141 before its `exit 1`.)
  # The boot deletes all three before starting the server, so each must be this boot's.
  for log in logs/latest.log logs/kubejs/startup.log logs/kubejs/server.log; do
    if [ ! -f "$log" ]; then echo "MISSING LOG: $1/$log"; exit 1; fi
  done
  if grep -q -E '^\[.*ERROR' logs/kubejs/startup.log logs/kubejs/server.log; then echo "KUBEJS ERRORS"; grep -E 'ERROR' logs/kubejs/*.log | head -40 || true; exit 1; fi
  # A recipe the codec rejects, datapack or script, is dropped with only this vanilla line (RecipeManager.apply): the recipe dump
  # and KubeJS's "failed recipes" count both miss it (tools/tests/test_if_dissolution_data.py docstring).
  if grep -q 'Parsing error loading recipe' logs/latest.log; then echo "RECIPE PARSE ERRORS"; grep -A2 'Parsing error loading recipe' logs/latest.log | head -40 || true; exit 1; fi
  # Shipped configs: NeoForge rewrites a config/ file its spec calls incorrect (a renamed key reverts to the mod's default) with
  # only a WARN, and a renamed file is never read. check_configs.py checks each shipped config/**/*.toml was tracked and
  # loaded from $1/config, not corrected or recreated, and installed byte-identical (its header cites the loader jar).
  python3 "$ROOT/tools/check_configs.py" "$1" || { echo "CONFIG ERRORS"; exit 1; }
  # Questbook: print the load line and fail on any FTB Quests error (a malformed SNBT id or reward is logged, not thrown).
  grep '\[FTB Quests/\]: Loaded' console.log || echo "WARN: no FTB Quests 'Loaded' line within the grace period"
  if grep -E '/(ERROR|WARN)\] \[FTB Quests/\]' console.log | grep -v -i 'translation'; then echo "FTBQUESTS ERRORS"; exit 1; fi
  echo "BOOT OK"
}

if [ "${1:-}" = "--check" ]; then
  [ $# -le 2 ] || { echo "usage: $0 [--check [RUN_DIR]]"; exit 2; }
  CHECK_DIR="${2:-$RUN}"
  [ -d "$CHECK_DIR" ] || { echo "no such directory: $CHECK_DIR"; exit 2; }
  post_boot_checks "$(cd "$CHECK_DIR" && pwd)"
  exit 0
fi
[ $# -eq 0 ] || { echo "usage: $0 [--check [RUN_DIR]]"; exit 2; }
JAVA="${JAVA_HOME:-$(/usr/libexec/java_home -v 21)}/bin/java"
mkdir -p "$RUN"
cd "$ROOT"
packwiz serve -p 8087 >/dev/null 2>&1 &
SERVE_PID=$!
sleep 2
cd "$RUN"
if [ ! -f run.sh ]; then
  curl -fsSL -o installer.jar "https://maven.neoforged.net/releases/net/neoforged/neoforge/$NEO/neoforge-$NEO-installer.jar"
  "$JAVA" -jar installer.jar --installServer .
  printf 'eula=true\n' > eula.txt
  printf -- '-Xms4G\n-Xmx6G\n' > user_jvm_args.txt
fi
curl -fsSL -o packwiz-installer-bootstrap.jar https://github.com/packwiz/packwiz-installer-bootstrap/releases/download/v0.0.3/packwiz-installer-bootstrap.jar
"$JAVA" -jar packwiz-installer-bootstrap.jar -g -s server http://localhost:8087/pack.toml
kill "$SERVE_PID" || true
rm -f logs/latest.log logs/kubejs/*.log console.log
export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 21)}"; export PATH="$JAVA_HOME/bin:$PATH"   # run.sh calls bare `java`
./run.sh nogui > console.log 2>&1 &
SERVER_PID=$!
for i in $(seq 1 120); do
  if grep -q 'Done (' console.log 2>/dev/null; then break; fi
  if grep -q -E 'Failed to load datapacks|Failed to start the minecraft server|Exception in thread "main"|Missing or unsupported mandatory dependencies|Mod ID: .* Requested by' console.log 2>/dev/null; then break; fi
  sleep 5
done
# FTB Quests loads the quest files ~1 s after "Done": give it up to 20 s so the chapter/quest count is logged.
if grep -q 'Done (' console.log 2>/dev/null; then
  for i in $(seq 1 20); do grep -q '\[FTB Quests/\]: Loaded' console.log 2>/dev/null && break; sleep 1; done
fi
# run.sh is a plain wrapper (no exec): kill the java child too, then wait for it to exit.
JAVA_PID="$(pgrep -P "$SERVER_PID" || true)"
kill $JAVA_PID "$SERVER_PID" 2>/dev/null || true
for i in $(seq 1 60); do [ -n "$JAVA_PID" ] && kill -0 $JAVA_PID 2>/dev/null || break; sleep 1; done
sleep 3
post_boot_checks "$RUN"
