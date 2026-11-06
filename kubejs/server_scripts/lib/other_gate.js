// priority: 1
// The Other gate: the decisions behind the Teleport Pad script (v0.3 spec §4.2), the travel check (§4.3) and the arrival
// check (§4.4); D100 two-click unlock, D101 per-team unlock with no follow-in, D109 fail closed for The Other and The Beyond.
// Pure JavaScript: no KubeJS binding and no Java call appears here. events.js reads the game state, calls these functions
// and carries out the action objects they return; tools/tests/test_other_gate.py runs them in node against the real
// lib/ids.js. IDS is read only when a function runs, so the load order against ids.js does not matter. All server scripts
// share one scope (HANDOFF §6), so OTHER_GATE is this file's only top-level name.
//
// Inputs: plain strings, plus callbacks for anything that costs a lookup, so each rule asks only for what it needs.
//   pad(c):     c.dim (the pad's dimension id), c.hand ('MAIN_HAND' | 'OFF_HAND'), c.team() -> { found, unlocked },
//               c.held() -> { main, off } (item ids in the two hands)
//   travel(c):  c.dest (destination dimension id), c.exempt() -> creative or spectator, c.team() -> { found, unlocked }
//   arrival(c): the same three fields as travel
// Outputs (error is null unless a callback threw; the action is then the fail-closed one):
//   pad:     { cancel, unlock, shrink: 'MAIN_HAND' | 'OFF_HAND' | null, message, error }
//   travel:  { cancel, message, error }
//   arrival: { sendToSpawn, message, error }
const OTHER_GATE = {
  // Player text, verbatim from spec §4.2 (pad rows) and §4.3 (travel check). The arrival check (§4.4) reuses the travel
  // check's text for the same destination; see arrivalRule.
  MSG: {
    unlocked: 'The Other is open to your team. Sneak and right-click the pad with both hands empty to travel.',
    locked: 'Locked. Right-click this pad holding a Key to The Other.',
    beyond: 'The Beyond is closed in Confluence.',
    team: 'Your team has not unlocked The Other.',
  },

  // The two dimensions D109 fails closed for.
  gated: function (dim) {
    return dim === IDS.other.dimension || dim === IDS.other.beyond
  },

  padAction: function (cancel, unlock, shrink, message, error) {
    return { cancel: cancel, unlock: unlock, shrink: shrink, message: message, error: error }
  },

  // §4.2 table, top to bottom. The team is looked up only for a pad in the Nether, the held items only on a main-hand
  // click there by a locked team. With no FTB Teams manager or no team, a key click shows the Locked message and the
  // key stays in hand (§4.2 unlock step 1).
  padRule: function (c) {
    const main = c.hand === 'MAIN_HAND'
    if (c.dim === IDS.vanilla.theEnd) return OTHER_GATE.padAction(true, false, null, main ? OTHER_GATE.MSG.beyond : null, null)
    if (c.dim !== IDS.vanilla.theNether) return OTHER_GATE.padAction(false, false, null, null, null)
    const team = c.team()
    if (team.found && team.unlocked) return OTHER_GATE.padAction(false, false, null, null, null)
    if (!main) return OTHER_GATE.padAction(true, false, null, null, null)
    const held = c.held()
    const shrink = held.main === IDS.pack.otherKey ? 'MAIN_HAND' : (held.off === IDS.pack.otherKey ? 'OFF_HAND' : null)
    if (shrink === null || !team.found) return OTHER_GATE.padAction(true, false, null, OTHER_GATE.MSG.locked, null)
    return OTHER_GATE.padAction(true, true, shrink, OTHER_GATE.MSG.unlocked, null)
  },

  // §4.2 "On any error, log and cancel (fail closed)": no unlock, no key taken.
  pad: function (c) {
    try {
      return OTHER_GATE.padRule(c)
    } catch (e) {
      return OTHER_GATE.padAction(true, false, null, null, String(e))
    }
  },

  // §4.3. Destination first; creative and spectator players pass (D109); the team is looked up only for The Other.
  travelRule: function (c) {
    if (!OTHER_GATE.gated(c.dest) || c.exempt()) return { cancel: false, message: null, error: null }
    if (c.dest === IDS.other.beyond) return { cancel: true, message: OTHER_GATE.MSG.beyond, error: null }
    const team = c.team()
    if (team.found && team.unlocked) return { cancel: false, message: null, error: null }
    return { cancel: true, message: OTHER_GATE.MSG.team, error: null }
  },

  // §4.3 error rule: cancel only when the destination is The Other or The Beyond. events.js also calls this from its own
  // catch, where dest is null if reading the destination itself failed.
  travelError: function (dest, e) {
    return { cancel: OTHER_GATE.gated(dest), message: null, error: String(e) }
  },

  travel: function (c) {
    try {
      return OTHER_GATE.travelRule(c)
    } catch (e) {
      return OTHER_GATE.travelError(c.dest, e)
    }
  },

  // §4.4: a survival or adventure player who arrives in The Beyond, or in The Other with a locked team (or no team), is
  // sent to the Overworld spawn with the locked message. §4.4's "locked message" is read as the travel check's message for
  // the same destination (§4.3): MSG.beyond for The Beyond, MSG.team for The Other. §4.2's pad text ("Locked. Right-click
  // this pad...") does not fit a player who arrived by tablet, or The Beyond at all.
  arrivalRule: function (c) {
    if (!OTHER_GATE.gated(c.dest) || c.exempt()) return { sendToSpawn: false, message: null, error: null }
    if (c.dest === IDS.other.beyond) return { sendToSpawn: true, message: OTHER_GATE.MSG.beyond, error: null }
    const team = c.team()
    if (team.found && team.unlocked) return { sendToSpawn: false, message: null, error: null }
    return { sendToSpawn: true, message: OTHER_GATE.MSG.team, error: null }
  },

  // §4.4 error rule: for The Other or The Beyond, treat the team as locked and move the player.
  arrivalError: function (dest, e) {
    if (!OTHER_GATE.gated(dest)) return { sendToSpawn: false, message: null, error: String(e) }
    const message = dest === IDS.other.beyond ? OTHER_GATE.MSG.beyond : OTHER_GATE.MSG.team
    return { sendToSpawn: true, message: message, error: String(e) }
  },

  arrival: function (c) {
    try {
      return OTHER_GATE.arrivalRule(c)
    } catch (e) {
      return OTHER_GATE.arrivalError(c.dest, e)
    }
  },
}
