#!/usr/bin/env bash
# Headless boot of the pack in .run/server. Exit 0 iff the server reached "Done" with no KubeJS errors.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NEO=21.1.250
RUN="$ROOT/.run/server"
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
# run.sh is a plain wrapper (no exec): kill the java child too, then wait for it to exit.
JAVA_PID="$(pgrep -P "$SERVER_PID" || true)"
kill $JAVA_PID "$SERVER_PID" 2>/dev/null || true
for i in $(seq 1 60); do [ -n "$JAVA_PID" ] && kill -0 $JAVA_PID 2>/dev/null || break; sleep 1; done
sleep 3
grep -E 'Done \(|Failed to load datapacks|Failed to start the minecraft server|Missing or unsupported mandatory|Requested by' console.log || true
if ! grep -q 'Done (' console.log; then echo "BOOT FAILED"; exit 1; fi
if grep -q -E '^\[.*ERROR' logs/kubejs/startup.log logs/kubejs/server.log 2>/dev/null; then echo "KUBEJS ERRORS"; grep -E 'ERROR' logs/kubejs/*.log | head -40; exit 1; fi
echo "BOOT OK"
