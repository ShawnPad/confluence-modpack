#!/usr/bin/env bash
# Stand-in for the java process under run.sh, for test_server_session_dry.py: a child of run.sh, as the real one is. The file
# `mode` in the server folder picks the behaviour, and golden/session-latest-log.txt (copied in as good.log) is its latest.log.
mode=$(cat mode)
lvl=$(sed -n 's/^level-name=//p' server.properties)
mkdir -p "$lvl/data" logs/kubejs kubejs/exported
touch "$lvl/marker" "$lvl/level.dat"
echo $$ > java.pid
: > logs/kubejs/server.log
: > logs/kubejs/startup.log
echo '[]' > kubejs/exported/recipes.json
case "$mode" in
  nodone) echo "Failed to start the minecraft server"; exit 1 ;;
  wrongworld) lvl=somewhere_else ;;
esac
case "$mode" in
  noguard) grep -v 'guard OK' good.log > logs/latest.log ;;
  nolog) ;;   # any latest.log still here is an older boot's
  *) cp good.log logs/latest.log ;;
esac
[ "$mode" = nostop ] && trap '' TERM   # outlives both the stop and the SIGTERM: only SIGKILL ends it
echo "[Server thread/INFO] [minecraft/DedicatedServer]: Preparing level \"$lvl\""
echo '[Server thread/INFO] [minecraft/DedicatedServer]: Done (1.0s)! For help, type "help"'
echo '[Server thread/INFO] [FTB Quests/]: Loaded 14 chapters'
if [ "$mode" = crash ]; then sleep 1; echo "Exception ticking world"; exit 1; fi
while read -r line; do
  if [ "$line" = stop ]; then
    if [ "$mode" = nostop ]; then touch stop-seen; continue; fi
    echo "[Server thread/INFO] [minecraft/MinecraftServer]: Stopping the server"
    exit 0
  fi
  echo "[Server thread/INFO] [minecraft/MinecraftServer]: reply to $line"
done
while :; do sleep 1; done   # stdin at EOF: the real console thread ends and the server runs on
