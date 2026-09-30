// Runs kubejs/server_scripts/lib/ids.js and worldgen.js in one node vm context, the way KubeJS 2101 runs every server script
// in one shared scope (ids.js is priority 1, so it loads first), with stubs for the three KubeJS globals worldgen.js touches:
// ServerEvents.generateData (records the handler), JsonIO.toObject (a JSON round trip) and console.log. It then calls each
// recorded handler with a stub `pack` whose json(id, obj) records the file, and prints
// {"phases": [...], "log": [...], "files": {"<namespace:path>": <json>}} on stdout for tools/tests/test_worldgen.py.
// Usage: node tools/tests/worldgen_harness.js <path to kubejs/>
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const kubejs = process.argv[2]
const handlers = []
const log = []
const context = vm.createContext({
  ServerEvents: { generateData: (phase, fn) => handlers.push({ phase: phase, fn: fn }) },
  JsonIO: { toObject: o => JSON.parse(JSON.stringify(o)) },
  console: { log: s => log.push(String(s)) },
})
for (const rel of ['server_scripts/lib/ids.js', 'server_scripts/worldgen.js']) {
  vm.runInContext(fs.readFileSync(path.join(kubejs, rel), 'utf8'), context, { filename: rel })
}
const files = {}
handlers.forEach(h => h.fn({ json: (id, obj) => { files[id] = obj } }))
process.stdout.write(JSON.stringify({ phases: handlers.map(h => h.phase), log: log, files: files }))
