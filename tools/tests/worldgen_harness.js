// Runs kubejs/server_scripts/lib/ids.js and worldgen.js in one node vm context, the way KubeJS 2101 runs every server script
// in one shared scope (ids.js is priority 1, so it loads first), with stubs for the KubeJS globals worldgen.js touches:
// ServerEvents.generateData (records the handler), JsonIO.toObject (a JSON round trip) and console (log, plus info / warn /
// error, recorded with a level prefix). It then calls each recorded handler with a stub `pack` whose json(id, obj) records
// the file, and prints {"phases": [...], "log": [...], "files": {"<namespace:path>": <json>}} on stdout for
// tools/tests/test_worldgen.py. A script that throws exits non-zero with the error on stderr.
// Scope: this is node's V8, not the pack's Rhino (rhino-2101.2.7-build.85.jar under KubeJS 2101.7.2), and it loads only
// ids.js and worldgen.js. It checks the JSON the rows emit, not that the file loads in KubeJS. V8 accepts things Rhino
// rejects: a `const` declared directly inside `try` runs here but throws "redeclaration of var" on Rhino 2101.2.7
// (tools/tests/test_rhino_hazards.py lints for that one). The load proof is tools/server_boot.sh, which fails on any
// ERROR line in logs/kubejs/{startup,server}.log.
// Usage: node tools/tests/worldgen_harness.js <path to kubejs/>
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const kubejs = process.argv[2]
if (!kubejs || !fs.existsSync(path.join(kubejs, 'server_scripts', 'worldgen.js'))) {
  process.stderr.write('usage: node tools/tests/worldgen_harness.js <path to kubejs/> (got ' + kubejs +
    ': no server_scripts/worldgen.js)\n')
  process.exit(2)
}
const handlers = []
const log = []
const context = vm.createContext({
  ServerEvents: { generateData: (phase, fn) => handlers.push({ phase: phase, fn: fn }) },
  JsonIO: { toObject: o => JSON.parse(JSON.stringify(o)) },
  console: {
    log: s => log.push(String(s)),
    info: s => log.push('info: ' + s),
    warn: s => log.push('warn: ' + s),
    error: s => log.push('error: ' + s),
  },
})
for (const rel of ['server_scripts/lib/ids.js', 'server_scripts/worldgen.js']) {
  vm.runInContext(fs.readFileSync(path.join(kubejs, rel), 'utf8'), context, { filename: rel })
}
const files = {}
handlers.forEach(h => h.fn({ json: (id, obj) => { files[id] = obj } }))
process.stdout.write(JSON.stringify({ phases: handlers.map(h => h.phase), log: log, files: files }))
