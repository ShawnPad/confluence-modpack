"""The Other gate rules (v0.3 spec §4.2-4.4; D100, D101, D109), run in node against the real lib/ids.js.

kubejs/server_scripts/lib/other_gate.js is plain JavaScript with no KubeJS or Java calls, so node can run it. Each case
loads ids.js and other_gate.js into one vm context (the way KubeJS gives all server scripts one scope), calls one
OTHER_GATE function with stub callbacks, and returns the action plus how often each callback ran.

node runs V8, NOT the pack's Rhino (rhino-2101.2.7-build.85.jar under KubeJS 2101.7.2), so these tests pin the decisions,
not that Rhino accepts the file: the load proof is the boot (tools/server_boot.sh fails on any KubeJS ERROR line), and the
behaviour proof is the in-game probe (v0.3 plan Task 12, spec §12 probes 2 and 3). node must be on PATH: the `node` fixture
asserts it, so the node tests run rather than skip.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPTS = ROOT / "kubejs" / "server_scripts"
LIB = SERVER_SCRIPTS / "lib"
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def node():
    assert NODE, ("node is not on PATH; the other-gate rules are JavaScript and these tests run them in node "
                  "(brew install node; v22.3.0 was used when this test was written)")
    return NODE


needs_node = pytest.mark.usefixtures("node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm')
const ctx = vm.createContext({})
for (const f of process.argv.slice(1)) vm.runInContext(fs.readFileSync(f, 'utf8'), ctx, { filename: f })
const c = JSON.parse(fs.readFileSync(0, 'utf8'))
const calls = { team: 0, held: 0, exempt: 0 }
const answer = (name, value) => { calls[name]++; if (value === 'throw') throw new Error('boom in ' + name); return value }
const input = { dim: c.dim, hand: c.hand, dest: c.dest,
  team: () => answer('team', c.team), held: () => answer('held', c.held), exempt: () => answer('exempt', c.exempt) }
const gate = vm.runInContext('OTHER_GATE', ctx)
const out = c.fn.endsWith('Error') ? gate[c.fn](c.dest, new Error('outer boom')) : gate[c.fn](input)
process.stdout.write(JSON.stringify({ out: out, calls: calls }))
"""

# Ids the rules see as input. The first six equal IDS.vanilla.* / IDS.other.* (lib/ids.js, Task 2):
# allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/dimension/{the_other,the_beyond,mining}.json. MOON is only an
# unrelated dimension for the untouched cases: adastra-1.21.1-1.16.25-neoforge.jar!data/ad_astra/dimension/moon.json
# (no IDS key; Task 2 lists ad_astra:moon among the ids used outside KubeJS code). KEY is IDS.pack.otherKey.
NETHER, END, OVERWORLD = "minecraft:the_nether", "minecraft:the_end", "minecraft:overworld"
OTHER, BEYOND, MINING, MOON = "allthemodium:the_other", "allthemodium:the_beyond", "allthemodium:mining", "ad_astra:moon"
KEY, AIR, DIRT = "kubejs:other_key", "minecraft:air", "minecraft:dirt"
UNLOCKED = {"found": True, "unlocked": True}
LOCKED = {"found": True, "unlocked": False}
NO_TEAM = {"found": False, "unlocked": False}
MSG_UNLOCKED = "The Other is open to your team. Sneak and right-click the pad with both hands empty to travel."
MSG_LOCKED = "Locked. Right-click this pad holding a Key to The Other."
MSG_BEYOND = "The Beyond is closed in Confluence."
MSG_TEAM = "Your team has not unlocked The Other."

PAD_UNTOUCHED = {"cancel": False, "unlock": False, "shrink": None, "message": None, "error": None}


def decide(fn, **case):
    case["fn"] = fn
    proc = subprocess.run(
        [NODE, "-e", HARNESS, str(LIB / "ids.js"), str(LIB / "other_gate.js")],
        input=json.dumps(case), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def pad(dim, hand, team=LOCKED, main=AIR, off=AIR):
    return decide("pad", dim=dim, hand=hand, team=team, held={"main": main, "off": off})


# ---- §4.2 pad table -------------------------------------------------------------------------------------------------

@needs_node
@pytest.mark.parametrize("hand", ["MAIN_HAND", "OFF_HAND"])
def test_pad_nether_unlocked_team_is_untouched(hand):
    r = pad(NETHER, hand, team=UNLOCKED, main=KEY)
    assert r["out"] == PAD_UNTOUCHED
    assert r["calls"] == {"team": 1, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("main,off,shrink", [(KEY, AIR, "MAIN_HAND"), (AIR, KEY, "OFF_HAND"), (KEY, KEY, "MAIN_HAND"),
                                             (DIRT, KEY, "OFF_HAND")])
def test_pad_nether_locked_key_click_unlocks_and_takes_one_key(main, off, shrink):
    r = pad(NETHER, "MAIN_HAND", team=LOCKED, main=main, off=off)
    assert r["out"] == {"cancel": True, "unlock": True, "shrink": shrink, "message": MSG_UNLOCKED, "error": None}


@needs_node
@pytest.mark.parametrize("main,off", [(AIR, AIR), (DIRT, AIR), (AIR, DIRT)])
def test_pad_nether_locked_main_hand_without_key_is_refused(main, off):
    r = pad(NETHER, "MAIN_HAND", team=LOCKED, main=main, off=off)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": MSG_LOCKED, "error": None}


@needs_node
@pytest.mark.parametrize("team", [LOCKED, NO_TEAM])
def test_pad_nether_locked_off_hand_event_cancels_silently(team):
    r = pad(NETHER, "OFF_HAND", team=team, off=KEY)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": None, "error": None}
    assert r["calls"]["held"] == 0


@needs_node
@pytest.mark.parametrize("main,off", [(KEY, AIR), (AIR, KEY)])
def test_pad_no_team_keeps_the_key(main, off):
    r = pad(NETHER, "MAIN_HAND", team=NO_TEAM, main=main, off=off)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": MSG_LOCKED, "error": None}


@needs_node
@pytest.mark.parametrize("hand,message", [("MAIN_HAND", MSG_BEYOND), ("OFF_HAND", None)])
def test_pad_end_always_cancels_without_a_team_lookup(hand, message):
    r = pad(END, hand, team=UNLOCKED, main=KEY)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": message, "error": None}
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("dim", [OVERWORLD, MINING, OTHER, BEYOND, MOON])
@pytest.mark.parametrize("hand", ["MAIN_HAND", "OFF_HAND"])
def test_pad_other_dimensions_are_untouched(dim, hand):
    r = pad(dim, hand, team=LOCKED, main=KEY)
    assert r["out"] == PAD_UNTOUCHED
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("dim,hand,team,held,out", [
    (NETHER, "MAIN_HAND", LOCKED, {"main": AIR, "off": AIR},
     {"cancel": True, "unlock": False, "shrink": None, "message": MSG_LOCKED, "error": None}),
    (NETHER, "MAIN_HAND", LOCKED, {"main": KEY, "off": AIR},
     {"cancel": True, "unlock": True, "shrink": "MAIN_HAND", "message": MSG_UNLOCKED, "error": None}),
    (NETHER, "OFF_HAND", LOCKED, {"main": AIR, "off": KEY},
     {"cancel": True, "unlock": False, "shrink": None, "message": None, "error": None}),
    (END, "MAIN_HAND", UNLOCKED, {"main": AIR, "off": AIR},
     {"cancel": True, "unlock": False, "shrink": None, "message": MSG_BEYOND, "error": None}),
])
def test_pad_has_no_game_mode_exemption(dim, hand, team, held, out):
    """Spec §4.2: the pad rules hold "in every game mode (no creative exemption at the pad)" (D109). Given an exempt callback
    that says yes, the pad rule never calls it and still cancels."""
    r = decide("pad", dim=dim, hand=hand, team=team, held=held, exempt=True)
    assert r["out"] == out
    assert r["calls"]["exempt"] == 0


@needs_node
@pytest.mark.parametrize("team,held", [("throw", {"main": KEY, "off": AIR}), (LOCKED, "throw")])
def test_pad_error_fails_closed_and_keeps_the_key(team, held):
    r = decide("pad", dim=NETHER, hand="MAIN_HAND", team=team, held=held)
    out = r["out"]
    assert (out["cancel"], out["unlock"], out["shrink"], out["message"]) == (True, False, None, None)
    assert "boom" in out["error"]


# ---- §4.3 travel check ----------------------------------------------------------------------------------------------

@needs_node
@pytest.mark.parametrize("team", [UNLOCKED, LOCKED, NO_TEAM])
def test_travel_beyond_is_closed_to_everyone_without_a_team_lookup(team):
    r = decide("travel", dest=BEYOND, exempt=False, team=team)
    assert r["out"] == {"cancel": True, "message": MSG_BEYOND, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("team,cancel,message", [(UNLOCKED, False, None), (LOCKED, True, MSG_TEAM), (NO_TEAM, True, MSG_TEAM)])
def test_travel_other_follows_the_team(team, cancel, message):
    r = decide("travel", dest=OTHER, exempt=False, team=team)
    assert r["out"] == {"cancel": cancel, "message": message, "error": None}
    assert r["calls"]["team"] == 1


@needs_node
@pytest.mark.parametrize("dest", [OTHER, BEYOND])
def test_travel_creative_and_spectator_are_exempt(dest):
    r = decide("travel", dest=dest, exempt=True, team=LOCKED)
    assert r["out"] == {"cancel": False, "message": None, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("dest", [NETHER, OVERWORLD, END, MINING, MOON])
def test_travel_other_destinations_are_untouched_and_read_nothing(dest):
    r = decide("travel", dest=dest, exempt=False, team=LOCKED)
    assert r["out"] == {"cancel": False, "message": None, "error": None}
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("dest,exempt,team", [(OTHER, False, "throw"), (OTHER, "throw", UNLOCKED), (BEYOND, "throw", UNLOCKED)])
def test_travel_error_fails_closed_for_the_two_gated_dimensions(dest, exempt, team):
    out = decide("travel", dest=dest, exempt=exempt, team=team)["out"]
    assert out["cancel"] is True and out["message"] is None and "boom" in out["error"]


@needs_node
@pytest.mark.parametrize("dest,cancel", [(OTHER, True), (BEYOND, True), (NETHER, False), (MOON, False), (None, False)])
def test_travel_outer_error_cancels_only_the_gated_dimensions(dest, cancel):
    out = decide("travelError", dest=dest)["out"]
    assert out == {"cancel": cancel, "message": None, "error": "Error: outer boom"}


# ---- §4.4 arrival check ---------------------------------------------------------------------------------------------

@needs_node
@pytest.mark.parametrize("team", [UNLOCKED, LOCKED, NO_TEAM])
def test_arrival_beyond_always_sends_to_spawn(team):
    r = decide("arrival", dest=BEYOND, exempt=False, team=team)
    assert r["out"] == {"sendToSpawn": True, "message": MSG_BEYOND, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("team,send,message", [(UNLOCKED, False, None), (LOCKED, True, MSG_TEAM), (NO_TEAM, True, MSG_TEAM)])
def test_arrival_other_follows_the_team(team, send, message):
    r = decide("arrival", dest=OTHER, exempt=False, team=team)
    assert r["out"] == {"sendToSpawn": send, "message": message, "error": None}


@needs_node
@pytest.mark.parametrize("dest", [OTHER, BEYOND])
def test_arrival_creative_and_spectator_are_exempt(dest):
    r = decide("arrival", dest=dest, exempt=True, team=LOCKED)
    assert r["out"] == {"sendToSpawn": False, "message": None, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("dest", [NETHER, OVERWORLD, END, MINING, MOON])
def test_arrival_other_destinations_are_untouched_and_read_nothing(dest):
    r = decide("arrival", dest=dest, exempt=False, team=LOCKED)
    assert r["out"] == {"sendToSpawn": False, "message": None, "error": None}
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("dest,exempt,team,message", [(OTHER, False, "throw", MSG_TEAM), (OTHER, "throw", UNLOCKED, MSG_TEAM),
                                                     (BEYOND, "throw", UNLOCKED, MSG_BEYOND)])
def test_arrival_error_treats_the_team_as_locked(dest, exempt, team, message):
    out = decide("arrival", dest=dest, exempt=exempt, team=team)["out"]
    assert out["sendToSpawn"] is True and out["message"] == message and "boom" in out["error"]


@needs_node
@pytest.mark.parametrize("dest,send,message", [(OTHER, True, MSG_TEAM), (BEYOND, True, MSG_BEYOND), (NETHER, False, None),
                                               (None, False, None)])
def test_arrival_outer_error_moves_only_from_the_gated_dimensions(dest, send, message):
    out = decide("arrivalError", dest=dest)["out"]
    assert out == {"sendToSpawn": send, "message": message, "error": "Error: outer boom"}


# ---- one shared scope -----------------------------------------------------------------------------------------------

# A column-0 declaration of one name: const, let, var, class, or a function (async, generator or plain).
TOP_LEVEL = re.compile(r"^(?:(?:const|let|var|class)\s+|(?:async\s+)?function\s*\*?\s*)([A-Za-z_$][\w$]*)", re.M)
DESTRUCTURING = re.compile(r"^(?:const|let|var)\s*[\[{]", re.M)
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
# After one of these, a '/' starts a regex literal; after anything else (a name, number, ')' or ']') it divides.
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^") | {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void",
                                            "throw", "instanceof"}


def blank(src):
    """src with every comment, and the inside of every string, template and regex literal, turned into spaces (newlines
    kept), so what is left is code at its own line and column. A '/*' inside a line comment (a path such as data/*/recipe)
    therefore opens nothing."""
    out, i, n, prev = list(src), 0, len(src), None

    def wipe(a, b):
        for k in range(a, min(b, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            wipe(i, j)
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            wipe(i, j)
            i = j
        elif c in "'\"`":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            wipe(i + 1, j)
            i, prev = j + 1, "str"
        elif c == "/" and (prev is None or prev in REGEX_AFTER):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n" and (src[j] != "/" or in_class):
                if src[j] == "\\":
                    j += 1
                elif src[j] in "[]":
                    in_class = src[j] == "["
                j += 1
            wipe(i + 1, j)
            i, prev = j + 1, "regex"
        elif IDENT.match(src, i):
            m = IDENT.match(src, i)
            i, prev = m.end(), m.group()
        else:
            i, prev = i + 1, (prev if c.isspace() else c)
    return "".join(out)


def top_level_names(src, where):
    """(names, problems) for one script: the name each column-0 declaration declares, and every column-0 declaration that
    this check cannot read as exactly one name (a destructuring pattern, or a second declarator after a top-level comma)."""
    code = blank(src)

    def line(pos):
        return code.count("\n", 0, pos) + 1

    problems = [f"{where}:{line(m.start())}: a destructuring declaration at the top level; declare one name per statement"
                for m in DESTRUCTURING.finditer(code)]
    names = []
    for m in TOP_LEVEL.finditer(code):
        names.append(m.group(1))
        depth, i = 0, m.end()
        while i < len(code) and not (depth == 0 and code[i] in ";\n"):
            depth += (code[i] in "([{") - (code[i] in ")]}")
            if code[i] == "," and depth == 0:
                problems.append(f"{where}:{line(m.start())}: '{m.group(1)}' is followed by a second declarator; declare one "
                                "name per statement")
                break
            i += 1
    return names, problems


def test_server_script_top_level_names_are_unique():
    """KubeJS 2101 runs every server script in one scope (HANDOFF §6): a top-level name may be declared only once."""
    seen, problems = {}, []
    for path in sorted(SERVER_SCRIPTS.rglob("*.js")):
        rel = str(path.relative_to(SERVER_SCRIPTS))
        names, bad = top_level_names(path.read_text(encoding="utf-8"), rel)
        problems += bad
        for name in names:
            seen.setdefault(name, []).append(rel)
    assert problems == [], "top-level declarations this check cannot read as one name each:\n" + "\n".join(problems)
    dupes = {name: files for name, files in seen.items() if len(files) > 1}
    assert dupes == {}, f"declared at the top level of more than one server script (one shared scope): {dupes}"
    assert seen["OTHER_GATE"] == ["lib/other_gate.js"]
    assert seen["OTHER_GATE_MC"] == ["events.js"]


def test_top_level_scanner_reads_every_declaration_form():
    """The red case for the scanner above: each declaration form is read, comments and literals hide nothing and invent
    nothing, and destructuring or a second declarator is reported with its line."""
    src = "\n".join([
        "// a path in a line comment, data/*/recipe/**, opens no block comment",   # 1
        "const VISIBLE = 1",                                                          # 2
        "/*",                                                                         # 3
        "const HIDDEN = 1",                                                           # 4
        "*/",                                                                         # 5
        "let s = '/* not a comment', t0 = 0",                                         # 6
        "class Klass {}",                                                             # 7
        "async function asyncFn(a, b) { return a, b }",                               # 8
        "function* gen() {}",                                                         # 9
        "function *gen2() {}",                                                        # 10
        "let re = /x\\/*/g, second = 2",                                              # 11
        "const { picked } = VISIBLE",                                                 # 12
        "const list = [1, 2], third = 3",                                             # 13
        "const obj = {",                                                              # 14
        "  a: 1, b: [2, 3],",                                                         # 15
        "}",                                                                          # 16
        "var last = f(1,",                                                            # 17
        "  2)",                                                                       # 18
        "",
    ])
    names, problems = top_level_names(src, "x.js")
    assert names == ["VISIBLE", "s", "Klass", "asyncFn", "gen", "gen2", "re", "list", "obj", "last"]
    assert [p.split(":")[1] for p in problems] == ["12", "6", "11", "13"], problems
