"""tools/gamerules.toml against the jars it cites, and the two KubeJS scripts against it (v0.3 Task 11d, D137).

The pin is the list of game rules every boot must register: tools/check_boot_log.py compares the detector's line with it. It
holds 51 vanilla names (GameRules.<clinit>), three Twilight Forest ids and one Accessories id, and every GameRules.register
call site in the server's mod jars. These tests re-read each from the bytecode with tools/scan_gamerules.py, so a mod update
that adds, drops or moves a game rule fails here (the drift test) before a boot does:
- the register call sites in .run/server/mods, jar-in-jar included, are exactly the [[register_call]] pins;
- each modded id is the string the pinned ldc loads, and the Twilight Forest supplier fields exist;
- the vanilla names are GameRules.<clinit>'s, in order, and NeoForge does not patch GameRules.
The two KubeJS scripts run for real, under node with stubs (tools/tests/gamerule_scripts_harness.js): the guard's fail-loud cases
and its reload, the detector's two instances, and each script's logged line read by check_boot_log's own code.
The jar tests skip only when no server has been booted from this clone (kjs.JAR_SKIP); with a server there, a jar missing
from where these tests read it fails. The scanner's own tests use class files assembled here, and the script tests need only
node and kubejs/, so both run in any clone.
"""
import functools
import io
import json
import re
import struct
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

from kjs import JAR_SKIP, MODS, PW_MODS, ROOT, node_fixture  # noqa: F401 (node_fixture provides the `node` fixture)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_boot_log  # noqa: E402
import scan_gamerules  # noqa: E402

GUARD = ROOT / "kubejs" / "startup_scripts" / "tf_gamerules_guard.js"
DETECTOR = ROOT / "kubejs" / "server_scripts" / "gamerules.js"
LIBRARIES = MODS.parent / "libraries"
SRG = LIBRARIES / "net/minecraft/server/1.21.1-20240808.144430/server-1.21.1-20240808.144430-srg.jar"
HARNESS = ROOT / "tools" / "tests" / "gamerule_scripts_harness.js"
GR = "net/minecraft/world/level/GameRules"
REGISTER_DESC = f"(Ljava/lang/String;L{GR}$Category;L{GR}$Type;)L{GR}$Key;"


@functools.cache
def pin():
    """tools/gamerules.toml, read when a test asks: a bad pin fails those tests and does not stop pytest at collection."""
    return check_boot_log.load_gamerules()


def neoforge_jar(pack_toml=ROOT / "pack.toml"):
    """The NeoForge -server jar of the version pack.toml names."""
    with open(pack_toml, "rb") as f:
        version = tomllib.load(f)["versions"]["neoforge"]
    return LIBRARIES / f"net/neoforged/neoforge/{version}/neoforge-{version}-server.jar"


# ---- a class-file assembler for the scanner's own tests ------------------------------------------------------------------

class Pool:
    """A constant pool: each method returns the index of its entry, adding it once."""

    def __init__(self):
        self.entries, self.index = [], {}

    def _add(self, key, raw):
        if key not in self.index:
            self.entries.append(raw)
            self.index[key] = len(self.entries)
        return self.index[key]

    def utf8(self, s):
        b = s.encode()
        return self._add(("utf8", s), b"\x01" + struct.pack(">H", len(b)) + b)

    def cls(self, name):
        return self._add(("class", name), b"\x07" + struct.pack(">H", self.utf8(name)))

    def string(self, s):
        return self._add(("string", s), b"\x08" + struct.pack(">H", self.utf8(s)))

    def nat(self, name, desc):
        return self._add(("nat", name, desc), b"\x0c" + struct.pack(">HH", self.utf8(name), self.utf8(desc)))

    def method(self, owner, name, desc):
        return self._add(("method", owner, name, desc), b"\x0a" + struct.pack(">HH", self.cls(owner), self.nat(name, desc)))

    def handle(self, owner, name, desc):
        return self._add(("handle", owner, name, desc), b"\x0f\x06" + struct.pack(">H", self.method(owner, name, desc)))

    def long(self, value):   # takes two slots, as in a real pool
        i = self._add(("long", value), b"\x05" + struct.pack(">q", value))
        self.entries.append(None)
        return i


def classfile(name, methods, fields=(), extra=None):
    """A class file named `name` with static methods [(method name, code)] or [(method name, code, descriptor)] (code a function
    of the Pool returning bytes; the descriptor defaults to ()V), the fields `fields` [(name, descriptor)] or [(name, descriptor,
    access flags)] (the flags default to public static final), and extra(pool) run first so its entries come before the
    methods'."""
    pool = Pool()
    if extra:
        extra(pool)
    this, sup = pool.cls(name), pool.cls("java/lang/Object")
    code_name = pool.utf8("Code")
    built = [(pool.utf8(m), pool.utf8(d[0] if d else "()V"), code(pool)) for m, code, *d in methods]
    fs = [(pool.utf8(f), pool.utf8(d), a[0] if a else 0x19) for f, d, *a in fields]
    out = b"\xca\xfe\xba\xbe" + struct.pack(">HHH", 0, 65, len(pool.entries) + 1)
    out += b"".join(e for e in pool.entries if e is not None)
    out += struct.pack(">HHHH", 0x21, this, sup, 0)
    out += struct.pack(">H", len(fs)) + b"".join(struct.pack(">HHHH", a, n, d, 0) for n, d, a in fs)
    out += struct.pack(">H", len(built))
    for n, d, code in built:
        attr = struct.pack(">HHI", 4, 4, len(code)) + code + struct.pack(">HH", 0, 0)
        out += struct.pack(">HHHH", 0x09, n, d, 1) + struct.pack(">HI", code_name, len(attr)) + attr
    return out + struct.pack(">H", 0)


def ldc(pool, s):
    i = pool.string(s)
    return b"\x12" + bytes([i]) if i < 256 else b"\x13" + struct.pack(">H", i)


def invoke(pool, owner=GR, name="register", desc=REGISTER_DESC, op=0xb8):
    return bytes([op]) + struct.pack(">H", pool.method(owner, name, desc))


def register_code(rule):
    """ldc rule; getstatic-free stand-ins for the category and type (aconst_null x2); invokestatic register; pop; return."""
    return lambda pool: ldc(pool, rule) + b"\x01\x01" + invoke(pool) + b"\x57\xb1"


def jar_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


# ---- the scanner, on assembled classes --------------------------------------------------------------------------------

def test_a_register_call_is_found_with_its_offset_and_rule():
    b = classfile("a/Rules", [("init", register_code("a.rule"))])
    assert scan_gamerules.class_register_calls(b) == [("a/Rules", "init", 4)]
    assert scan_gamerules.ldc_string(b, "init", 0) == "a.rule"
    assert scan_gamerules.ldc_string(b, "init", 2) is None          # aconst_null, not an ldc
    assert scan_gamerules.register_sites(b, "init") == [(4, "a.rule")]
    assert scan_gamerules.register_names(b, "init") == ["a.rule"]


def test_each_call_gets_the_string_loaded_since_the_previous_one():
    def code(pool):
        two = ldc(pool, "first") + b"\x01\x01" + invoke(pool) + b"\x57" + ldc(pool, "second") + b"\x01\x01" + invoke(pool) + b"\x57"
        return two + b"\x01\x01\x01" + invoke(pool) + b"\x57\xb1"          # a third call with no ldc of its own
    b = classfile("a/Three", [("init", code)])
    assert scan_gamerules.register_sites(b, "init") == [(4, "first"), (12, "second"), (19, None)]


def test_a_wide_ldc_and_a_two_slot_constant_are_read():
    """ldc_w (a pool index over 255) and a long, which takes two pool slots, before the string."""
    def fill(pool):
        pool.long(7)
        for i in range(300):
            pool.utf8(f"filler{i}")
    b = classfile("a/Wide", [("init", register_code("wide.rule"))], extra=fill)
    assert scan_gamerules.class_register_calls(b) == [("a/Wide", "init", 5)]
    assert scan_gamerules.register_names(b, "init") == ["wide.rule"]


def test_a_switch_before_the_call_keeps_the_offsets_right():
    """tableswitch and lookupswitch pad to a 4-byte boundary and have variable length; the call after them is still found."""
    def code(pool):
        table = b"\x03\xaa" + b"\x00\x00" + struct.pack(">iii", 20, 0, 1) + struct.pack(">ii", 20, 20)   # iconst_0 at 0
        look = b"\x03\xab" + b"\x00\x00" + struct.pack(">ii", 20, 1) + struct.pack(">ii", 5, 20)
        return table + look + ldc(pool, "after.switch") + b"\x01\x01" + invoke(pool) + b"\x57\xb1"
    b = classfile("a/Switch", [("init", code)])
    (site,) = scan_gamerules.class_register_calls(b)
    assert site[2] == 24 + 20 + 4 and scan_gamerules.register_names(b, "init") == ["after.switch"]


def test_a_wide_iinc_before_the_call_keeps_the_offsets_and_the_id():
    """wide iinc is 6 bytes. Its last two bytes (a nop, then sipush) would swallow the ldc if it were read as 4."""
    def code(pool):
        return b"\xc4\x84\x00\x01\x00\x11" + ldc(pool, "after.iinc") + b"\x01\x01" + invoke(pool) + b"\x57\xb1"
    b = classfile("a/WideIinc", [("init", code)])
    assert scan_gamerules.register_sites(b, "init") == [(10, "after.iinc")]
    assert [pc for pc, _, _ in scan_gamerules.instructions(code(Pool()))][:2] == [0, 6]


def test_a_wide_iload_before_the_call_keeps_the_offsets_and_the_id():
    """wide iload is 4 bytes. Read as 6, it would skip the ldc after it."""
    def code(pool):
        return b"\xc4\x15\x00\x01" + ldc(pool, "after.iload") + b"\x01\x01" + invoke(pool) + b"\x57\xb1"
    b = classfile("a/WideIload", [("init", code)])
    assert scan_gamerules.register_sites(b, "init") == [(8, "after.iload")]
    assert [pc for pc, _, _ in scan_gamerules.instructions(code(Pool()))][:2] == [0, 4]


def test_an_invokeinterface_before_the_call_keeps_the_offsets_and_the_id():
    """invokeinterface has 4 operand bytes (index, count, 0). Its count here is 0x11, sipush, which would swallow the 0 and the ldc
    if the operands were read short."""
    def code(pool):
        return (b"\x01\xb9" + struct.pack(">H", pool.method("a/I", "m", "()V")) + b"\x11\x00" + ldc(pool, "after.interface")
                + b"\x01\x01" + invoke(pool) + b"\x57\xb1")
    b = classfile("a/Iface", [("init", code)])
    assert scan_gamerules.register_sites(b, "init") == [(10, "after.interface")]


def test_a_class_under_net_minecraft_in_a_mod_jar_is_reported():
    """A mod's class in the net/minecraft/ package registers a rule like any other: the scan reads mod jars only, and
    vanilla's own <clinit> is read directly."""
    b = classfile("net/minecraft/modded/Rules", [("init", register_code("mc.rule"))])
    assert scan_gamerules.class_register_calls(b) == [("net/minecraft/modded/Rules", "init", 4)]


def overloads():
    return classfile("a/Over", [("register", register_code("one.rule")), ("register", register_code("two.rule"), "(I)V")])


def test_overloaded_methods_each_report_their_own_site():
    assert scan_gamerules.class_register_calls(overloads()) == [("a/Over", "register", 4), ("a/Over", "register", 4)]


def test_the_cli_lists_each_overload_with_its_own_id(tmp_path, capsys):
    """Twilight Forest's TFGameRules already has two methods named register, so a call site in one must not stop the listing."""
    (tmp_path / "o-1.jar").write_bytes(jar_bytes({"a/Over.class": overloads()}))
    assert scan_gamerules.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["o-1.jar :: a/Over.register @4 registers [one.rule]",
                                                    "o-1.jar :: a/Over.register @4 registers [two.rule]",
                                                    "2 GameRules.register call site(s) in 1 jar(s)"]


@pytest.mark.parametrize("make", ["missing", "file"])
def test_the_cli_refuses_a_path_that_is_not_a_directory(tmp_path, capsys, make):
    """A mistyped path must not read as a clean scan (0 sites, exit 0)."""
    target = tmp_path / "mods"
    if make == "file":
        target.write_text("not a directory")
    assert scan_gamerules.main([str(target)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and f"NO MODS DIRECTORY {target}" in captured.err


def test_other_register_methods_are_not_reported():
    def code(pool):
        return (b"\x01\x01\x01" + invoke(pool, owner="a/Other") + b"\x57"          # another class's register
                + invoke(pool, name="registerOther") + b"\x57"                       # another GameRules method
                + b"\x01" + invoke(pool, name="<init>", desc="()V", op=0xb7) + b"\xb1")
    assert scan_gamerules.class_register_calls(classfile("a/Quiet", [("init", code)])) == []


def test_a_method_handle_to_register_is_reported():
    """GameRules::register passed as a function is a register call the bytecode walk would not see."""
    b = classfile("a/Ref", [("init", lambda pool: b"\xb1")], extra=lambda pool: pool.handle(GR, "register", REGISTER_DESC))
    assert scan_gamerules.class_register_calls(b) == [("a/Ref", "<method handle>", -1)]


def test_jar_in_jar_call_sites_name_both_jars(tmp_path):
    inner = jar_bytes({"b/Inner.class": classfile("b/Inner", [("setup", register_code("inner.rule"))])})
    outer = jar_bytes({"a/Outer.class": classfile("a/Outer", [("init", register_code("outer.rule"))]),
                       "META-INF/jarjar/inner-1.0.jar": inner, "a/Plain.class": classfile("a/Plain", [])})
    (tmp_path / "outer-1.0.jar").write_bytes(outer)
    (tmp_path / "notes.txt").write_text("not a jar")
    assert scan_gamerules.register_calls(tmp_path) == [
        ("outer-1.0.jar", "a/Outer", "init", 4),
        ("outer-1.0.jar!META-INF/jarjar/inner-1.0.jar", "b/Inner", "setup", 4)]
    assert scan_gamerules.ldc_string(scan_gamerules.read_class(tmp_path, "outer-1.0.jar!META-INF/jarjar/inner-1.0.jar",
                                                               "b/Inner"), "setup", 0) == "inner.rule"


def test_static_fields_lists_only_static_fields():
    """The guard reads TFGameRules' suppliers as static fields, so an instance field of that name would not do."""
    b = classfile("a/F", [], fields=[("RULE", "Ljava/util/function/Supplier;"), ("N", "I"),
                                     ("INSTANCE", "Ljava/util/function/Supplier;", 0x0011)])
    assert scan_gamerules.static_fields(b) == {"RULE": "Ljava/util/function/Supplier;", "N": "I"}


def test_the_cli_lists_the_call_sites(tmp_path, capsys):
    (tmp_path / "x-1.jar").write_bytes(jar_bytes({"a/X.class": classfile("a/X", [("init", register_code("x.rule"))])}))
    assert scan_gamerules.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["x-1.jar :: a/X.init @4 registers [x.rule]",
                                                    "1 GameRules.register call site(s) in 1 jar(s)"]


# ---- the pin against the pack's own files -----------------------------------------------------------------------------

def pw_filename(pw_toml):
    with open(PW_MODS / pw_toml, "rb") as f:
        return tomllib.load(f)["filename"]


def test_the_pinned_jars_are_the_shipped_ones():
    """A packwiz update to either mod fails here, before any boot: re-read its game rules and update tools/gamerules.toml."""
    shipped = {"twilightforest": pw_filename("the-twilight-forest.pw.toml"), "accessories": pw_filename("aether.pw.toml")}
    for entry in pin().modded + pin().register_calls:
        outer = entry["jar"].split("!")[0]
        assert outer in shipped.values(), f"{entry} names {outer}, not a shipped jar ({shipped})"
    assert {m["mod"]: m["jar"].split("!")[0] for m in pin().modded} == shipped


def test_every_modded_id_has_one_register_call_pin():
    pinned = [i for call in pin().register_calls for i in call["ids"]]
    assert sorted(pinned) == sorted(m["id"] for m in pin().modded)


def script_array(text, name):
    m = re.search(rf"const {name} = \[([^\]]*)\]", text)
    assert m, f"no `const {name} = [...]`"
    return re.findall(r"'([^']*)'", m.group(1))


def test_the_guard_resolves_the_pinned_twilight_forest_rules():
    text = GUARD.read_text()
    tf = [m for m in pin().modded if m["mod"] == "twilightforest"]
    assert script_array(text, "TF_IDS") == [m["id"] for m in tf]
    assert script_array(text, "FIELDS") == [m["field"] for m in tf]
    assert "Java.loadClass('twilightforest.init.TFGameRules')" in text


# ---- the two real scripts, under node with stubs ----------------------------------------------------------------------------

def harness(node, mode, scenario):
    res = subprocess.run([node, str(HARNESS), mode, str(ROOT / "kubejs")], input=json.dumps(scenario), capture_output=True,
                         text=True, cwd=ROOT, timeout=120)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def tf():
    return [m for m in pin().modded if m["mod"] == "twilightforest"]


def tf_ids():
    return [m["id"] for m in tf()]


def good_suppliers():
    return {m["field"]: {"id": m["id"], "registers": True} for m in tf()}


def guard(node, *runs, rules=None, suppliers=None):
    """One simulated JVM, one script run per item of `runs` (the harness's header has the scenario). The defaults are the shipped
    state: vanilla's 51 rules, and three good suppliers."""
    return harness(node, "guard", {"rules": pin().vanilla if rules is None else rules,
                                   "suppliers": good_suppliers() if suppliers is None else suppliers,
                                   "runs": list(runs) or [{}]})["runs"]


def ok_line():
    return ("confluence tf-gamerules guard OK: registered " + ", ".join(tf_ids()) + " before Twilight Forest construction (rules "
            "51 -> 54)")


def reload_line():
    return ("confluence tf-gamerules guard: startup scripts reloaded; the first run in this JVM registered " + ", ".join(tf_ids())
            + " (rules 51 -> 54), still registered (rules 54); the order check runs only on the first run")


def startup_header(text, level="INFO"):
    """`text` as latest.log carries a startup script's console line (check_boot_log's docstring has a real one)."""
    return f"[02Oct2026 18:59:31.625] [modloading-worker-0/{level}] [KubeJS Startup/]: startup_scripts:{GUARD.name}#112: {text}\n"


def server_header(text):
    return f"[02Oct2026 18:59:40.000] [Server thread/INFO] [KubeJS Server/]: {text}\n"


def assert_failed_loud(run, why):
    """A throw whose message says why, nothing logged, and no record: the guard's failure is what stops the server (D137)."""
    assert run["threw"] and "confluence tf-gamerules guard FAILED: " in run["threw"] and why in run["threw"], run
    assert run["logs"] == [] and run["record"] is None, run


def test_a_clean_first_run_registers_the_three_rules_and_logs_the_ok_line(node):
    (run,) = guard(node)
    assert run["threw"] is None, run
    assert run["logs"] == [{"level": "info", "text": ok_line()}]
    assert run["rules"] == sorted(pin().vanilla + tf_ids())
    assert run["record"] == "rules 51 -> 54"


@pytest.mark.parametrize("index", range(3))
def test_a_twilight_forest_rule_already_registered_throws(node, index):
    """Check (1): the fml.toml edge is missing, so Twilight Forest's tasks ran first."""
    rule = ["tfEnforcedProgression", "playersTfPortalDefaultDelay", "playersTfPortalCreativeDelay"][index]
    (run,) = guard(node, rules=pin().vanilla + [rule])
    assert_failed_loud(run, f"Twilight Forest registered [{rule}] before this script ran")
    assert run["rules"] == sorted(pin().vanilla + [rule])    # it threw before it resolved a supplier


@pytest.mark.parametrize("index", range(3))
def test_a_missing_supplier_field_throws(node, index):
    """Check (2): a renamed field. The field reads as undefined here; a field read that throws is the next test."""
    suppliers = good_suppliers()
    field = list(suppliers)[index]
    del suppliers[field]
    (run,) = guard(node, suppliers=suppliers)
    assert_failed_loud(run, f"TFGameRules.{field} is null or missing (expected the supplier of {tf_ids()[index]})")


def test_a_null_supplier_field_throws(node):
    suppliers = good_suppliers()
    field = list(suppliers)[0]
    suppliers[field] = {"null": True}
    (run,) = guard(node, suppliers=suppliers)
    assert_failed_loud(run, f"TFGameRules.{field} is null or missing")


def test_a_supplier_field_whose_read_throws_is_reported_by_name(node):
    suppliers = good_suppliers()
    field = list(suppliers)[1]
    suppliers[field] = {"throws": True}
    (run,) = guard(node, suppliers=suppliers)
    assert_failed_loud(run, f"TFGameRules has no field {field} for {tf_ids()[1]}")


def test_a_supplier_returning_another_id_throws(node):
    """Check (2): the ids differ. The other id is registered, so only the comparison can catch this."""
    suppliers = good_suppliers()
    field = list(suppliers)[0]
    suppliers[field] = {"id": "somethingElse", "registers": True}
    (run,) = guard(node, suppliers=suppliers)
    assert_failed_loud(run, f"the suppliers returned [somethingElse, {tf_ids()[1]}, {tf_ids()[2]}]")


def test_rules_still_missing_after_resolving_throws(node):
    """Check (3): the suppliers return the right keys, and a rule is not in a fresh GameRules() afterwards."""
    suppliers = good_suppliers()
    field = list(suppliers)[2]
    suppliers[field]["registers"] = False
    (run,) = guard(node, suppliers=suppliers)
    assert_failed_loud(run, f"[{tf_ids()[2]}] not registered after resolving the suppliers")


def failing_jvm(kind):
    """guard()'s keywords for a JVM whose first run fails, by check."""
    suppliers = good_suppliers()
    field = list(suppliers)[0]
    if kind == "already registered":
        return {"rules": pin().vanilla + [tf_ids()[0]]}, "before this script ran", "before this script ran"
    if kind == "missing field":
        del suppliers[field]
        return {"suppliers": suppliers}, "is null or missing", "is null or missing"
    # In the other two the failed run has already registered Twilight Forest rules, so the re-run fails at check (1).
    if kind == "wrong id":
        suppliers[field] = {"id": "somethingElse", "registers": True}
        return {"suppliers": suppliers}, "the suppliers returned", "before this script ran"
    suppliers[field]["registers"] = False
    return {"suppliers": suppliers}, "not registered after resolving", "before this script ran"


@pytest.mark.parametrize("kind", ["already registered", "missing field", "wrong id", "rule not registered"])
def test_a_rerun_after_a_failed_first_run_still_throws(node, kind):
    """The record is only for a first run that passed, so a failure cannot turn into a passing reload."""
    keywords, first_why, second_why = failing_jvm(kind)
    first, second = guard(node, {}, {}, **keywords)
    assert_failed_loud(first, first_why)
    assert_failed_loud(second, second_why)


def test_a_rerun_after_a_good_first_run_logs_the_reload_line(node):
    """`/kubejs reload startup-scripts`: the rules are there from the first run, which is no error, and is no second OK line."""
    first, second = guard(node, {}, {})
    assert second["threw"] is None, second
    assert second["logs"] == [{"level": "info", "text": reload_line()}]
    assert "guard OK" not in second["logs"][0]["text"]
    assert second["record"] == first["record"] == "rules 51 -> 54"
    assert second["rules"] == first["rules"]


def test_a_reload_still_checks_the_supplier_fields(node):
    field = tf()[0]["field"]
    _, second = guard(node, {}, {"suppliers": {field: {"null": True}}})
    assert second["threw"] and f"TFGameRules.{field} is null or missing" in second["threw"]
    assert second["logs"] == []


def test_a_reload_still_checks_the_rules_are_registered(node):
    rule = tf_ids()[1]
    _, second = guard(node, {}, {"removeRules": [rule]})
    assert second["threw"] and f"[{rule}] not registered after resolving" in second["threw"]
    assert second["logs"] == []


def detector(node, server, registry):
    return harness(node, "detector", {"server": server, "registry": registry})


def test_the_detector_reads_the_server_instance_and_a_fresh_one(node):
    """The two stubs hold different sets, in no order: each list shows its own instance's names, sorted."""
    out = detector(node, ["c", "a", "b"], ["z", "a"])
    assert out["handlers"] == 1
    assert out["logs"] == [{"level": "log", "text": "confluence gamerules: server 3 [a,b,c]; registry 2 [a,z]"}]


def test_a_real_good_boot_passes_check_boot_log(node):
    """What the two scripts really log, on a good boot, read by the checker's own code: one guard OK line, 55 and 55."""
    expected = check_boot_log.expected_gamerules(pin())
    (run,) = guard(node)
    names = sorted(expected)
    line = detector(node, names, names)["logs"][0]["text"]
    log = startup_header(run["logs"][0]["text"]) + server_header(line)
    assert check_boot_log.gamerule_problems(log, expected) == ("game rules: 55 expected, server 55, registry 55, guard OK", [])


def test_the_reload_line_is_not_a_guard_ok_line(node):
    """A reload adds a line the checker's exactly-one count must not see, or a reload before a stop would fail the boot check."""
    expected = check_boot_log.expected_gamerules(pin())
    first, second = guard(node, {}, {})
    names = sorted(expected)
    log = (startup_header(first["logs"][0]["text"]) + startup_header(second["logs"][0]["text"])
           + server_header(detector(node, names, names)["logs"][0]["text"]))
    assert check_boot_log.gamerule_problems(log, expected) == ("game rules: 55 expected, server 55, registry 55, guard OK", [])


def test_a_real_detector_line_with_different_sets_fails_check_boot_log(node):
    expected = check_boot_log.expected_gamerules(pin())
    lost = "playersSleepingPercentage"
    server = sorted(expected - {lost})
    line = detector(node, server, sorted(expected))["logs"][0]["text"]
    (run,) = guard(node)
    log = startup_header(run["logs"][0]["text"]) + server_header(line)
    summary, problems = check_boot_log.gamerule_problems(log, expected)
    assert summary == "game rules: 55 expected, server 54, registry 55, guard OK, 2 bad"
    assert problems == [f"GAMERULES latest.log:2: server missing [{lost}], unexpected []",
                        f"GAMERULES latest.log:2: server and registry differ: only in server [], only in registry [{lost}]"]


# ---- the pin against the jars (the drift test) ------------------------------------------------------------------------

def need(path):
    """`path`, once a server has been booted from this clone. Then the path must exist, as in kjs.pinned_jar: a jar that moved is
    a changed premise, not a clone without jars."""
    if not MODS.is_dir():
        pytest.skip(f"{MODS} {JAR_SKIP}")
    assert path.exists(), (f"{path} does not exist, but {MODS} does, so this test no longer reads what it was written against: "
                           "recheck the test's premise against the server's libraries and update the constant in this file")
    return path


def test_need_skips_only_when_no_server_was_booted(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "MODS", tmp_path / "no-mods")
    with pytest.raises(pytest.skip.Exception, match="no server has been booted"):
        need(tmp_path / "absent.jar")


def test_need_fails_on_a_missing_library_jar(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.modules[__name__], "MODS", tmp_path)
    # BaseException: pytest's skip is one, and an escaped skip would mark this test skipped instead of failing it.
    with pytest.raises(BaseException) as raised:
        need(tmp_path / "absent.jar")
    assert raised.type is AssertionError and "recheck the test's premise" in str(raised.value)
    assert need(tmp_path) == tmp_path


def test_the_neoforge_path_follows_pack_toml(tmp_path):
    toml = tmp_path / "pack.toml"
    toml.write_text('[versions]\nneoforge = "21.1.999"\n')
    assert neoforge_jar(toml) == LIBRARIES / "net/neoforged/neoforge/21.1.999/neoforge-21.1.999-server.jar"


@pytest.fixture(scope="module")
def call_sites():
    need(MODS)
    return scan_gamerules.register_calls(MODS)


def test_the_register_call_sites_are_the_pinned_ones(call_sites):
    """Every GameRules.register call in a server mod jar, jar-in-jar included. A new one is a new game rule (pin it, after
    reading its id with javap -c); a missing one is a rule gone or moved (Twilight Forest's fix would move its three)."""
    pinned = sorted((c["jar"], c["class"], c["method"], c["offset"]) for c in pin().register_calls)
    assert sorted(call_sites) == pinned


def test_each_pinned_call_registers_its_ids():
    for call in pin().register_calls:
        b = scan_gamerules.read_class(need(MODS), call["jar"], call["class"])
        if call["method"].startswith("lambda$"):
            # Twilight Forest's lambda takes the id as an argument; the ids' ldc offsets are in <clinit> ([[modded]] entries).
            assert scan_gamerules.register_names(b, call["method"]) == [None]
        else:
            assert scan_gamerules.register_names(b, call["method"]) == call["ids"]


def test_each_modded_id_is_the_ldc_at_its_pinned_offset():
    for m in pin().modded:
        b = scan_gamerules.read_class(need(MODS), m["jar"], m["class"])
        assert scan_gamerules.ldc_string(b, m["method"], m["ldc"]) == m["id"], m


def test_the_twilight_forest_supplier_fields_exist():
    tf = [m for m in pin().modded if m["mod"] == "twilightforest"]
    fields = scan_gamerules.static_fields(scan_gamerules.read_class(need(MODS), tf[0]["jar"], tf[0]["class"]))
    assert {m["field"]: fields.get(m["field"]) for m in tf} == {m["field"]: "Ljava/util/function/Supplier;" for m in tf}


def test_the_vanilla_names_are_game_rules_clinit_in_order():
    with zipfile.ZipFile(need(SRG)) as z:
        b = z.read(f"{GR}.class")
    assert pin().vanilla == scan_gamerules.register_names(b, "<clinit>")


def test_neoforge_does_not_patch_game_rules():
    """NeoForge's patched classes are in its -server jar (ServerLevel is there); GameRules is not, so the srg jar's is the one
    that runs. The version is pack.toml's, so a NeoForge update re-checks this."""
    with zipfile.ZipFile(need(neoforge_jar())) as z:
        names = set(z.namelist())
    assert "net/minecraft/server/level/ServerLevel.class" in names
    assert f"{GR}.class" not in names
