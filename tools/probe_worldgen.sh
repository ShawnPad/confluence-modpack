#!/usr/bin/env bash
# Worldgen probe: sync the pack into .run/server, boot it, generate a fresh block of chunks in one
# dimension, count blocks (or block tags) inside a y band, print per-chunk densities, stop the server.
# The count is a `fill … replace` that turns matches into barrier, so a block counted once reads 0 on a
# second pass: pick an ungenerated centre (or a new block id) for every run. Exit 1 iff any count is 0, or the forceload it
# adds is not removed: it sends `forceload remove` for the same area before the stop, and its EXIT trap does so when it fails
# mid-run (tools/probe_lib.sh; v0.3 Task 11c, D136). Exit 2 for a usage error, which includes a radius over 8.
#
#   tools/probe_worldgen.sh -d twilightforest:twilight_forest -y -32,10 [-c 0,0] [-r 8] \
#       allthemodium:allthemodium_ore '#minecraft:coal_ores'
#
# -d dimension id   -y ymin,ymax   -c centre chunk (default 0,0)   -r chunk radius, 1 to 8 (default 8 → 16×16 chunks,
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
# The area is (2r)^2 chunks, and forceload refuses one over 256 ("Too many chunks", ForceLoadCommand.changeForceLoad offsets
# 108-153 in neoforge-21.1.250-server.jar): the counts would then cover chunks nothing keeps loaded. Refuse it before the boot.
case "$RADIUS" in [1-8]) ;; *) echo "-r $RADIUS: forceload takes 1 to 256 chunks: -r 1 to 8 ((2r)^2 chunks)" >&2; exit 2 ;; esac
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

. "$ROOT/tools/probe_lib.sh"           # start_server, cmd, release and the EXIT trap (v0.3 Task 11c, D136)
start_server "$RUN/console.probe.log"
in_dim() { cmd "execute in $DIM run $1" "${2:-60}"; }

for i in $(seq 1 60); do grep -q 'Done (' "$LOG" 2>/dev/null && break; sleep 5; done
grep -q 'Done (' "$LOG" || { echo "BOOT FAILED (see $LOG)"; exit 1; }

echo "probe: $DIM chunks [$((CX - RADIUS)),$((CZ - RADIUS))]..[$((CX + RADIUS - 1)),$((CZ + RADIUS - 1))] ($CHUNKS), y $YMIN..$YMAX"
FORCED="execute in $DIM run forceload remove $X1 $Z1 $X2 $Z2"   # before the add: a probe ended while it waits still removes it
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
release || FAIL=1
exit $FAIL
