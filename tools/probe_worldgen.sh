#!/usr/bin/env bash
# Worldgen probe: sync the pack into .run/server, boot it, generate a fresh block of chunks in one
# dimension, count blocks (or block tags) inside a y band, print per-chunk densities, stop the server.
# The count is a `fill … replace` that turns matches into barrier, so a block counted once reads 0 on a
# second pass: pick an ungenerated centre (or a new block id) for every run. Exit 1 iff any count is 0.
#
#   tools/probe_worldgen.sh -d twilightforest:twilight_forest -y -32,10 [-c 0,0] [-r 8] \
#       allthemodium:allthemodium_ore '#minecraft:coal_ores'
#
# -d dimension id   -y ymin,ymax   -c centre chunk (default 0,0)   -r chunk radius (default 8 → 16×16 chunks,
# forceload's 256-chunk ceiling)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/.run/server"
DIM="" YBAND="" CENTRE="0,0" RADIUS=8
while getopts 'd:y:c:r:' opt; do
  case $opt in d) DIM=$OPTARG;; y) YBAND=$OPTARG;; c) CENTRE=$OPTARG;; r) RADIUS=$OPTARG;; *) exit 2;; esac
done
shift $((OPTIND - 1))
[ -n "$DIM" ] && [ -n "$YBAND" ] && [ $# -ge 1 ] || { sed -n '2,11p' "$0"; exit 2; }
[ -x "$RUN/run.sh" ] || { echo "no server in $RUN: run tools/server_boot.sh once first"; exit 2; }
YMIN=${YBAND%,*}; YMAX=${YBAND#*,}; CX=${CENTRE%,*}; CZ=${CENTRE#*,}
X1=$(( (CX - RADIUS) * 16 )); Z1=$(( (CZ - RADIUS) * 16 )); X2=$(( (CX + RADIUS) * 16 - 1 )); Z2=$(( (CZ + RADIUS) * 16 - 1 ))
CHUNKS=$(( 4 * RADIUS * RADIUS ))
export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 21)}"; export PATH="$JAVA_HOME/bin:$HOME/go/bin:$PATH"

# Same sync as server_boot.sh: kubejs/, config/ and the mod list in .run/server are packwiz copies.
cd "$ROOT"
packwiz serve -p 8087 >/dev/null 2>&1 &
SERVE_PID=$!
sleep 2
cd "$RUN"
java -jar packwiz-installer-bootstrap.jar -g -s server http://localhost:8087/pack.toml >/dev/null
kill "$SERVE_PID" || true

FIFO="$(mktemp -u "${TMPDIR:-/tmp}/probe_in.XXXXXX")"
mkfifo "$FIFO"
sleep 100000 > "$FIFO" &            # holds the pipe open; the server reads commands from it
HOLD_PID=$!
LOG="$RUN/console.probe.log"
./run.sh nogui < "$FIFO" > "$LOG" 2>&1 &
SERVER_PID=$!
cleanup() {
  printf 'stop\n' > "$FIFO" 2>/dev/null || true
  for i in $(seq 1 60); do pgrep -P "$SERVER_PID" >/dev/null 2>&1 || break; sleep 1; done
  JAVA_PID="$(pgrep -P "$SERVER_PID" || true)"; kill $JAVA_PID "$SERVER_PID" "$HOLD_PID" 2>/dev/null || true
  rm -f "$FIFO"
}
trap cleanup EXIT

# Send one console command and return the server's reply line(s) (logged as [minecraft/MinecraftServer]).
cmd() {
  local before; before=$(wc -l < "$LOG")
  printf '%s\n' "$1" > "$FIFO"
  for i in $(seq 1 "${2:-60}"); do
    sleep 1
    tail -n +"$((before + 1))" "$LOG" | grep -q 'minecraft/MinecraftServer\]: ' && break
  done
  tail -n +"$((before + 1))" "$LOG" | grep 'minecraft/MinecraftServer\]: ' | sed 's/.*MinecraftServer\]: //'
}
in_dim() { cmd "execute in $DIM run $1" "${2:-60}"; }

for i in $(seq 1 60); do grep -q 'Done (' "$LOG" 2>/dev/null && break; sleep 5; done
grep -q 'Done (' "$LOG" || { echo "BOOT FAILED (see $LOG)"; exit 1; }

echo "probe: $DIM chunks [$((CX - RADIUS)),$((CZ - RADIUS))]..[$((CX + RADIUS - 1)),$((CZ + RADIUS - 1))] ($CHUNKS), y $YMIN..$YMAX"
in_dim "forceload add $X1 $Z1 $X2 $Z2" | grep -E 'Marked|Unable' || true
# forceload keeps the block resident between counts; the first counting fill generates whatever is not loaded yet.
cmd "gamerule commandModificationBlockLimit 100000000" >/dev/null

FAIL=0
for id in "$@"; do
  r=$(in_dim "fill $X1 $YMIN $Z1 $X2 $YMAX $Z2 minecraft:barrier replace $id" 120)
  n=$(printf '%s' "$r" | grep -oE 'filled [0-9]+' | grep -oE '[0-9]+' || true)
  case "$r" in *"No blocks were filled"*) n=0;; esac
  [ -n "$n" ] || { echo "$id: unexpected reply: $r"; FAIL=1; continue; }
  printf '%-45s %8d blocks  %7.2f / chunk\n' "$id" "$n" "$(echo "$n / $CHUNKS" | bc -l)"
  [ "$n" -gt 0 ] || FAIL=1
done
exit $FAIL
