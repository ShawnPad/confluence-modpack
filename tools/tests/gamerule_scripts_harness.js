// Runs the real kubejs/startup_scripts/tf_gamerules_guard.js or kubejs/server_scripts/gamerules.js in node vm contexts, with stubs
// for what they touch, and prints what they did as JSON on stdout for tools/tests/test_gamerules_jars.py (v0.3 Task 11d, D137).
// run_server_scripts.js does not fit: it reads server scripts only, has no Java.loadClass or `global`, and its ServerEvents.loaded
// is an inert stand-in that never fires.
// Scope: this is node's V8, not the pack's Rhino, and the stubs model only the calls the scripts make. It tests the scripts'
// logic. The load proof is tools/server_boot.sh, and how a real Java field read fails is the clone boot neg-c (D137).
//
// Usage: node tools/tests/gamerule_scripts_harness.js guard|detector <path to kubejs/>, with one JSON scenario on stdin.
//
// guard scenario:
//   { rules: [name],                    the rules registered when the first run starts (GameRules.GAME_RULE_TYPES)
//     suppliers: { FIELD: supplier },   TFGameRules' static fields; a field not named here is missing
//     runs: [ { suppliers, addRules, removeRules } ] }
// Each run is one execution of the script in a new vm context, as ScriptManager.reload makes, in one simulated JVM: the rules, the
// `global` map and each supplier's memoized state carry over. A run first applies its own changes: `suppliers` replaces the fields
// it names, and addRules and removeRules edit the registered rules.
// A supplier is { id, registers } (get() returns a key with that id and, on its first call only, as Suppliers.memoize does, adds
// the id to the rules when `registers` is true), { null: true } (the field is null) or { throws: true } (reading the field throws).
// stdout: { runs: [ { threw: message or null, logs: [{ level, text }], record: global's entry or null, rules: [name] sorted } ] }
//
// detector scenario: { server: [name], registry: [name] }, the keys the server's GameRules and a new GameRules() list, in that
// order. stdout: { handlers: how many ServerEvents.loaded handlers registered, logs: [{ level, text }] }, after firing each.
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const RECORD_KEY = 'confluence:tf_gamerules_guard'
const [mode, kubejs] = process.argv.slice(2)
const SCRIPTS = { guard: 'startup_scripts/tf_gamerules_guard.js', detector: 'server_scripts/gamerules.js' }
if (!SCRIPTS[mode] || !kubejs || !fs.existsSync(path.join(kubejs, SCRIPTS[mode]))) {
  process.stderr.write('usage: node tools/tests/gamerule_scripts_harness.js guard|detector <path to kubejs/> (got ' + mode + ', ' +
    kubejs + ')\n')
  process.exit(2)
}
const source = fs.readFileSync(path.join(kubejs, SCRIPTS[mode]), 'utf8')
const scenario = JSON.parse(fs.readFileSync(0, 'utf8'))

const recordingConsole = logs => {
  const out = {}
  for (const level of ['log', 'info', 'warn', 'error']) out[level] = s => { logs.push({ level: level, text: String(s) }) }
  return out
}
// new GameRules().createTag().getAllKeys() and MinecraftServer.getGameRules().createTag().getAllKeys().
const rulesObject = keys => ({ createTag: () => ({ getAllKeys: () => ({ forEach: fn => [...keys].forEach(k => fn(k)) }) }) })
const classLoader = classes => ({
  loadClass: name => {
    if (!(name in classes)) throw new Error('harness: the script loaded an unexpected class ' + name)
    return classes[name]
  },
})
const GAME_RULES = 'net.minecraft.world.level.GameRules'

function runGuard() {
  const rules = new Set(scenario.rules)
  const fields = {}
  const memoized = new Map()
  const setSuppliers = given => { Object.assign(fields, given) }
  const global = new Map()          // BuiltinKubeJSPlugin.GLOBAL, a java.util.HashMap: only these three calls
  const globalStub = { containsKey: k => global.has(k), put: (k, v) => { global.set(k, v) }, get: k => global.get(k) }
  const supplierOf = (field, spec) => ({
    get: () => {
      if (!memoized.has(field)) {
        if (spec.registers) rules.add(spec.id)
        memoized.set(field, { getId: () => spec.id })
      }
      return memoized.get(field)
    },
  })
  const TFGameRules = new Proxy({}, {
    get: (_, field) => {
      const spec = fields[field]
      if (spec === undefined) return undefined
      if (spec.throws) throw new Error('no such field ' + String(field))
      return spec.null ? null : supplierOf(field, spec)
    },
  })
  setSuppliers(scenario.suppliers)
  const results = scenario.runs.map(run => {
    setSuppliers(run.suppliers || {})
    ;(run.addRules || []).forEach(r => rules.add(r))
    ;(run.removeRules || []).forEach(r => rules.delete(r))
    const logs = []
    const GameRules = function () { Object.assign(this, rulesObject(rules)) }
    const context = vm.createContext({
      console: recordingConsole(logs),
      global: globalStub,
      Java: classLoader({ [GAME_RULES]: GameRules, 'twilightforest.init.TFGameRules': TFGameRules }),
    })
    let threw = null
    try {
      vm.runInContext(source, context, { filename: SCRIPTS.guard })
    } catch (e) {
      threw = String(e && e.message !== undefined ? e.message : e)
    }
    return { threw: threw, logs: logs, record: global.has(RECORD_KEY) ? global.get(RECORD_KEY) : null, rules: [...rules].sort() }
  })
  return { runs: results }
}

function runDetector() {
  const logs = []
  const handlers = []
  const GameRules = function () { Object.assign(this, rulesObject(scenario.registry)) }
  const context = vm.createContext({
    console: recordingConsole(logs),
    Java: classLoader({ [GAME_RULES]: GameRules }),
    ServerEvents: { loaded: fn => { handlers.push(fn) } },
  })
  vm.runInContext(source, context, { filename: SCRIPTS.detector })
  const event = { server: { getGameRules: () => rulesObject(scenario.server) } }
  handlers.forEach(fn => fn(event))
  return { handlers: handlers.length, logs: logs }
}

process.stdout.write(JSON.stringify(mode === 'guard' ? runGuard() : runDetector()))
