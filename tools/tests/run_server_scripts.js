// The shared KubeJS server-script runner for the recipe and tag tests (v0.3 Task 8; extended in Task 8b). It loads server
// scripts into ONE shared scope, as KubeJS 2101 does, with recording stand-ins for the KubeJS globals, fires every
// ServerEvents.recipes handler and every ServerEvents.tags(registry, fn) handler those scripts registered, and prints one JSON
// object on stdout. tools/tests/kjs.py's run() is the Python entry point; tools/tests/worldgen_harness.js (worldgen) and the
// harnesses inside test_other_gate*.py (native listeners) cover other events and stay separate.
//
// Usage, from pack/:
//   node tools/tests/run_server_scripts.js kubejs/server_scripts/bypass.js [more scripts]   every lib/*.js plus these
//   node tools/tests/run_server_scripts.js --all                                             every server script
// With CONFLUENCE_SCRIPTS_ROOT set, scripts are read from that directory instead of pack/kubejs/server_scripts (the mutation
// corpus, tools/tests/test_pin_mutations.py, points it at a mutated copy). The runner then says so on stderr, and `scriptsRoot`
// on stdout names the directory read. Script arguments are still written kubejs/server_scripts/<path>, and every `file` field
// and error string names a script that way, whichever root was read.
//
// stdout: one JSON object and nothing else. The scripts' console (log, info, warn, error, debug) goes to stderr.
// Keys from Task 8, whose meaning does not change (test_bypass_v03.py and Task 9 read them):
//   handlers   { recipes: n, blockTags: n, tags: { '<registry>': n } }   handler counts; `tags` is new in 8b, one entry per
//              registry, and blockTags equals tags['minecraft:block']
//   removed    [string]  one per event.remove(f): '<id>' for {id: 'string'}, '/regex/flags' for {id: /regex/}, 'output:<x>' for
//              {output: x} (a non-string x written as its JSON), and 'filter:<json>' for any other filter (another key, more
//              than one key, a non-object), with each RegExp in that JSON written as its '/source/flags' string. So a filter
//              the tests do not expect never passes as an id or an output.
//   custom     [{ id, json }]  one per .id(...) call on an event.custom(json) recipe, id as String(id); an id-less custom is
//              not listed here (see `customs`)
//   blockTags  [{ tag, op: 'add' | 'remove' | 'removeAll', values: [string] }]  every edit made by a minecraft:block tags handler
//   errors     [string]  one per script that failed to load and per handler that threw: '<file> load: <error>',
//              '<file> recipes handler <i>: <error>' or '<file> tags(<registry>) handler <i>: <error>', each followed by
//              ' [at kubejs/server_scripts/<path>:<line>]', the first stack frame inside a pack script, when there is one
// Keys added in Task 8b (additive only):
//   recipes    [{ kind: 'shaped' | 'shapeless', id, output, outputStack, pattern, key, ingredients, extra, file, handler,
//              chain }]  one per event.shaped(output, pattern, key) or event.shapeless(output, ingredients) call, recorded at
//              call time. `output` is the argument as given; `outputStack` is the stack KubeJS makes of a string output (read
//              as Item.of reads it, below: '2x ae2:drive' -> { id: 'ae2:drive', count: 2 }) and null for any other output (an
//              Item.of stack is already one). A string KubeJS cannot read records no row: see "The recipes event" below. `id`
//              is null until .id(x) is called on the returned recipe; `pattern`/`key` are null for shapeless and `ingredients`
//              null for shaped; `extra` holds any arguments past those; `chain` lists every other call made on the returned
//              recipe, as { member, args } (.damageIngredient, .keepIngredient, ...)
//   customs    [{ id, json, file, handler, chain }]  one per event.custom(json) call, recorded at call time; `id` stays null
//              when .id() is never called
//   filters    [{ filter, file, handler }]  one per event.remove(f), with the raw filter
//   other      [{ member, args, file, handler }]  one per call of any other recipes-event member (replaceInput,
//              forEachRecipe, smelting, recipes.<ns>.<type>, ...), recorded and not thrown. A dotted member is a call made
//              through a property: dump.js's event.addedRecipes.forEach(fn) records member 'addedRecipes.forEach'. Such a
//              call returns a recording stand-in, so a call chained on its result is recorded as well, as
//              '<member>().<next>' (event.findRecipes(f).forEach(fn) -> 'findRecipes', then 'findRecipes().forEach'). Each
//              function passed to such a call is called once, with a recording recipe probe as its only argument (see
//              `callbacks`), so what a callback does to a recipe is recorded too. A property set through such a member
//              (event.x.y = v) is recorded as { member: 'x.y', op: 'set', args: [v], ... }.
//   callbacks  [{ call, op: 'call' | 'set', member, args, file, handler }]  one per method call on (op 'call'), or property set
//              on (op 'set'), the probe a callback received, where `call` is the `other` member that received the callback
//              (dump.js: 'forEachRecipe' and 'addedRecipes.forEach'). `member` is dotted for a call through a property
//              (r.json.add(x) -> 'json.add'), and a call returns a recording stand-in, so a call chained on a call's result is
//              recorded too (r.get('result').setCount(64) -> 'get', then 'get().setCount'). A plain property read is not
//              recorded (it changes nothing). The probe coerces to '<recipe probe>'. A callback that throws adds an `errors`
//              entry '<file> recipes handler <i>: <call> callback: <error>'. One probe, one call: every read returns a
//              stand-in, so a branch on a value read from the recipe takes one side only, and an edit on the other side is not
//              seen (test_recipe_scripts.py lints dump.js's source against an allowlist of members for that reason).
//   tagEvents  [{ registry, tag, op, values, file, handler }]  every edit by every tags handler, for every registry
//   loaded     [file]  the scripts run, in load order
//   skipped    [{ file, reason }]  the scripts KubeJS would not load (see "Per-file properties")
//   scriptsRoot  the absolute directory the scripts were read from
// `file` is the script that registered the handler (not the lib/*.js helper that made the call; the error frame names that
// one). `handler` is the handler's index among all handlers of that event (recipes) or of that registry (tags), in the order
// KubeJS runs them: script load order, then registration order within a script.
//
// Every recorded value goes through one JSON replacer, so nothing is silently dropped: a RegExp becomes
// { RegExp: '/source/flags' } (tested with the realm-safe Object.prototype.toString, as a script's RegExp comes from the vm
// realm), undefined becomes '<undefined>', an inert stand-in '<inert>', a recipe returned by shaped/shapeless/custom
// '<recipe>', a function '<function>', a Map { Map: [[k, v], ...] }, a Set { Set: [...] }, a symbol its String(), a bigint
// '<n>n', NaN and the infinities '<NaN>' / '<Infinity>' / '<-Infinity>', and a value JSON cannot hold at all (a cycle)
// '<unserialisable: <error>>'. The one exception is `removed`'s 'filter:<json>', which keeps Task 8's '/source/flags' string.
//
// Modelled:
//   - Load order: KubeJS's own (kubejs-neoforge-2101.7.2-build.377.jar, javap -c). ScriptFile.<init> reads every line
//     (Files.readAllLines) and String.trim()s it. A trimmed line that is empty or starts with 'import ' is blanked (the
//     constant is 'import' plus a space, read from the class file's bytes, so ids.js's `importBus: ...` lines survive). A
//     trimmed line that starts with '//' has its rest, trimmed, matched against PROPERTY_PATTERN ^(\w+)\s*[:=]?\s*(-?\w+)$
//     (Matcher.find); each match's trimmed groups append a value to that property's list, and the line is blanked.
//     ScriptFile.load evaluates the blanked lines joined with '\n', and so does this runner. getProperty returns a
//     property's last value. priority = Integer.parseInt(getProperty('priority', '0')).
//     ScriptFile.compareTo sorts priority descending, then ScriptFileInfo.locationPath (the path inside server_scripts/) by
//     String.compareToIgnoreCase; lower-casing both sides matches that for ASCII paths.
//   - Per-file properties, from the same <init> and ScriptFile.skipLoading(). A priority Integer.parseInt rejects throws
//     NumberFormatException out of <init>; ScriptManager.loadFile catches it and logs an error, so the file does not load:
//     here it goes to `errors` and is not run. skipLoading returns, in order: "Ignored" when getProperty('ignored', 'false')
//     or getProperty('ignore', 'false') equals 'true'; "Client only" when a `requires: client` line is present (the server
//     is a dedicated server); "Pack mode mismatch" when getProperty('packmode', '') is non-empty and differs from
//     CommonProperties.packMode, which is kubejs/config/common.json's "packmode" (read from pack/kubejs/config/common.json if
//     the pack ships one, else '', KubeJS's default); and "Mod <id> is not loaded" for any other `requires` value. Each of
//     the first three is mirrored and listed in `skipped`, and skipLoading returns the first reason that applies, so a file
//     skipped for one of them never reaches the mod check. The mod list is not modelled: on a file none of the first three
//     skips, a `requires: <mod id>` line adds an error, and the file still runs, so a script that starts using it fails every
//     test until this runner learns the list.
//     No server script uses ignored, ignore, requires or packmode today (Task 8b checked).
//   - --all: ScriptManager.collectScripts walks the scripts directory with Files.walk(dir, 10, FOLLOW_LINKS) and takes every
//     .js file, and every .ts file but .d.ts. This walks to the same depth, follows links, and lists a .ts file in `errors`
//     (not modelled).
//   - Item.of(x), Item.of(x, n) return a stack { id, count } (plus `components` when the string has a patch): ItemWrapper.of(
//     ItemStack) returns its argument and ItemWrapper.of(ItemStack, int) a copy with count n (kubejs-neoforge-2101.7.2-build.377
//     .jar, as test_mek_tier5.py cited it). A string argument becomes an ItemStack through the ItemStack type wrapper,
//     ItemWrapper.wrap (BuiltinKubeJSPlugin.registerTypeWrappers, offsets 498-506: ItemStack.class with bootstrap method 60,
//     a lambda for ItemWrapper::wrap), and this runner reads it the same way (javap -c, Task 8b review), in readItemString:
//       wrapResult: trim; if the first ' ' is at index i >= 2 and the first 'x' is at i - 1, the count is
//         Integer.parseInt(s[0, i-1)) and the rest is s[i+1..]; else the count is 1. The final stack gets that count
//         (kjs$withCount), whatever the rest said.
//       parseString: '', '-', 'air' and 'minecraft:air' are the empty stack. read: skip whitespace; at the end or at '-' the
//         empty stack; a leading number (StringReader.readDouble, then Mth.ceil) must be followed by optional whitespace, 'x'
//         and optional whitespace, and be >= 1; then the id is ID.readGreedy (the longest run of ResourceLocation
//         characters [a-z0-9_:/.-]) read by ResourceLocation.read (no namespace, or an empty one before the ':', is
//         'minecraft'); then a '[' or '{' starts a components/NBT patch (DataComponentWrapper.readPatch), kept here as its
//         raw text in `components`. Anything after the id that is not a patch is ignored, as read() does.
//     The Java details, each compared with the JDK or the jar (Task 8b round 3; tools/tests/test_run_server_scripts.py pins
//     them): String.trim strips only chars <= U+0020, so a leading U+0001 goes and a leading U+2000 stays; read() then skips
//     Character.isWhitespace, which is true for U+2000 (and the other Unicode separators but the no-break spaces), so
//     '<U+2000>ae2:drive' is ae2:drive. Integer.parseInt reads any Unicode decimal digit, so a fullwidth '3' counts 3.
//     Mth.ceil wraps a count above 2147483647 to -2147483648, which then fails the >= 1 check.
//     So '2x ae2:drive' is { id: 'ae2:drive', count: 2 }, '2x 2x ae2:drive' is { id: 'ae2:drive', count: 2 } (read() takes
//     the second count, and kjs$withCount replaces it), and 'ae2:terminal[minecraft:rarity="epic"]' is
//     { id: 'ae2:terminal', count: 1, components: '[minecraft:rarity="epic"]' }. What KubeJS rejects (a count parseInt or
//     readDouble refuses, a missing 'x', a count below 1, an invalid resource location, and an id with an empty path, which
//     ItemWrapper.findItem reports as "Item with ID <id> does not exist!": '#c:ingots/iron' and 'AE2:Drive' read one) throws
//     here, so it lands in `errors`. The empty stack is { id: 'minecraft:air', count: 0 }. The item registry is not
//     modelled beyond that: any other well-formed id is accepted. Every other Item member is inert.
//     A components or NBT patch is kept as raw text and not read: one KubeJS rejects (unbalanced brackets, an unknown
//     component, a malformed value) records a row here all the same. The pack writes none (Task 8b round 4).
//     Item.of(x) or Item.of(x, n) with an x that is neither a string nor a stack this runner made (Item.getItem(id),
//     Ingredient.of(id).first, any stand-in, undefined) throws here, into `errors`: KubeJS would wrap an ItemLike into a
//     real stack (ItemWrapper's wrapTrivial calls getDefaultInstance), so the recipe is real in game, but its output is not
//     modelled, and a row naming '<inert>' would make a maker no test sees (Task 8b round 4). A shaped or shapeless output
//     that is not a string or a stack at all (event.shaped(Item.getItem(id), ...)) is recorded as given, and
//     tools/tests/kjs.py's products() fails on it.
//   - A shaped or shapeless recipe's string output goes through the same reading (`outputStack`), so tools/tests/kjs.py's
//     products() takes a script output's id from the stack, never from the raw string.
//   - The recipes event: shaped, shapeless, custom, remove, and .id() on the recipe each returns; everything else is recorded
//     under `other` (or, on a returned recipe, under its row's `chain`). A shaped or shapeless string output KubeJS cannot
//     read is caught by RecipeTypeFunction.call (it catches any Throwable, logs it and returns a recipe it never adds; javap
//     -c), so the handler goes on: here that adds an `errors` entry '<file> recipes handler <i>: event.<kind> output:
//     <error>', records no row, and returns a stand-in recipe. Item.of('<bad string>') is not inside a recipe function, so
//     here it throws into the script and stops that handler (KubeJS's ItemWrapper.wrap throws a KubeRuntimeException there;
//     that Rhino passes it to the script unchanged is assumed, not probed).
//   - The tags event: add, remove and removeAll, called on the event or on the wrapper get(tag) returns (the edit members of
//     kubejs-neoforge-2101.7.2-build.377.jar TagKubeEvent and TagWrapper, javap). As in KubeJS the event's members return that
//     wrapper, so a chained call is recorded too. removeAllTagsFrom (also an edit member) and every other member are not
//     modelled: calling one throws a TypeError, which lands in `errors`. A registry is written as a resource location: 'block'
//     and 'minecraft:block' are the same registry.
//   - Every other KubeJS global a script touches (StartupEvents, BlockEvents, NativeEvents, LootJS, Java, JsonIO, Ingredient,
//     Fluid, ...) and every other ServerEvents member (loaded, generateData, ...) is an inert stand-in: callable,
//     constructible, every property is itself, and it coerces to '<inert>' (Symbol.toPrimitive) and is not a promise (`then`
//     is undefined). Ingredient.of and Fluid.of are inert: no test needs a model. Their handlers never run. The stand-in is a
//     function, so it is truthy: a script branch on one (if (Platform.isLoaded('x')) ..., if (Utils.server) ...) always takes
//     the true side here, whatever the real value would be.
// Not modelled: a top-level const/let/class clash with another script's name is a SyntaxError here too, but two plain
// `function` declarations with the same name do NOT throw in a node vm context (the later one silently wins; node v22.3.0), so
// test_other_gate.py's test_server_script_top_level_names_are_unique checks name uniqueness.
//
// node runs V8, NOT the pack's Rhino (rhino-2101.2.7-build.85.jar under KubeJS 2101.7.2). A script that loads and runs here can
// still fail in KubeJS: Rhino throws `redeclaration of var` for a const inside a try block when the block runs, and V8 accepts
// it (tools/tests/test_rhino_hazards.py lints that). So this runner pins what the scripts ask KubeJS to do, not that KubeJS
// accepts them. The load proof is the boot, tools/server_boot.sh (it fails on any KubeJS ERROR line and on "Parsing error
// loading recipe"); handler bodies that only run in play (events.js listeners) are proved by the in-game probe.
'use strict'
const fs = require('fs')
const path = require('path')
const util = require('util')
const vm = require('vm')

const ROOT = path.resolve(__dirname, '..', '..')
const PREFIX = 'kubejs/server_scripts/'
const DEFAULT_SCRIPTS = path.join(ROOT, 'kubejs', 'server_scripts')
const SCRIPTS = process.env.CONFLUENCE_SCRIPTS_ROOT ? path.resolve(process.env.CONFLUENCE_SCRIPTS_ROOT) : DEFAULT_SCRIPTS
if (SCRIPTS !== DEFAULT_SCRIPTS) process.stderr.write('run_server_scripts.js: CONFLUENCE_SCRIPTS_ROOT is set; reading scripts from ' + SCRIPTS + '\n')
if (!fs.existsSync(path.join(SCRIPTS, 'lib'))) {
  process.stderr.write('run_server_scripts.js: ' + SCRIPTS + ' is not a server_scripts directory (it has no lib/)\n')
  process.exit(2)
}
const out = {
  handlers: { recipes: 0, blockTags: 0, tags: {} }, removed: [], custom: [], blockTags: [], errors: [],
  recipes: [], customs: [], filters: [], other: [], callbacks: [], tagEvents: [], loaded: [], skipped: [], scriptsRoot: SCRIPTS,
}
const handlers = { recipes: [], tags: {} }   // each entry { fn, file }
let loading = null   // the script being loaded, so a handler knows which file registered it

// ---- serialisation: one replacer for every recorded value
const labels = new WeakMap()   // stand-in proxy -> how it serialises
const isRegExp = v => Object.prototype.toString.call(v) === '[object RegExp]'   // realm-safe: instanceof fails across vm realms
const tagOf = v => Object.prototype.toString.call(v)
const replacer = legacyRegExp => function (key, v) {
  if (v === undefined) return '<undefined>'
  if (v !== null && (typeof v === 'object' || typeof v === 'function') && labels.has(v)) return labels.get(v)
  if (typeof v === 'function') return '<function>'
  if (isRegExp(v)) return legacyRegExp ? String(v) : { RegExp: String(v) }
  if (typeof v === 'symbol') return String(v)
  if (typeof v === 'bigint') return String(v) + 'n'
  if (typeof v === 'number' && !Number.isFinite(v)) return '<' + String(v) + '>'
  if (tagOf(v) === '[object Map]') return { Map: Array.from(v) }
  if (tagOf(v) === '[object Set]') return { Set: Array.from(v) }
  return v
}
const REPLACER = replacer(false)
const snap = v => {
  try { return JSON.parse(JSON.stringify(v, REPLACER)) } catch (e) { return '<unserialisable: ' + e + '>' }
}

// Callable and indexable, swallows everything: for globals a script only touches at load time. It also survives coercion:
// Symbol.toPrimitive yields a string, so '' + inert and `${inert}` do not throw; `then` is undefined, so it is not mistaken
// for a promise; `toJSON` is undefined, so JSON.stringify hands it to the replacer.
const inert = new Proxy(function () {}, {
  get: (target, key) => (key === Symbol.toPrimitive ? () => '<inert>' : key === 'then' || key === 'toJSON' ? undefined : inert),
  apply: () => inert,
  construct: () => inert,
})
labels.set(inert, '<inert>')

// ---- globals
const javaTrim = s => s.replace(/^[\u0000- ]+|[\u0000- ]+$/g, '')   // String.trim: code points <= U+0020 only
// The scripts' console writes to stderr, never stdout, so a script or handler that logs cannot corrupt the JSON on stdout
// (lib/loot.js calls console.error; dump.js, tagcheck.js and worldgen.js call console.log).
const toStderr = (...args) => { process.stderr.write(util.format(...args) + '\n') }
const scriptConsole = { log: toStderr, info: toStderr, warn: toStderr, error: toStderr, debug: toStderr }
const registryId = r => { const s = String(r); return s.includes(':') ? s : 'minecraft:' + s }
const ServerEvents = new Proxy({
  recipes: fn => { handlers.recipes.push({ fn, file: loading }) },
  tags: (registry, fn) => {
    const reg = registryId(registry);
    (handlers.tags[reg] = handlers.tags[reg] || []).push({ fn, file: loading })
  },
}, { get: (target, key) => (key in target ? target[key] : inert) })
// Item.of and item strings: see the header ("Item.of"). Any other Item member is inert.
const EMPTY_STACK = () => ({ id: 'minecraft:air', count: 0 })
// Character.isWhitespace (brigadier's StringReader.skipWhitespace): \t \n \u000b \f \r \u001c-\u001f, and the Unicode space,
// line and paragraph separators except the no-break spaces U+00A0, U+2007 and U+202F. Written with \u{...} escapes, so no
// separator character sits in this file. Compared with Character.isWhitespace over every char (JDK 22, Task 8b round 3).
const JAVA_WHITESPACE = /[\t\n\u000b\f\r\u001c-\u001f \u{1680}\u{2000}-\u{2006}\u{2008}-\u{200a}\u{2028}\u{2029}\u{205f}\u{3000}]/u
const isJavaWhitespace = c => JAVA_WHITESPACE.test(c)
// Character.digit(c, 10) for one UTF-16 char: the value of a Unicode decimal digit (Nd), else -1. Each Nd run is consecutive
// 0-9 blocks, so the value is the distance from the run's start, mod 10. A surrogate half is no digit. Compared with
// Character.digit over every char (JDK 22, Task 8b round 3).
const ND = /^\p{Nd}$/u
const javaDigit = c => {
  if (!ND.test(c)) return -1
  let z = c.charCodeAt(0)
  while (z > 0 && ND.test(String.fromCharCode(z - 1))) z--
  return (c.charCodeAt(0) - z) % 10
}
// Integer.parseInt(n): an optional ASCII '+' or '-', then one or more javaDigit digits, in int range; NaN where it throws.
const javaParseInt = n => {
  const sign = n[0] === '-' || n[0] === '+' ? n[0] : ''
  const digits = n.slice(sign.length)
  if (digits === '') return NaN
  let v = 0
  for (const c of digits.split('')) {
    const d = javaDigit(c)
    if (d < 0) return NaN
    v = v * 10 + d
  }
  v = sign === '-' ? -v : v
  return v >= -2147483648 && v <= 2147483647 ? v : NaN
}
// Mth.ceil(double) (server-1.21.1-20240808.144430-srg.jar, javap -c): i = (int) d; d > i ? i + 1 : i, in int arithmetic. (int)
// saturates at 2^31 - 1, so anything above it wraps to -2^31.
const javaCeil = d => {
  const i = Number.isNaN(d) ? 0 : d >= 2147483647 ? 2147483647 : d <= -2147483648 ? -2147483648 : Math.trunc(d)
  return d > i ? (i + 1) | 0 : i
}
const parseItemString = (s, whole) => {   // ItemWrapper.parseString and read; `whole` is the string the error names
  const fail = why => new Error("item string '" + whole + "': " + why)
  if (s === '' || s === '-' || s === 'air' || s === 'minecraft:air') return EMPTY_STACK()
  let p = 0
  const skip = () => { while (p < s.length && isJavaWhitespace(s[p])) p++ }
  skip()
  if (p >= s.length || s[p] === '-') return EMPTY_STACK()
  let count = 1
  if (/[0-9.]/.test(s[p])) {   // StringReader.isAllowedNumber is [0-9.-]; '-' was handled above
    const start = p
    while (p < s.length && /[0-9.-]/.test(s[p])) p++
    const num = s.slice(start, p)
    if (!/^[+-]?(\d+\.?\d*|\.\d+)$/.test(num)) throw fail("CommandSyntaxException: Invalid double '" + num + "'")
    count = javaCeil(Number(num))
    skip()
    if (s[p] !== 'x') throw fail("CommandSyntaxException: Expected 'x'")
    p++
    skip()
    if (count < 1) throw fail('Item count smaller than 1 is not allowed!')
  }
  const start = p
  while (p < s.length && /[0-9a-z_:\/.-]/.test(s[p])) p++   // ID.readGreedy: ResourceLocation.isAllowedInResourceLocation
  const raw = s.slice(start, p)
  // ResourceLocation.read: split at the first ':', an empty namespace meaning minecraft; no '/' in the namespace, no second ':'
  const m = /^(?:([a-z0-9_.-]*):)?([a-z0-9_.\/-]*)$/.exec(raw)
  if (!m) throw fail("invalid resource location '" + raw + "'")
  const id = (m[1] ? m[1] : 'minecraft') + ':' + m[2]
  // ItemWrapper.findItem: BuiltInRegistries.ITEM.getHolder(id), else "Item with ID <id> does not exist!". The registry is not
  // modelled, except that no item has an empty path ('#c:ingots/iron', 'AE2:Drive' and 'ae2:' all read one).
  if (m[2] === '') throw fail('Item with ID ' + id + ' does not exist! (an empty path)')
  const stack = { id, count }
  if (s[p] === '[' || s[p] === '{') stack.components = s.slice(p)
  return stack
}
// A stack this runner made (readItemString, Item.of): a plain object with a string id and an integer count, not a stand-in.
const isStack = v => v !== null && typeof v === 'object' && !labels.has(v) && typeof v.id === 'string' && Number.isInteger(v.count)
// Item.of's argument when it is not a string: KubeJS wraps anything ItemLike (an Item from Item.getItem, an Ingredient's
// .first, a block) into a real stack (ItemWrapper's wrapTrivial calls getDefaultInstance), so such a call makes a recipe in
// game. None of those is modelled here (each is a stand-in), so it throws, and the handler's error lands in `errors`, rather
// than record a maker whose output no test can read (Task 8b round 4: Item.of(Item.getItem('ae2:drive'), 1) once recorded
// { id: '<inert>', count: 1 }).
const notModelled = (x, n) => new Error('Item.of(' + snapJson(x) + (n === undefined ? '' : ', ' + n) + '): the argument is ' +
  'not an item string or a stack this runner made; KubeJS would make a real stack of it, which is not modelled (see the ' +
  'header, "Item.of")')
const snapJson = x => { try { return JSON.stringify(snap(x)) } catch (e) { return String(e) } }
const withCount = (stack, n) => {   // ItemStack.kjs$withCount / ItemWrapper.of(ItemStack, int)
  if (!isStack(stack)) throw notModelled(stack, n)
  return stack.id === 'minecraft:air' || n <= 0 ? EMPTY_STACK() : Object.assign({}, stack, { count: n })
}
const readItemString = str => {   // ItemWrapper.wrapResult, the CharSequence case
  const whole = String(str)
  let s = javaTrim(whole)
  let count = 1
  const sp = s.indexOf(' ')
  if (sp >= 2 && s.indexOf('x') === sp - 1) {
    const n = s.slice(0, sp - 1)
    count = javaParseInt(n)
    if (Number.isNaN(count)) throw new Error("item string '" + whole + "': NumberFormatException: For input string: \"" + n + '"')
    s = s.slice(sp + 1)
  }
  return withCount(parseItemString(s, whole), count)
}
const itemOf = (x, n) => {
  const stack = typeof x === 'string' ? readItemString(x) : x
  if (!isStack(stack)) throw notModelled(x, n)
  return n === undefined ? stack : withCount(stack, n)
}
const Item = new Proxy({ of: itemOf }, { get: (target, key) => (key in target ? target[key] : inert) })
const sandbox = { console: scriptConsole, ServerEvents, Item }
for (const name of ['StartupEvents', 'ClientEvents', 'BlockEvents', 'ItemEvents', 'EntityEvents', 'PlayerEvents', 'LevelEvents',
  'NetworkEvents', 'NativeEvents', 'LootJS', 'LootEntry', 'Java', 'JsonIO', 'Utils', 'Ingredient', 'Fluid', 'Text', 'Component',
  'Platform']) sandbox[name] = inert
vm.createContext(sandbox)

// ---- which scripts, and in what order
const FRAME = /(kubejs\/server_scripts\/[^\s:()]+\.js):(\d+)/
const frameOf = e => {
  const m = e !== null && typeof e === 'object' && typeof e.stack === 'string' ? FRAME.exec(e.stack) : null
  return m ? ' [at ' + m[1] + ':' + m[2] + ']' : ''
}
const errorText = e => { try { return String(e) } catch (x) { return '<unprintable error>' } }
const fail = (where, e) => { out.errors.push(where + ': ' + errorText(e) + frameOf(e)) }
const label = rel => PREFIX + rel                        // 'tiers/tier5.js' -> 'kubejs/server_scripts/tiers/tier5.js'
const absolute = rel => path.join(SCRIPTS, rel)

const walk = (dir, depth, acc) => {   // Files.walk(dir, 10, FOLLOW_LINKS): entries up to 10 levels below dir
  for (const name of fs.readdirSync(dir).sort()) {
    const p = path.join(dir, name)
    const st = fs.statSync(p)   // follows links
    const rel = path.relative(SCRIPTS, p).split(path.sep).join('/')
    if (st.isDirectory()) { if (depth < 10) walk(p, depth + 1, acc) }
    else if (st.isFile() && name.endsWith('.js')) acc.push(rel)
    else if (st.isFile() && name.endsWith('.ts') && !name.endsWith('.d.ts')) out.errors.push(label(rel) + ' load: a .ts script, not modelled')
  }
  return acc
}
const args = process.argv.slice(2)
let files
if (args.includes('--all')) {
  files = walk(SCRIPTS, 1, [])
} else {
  files = fs.readdirSync(path.join(SCRIPTS, 'lib')).filter(f => f.endsWith('.js')).sort().map(f => 'lib/' + f)
  for (const a of args) {
    const rel = a.startsWith(PREFIX) ? a.slice(PREFIX.length) : null
    if (rel === null) out.errors.push(a + ': not a ' + PREFIX + '<path> argument')
    else if (!files.includes(rel)) files.push(rel)
  }
}

const PROPERTY = /^(\w+)\s*[:=]?\s*(-?\w+)$/
const packModeConfig = () => {
  const p = path.join(ROOT, 'kubejs', 'config', 'common.json')
  if (!fs.existsSync(p)) return ''
  const v = JSON.parse(fs.readFileSync(p, 'utf8')).packmode
  return typeof v === 'string' ? v : ''
}
const PACK_MODE = packModeConfig()
const INT32 = v => /^-?\d+$/.test(v) && Number(v) >= -2147483648 && Number(v) <= 2147483647
// ScriptFile.<init>: the blanked source and the properties.
const readScript = rel => {
  const lines = fs.readFileSync(absolute(rel), 'utf8').split(/\r\n|\r|\n/)
  const props = {}
  lines.forEach((raw, i) => {
    const line = javaTrim(raw)
    if (line === '' || line.startsWith('import ')) { lines[i] = ''; return }
    if (!line.startsWith('//')) return
    const m = PROPERTY.exec(javaTrim(line.slice(2)))
    if (m) (props[javaTrim(m[1])] = props[javaTrim(m[1])] || []).push(javaTrim(m[2]))
    lines[i] = ''
  })
  const get = (name, def) => (props[name] ? props[name][props[name].length - 1] : def)
  return { rel, source: lines.join('\n'), props, get }
}
const scripts = []
for (const rel of files) {
  if (!fs.existsSync(absolute(rel))) { out.errors.push(label(rel) + ' load: missing'); continue }
  const s = readScript(rel)
  const priority = s.get('priority', '0')
  if (!INT32(priority)) {
    out.errors.push(label(rel) + ' load: priority ' + priority + ' is not an int (Integer.parseInt throws; KubeJS does not load the file)')
    continue
  }
  s.priority = Number(priority)
  const requires = s.props.requires || []
  if (s.get('ignored', 'false') === 'true' || s.get('ignore', 'false') === 'true') s.skip = 'Ignored'
  else if (requires.includes('client')) s.skip = 'Client only'
  else if (s.get('packmode', '') !== '' && s.get('packmode', '') !== PACK_MODE) s.skip = 'Pack mode mismatch'
  if (!s.skip) {
    requires.filter(m => m !== 'client').forEach(m => {
      out.errors.push(label(rel) + ' load: requires ' + m + ', and the mod list is not modelled (run_server_scripts.js header)')
    })
  }
  scripts.push(s)
}
const locationPath = s => s.rel.toLowerCase()
scripts.sort((a, b) => {
  const la = locationPath(a), lb = locationPath(b)
  return b.priority - a.priority || (la < lb ? -1 : la > lb ? 1 : 0)
})
for (const s of scripts) {
  if (s.skip) { out.skipped.push({ file: label(s.rel), reason: s.skip }); continue }
  loading = label(s.rel)
  out.loaded.push(loading)
  try { vm.runInContext(s.source, sandbox, { filename: loading }) } catch (e) { fail(loading + ' load', e) }
}
loading = null

// ---- the recipes event
const flat = a => a.reduce((acc, x) => acc.concat(Array.isArray(x) ? flat(x) : [x]), [])
const filterJson = f => JSON.stringify(f, replacer(true))
const recordRemoval = f => {
  const keys = f !== null && typeof f === 'object' && !isRegExp(f) ? Object.keys(f) : null
  const only = k => keys !== null && keys.length === 1 && keys[0] === k
  if (only('id') && typeof f.id === 'string') return f.id
  if (only('id') && isRegExp(f.id)) return String(f.id)
  if (only('output')) return 'output:' + (typeof f.output === 'string' ? f.output : filterJson(f.output))
  return 'filter:' + filterJson(f)
}
// A member called through a property of an unmodelled member (event.addedRecipes.forEach) records its dotted name, and a call
// returns another recorder named '<member>()', so a call chained on a call's result is recorded too
// (r.get('result').setCount(64) -> 'get', then 'get().setCount'). `sink` records a call: out.other for the event's members,
// out.callbacks for a callback's recipe probe.
const recorder = (member, ctx, sink) => {
  const r = new Proxy(function () {}, {
    get: (target, key) => (key === Symbol.toPrimitive ? () => '<inert>'
      : key === 'then' || key === 'toJSON' || typeof key === 'symbol' ? undefined : recorder(member + '.' + key, ctx, sink)),
    set: (target, key, v) => { sink('set', member + '.' + String(key), [v]); return true },
    apply: (target, self, args) => { sink('call', member, args); return recorder(member + '()', ctx, sink) },
    construct: (target, args) => { sink('call', 'new ' + member, args); return recorder('new ' + member + '()', ctx, sink) },
  })
  labels.set(r, '<inert>')
  return r
}
// The event's own unmodelled members: recorded in `other`, and each function argument is called once with a recipe probe.
const eventSink = ctx => (op, member, args) => {
  out.other.push(op === 'set' ? { member, op, args: snap(args), file: ctx.file, handler: ctx.handler }
    : { member, args: snap(args), file: ctx.file, handler: ctx.handler })
  if (op === 'call') args.forEach(a => { if (typeof a === 'function') probeCallback(member.replace(/^new /, ''), a, ctx) })
}
// One probe per callback, called once. Every read returns a stand-in, so a branch on what the callback reads from the recipe
// (if (String(r.getOrCreateId()).startsWith('ae2:')) ...) takes one side only, and an edit on the other side is never seen
// here. test_recipe_scripts.py lints dump.js's source for that reason.
const probeCallback = (call, fn, ctx) => {
  const sink = (op, member, args) => {
    out.callbacks.push({ call, op, member, args: snap(args), file: ctx.file, handler: ctx.handler })
  }
  const probe = new Proxy({}, {
    get: (target, key) => (key === Symbol.toPrimitive ? () => '<recipe probe>'
      : key === 'then' || key === 'toJSON' || typeof key === 'symbol' ? undefined : recorder(String(key), ctx, sink)),
    set: (target, key, v) => { sink('set', String(key), [v]); return true },
  })
  labels.set(probe, '<recipe probe>')
  try { fn(probe) } catch (e) { fail(ctx.file + ' recipes handler ' + ctx.handler + ': ' + call + ' callback', e) }
}
// The recipe shaped/shapeless/custom return: .id(x) sets the row's id; any other call is appended to the row's chain.
const recipeHandle = (row, legacyCustom) => {
  const h = new Proxy({}, {
    get: (target, key) => {
      if (key === Symbol.toPrimitive) return () => '<recipe>'
      if (key === 'then' || key === 'toJSON' || typeof key === 'symbol') return undefined
      if (key === 'id') {
        return (...args) => {
          row.id = snap(args[0])
          if (args.length !== 1) row.chain.push({ member: 'id', args: snap(args) })
          if (legacyCustom) out.custom.push({ id: String(args[0]), json: row.json })
          return h
        }
      }
      return (...args) => { row.chain.push({ member: String(key), args: snap(args) }); return h }
    },
  })
  labels.set(h, '<recipe>')
  return h
}
const recipeEvent = ctx => new Proxy({}, {
  get: (target, key) => {
    if (key === Symbol.toPrimitive) return () => '<inert>'
    if (key === 'then' || key === 'toJSON' || typeof key === 'symbol') return undefined
    if (key === 'shaped' || key === 'shapeless') {
      return (...args) => {
        const shaped = key === 'shaped'
        // A string output becomes an ItemStack through ItemWrapper.wrap, as Item.of's argument does (the shaped and shapeless
        // schemas' result is an ItemStackComponent: ComponentValueMap.getValue -> RecipeComponent.wrap -> Context.jsToJava
        // with ItemStackComponent's type info -> the ItemStack type wrapper). When that throws, RecipeTypeFunction.call
        // catches it (any Throwable), logs it and returns a recipe it never adds, and the handler goes on: here the error goes
        // to `errors`, no row is recorded, and the returned stand-in takes .id() and the rest as a recipe would.
        let outputStack = null
        if (typeof args[0] === 'string') {
          try { outputStack = readItemString(args[0]) } catch (e) {
            fail(ctx.file + ' recipes handler ' + ctx.handler + ': event.' + key + ' output', e)
            return recipeHandle({ id: null, chain: [] }, false)
          }
        }
        const row = { kind: key, id: null, output: snap(args[0]), outputStack, pattern: shaped ? snap(args[1]) : null,
          key: shaped ? snap(args[2]) : null, ingredients: shaped ? null : snap(args[1]), extra: snap(args.slice(shaped ? 3 : 2)),
          file: ctx.file, handler: ctx.handler, chain: [] }
        out.recipes.push(row)
        return recipeHandle(row, false)
      }
    }
    if (key === 'custom') {
      return (json, ...extra) => {
        const row = { id: null, json: snap(json), file: ctx.file, handler: ctx.handler, chain: [] }
        if (extra.length) row.extra = snap(extra)
        out.customs.push(row)
        return recipeHandle(row, true)
      }
    }
    if (key === 'remove') {
      return (...args) => {
        const f = args[0]
        out.removed.push(recordRemoval(f))
        const row = { filter: snap(f), file: ctx.file, handler: ctx.handler }
        if (args.length !== 1) row.args = snap(args)
        out.filters.push(row)
      }
    }
    return recorder(String(key), ctx, eventSink(ctx))
  },
})

// ---- the tags event
const tagEvent = (registry, ctx) => {
  const record = (op, tag, values) => {
    const all = flat(values)
    out.tagEvents.push({ registry, tag: snap(tag), op, values: snap(all), file: ctx.file, handler: ctx.handler })
    if (registry === 'minecraft:block') out.blockTags.push({ tag: String(tag), op: op, values: all.map(String) })
  }
  const wrapper = tag => {
    const w = {
      add: (...values) => { record('add', tag, values); return w },
      remove: (...values) => { record('remove', tag, values); return w },
      removeAll: () => { record('removeAll', tag, []); return w },
    }
    return w
  }
  return {
    get: tag => wrapper(tag),
    add: (tag, ...values) => wrapper(tag).add(...values),
    remove: (tag, ...values) => wrapper(tag).remove(...values),
    removeAll: tag => wrapper(tag).removeAll(),
  }
}

out.handlers.recipes = handlers.recipes.length
for (const reg of Object.keys(handlers.tags)) out.handlers.tags[reg] = handlers.tags[reg].length
out.handlers.blockTags = (handlers.tags['minecraft:block'] || []).length
handlers.recipes.forEach(({ fn, file }, i) => {
  try { fn(recipeEvent({ file, handler: i })) } catch (e) { fail(file + ' recipes handler ' + i, e) }
})
for (const reg of Object.keys(handlers.tags)) {
  handlers.tags[reg].forEach(({ fn, file }, i) => {
    try { fn(tagEvent(reg, { file, handler: i })) } catch (e) { fail(file + ' tags(' + reg + ') handler ' + i, e) }
  })
}
process.stdout.write(JSON.stringify(out))
