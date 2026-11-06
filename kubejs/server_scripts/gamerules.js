// Log the game-rule names of the server's GameRules and of a fresh GameRules(), once per server start, so that
// tools/check_boot_log.py can compare both with tools/gamerules.toml (v0.3 Task 11d, D137). The pin is 51 vanilla rules,
// 3 Twilight Forest rules and 1 Accessories rule. A boot whose line differs, or has no line, fails.
//
// Why: Twilight Forest 4.8.3345 registers its three rules from three Worker-Main tasks at once, into vanilla's unlocked
// TreeMap GameRules.GAME_RULE_TYPES. That can drop any key or leave a cycle, and nothing logs it. One clone boot of the
// shipped pack lost playersTfPortalDefaultDelay, and the boot check of the day passed it.
// kubejs/startup_scripts/tf_gamerules_guard.js now registers the three rules first; this line is how a boot proves the
// result.
//
// Why both instances, from server-1.21.1-20240808.144430-srg.jar (javap -c):
// - GameRules() copies GAME_RULE_TYPES into its own map (<init>()V offsets 5-39), so a lost key is missing from every
//   instance made after the loss.
// - The server's instance is the one ServerLevel.tick reads. It comes from the level's settings (LevelSettings.parse,
//   new GameRules(DynamicLike) at offset 104).
// - MinecraftServer.getGameRules() returns overworld().getGameRules() (neoforge-21.1.250-server.jar, offsets 0-7).
// - GameRules.createTag() writes one CompoundTag key per rule in that instance (offsets 0-24), and getAllKeys() lists the
//   keys.
//
// Event: ServerEvents.loaded, which is ServerStartingEvent (see tagcheck.js's header). It runs once per server start and
// does not re-fire on /reload. KubeJS's class filter allows net.minecraft.
//
// The line is sorted and comma-separated:
//   confluence gamerules: server 55 [accessories.keepAccessoryInventory,announceAdvancements,...]; registry 55 [...]
ServerEvents.loaded(event => {
  const GameRules = Java.loadClass('net.minecraft.world.level.GameRules')
  const names = rules => {
    const out = []
    rules.createTag().getAllKeys().forEach(k => { out.push(String(k)) })
    out.sort()
    return out
  }
  const server = names(event.server.getGameRules())
  const registry = names(new GameRules())
  console.log('confluence gamerules: server ' + server.length + ' [' + server.join(',') + ']; registry ' + registry.length +
    ' [' + registry.join(',') + ']')
})
