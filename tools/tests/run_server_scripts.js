// Test harness (v0.3 Task 8). Loads KubeJS server scripts into ONE shared scope, as KubeJS 2101 does, with recording
// stand-ins for the KubeJS globals. A top-level const/let/class whose name clashes with any other top-level name is a
// SyntaxError here too. Two plain `function` declarations with the same name do NOT throw in a node vm context (the later one
// silently wins; checked on node v22.3.0), so this harness does not catch that case: plan Task 9's
// test_server_script_top_level_names_are_unique checks name uniqueness. The harness then fires every ServerEvents.recipes
// handler and every ServerEvents.tags('block') handler those scripts registered, and prints one JSON object on stdout:
//   { handlers: { recipes: n, blockTags: n }, removed: [id | '/regex/' | 'output:<id>' | 'filter:<json>'], custom: [{ id, json }],
//     blockTags: [{ tag, op: 'add' | 'remove' | 'removeAll', values }], errors: [string] }
// stdout carries that object and nothing else: the scripts' console (log, info, warn, error, debug) goes to stderr.
// Usage, from pack/:  node tools/tests/run_server_scripts.js kubejs/server_scripts/bypass.js [more scripts]
// Every kubejs/server_scripts/lib/*.js loads too (the scripts call IDS, tagId() and gate.*). Load order is KubeJS's own; see
// `priority` below.
// Only these event members are modelled: remove/custom/shaped/shapeless on the recipes event, and add/remove/removeAll,
// called on the event or on the wrapper get(tag) returns, on the tags event (the edit members of
// kubejs-neoforge-2101.7.2-build.377.jar TagKubeEvent and TagWrapper, javap; removeAllTagsFrom, also an edit member, is not
// modelled). Calling any other member of either event throws a TypeError, which lands in `errors`. Any other KubeJS global a script touches while loading is an inert stand-in.
// Not recorded yet (plan Task 8b records both): shaped and shapeless recipes, and an event.custom(json) whose .id(...) is
// never called. A script that adds a recipe either way passes the node tests unseen; only the boot's recipe dump lists it.
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
// KubeJS's load order, mirrored (kubejs-neoforge-2101.7.2-build.377.jar, javap -c). ScriptFile.<init> reads every line of the
// file (Files.readAllLines). Each line is String.trim()med; one that starts with '//' has the rest, trimmed, matched against
// PROPERTY_PATTERN ^(\w+)\s*[:=]?\s*(-?\w+)$, and each match is appended to that property's list. getProperty returns the
// list's LAST value, and <init> sets priority = Integer.parseInt(getProperty('priority', '0')). ScriptFile.compareTo sorts
// priority descending, then ScriptFileInfo.locationPath (the path inside server_scripts/) by String.compareToIgnoreCase;
// lower-casing both sides matches that for the pack's ASCII paths.
const PROPERTY = /^(\w+)\s*[:=]?\s*(-?\w+)$/
const javaTrim = s => s.replace(/^[\u0000-\u0020]+|[\u0000-\u0020]+$/g, '')   // String.trim: code points <= U+0020 only
const priority = rel => {
  let value = '0'
  for (const raw of fs.readFileSync(path.join(ROOT, rel), 'utf8').split(/\r\n|\r|\n/)) {
    const line = javaTrim(raw)
    const m = line.startsWith('//') ? PROPERTY.exec(javaTrim(line.slice(2))) : null
    if (m && m[1] === 'priority') value = m[2]
  }
  if (/^-?\d+$/.test(value)) return Number(value)
  out.errors.push(rel + ': priority ' + value + ' is not an integer (KubeJS Integer.parseInt throws)')
  return 0
}
const locationPath = rel => rel.replace(/^kubejs\/server_scripts\//, '').toLowerCase()
const priorities = new Map(files.map(f => [f, priority(f)]))   // once per file, as ScriptFile.<init> does
const byLoadOrder = (a, b) => {
  const la = locationPath(a), lb = locationPath(b)
  return priorities.get(b) - priorities.get(a) || (la < lb ? -1 : la > lb ? 1 : 0)
}
files.sort(byLoadOrder).forEach(load)

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
// Every tag edit is recorded with its op, whether it is called on the event or on the wrapper get(tag) returns. As in KubeJS,
// the event's add/remove/removeAll return that wrapper, so a chained call is recorded too.
const record = (op, tag, values) => { out.blockTags.push({ tag: String(tag), op: op, values: flat(values).map(String) }) }
const wrapper = tag => {
  const w = {
    add: (...values) => { record('add', tag, values); return w },
    remove: (...values) => { record('remove', tag, values); return w },
    removeAll: () => { record('removeAll', tag, []); return w },
  }
  return w
}
const tagEvent = {
  get: tag => wrapper(tag),
  add: (tag, ...values) => wrapper(tag).add(...values),
  remove: (tag, ...values) => wrapper(tag).remove(...values),
  removeAll: tag => wrapper(tag).removeAll(),
}
out.handlers.recipes = handlers.recipes.length
out.handlers.blockTags = (handlers.tags.block || []).length
handlers.recipes.forEach(fn => { try { fn(recipeEvent) } catch (e) { out.errors.push('recipes handler: ' + e) } })
;(handlers.tags.block || []).forEach(fn => { try { fn(tagEvent) } catch (e) { out.errors.push('block tags handler: ' + e) } })
process.stdout.write(JSON.stringify(out))
