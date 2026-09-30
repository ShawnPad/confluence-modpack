// Test harness (v0.3 Task 8). Loads KubeJS server scripts into ONE shared scope, as KubeJS 2101 does, with recording
// stand-ins for the KubeJS globals. A top-level const/let/class whose name clashes with any other top-level name is a
// SyntaxError here too. Two plain `function` declarations with the same name do NOT throw in a node vm context (the later one
// silently wins; checked on node v22.3.0), so this harness does not catch that case: plan Task 9's
// test_server_script_top_level_names_are_unique checks name uniqueness. The harness then fires every ServerEvents.recipes
// handler and every ServerEvents.tags('block') handler those scripts registered, and prints one JSON object on stdout:
//   { handlers: { recipes: n, blockTags: n }, removed: [id | '/regex/' | 'output:<id>' | 'filter:<json>'], custom: [{ id, json }],
//     blockTags: [{ tag, values }], errors: [string] }
// stdout carries that object and nothing else: the scripts' console (log, info, warn, error, debug) goes to stderr.
// Usage, from pack/:  node tools/tests/run_server_scripts.js kubejs/server_scripts/bypass.js [more scripts]
// Every kubejs/server_scripts/lib/*.js loads too (the scripts call IDS, tagId() and gate.*). Load order is KubeJS's own:
// the '// priority: N' header on the first line, higher first, then the path (lib/ids.js comment, ScriptFile.compareTo).
// Only the event members the tested scripts call are modelled: remove/custom/shaped/shapeless on the recipes event, and
// add/get(...).add on the tags event. Any other KubeJS global a script touches while loading is an inert stand-in.
// node runs V8, NOT the pack's Rhino (rhino-2101.2.7-build.85.jar under KubeJS 2101.7.2). A script that loads and runs here can
// still fail in KubeJS: for example Rhino throws `redeclaration of var` for a `const` directly inside a `try` block, which V8
// accepts (tools/tests/test_rhino_hazards.py lints that one case). So this harness pins what the scripts ask KubeJS to do, not
// that KubeJS accepts them; the load proof is the boot, tools/server_boot.sh (it fails on any KubeJS ERROR line and on
// "Parsing error loading recipe").
'use strict'
const fs = require('fs')
const path = require('path')
const util = require('util')
const vm = require('vm')

const ROOT = path.resolve(__dirname, '..', '..')
const out = { handlers: { recipes: 0, blockTags: 0 }, removed: [], custom: [], blockTags: [], errors: [] }
const handlers = { recipes: [], tags: {} }

// Callable and indexable, swallows everything: for globals a script only touches at load time. It also survives coercion:
// Symbol.toPrimitive yields a string, so '' + inert and `${inert}` do not throw, and `then` is undefined, so it is not
// mistaken for a promise.
const inert = new Proxy(function () {}, {
  get: (target, key) => (key === Symbol.toPrimitive ? () => '<inert>' : key === 'then' ? undefined : inert),
  apply: () => inert,
  construct: () => inert,
})
// The scripts' console writes to stderr, never stdout, so a script or handler that logs cannot corrupt the JSON on stdout
// (lib/loot.js calls console.error; dump.js, tagcheck.js and worldgen.js call console.log).
const toStderr = (...args) => { process.stderr.write(util.format(...args) + '\n') }
const scriptConsole = { log: toStderr, info: toStderr, warn: toStderr, error: toStderr, debug: toStderr }
const ServerEvents = new Proxy({
  recipes: fn => { handlers.recipes.push(fn) },
  tags: (registry, fn) => { (handlers.tags[registry] = handlers.tags[registry] || []).push(fn) },
}, { get: (target, key) => (key in target ? target[key] : inert) })
const sandbox = { console: scriptConsole, ServerEvents }
for (const name of ['StartupEvents', 'ClientEvents', 'BlockEvents', 'ItemEvents', 'EntityEvents', 'PlayerEvents', 'LevelEvents',
  'NetworkEvents', 'NativeEvents', 'LootJS', 'Java', 'JsonIO', 'Utils', 'Item', 'Ingredient', 'Text', 'Component']) sandbox[name] = inert
vm.createContext(sandbox)

// Realm-safe: a RegExp literal in a script is created in the vm context, so `instanceof RegExp` would be false here.
const isRegExp = v => Object.prototype.toString.call(v) === '[object RegExp]'
const flat = args => args.reduce((acc, a) => acc.concat(Array.isArray(a) ? flat(a) : [a]), [])
const load = rel => {
  try { vm.runInContext(fs.readFileSync(path.join(ROOT, rel), 'utf8'), sandbox, { filename: rel }) }
  catch (e) { out.errors.push(rel + ': ' + e) }
}
const LIB = 'kubejs/server_scripts/lib'
const files = fs.readdirSync(path.join(ROOT, LIB)).filter(f => f.endsWith('.js')).map(f => LIB + '/' + f)
process.argv.slice(2).forEach(f => { if (!files.includes(f)) files.push(f) })
const priority = rel => { const m = /^\s*\/\/ priority: (-?\d+)/.exec(fs.readFileSync(path.join(ROOT, rel), 'utf8')); return m ? Number(m[1]) : 0 }
files.sort((a, b) => priority(b) - priority(a) || (a < b ? -1 : a > b ? 1 : 0)).forEach(load)

// A removal filter is recorded by its exact shape: {id: 'string'} as the id, {id: /regex/} as '/regex/', {output: x} as
// 'output:<x>', and any other filter (another key, more than one key, a non-object) as 'filter:' + its JSON, with each RegExp
// written as its '/source/flags' string. So a filter the tests do not expect never passes as an id or an output.
const filterJson = f => JSON.stringify(f, (key, value) => (isRegExp(value) ? String(value) : value))
const recordRemoval = f => {
  const keys = f !== null && typeof f === 'object' && !isRegExp(f) ? Object.keys(f) : null
  const only = k => keys !== null && keys.length === 1 && keys[0] === k
  if (only('id') && typeof f.id === 'string') return f.id
  if (only('id') && isRegExp(f.id)) return String(f.id)
  if (only('output')) return 'output:' + f.output
  return 'filter:' + filterJson(f)
}
const recipeEvent = {
  remove: f => { out.removed.push(recordRemoval(f)) },
  custom: json => ({ id: id => { out.custom.push({ id: String(id), json: JSON.parse(JSON.stringify(json)) }) } }),
  shaped: () => ({ id: () => {} }),
  shapeless: () => ({ id: () => {} }),
}
const record = (tag, values) => { out.blockTags.push({ tag: String(tag), values: flat(values).map(String) }) }
const tagEvent = {
  add: (tag, ...values) => record(tag, values),
  get: tag => { const w = { add: (...v) => { record(tag, v); return w }, remove: () => w, removeAll: () => w }; return w },
  remove: () => {},
  removeAll: () => {},
}
out.handlers.recipes = handlers.recipes.length
out.handlers.blockTags = (handlers.tags.block || []).length
handlers.recipes.forEach(fn => { try { fn(recipeEvent) } catch (e) { out.errors.push('recipes handler: ' + e) } })
;(handlers.tags.block || []).forEach(fn => { try { fn(tagEvent) } catch (e) { out.errors.push('block tags handler: ' + e) } })
process.stdout.write(JSON.stringify(out))
