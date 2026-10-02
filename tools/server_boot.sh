#!/usr/bin/env bash
# Headless boot of the pack in .run/server. An EXIT trap kills what it starts in the background (packwiz serve, then run.sh and
# its java child), however the script ends before the server is stopped; a server still running 60 s after the stop is killed
# with SIGKILL and fails the boot (SERVER DID NOT STOP), and the trap is cleared before the checks. Exit 0 iff the server reached "Done" with no KubeJS errors, no recipe parse errors
# (logs/latest.log must exist), every shipped config/ file loaded unchanged (tools/check_configs.py), no FTB Quests errors and
# no ERROR or FATAL line in logs/latest.log that tools/boot_allowlist.txt does not explain (tools/check_boot_log.py).
# tools/server_boot.sh --check [RUN_DIR] runs only those post-boot checks, on the logs a boot already left in RUN_DIR (default
# .run/server), without booting.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NEO=21.1.250
RUN="$ROOT/.run/server"

# The post-boot checks, run in the server directory $1 (absolute); $2 (default 0) is the status so far, 1 when the server did
# not stop. Every check runs, even after one fails (v0.3 Task 8c round 2): each failure prints its label, and the function ends
# the script with the combined status, BOOT OK and 0 when all passed, BOOT CHECKS FAILED and 1 otherwise.
post_boot_checks() {
  cd "$1"
  local status="${2:-0}" rc=0
  grep -E 'Done \(|Failed to load datapacks|Failed to start the minecraft server|Missing or unsupported mandatory|Requested by' console.log || true
  if ! grep -q 'Done (' console.log; then echo "BOOT FAILED"; status=1; fi
  # The checks below grep these files, and a grep that cannot read its file matches nothing: a missing log would pass them.
  # (Each `grep | head -40` below ends in `|| true`: under pipefail a grep that head cut off exits 141, and set -e would
  # then end the script with 141.)
  # The boot deletes all three before starting the server, so each must be this boot's.
  for log in logs/latest.log logs/kubejs/startup.log logs/kubejs/server.log; do
    if [ ! -f "$log" ]; then echo "MISSING LOG: $1/$log"; status=1; fi
  done
  if grep -q -E '^\[.*ERROR' logs/kubejs/startup.log logs/kubejs/server.log 2>/dev/null; then
    echo "KUBEJS ERRORS"; grep -E 'ERROR' logs/kubejs/*.log 2>/dev/null | head -40 || true; status=1
  fi
  # A recipe the codec rejects, datapack or script, is dropped with only this vanilla line (RecipeManager.apply): the recipe dump
  # and KubeJS's "failed recipes" count both miss it (tools/tests/test_if_dissolution_data.py docstring).
  if grep -q 'Parsing error loading recipe' logs/latest.log 2>/dev/null; then
    echo "RECIPE PARSE ERRORS"; grep -A2 'Parsing error loading recipe' logs/latest.log | head -40 || true; status=1
  fi
  # Shipped configs: NeoForge rewrites a config/ file its spec calls incorrect (a renamed key reverts to the mod's default) with
  # only a WARN, and a renamed file is never read. check_configs.py checks each shipped config/**/*.toml was tracked and
  # loaded from $1/config, not corrected or recreated, and installed byte-identical (its header cites the loader jar).
  python3 "$ROOT/tools/check_configs.py" "$1" || { echo "CONFIG ERRORS"; status=1; }
  # Questbook: print the load line and fail on any FTB Quests error (a malformed SNBT id or reward is logged, not thrown).
  grep '\[FTB Quests/\]: Loaded' console.log || echo "WARN: no FTB Quests 'Loaded' line within the grace period"
  if grep -E '/(ERROR|WARN)\] \[FTB Quests/\]' console.log | grep -v -i 'translation'; then echo "FTBQUESTS ERRORS"; status=1; fi
  # Every ERROR/FATAL record in logs/latest.log must match a documented tools/boot_allowlist.txt entry, and the log must reach
  # the server's Done line (v0.3 Task 8c). WARN lines are not checked: the config WARNs are check_configs.py's, and the
  # allowlist header lists the known WARN noise. Its exit codes (its docstring): 1 an unknown record or an incomplete log,
  # 2 a usage error, 3 a missing or bad allowlist.
  python3 "$ROOT/tools/check_boot_log.py" "$1" || rc=$?
  case "$rc" in
    0) ;;
    2) echo "BOOT LOG CHECK USAGE ERROR"; status=1 ;;
    3) echo "BAD ALLOWLIST"; status=1 ;;
    *) echo "BOOT LOG ERRORS"; status=1 ;;
  esac
  if [ "$status" -eq 0 ]; then echo "BOOT OK"; else echo "BOOT CHECKS FAILED"; fi
  exit "$status"
}

if [ "${1:-}" = "--check" ]; then
  [ $# -le 2 ] || { echo "usage: $0 [--check [RUN_DIR]]"; exit 2; }
  CHECK_DIR="${2:-$RUN}"
  [ -d "$CHECK_DIR" ] || { echo "no such directory: $CHECK_DIR"; exit 2; }
  post_boot_checks "$(cd "$CHECK_DIR" && pwd)"   # it exits with the checks' status
fi
[ $# -eq 0 ] || { echo "usage: $0 [--check [RUN_DIR]]"; exit 2; }
JAVA="${JAVA_HOME:-$(/usr/libexec/java_home -v 21)}/bin/java"
mkdir -p "$RUN"
cd "$ROOT"
packwiz serve -p 8087 >/dev/null 2>&1 &
SERVE_PID=$!
trap 'kill "$SERVE_PID" 2>/dev/null || true' EXIT
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
JAVA_PID=""
# $JAVA_PID too: once run.sh is killed below, its java child is no longer its child, and pgrep -P cannot find it
trap 'kill $(pgrep -P "$SERVER_PID" 2>/dev/null || true) $JAVA_PID "$SERVER_PID" "$SERVE_PID" 2>/dev/null || true' EXIT
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
STOP_STATUS=0
if [ -n "$JAVA_PID" ] && kill -0 $JAVA_PID 2>/dev/null; then
  kill -9 $JAVA_PID 2>/dev/null || true
  echo "SERVER DID NOT STOP"; STOP_STATUS=1
fi
sleep 3
# Everything is stopped: clear the trap and the PIDs, so nothing signals a PID the system may since have reused.
trap - EXIT
SERVE_PID="" SERVER_PID="" JAVA_PID=""
post_boot_checks "$RUN" "$STOP_STATUS"
