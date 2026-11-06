#!/usr/bin/env bash
# In-game probe session (plan v0.3 Task 12, spec §12 items 2-6): sync the pack into .run/server as server_boot.sh
# does, boot a separate world, and keep the server and `packwiz serve -p 8087` up until the session is stopped.
#
#   tools/server_session.sh start [--offline] [--world NAME]   runs in the foreground until the server stops
#   tools/server_session.sh wait                               block until the server is ready (up to 600 s)
#   tools/server_session.sh cmd '<console command>' [SECONDS]  send one console command, print the reply line(s)
#   tools/server_session.sh status                             exit 0 and "session: up ..." if running, else 1
#   tools/server_session.sh stop                               send `stop` and wait until the session is down
#
# --world NAME  world folder in .run/server (default probe_v03). `world` belongs to server_boot.sh and is refused.
# --offline     online-mode=false for this session only.
# server.properties (level-name, online-mode) is backed up and restored when the session ends, by the EXIT trap, or by the
# next `stop` or `start` after a crash. Until then a server_boot.sh would read the session's values.
# A start is ready only after tools/check_boot_log.py passes (the Moonlight packs of D134, the game rules and guard line of
# D137). A failed start is a finding, never a flake (D134): its logs go to .run/failed-boots/<UTC timestamp>/; do not retry it
# away. The end of a session prints the forced-chunk count of the test world (D136), and a count above 0 fails.
# CONFLUENCE_RUN overrides the server folder (the unit tests point it at an empty folder). CONFLUENCE_SESSION_SETTLE (2 s, the
# wait for packwiz serve), _POLL (5 s, between looks for Done) and _STOP_WAIT (60 s, each wait of an interrupted start) exist for
# the dry-run tests.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="${CONFLUENCE_RUN:-$ROOT/.run/server}"
FIFO="$RUN/session.in"
PIDS="$RUN/session.pids"
LOG="$RUN/console.session.log"
PROPS="$RUN/server.properties"
BACKUP="$RUN/server.properties.session-backup"
SETTLE="${CONFLUENCE_SESSION_SETTLE:-2}"
POLL="${CONFLUENCE_SESSION_POLL:-5}"
STOP_WAIT="${CONFLUENCE_SESSION_STOP_WAIT:-60}"
# Anchored on the program itself, so a shell or a test whose command line only mentions these does not refuse a start.
SERVER_PATTERN='^[^ ]*java .*unix_args\.txt'
SERVE_PATTERN='^[^ ]*packwiz serve'

usage() { sed -n '/^set -uo/q;/^# /p' "$0"; exit 2; }
pid_of() { [ -f "$PIDS" ] && sed -n "s/^$1=//p" "$PIDS"; }
alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }
is_up() { alive "$(pid_of server)"; }
is_starting() { ! is_up && alive "$(pid_of start)"; }
is_ready() { is_up && [ "$(pid_of ready)" = 1 ]; }
# Whether the session file's server= PID is a run.sh, and if not, say so: it may belong to something else by now (a reboot).
# Empty output is no evidence (ps failed, or the process just went): only a command that is visibly something else counts.
server_ours() {
  local c; c="$(ps -o command= -p "$(pid_of server)" 2>/dev/null)"
  [ -z "$c" ] || printf '%s\n' "$c" | grep -Eq 'run\.sh|unix_args'
}
reused_hint() {
  echo "session: pid $(pid_of server) in $PIDS is not a run.sh, so it may be a reused PID from a dead session; tools/server_session.sh stop clears it and leaves that process alone" >&2
}
opened_world() { sed -n 's/.*Preparing level "\(.*\)".*/\1/p' "$LOG" 2>/dev/null | head -1; }

# Same pattern as tools/probe_lib.sh (D136): opening the pipe read-write never blocks, so no write waits in open(2) for a reader
# that has died. The caller checks the server is up first, because a write still blocks on a full pipe, which only a server
# that stopped reading can leave. The descriptor stays open until this process exits, so the line outlives a reader that has
# not opened the pipe yet.
send_console() { [ -p "$FIFO" ] && { exec 3<>"$FIFO"; printf '%s\n' "$1" >&3; }; }

# Same reply capture as probe_worldgen.sh: console replies are logged as [minecraft/MinecraftServer]. That logger also
# carries lag warnings ("Can't keep up!", e.g. .run/server/console.probe.log line 816), chat (MinecraftServer.logChatMessage:
# "<name> text", or "[Not Secure] <name> text"), joins and leaves, and advancement broadcasts (vanilla lang
# multiplayer.player.joined/left, chat.type.advancement.*). replies drops those, so they neither end the wait nor print.
replies() {
  tail -n +"$(($1 + 1))" "$LOG" | grep 'minecraft/MinecraftServer\]: ' \
    | grep -Ev -e "Can't keep up!" -e '\]: (\[[^]]*\] )?<[^>]+> ' -e ' (joined|left) the game$' \
        -e ' has (made the advancement|completed the challenge|reached the goal) ' \
    | sed 's/.*MinecraftServer\]: //'
}

do_cmd() {
  is_up && [ -p "$FIFO" ] && [ -f "$LOG" ] || { echo "no session: start one with tools/server_session.sh start"; exit 2; }
  local before out opened
  server_ours || reused_hint
  # A forceload sent to any other world would stay in it (D136). start stops such a server; this covers the time until it has.
  opened="$(opened_world)"
  if [ -n "$opened" ] && [ "$opened" != "$(pid_of world)" ]; then
    echo "no session: the server opened world $opened, not $(pid_of world); nothing sent"; exit 2
  fi
  before=$(wc -l < "$LOG")
  send_console "$1"
  for _ in $(seq 1 "$2"); do
    sleep 1
    [ -n "$(replies "$before")" ] && break
  done
  sleep 1
  out="$(replies "$before")"
  [ -n "$out" ] || { echo "(no reply within $2 s; see $LOG)"; exit 1; }
  printf '%s\n' "$out"
}

do_wait() {
  for i in $(seq 1 600); do
    is_ready && { echo "session: up (world $(pid_of world))"; exit 0; }
    if ! is_up && ! is_starting && [ "$i" -gt 5 ]; then echo "session: down"; exit 1; fi
    sleep 1
  done
  echo "session: still booting after 600 s (see $LOG)"; exit 1
}

do_status() {
  if is_up; then server_ours || reused_hint; echo "session: up (world $(pid_of world), console log $LOG)"; exit 0; fi
  if is_starting; then echo "session: starting (syncing the pack)"; exit 1; fi
  echo "session: down"; exit 1
}

# The test world must hold no forced chunks (D136): server_boot.sh fails on any. A session only ever opens its own world, so
# this is the proof, not the protection. It reads server.properties, so it runs after the restore.
check_test_world() {
  python3 "$ROOT/tools/count_forced_chunks.py" "$RUN" \
    || { echo "FORCED CHUNKS: the test world did not read clean (tools/count_forced_chunks.py above); server_boot.sh will fail"; return 1; }
}

# A PID from an old session file may belong to something else by now (a reboot), so only signal what still looks like ours.
kill_ours() { [ -n "$2" ] && ps -o command= -p "$2" 2>/dev/null | grep -q "$1" && kill "$2" 2>/dev/null; }

# After a start process that never ran its trap (kill -9, a power loss).
clear_leftovers() {
  kill_ours 'sleep 100000' "$(pid_of hold)"
  kill_ours 'packwiz' "$(pid_of serve)"
  if [ -f "$BACKUP" ]; then mv "$BACKUP" "$PROPS"; echo "restored server.properties from an earlier session's backup"; fi
  rm -f "$FIFO" "$PIDS"
}

do_stop() {
  local rc=0 p h java
  if is_starting; then
    if ! kill_ours server_session "$(pid_of start)"; then
      echo "session: pid $(pid_of start) in $PIDS is not a session start, so it is probably a reused PID; not signalling it"
      clear_leftovers; check_test_world || rc=1
      echo "session: not running"; exit "$rc"
    fi
    for _ in $(seq 1 120); do [ -f "$PIDS" ] || break; sleep 1; done
    if [ -f "$PIDS" ]; then echo "session: still stopping after 120 s (pid $(pid_of start))"; exit 1; fi
    echo "session: stopped while starting"; exit 0
  fi
  if is_up && ! server_ours; then reused_hint; p=reused; fi
  if ! is_up || [ "${p:-}" = reused ]; then
    if [ -f "$PIDS" ] || [ -f "$BACKUP" ]; then clear_leftovers; check_test_world || rc=1; fi
    echo "session: not running"; exit "$rc"
  fi
  p="$(pid_of server)" h="$(pid_of hold)"
  java="$(pgrep -P "$p" | head -1)"
  # With the holder gone the server's stdin is at EOF, so its console thread has ended and no `stop` can reach it.
  if [ -n "$h" ] && ! alive "$h"; then
    echo "the console holder (pid $h) is dead, so stop cannot reach the server. kill ${java:-$p} still saves the world (its shutdown hook); then run tools/server_session.sh stop again"
    exit 1
  fi
  echo 'stopping=1' >> "$PIDS"
  send_console stop
  # After `stop` the JVM can linger about 60 s on an idle pool thread once the world is saved (D136 finding b).
  for _ in $(seq 1 120); do alive "$p" || break; sleep 1; done
  alive "$p" && { echo "the server (pid $p) is still running after 120 s; run stop again, or kill ${java:-$p}, which still saves the world"; exit 1; }
  for _ in $(seq 1 30); do [ -f "$PIDS" ] || break; alive "$(pid_of start)" || break; sleep 1; done
  # the start process is gone, so its trap never ran: clean up here
  if [ -f "$PIDS" ] && ! alive "$(pid_of start)"; then clear_leftovers; fi
  check_test_world || rc=1
  echo "session: stopped"
  exit "$rc"
}

# Keep a failed start's evidence, as server_boot.sh does (D134): the next boot deletes or rewrites all of it.
archive_failed_boot() {
  (
    cd "$RUN" || exit 0
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"
    archive="$ROOT/.run/failed-boots/$stamp"
    n=0 missing=""
    while [ -e "$archive" ]; do n=$((n + 1)); archive="$ROOT/.run/failed-boots/$stamp-$n"; done
    if ! mkdir -p "$archive" 2>/dev/null; then echo "failed-boot archive: NOT CREATED ($archive)"; exit 0; fi
    for f in logs/latest.log logs/debug.log console.session.log logs/kubejs/startup.log logs/kubejs/server.log \
             kubejs/exported/recipes.json; do
      if [ -f "$f" ]; then
        { mkdir -p "$archive/$(dirname "$f")" && cp -p "$f" "$archive/$f"; } || echo "  (could not archive $f)"
      else
        missing="$missing $f"
      fi
    done
    printf '%s\n' "$RUN" > "$archive/SOURCE" || true
    echo "failed-boot archive: $archive"
    if [ -n "$missing" ]; then echo "  (not present, not archived:$missing)"; fi
  )
}

cleanup() {
  local status=$? java_pid
  trap - EXIT
  trap '' INT TERM HUP   # a second signal must not skip the restore
  if alive "$SERVER_PID"; then
    java_pid="$(pgrep -P "$SERVER_PID")"
    send_console stop
    for _ in $(seq 1 "$STOP_WAIT"); do alive "$SERVER_PID" || break; sleep 1; done
    if alive "$SERVER_PID"; then
      kill $java_pid "$SERVER_PID" 2>/dev/null
      for _ in $(seq 1 "$STOP_WAIT"); do alive "$java_pid" || break; sleep 1; done
      if alive "$java_pid"; then kill -9 $java_pid 2>/dev/null; echo "SERVER DID NOT STOP (SIGKILL)"; status=1; FAILED=1; fi
    fi
  fi
  [ "$FAILED" = 1 ] && archive_failed_boot
  for p in "$HOLD_PID" "$SERVE_PID"; do alive "$p" && kill "$p"; done
  [ -f "$BACKUP" ] && mv "$BACKUP" "$PROPS"
  rm -f "$FIFO" "$PIDS"
  echo "session: down (world $WORLD kept in $RUN/$WORLD; online-mode=$(sed -n 's/^online-mode=//p' "$PROPS"))"
  # Not on a sync that never got as far as the server: nothing can have touched the world.
  if [ -n "$SERVER_PID" ]; then check_test_world || status=1; fi
  exit "$status"
}

# Stop on what server_boot.sh's post-boot check calls a bad boot log: an unknown ERROR, the Moonlight generated packs (D134),
# the game rules or the guard line (D137). Everything these read is logged before Done.
check_started_server() {
  local rc=0
  grep -E 'confluence tf-gamerules guard OK|confluence gamerules:' logs/latest.log 2>/dev/null | cut -c1-220
  python3 "$ROOT/tools/check_boot_log.py" "$RUN" || rc=$?
  case "$rc" in
    0) return 0 ;;
    2) echo "BOOT LOG CHECK USAGE ERROR" ;;
    3) echo "BAD ALLOWLIST" ;;
    4) echo "BAD GAMERULES PIN" ;;
    *) echo "BOOT LOG ERRORS" ;;
  esac
  return 1
}

do_start() {
  WORLD=probe_v03 OFFLINE=0 SERVER_PID='' HOLD_PID='' SERVE_PID='' FAILED=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --offline) OFFLINE=1; shift ;;
      --world) [ $# -ge 2 ] || usage; WORLD="$2"; shift 2 ;;
      *) usage ;;
    esac
  done
  # A plain name only, and any case of "world": macOS folders ignore case, so WORLD and ./world are the same folder.
  case "$WORLD" in
    ''|*[!A-Za-z0-9_-]*) echo "refusing --world '$WORLD': use letters, digits, _ and - only"; exit 2 ;;
  esac
  if [ "$(printf '%s' "$WORLD" | tr '[:upper:]' '[:lower:]')" = world ]; then
    echo "refusing --world $WORLD: that is server_boot.sh's world"; exit 2
  fi
  # Only a world: `--world mods` would have the server write into a server folder. session.lock alone is a world whose first
  # boot failed: the server takes the lock before it loads datapacks, so a start must still be able to run on it.
  if [ -e "$RUN/$WORLD" ] && [ ! -f "$RUN/$WORLD/level.dat" ] && [ ! -f "$RUN/$WORLD/session.lock" ]; then
    echo "refusing --world $WORLD: $RUN/$WORLD exists and holds no level.dat or session.lock, so it is not a world"; exit 2
  fi
  [ -x "$RUN/run.sh" ] && [ -f "$PROPS" ] || { echo "no server in $RUN: run tools/server_boot.sh once first"; exit 2; }
  if is_up || is_starting || pgrep -f "$SERVER_PATTERN" > /dev/null; then
    echo "a Minecraft server is already running (pgrep -fl unix_args.txt)"
    if is_up && ! server_ours; then reused_hint; fi
    exit 2
  fi
  clear_leftovers
  if pgrep -f "$SERVE_PATTERN" > /dev/null; then echo "packwiz serve is already running (pgrep -fl 'packwiz serve')"; exit 2; fi
  printf 'start=%s\nworld=%s\n' "$$" "$WORLD" > "$PIDS"
  trap cleanup EXIT
  trap 'exit 130' INT TERM HUP
  export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 21)}"; export PATH="$JAVA_HOME/bin:$HOME/go/bin:$PATH"

  # Same sync as server_boot.sh. packwiz serve stays up so a client instance can sync from it too.
  cd "$ROOT" || exit 1
  packwiz serve -p 8087 > "$RUN/packwiz-serve.session.log" 2>&1 &
  SERVE_PID=$!
  printf 'serve=%s\n' "$SERVE_PID" >> "$PIDS"
  sleep "$SETTLE"
  cd "$RUN" || exit 1
  { curl -fsSL -o packwiz-installer-bootstrap.jar https://github.com/packwiz/packwiz-installer-bootstrap/releases/download/v0.0.3/packwiz-installer-bootstrap.jar \
      && java -jar packwiz-installer-bootstrap.jar -g -s server http://localhost:8087/pack.toml; } > "$RUN/packwiz-sync.session.log" 2>&1 \
    || { echo "pack sync failed (see $RUN/packwiz-sync.session.log)"; exit 1; }
  cp "$PROPS" "$BACKUP" || { echo "could not back up server.properties"; exit 1; }
  awk -v world="$WORLD" -v offline="$OFFLINE" '
    /^level-name=/ { print "level-name=" world; next }
    /^online-mode=/ && offline == 1 { print "online-mode=false"; next }
    { print }' "$BACKUP" > "$PROPS"
  # A missing key would leave the server on its default world, `world`.
  grep -qx "level-name=$WORLD" "$PROPS" || { echo "server.properties has no level-name line to set"; exit 1; }
  if [ "$OFFLINE" = 1 ]; then grep -qx 'online-mode=false' "$PROPS" || { echo "server.properties has no online-mode line to set"; exit 1; }; fi
  mkfifo "$FIFO"
  # The console pipe's holder has it open read-write (D136), so the pipe always has a reader and a writer, and it is its own
  # process so that the server's console survives a kill -9 of this one.
  sleep 100000 3<>"$FIFO" > /dev/null 2>&1 &
  HOLD_PID=$!
  rm -f logs/latest.log logs/kubejs/*.log   # as server_boot.sh: the checks must read this boot's logs
  : > "$LOG"
  ./run.sh nogui < "$FIFO" > "$LOG" 2>&1 &
  SERVER_PID=$!
  FAILED=1   # until the checks pass
  printf 'server=%s\nhold=%s\n' "$SERVER_PID" "$HOLD_PID" >> "$PIDS"
  for _ in $(seq 1 120); do
    grep -q 'Done (' "$LOG" 2> /dev/null && break
    alive "$SERVER_PID" || break
    sleep "$POLL"
  done
  grep -q 'Done (' "$LOG" || { echo "BOOT FAILED (see $LOG)"; exit 1; }
  [ "$(opened_world)" = "$WORLD" ] || { echo "the server did not open world $WORLD (no 'Preparing level \"$WORLD\"' in $LOG); stopping"; exit 1; }
  # FTB Quests loads the quest files about 1 s after Done, as in server_boot.sh.
  for _ in $(seq 1 20); do grep -q '\[FTB Quests/\]: Loaded' "$LOG" 2> /dev/null && break; sleep 1; done
  grep '\[FTB Quests/\]: Loaded' "$LOG" || echo "WARN: no FTB Quests 'Loaded' line within the grace period"
  check_started_server || { echo "stopping: the session did not start clean"; exit 1; }
  FAILED=0
  echo 'ready=1' >> "$PIDS"
  echo "SESSION UP world=$WORLD online-mode=$(sed -n 's/^online-mode=//p' "$PROPS") port=$(sed -n 's/^server-port=//p' "$PROPS") lan=$(ipconfig getifaddr en0 2> /dev/null || echo none) pack=http://localhost:8087/pack.toml"
  wait "$SERVER_PID"
  echo "the server has exited"
  # A server that dies by itself mid-session: its logs are as much a finding as a failed start's.
  if [ -z "$(pid_of stopping)" ]; then echo "the server exited without a stop from this script"; FAILED=1; exit 1; fi
}

case "${1:-}" in
  start) shift; do_start "$@" ;;
  wait) do_wait ;;
  cmd) [ $# -ge 2 ] || usage; do_cmd "$2" "${3:-30}" ;;
  status) do_status ;;
  stop) do_stop ;;
  *) usage ;;
esac
