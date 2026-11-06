#!/usr/bin/env bash
# Loot probe: sync the pack into .run/server, boot it, roll one or more loot tables into a chest many times and
# count how often an item shows up, then stop the server. The only test that sees what LootJS actually did to
# a table (weights, cleared pools): `check_recipes.py` and the boot log cannot.
#
#   tools/probe_loot.sh [-n 300] twilightforest:stronghold_cache,allthemodium:allthemodium_upgrade_smithing_template,10,50 \
#                                allthemodium:arch,allthemodium:allthemodium_upgrade_smithing_template,0,0
#
# Each spec is table,item,min,max: the item must appear in between min and max of the -n rolls (default 200)
# or the probe exits 1. One `loot insert` per roll into a chest at 0 300 0 in the Overworld, `data get` to
# read it, `data merge` to empty it; the three commands for every roll are queued at once and the log is parsed
# after the queue drains, so 300 rolls take seconds, not minutes. The chest's chunk is force-loaded for the run and released
# before the stop (`forceload remove 0 0`; its EXIT trap does it when the probe fails mid-run); a removal the server does not
# confirm fails the probe (tools/probe_lib.sh; v0.3 Task 11c, D136).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/.run/server"
ROLLS=200
while getopts 'n:' opt; do
  case $opt in n) ROLLS=$OPTARG;; *) exit 2;; esac
done
shift $((OPTIND - 1))
[ $# -ge 1 ] || { sed -n '2,12p' "$0"; exit 2; }
[ -x "$RUN/run.sh" ] || { echo "no server in $RUN: run tools/server_boot.sh once first"; exit 2; }
export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 21)}"; export PATH="$JAVA_HOME/bin:$HOME/go/bin:$PATH"

# Same sync as server_boot.sh / probe_worldgen.sh: kubejs/, config/ and the mod list in .run/server are packwiz copies.
cd "$ROOT"
packwiz serve -p 8087 >/dev/null 2>&1 &
SERVE_PID=$!
sleep 2
cd "$RUN"
java -jar packwiz-installer-bootstrap.jar -g -s server http://localhost:8087/pack.toml >/dev/null
kill "$SERVE_PID" || true

. "$ROOT/tools/probe_lib.sh"           # start_server, cmd, release and the EXIT trap (v0.3 Task 11c, D136)
start_server "$RUN/console.loot.log"

for i in $(seq 1 60); do grep -q 'Done (' "$LOG" 2>/dev/null && break; sleep 5; done
grep -q 'Done (' "$LOG" || { echo "BOOT FAILED (see $LOG)"; exit 1; }

POS="0 300 0"
FORCED="forceload remove 0 0"     # before the add: a probe ended while it waits still removes it
cmd "forceload add 0 0" | grep -E 'Marked|Unable|already' || true
cmd "setblock $POS minecraft:chest" >/dev/null
cmd "gamerule sendCommandFeedback true" >/dev/null

FAIL=0
for spec in "$@"; do
  IFS=, read -r TABLE ITEM MIN MAX <<<"$spec"
  MIN=${MIN:-1}; MAX=${MAX:-$ROLLS}
  START=$(wc -l < "$LOG")
  for i in $(seq 1 "$ROLLS"); do
    alive || break                  # a server that is gone reads nothing: 300 rolls would fill the pipe, and a write block
    printf 'loot insert %s loot %s\ndata get block %s Items\ndata merge block %s {Items:[]}\n' "$POS" "$TABLE" "$POS" "$POS" >&3
  done
  # The queue is drained when every `data merge` has been answered ("Modified block data", or "Nothing changed" when
  # the chest was already empty because the table rolled nothing).
  answered() { tail -n +"$((START + 1))" "$LOG" | grep -cE 'Modified block data of|Nothing changed' || true; }
  for i in $(seq 1 300); do
    [ "$(answered)" -ge "$ROLLS" ] && break
    alive || break
    sleep 1
  done
  n=$(answered)
  [ "$n" -ge "$ROLLS" ] || { echo "$TABLE: only $n of $ROLLS rolls were answered (see $LOG)"; FAIL=1; continue; }
  HITS=$(tail -n +"$((START + 1))" "$LOG" | grep 'has the following block data' | grep -c "\"$ITEM\"" || true)
  EMPTY=$(tail -n +"$((START + 1))" "$LOG" | grep -c 'has the following block data: \[\]' || true)
  UNKNOWN=$(tail -n +"$((START + 1))" "$LOG" | grep -c -iE 'Unknown loot table|Incorrect argument|Unknown or incomplete command' || true)
  [ "$UNKNOWN" -eq 0 ] || { echo "$TABLE: $UNKNOWN command errors (see $LOG)"; FAIL=1; }
  printf '%-40s %-55s %4d / %d rolls (%5.1f%%), %d empty chests, expected %d..%d\n' "$TABLE" "$ITEM" "$HITS" "$ROLLS" "$(echo "100 * $HITS / $ROLLS" | bc -l)" "$EMPTY" "$MIN" "$MAX"
  { [ "$HITS" -ge "$MIN" ] && [ "$HITS" -le "$MAX" ]; } || FAIL=1
done
release || FAIL=1
exit $FAIL
