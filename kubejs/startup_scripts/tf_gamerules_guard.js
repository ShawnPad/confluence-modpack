// Register Twilight Forest's three game rules here, once and on one thread, before Twilight Forest's own code can race to
// register them (v0.3 Task 11d, D137). Remove this file, and config/fml.toml's twilightforest = ["+kubejs"], once the pack
// runs a NeoForge 1.21.1 Twilight Forest release that contains upstream commit 4a98089 (research/twilightforest-gamerules-race.md).
//
// The race. Evidence is javap -c of the pack's jars:
// - twilightforest-1.21.1-4.8.3345-universal.jar
//   - TwilightForestMod.<init> calls TFGameRules.register() at offset 29.
//   - That method (offsets 0-13) passes each Supplier in TFGameRules.GAME_RULES, a HashSet, to lambda$register$2.
//   - lambda$register$2 (offsets 0-14) runs the supplier's get() on Util.backgroundExecutor().
//   - Each supplier is the Suppliers.memoize(...) that TFGameRules.register(String, Category, Type) builds (offsets 3-8)
//     around lambda$register$1, and that lambda calls GameRules.register at offset 3.
// - server-1.21.1-20240808.144430-srg.jar
//   - Util.<clinit> (offsets 6-12) names that executor's pool "Main", so its threads are Worker-Main-N.
//   - GameRules.register is an unlocked put into GameRules.GAME_RULE_TYPES, which is a TreeMap (GameRules.<clinit> offsets 6-17).
//   - NeoForge 21.1.250 does not patch GameRules: neoforge-21.1.250-server.jar has no GameRules.class.
// So up to three threads write to one TreeMap at once. That can lose any key, a vanilla one too, and ServerLevel.tick's
// getRule then returns null on the first tick. It can also leave a cycle, and new GameRules() then loops until the heap
// runs out. Of 25 clone boots of the shipped pack, one lost a rule and one ran out of heap (D137).
//
// The fix: get the three suppliers here first.
// - Guava is 32.1.2-jre, the guava jar in the server's unix_args.txt (libraries/com/google/guava/guava/32.1.2-jre).
// - Its Suppliers.memoize (offsets 16-42) wraps a delegate that is not Serializable in
//   Suppliers$NonSerializableMemoizingSupplier. TF's lambda is not Serializable: TFGameRules' BootstrapMethods #0 is the
//   plain LambdaMetafactory.metafactory.
// - That class's get() runs the delegate once, under synchronized (offsets 14-49). It stores the value at 36 and sets the
//   volatile delegate to SUCCESSFULLY_COMPUTED at 40-43.
// - After that, get() returns the cached value without calling the delegate (offsets 1-7 and 60-67).
// So once this script has called get(), Twilight Forest's Worker-Main tasks only read the cached keys and never write to
// GAME_RULE_TYPES.
//
// Why this runs first:
// - In config/fml.toml, [dependencyOverrides] twilightforest = ["+kubejs"] makes FML construct KubeJS before Twilight Forest.
//   This is the same FML mechanism as D134's Moonlight chain.
// - KubeJS runs startup scripts inside its own constructor: kubejs-neoforge-2101.7.2-build.377.jar, KubeJS.<init> offset
//   310, ScriptManager.reload(). It skips them only when generating data (offsets 110-117 and 302-304).
//
// Fail loud. This script throws in each of these cases:
//  (1) A Twilight Forest rule is already registered before it runs. That means the fml.toml edge is missing or was not
//      honoured, so Twilight Forest's tasks ran first. The check reads a fresh GameRules(), whose constructor copies
//      GAME_RULE_TYPES (GameRules.<init>()V offsets 5-39). It sees only finished registrations, so it is necessary but not
//      sufficient: with the edge missing, Twilight Forest tasks queued but not yet run are invisible to it. On a boot it
//      runs on, tools/check_configs.py's check of FML's override banner covers that case.
//  (2) A supplier field is missing or renamed (a Twilight Forest update), or the suppliers return other ids.
//  (3) The ids are still not registered afterwards.
// What a throw does:
// - ScriptManager.load(long) catches it (handler at offset 320) and logs a [KubeJS Startup/] ERROR.
// - KubeJSModEventHandler.loadComplete0 (offsets 40-168) then stops a dedicated server with "There were KubeJS startup
//   script syntax errors!".
// - On a client with KubeJS's startupErrorGUI on, KubeJS shows its error screen instead (offsets 141-156).
// To get a blocked server running: remove this file, or put the fml.toml edge back, then restart (D137).
// On success the script logs one INFO line. tools/check_boot_log.py requires exactly one per boot:
//   confluence tf-gamerules guard OK: registered tfEnforcedProgression, ... before Twilight Forest construction (rules 51 -> 54)
//
// Reload.
// - `/kubejs reload startup-scripts` re-runs this file in the same JVM: KubeJSCommands, literal at offset 227;
//   reloadStartup offsets 0-34. ScriptManager.reload unloads and loads again.
// - The same command makes every connected client do the same (ReloadStartupScriptsPayload).
// - By then this script's first run has registered the three rules, so check (1) would log a false ERROR.
// - In a startup script, `global` is BuiltinKubeJSPlugin.GLOBAL (registerBindings offsets 0-30). It is one static HashMap,
//   made in that class's static initialiser (offsets 0-7).
// - A scan of the 118 mod jars (jar-in-jar included) found no other class that names that field, and no pack script
//   uses `global`. So the map is empty in a fresh JVM and keeps its entries across reloads.
// So the first run records its success in that map. A run that finds the record:
// - skips check (1);
// - still makes checks (2) and (3);
// - logs a different INFO line, without "guard OK".
// The first run in a JVM never finds the record, so it always fails loud.
//
// The code is wrapped in a function because KubeJS startup scripts share one top-level scope.
;(() => {
  const RECORD = 'confluence:tf_gamerules_guard'
  const GameRules = Java.loadClass('net.minecraft.world.level.GameRules')
  const TFGameRules = Java.loadClass('twilightforest.init.TFGameRules')
  const TF_IDS = ['tfEnforcedProgression', 'playersTfPortalDefaultDelay', 'playersTfPortalCreativeDelay']
  const FIELDS = ['ENFORCED_PROGRESSION_RULE', 'RULE_PLAYERS_TF_PORTAL_DEFAULT_DELAY', 'RULE_PLAYERS_TF_PORTAL_CREATIVE_DELAY']
  const fail = why => {
    throw new Error('confluence tf-gamerules guard FAILED: ' + why + ' (D137; see kubejs/startup_scripts/tf_gamerules_guard.js)')
  }
  const ruleIds = () => {
    const out = []
    new GameRules().createTag().getAllKeys().forEach(k => { out.push(String(k)) })
    return out
  }
  const reloaded = global.containsKey(RECORD)
  const before = ruleIds()
  const early = TF_IDS.filter(id => before.indexOf(id) >= 0)
  if (!reloaded && early.length > 0) {
    fail('Twilight Forest registered [' + early.join(', ') + '] before this script ran; is twilightforest = ["+kubejs"] in ' +
      'config/fml.toml [dependencyOverrides]?')
  }
  const got = FIELDS.map((field, i) => {
    let supplier = null
    try {
      supplier = TFGameRules[field]
    } catch (e) {
      fail('TFGameRules has no field ' + field + ' for ' + TF_IDS[i] + ' (' + e + ')')
    }
    if (supplier == null) fail('TFGameRules.' + field + ' is null or missing (expected the supplier of ' + TF_IDS[i] + ')')
    return String(supplier.get().getId())
  })
  if (got.join(',') !== TF_IDS.join(',')) {
    fail('the suppliers returned [' + got.join(', ') + '], expected [' + TF_IDS.join(', ') + ']')
  }
  const after = ruleIds()
  const missing = TF_IDS.filter(id => after.indexOf(id) < 0)
  if (missing.length > 0) {
    fail('[' + missing.join(', ') + '] not registered after resolving the suppliers')
  }
  if (reloaded) {
    console.info('confluence tf-gamerules guard: startup scripts reloaded; the first run in this JVM registered ' + got.join(', ') +
      ' (' + global.get(RECORD) + '), still registered (rules ' + after.length + '); the order check runs only on the first run')
  } else {
    global.put(RECORD, 'rules ' + before.length + ' -> ' + after.length)
    console.info('confluence tf-gamerules guard OK: registered ' + got.join(', ') + ' before Twilight Forest construction (rules ' +
      before.length + ' -> ' + after.length + ')')
  }
})()
