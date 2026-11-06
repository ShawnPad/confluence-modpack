#!/usr/bin/env bash
# Headless boot of the pack in .run/server. An EXIT trap kills what it starts in the background (packwiz serve, then run.sh
# and its java child), however the script ends before the server is stopped. A server still running 60 s after the stop is
# declared hung: the trap is re-armed to SIGKILL java and the dump, the server is thread-dumped (jcmd Thread.print -l,
# appended to console.log; v0.3 Task 11c), then killed with SIGKILL, and the boot fails (SERVER DID NOT STOP). The trap is
# cleared before the checks. Exit 0 iff the server reached "Done" with no KubeJS errors, no recipe parse errors
# (logs/latest.log must exist), every shipped config/ file loaded unchanged (tools/check_configs.py), no FTB Quests errors,
# no ERROR or FATAL line in logs/latest.log that tools/boot_allowlist.txt does not explain, no missing-tag WARN at all,
# Moonlight's pinned generated-pack set (tools/check_boot_log.py; D134), the pinned game-rule set and exactly one Twilight
# Forest guard OK line (also tools/check_boot_log.py, against tools/gamerules.toml: `game rules: 55 expected, server 55,
# registry 55, guard OK`; v0.3 Task 11d, D137), and nothing left keeping chunks loaded in the run world
# (tools/count_forced_chunks.py, read after the stop: `forced chunks: 0 (mod tickets: 0; ...)`; v0.3 Task 11c, D136).
# When a check fails, the boot's logs and recipe dump are copied to .run/failed-boots/<UTC timestamp>/ and the path is
# printed (or "NOT CREATED (<path>)" when it cannot be made). A boot refuses to start, exit 2, while a probe session has not
# cleaned up (.run/server/server.properties.session-backup; v0.3 Task 12).
# tools/server_boot.sh --check [RUN_DIR] runs only those post-boot checks, on the logs a boot already left in RUN_DIR
# (default .run/server), without booting. When the checks pass it only reads the logs; each failing --check is archived too,
# as a new copy under this pack's .run/failed-boots/ whatever RUN_DIR is (about 11 MB each; its SOURCE file names RUN_DIR).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NEO=21.1.250
RUN="$ROOT/.run/server"
CHECK_ONLY=""   # only --check sets it: one exported by the caller must not reach a boot's forced-chunk guard (Task 11c round 3)

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
  # Every ERROR/FATAL record in logs/latest.log must match a documented tools/boot_allowlist.txt entry, and Minecraft's
  # missing-tag WARN fails whatever the allowlist says; the log must reach the server's Done line (v0.3 Task 8c); Moonlight's
  # generated data packs must be the pinned set (v0.3 Task 10b, D134); and the game rules must be the pinned set, with the
  # Twilight Forest guard's OK line (v0.3 Task 11d, D137). Other WARN lines are not checked: the config WARNs are
  # check_configs.py's, and the allowlist header lists the known WARN noise. Its exit codes (its docstring): 1 an unknown
  # record, a game-rule or dynamic-pack problem or an incomplete log, 2 a usage error, 3 a missing or bad allowlist, 4 a
  # missing or bad tools/gamerules.toml.
  python3 "$ROOT/tools/check_boot_log.py" "$1" || rc=$?
  case "$rc" in
    0) ;;
    2) echo "BOOT LOG CHECK USAGE ERROR"; status=1 ;;
    3) echo "BAD ALLOWLIST"; status=1 ;;
    4) echo "BAD GAMERULES PIN"; status=1 ;;
    *) echo "BOOT LOG ERRORS"; status=1 ;;
  esac
  # Forced chunks and mod tickets (v0.3 Task 11c, D136). A forceload or a chunk loader left in the world is re-added at every
  # boot, and a stop that arrives while those chunks load waits for every one (25-199 s with the 5,121 two probes had
  # leaked, against 1.3-1.4 s without): SERVER DID NOT STOP at random. count_forced_chunks.py reads each data/chunks.dat in
  # the run world and prints `forced chunks: F (mod tickets: M; ...)`; F + M above 0 fails, so a leak fails every boot
  # instead of some. After a clean stop the files are this boot's final save; after the SIGKILL (SERVER DID NOT STOP) they
  # are the last save before it, which is still what the next boot re-adds. Its exit codes (its docstring): 1 something
  # counted, 2 a usage error, an unreadable file or no world. A boot always has a world; --check passes --allow-no-world,
  # since its RUN_DIR may be a failed-boot archive (logs only, no server.properties), and the guard then prints `forced
  # chunks: 0 (no world at ...)` and passes. A RUN_DIR with server.properties and no world fails even then.
  rc=0
  python3 "$ROOT/tools/count_forced_chunks.py" ${CHECK_ONLY:+--allow-no-world} "$1" || rc=$?
  case "$rc" in
    0) ;;
    1) echo "FORCED CHUNKS"; status=1 ;;
    *) echo "FORCED CHUNKS CHECK ERROR"; status=1 ;;
  esac
  if [ "$status" -ne 0 ]; then
    # Keep the failed boot's evidence (v0.3 Task 10b, D134): the next boot deletes latest.log, console.log and the KubeJS
    # logs, rotates debug.log, and rewrites the recipe dump. Each failure gets its own .run/failed-boots/<UTC timestamp>/
    # (git and packwiz both ignore .run/). A file that is not there is named, not fatal, and so is an archive directory that
    # cannot be made (a read-only .run/, a full disk): the boot still ends with its label and status.
    local stamp archive n=0 f missing=""
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    archive="$ROOT/.run/failed-boots/$stamp"
    while [ -e "$archive" ]; do n=$((n + 1)); archive="$ROOT/.run/failed-boots/$stamp-$n"; done
    if mkdir -p "$archive" 2>/dev/null; then
      for f in logs/latest.log logs/debug.log console.log logs/kubejs/startup.log logs/kubejs/server.log \
               kubejs/exported/recipes.json; do
        if [ -f "$f" ]; then
          { mkdir -p "$archive/$(dirname "$f")" && cp -p "$f" "$archive/$f"; } || echo "  (could not archive $f)"
        else
          missing="$missing $f"
        fi
      done
      # The archive is always under this pack's .run/, so it records which server directory it came from.
      printf '%s\n' "$1" > "$archive/SOURCE" || true
      echo "failed-boot archive: $archive"
      if [ -n "$missing" ]; then echo "  (not present, not archived:$missing)"; fi
    else
      echo "failed-boot archive: NOT CREATED ($archive)"
    fi
  fi
  if [ "$status" -eq 0 ]; then echo "BOOT OK"; else echo "BOOT CHECKS FAILED"; fi
  exit "$status"
}

if [ "${1:-}" = "--check" ]; then
  [ $# -le 2 ] || { echo "usage: $0 [--check [RUN_DIR]]"; exit 2; }
  CHECK_DIR="${2:-$RUN}"
  [ -d "$CHECK_DIR" ] || { echo "no such directory: $CHECK_DIR"; exit 2; }
  CHECK_ONLY=1
  post_boot_checks "$(cd "$CHECK_DIR" && pwd)"   # it exits with the checks' status
fi
[ $# -eq 0 ] || { echo "usage: $0 [--check [RUN_DIR]]"; exit 2; }
# A probe session has not cleaned up (v0.3 Task 12): level-name may still be its world, and this boot would check and pass that
# world. The backup exists exactly while tools/server_session.sh has server.properties changed. Not for --check, above.
if [ -f "$RUN/server.properties.session-backup" ]; then
  echo "a probe session has not cleaned up ($RUN/server.properties.session-backup exists): if no one is playing on it, run tools/server_session.sh stop first"
  exit 2
fi
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
rm -f logs/latest.log logs/kubejs/*.log console.log stop-threads.txt
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
STOP_STATUS=0 DUMP_PID=""
if [ -n "$JAVA_PID" ] && kill -0 $JAVA_PID 2>/dev/null; then
  # Declared hung: it outlived SIGTERM, so the trap's SIGTERM would leave it running. From here an interrupt SIGKILLs java
  # and the dump (Task 11c fix round 2, M1).
  trap 'kill -9 $JAVA_PID ${DUMP_PID:-} 2>/dev/null || true' EXIT
  # v0.3 Task 11c: record why it did not stop before killing it. The dump (jcmd, given 30 s) goes to a side file, and is
  # appended to console.log once java is dead: java writes console.log at its own offset, so it could overwrite an append.
  "$JAVA_HOME/bin/jcmd" $JAVA_PID Thread.print -l > stop-threads.txt 2>&1 &
  DUMP_PID=$!
  for i in $(seq 1 30); do kill -0 $DUMP_PID 2>/dev/null || break; sleep 1; done
  if kill -0 $DUMP_PID 2>/dev/null; then
    # SIGKILL and reap it before the note: a jcmd still running writes stop-threads.txt at its own offset, over the note (M2).
    kill -9 $DUMP_PID 2>/dev/null || true
    wait $DUMP_PID 2>/dev/null || true
    echo "(jcmd did not finish within 30 s; killed)" >> stop-threads.txt
  fi
  wait $DUMP_PID 2>/dev/null || true
  if kill -0 $JAVA_PID 2>/dev/null; then
    kill -9 $JAVA_PID 2>/dev/null || true
  else
    # Never signal a PID that has exited (M3). A stop just over 60 s ends while jcmd attaches, and jcmd then fails ("state
    # is not ready"): say so, or it reads as a hang.
    echo "(java exited on its own while jcmd ran: the stop took just over the 60 s wait)" >> stop-threads.txt
  fi
  echo "SERVER DID NOT STOP"; STOP_STATUS=1
fi
sleep 3
if [ -f stop-threads.txt ]; then
  { echo "==== SERVER DID NOT STOP: jcmd Thread.print -l, taken before the SIGKILL ===="; cat stop-threads.txt; } >> console.log
  rm -f stop-threads.txt
  echo "thread dump appended to console.log"
fi
# Everything is stopped: clear the trap and the PIDs, so nothing signals a PID the system may since have reused.
trap - EXIT
SERVE_PID="" SERVER_PID="" JAVA_PID=""
post_boot_checks "$RUN" "$STOP_STATUS"
