# Sourced by tools/probe_worldgen.sh and tools/probe_loot.sh (v0.3 Task 11c, D136): boot .run/server on a console pipe, send
# it commands, release the forceload the probe added, and stop it on the way out.
#
# The probe holds the console pipe itself, open for reading and writing (`exec 3<>`), and sends every command on fd 3. That
# open never blocks, and the pipe always has a reader, so no write waits in open(2). The old holder (`sleep 100000 > FIFO &`)
# was a writer only: once the server died, the next `printf > FIFO` blocked in open(2) for want of a reader, forever (Task 11c
# review, M4). A write still blocks while the pipe's buffer is full (8,192 bytes on macOS, measured), and only a server that
# has stopped reading leaves it full, so nothing is sent unless the server still runs (alive).
#
# A forceload is saved in the world and re-added at every boot, and a stop that arrives while those chunks load waits for all
# of them: the 5,121 chunks the two probes had left made tools/server_boot.sh's stop take 25-199 s (SERVER DID NOT STOP), and
# its forced-chunk guard now fails any boot that finds one. So a probe sets FORCED to the command that removes its forceload
# before it sends the add, and release sends it before the stop: on the normal path, and in the EXIT trap when the probe ends
# early (set -e, a signal).

# start_server LOG: start run.sh (in the working directory) on the console pipe, its output to LOG, and set the EXIT trap.
start_server() {
  LOG=$1 FORCED=""
  FIFO="$(mktemp -u "${TMPDIR:-/tmp}/probe_in.XXXXXX")"
  mkfifo "$FIFO"
  exec 3<>"$FIFO"
  ./run.sh nogui < "$FIFO" > "$LOG" 2>&1 3>&- &
  SERVER_PID=$!
  trap cleanup EXIT
}

alive() { pgrep -P "$SERVER_PID" >/dev/null 2>&1; }   # run.sh's java child

# Send one console command and print the server's reply line(s) (logged as [minecraft/MinecraftServer]), waiting up to $2
# seconds (default 60) for the first. To a server that is gone it sends nothing: it says so on stderr and returns 1.
cmd() {
  local before i
  alive || { echo "the server is gone; not sent: $1" >&2; return 1; }
  before=$(wc -l < "$LOG")
  printf '%s\n' "$1" >&3
  for i in $(seq 1 "${2:-60}"); do
    sleep 1
    tail -n +"$((before + 1))" "$LOG" | grep -q 'minecraft/MinecraftServer\]: ' && break
    alive || break
  done
  tail -n +"$((before + 1))" "$LOG" | grep 'minecraft/MinecraftServer\]: ' | sed 's/.*MinecraftServer\]: //'
}

# Send $FORCED once, and clear it. Only an "Unmarked" reply (commands.forceload.removed.single/.multiple) counts: any other
# forceload reply, none within 60 s, or a server that is gone prints FORCELOAD NOT RELEASED, on stderr (a trap can run inside
# `cmd ... >/dev/null`), and returns 1. It waits for the forceload reply itself, not the first reply line, which a queued
# command could have sent.
release() {
  [ -n "$FORCED" ] || return 0
  local undo="$FORCED" before reply="" i
  FORCED=""
  if alive; then
    before=$(wc -l < "$LOG")
    printf '%s\n' "$undo" >&3
    for i in $(seq 1 60); do
      reply=$(tail -n +"$((before + 1))" "$LOG" \
              | grep -E 'MinecraftServer\]: (Unmarked|No chunks were removed|Too many chunks)' \
              | sed 's/.*MinecraftServer\]: //' | head -1 || true)
      [ -n "$reply" ] && break
      alive || break
      sleep 1
    done
  fi
  case "$reply" in Unmarked*) echo "$reply"; return 0 ;; esac
  [ -n "$reply" ] || alive || reply="the server is gone"
  echo "FORCELOAD NOT RELEASED ($undo): ${reply:-no forceload reply within 60 s}" >&2
  return 1
}

# The EXIT trap. A forceload still set here means the probe ended early, so it is failing already: release's own status is
# not needed (and could not change a signal's, which bash 3.2 keeps whatever the trap does).
cleanup() {
  local i
  release || true
  if alive; then printf 'stop\n' >&3 || true; fi
  for i in $(seq 1 60); do alive || break; sleep 1; done
  JAVA_PID="$(pgrep -P "$SERVER_PID" || true)"; kill $JAVA_PID "$SERVER_PID" 2>/dev/null || true
  exec 3>&-
  rm -f "$FIFO"
}
