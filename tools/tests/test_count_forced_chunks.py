"""tools/count_forced_chunks.py (v0.3 Task 11c, D136): count what keeps chunks loaded in the run world.

A forceload a probe leaves behind is saved in that dimension's data/chunks.dat and re-added on every later boot, whose stop
must then wait for those chunks to load (25-199 s, SERVER DID NOT STOP). NeoForge keeps mod chunk-loader tickets in the same
file (`ModForced`) and reinstates them at boot too. The reader takes a run directory, finds the world (server.properties
level-name, read as Java properties, else "world"), counts the `Forced` long array and the `ModForced` block and entity
tickets of every data/chunks.dat in it, and:
  - prints `forced chunks: 0 (mod tickets: 0; N chunks.dat files read in <abs world>)` and exits 0 when there are none;
  - prints `forced chunks: F (mod tickets: M; ...)`, one line per dimension that holds any (absolute paths), and the operator
    hint (delete the files with the server stopped first; D136), and exits 1 when F + M > 0;
  - exits 2 for anything it could not read: a file that is not gzip, a corrupt deflate body, NBT nested too deep or of an
    unexpected shape (no `data` compound, no `Forced` long array, a malformed `ModForced`), a directory it cannot list, or no
    world at all. Exit 1 means only "counted more than 0". With --allow-no-world (server_boot.sh --check, whose RUN_DIR may
    be a failed-boot archive) a missing world prints `forced chunks: 0 (no world at <abs path>)` and exits 0.
"""
import base64
import gzip
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "count_forced_chunks.py"
# The Overworld's data/chunks.dat from .run/server/world, as the server wrote it (13 Sep 2026; probe_loot.sh's
# `forceload add 0 0`): gzip NBT, root {data: {Forced: [L; chunk 0,0]}, DataVersion: 3955}.
REAL_OVERWORLD = base64.b64decode("H4sIAAAAAAAA/+NiYOBiYElJLEnkYWBzyy9KTk1hYGBgZIABZgZuF6BkWGpRcWZ+HgMDfzEDAG1pu14zAAAA")


def named(tag_id, name, payload):
    return bytes([tag_id]) + struct.pack(">H", len(name.encode())) + name.encode() + payload


def compound(*entries):
    return b"".join(entries) + b"\x00"


def nbt_string(text):
    return struct.pack(">H", len(text.encode())) + text.encode()


def nbt_list(elem_type, items):
    return bytes([elem_type if items else 0]) + struct.pack(">i", len(items)) + b"".join(items)


def long_array(values):
    return struct.pack(">i", len(values)) + struct.pack(f">{len(values)}q", *values)


def chunk_long(x, z):
    """ChunkPos.toLong: x in the low 32 bits, z in the high 32."""
    return struct.unpack(">q", struct.pack(">Q", (x & 0xFFFFFFFF) | ((z & 0xFFFFFFFF) << 32)))[0]


BLOCK_POS = compound(named(3, "X", struct.pack(">i", 1)), named(3, "Y", struct.pack(">i", 64)),
                     named(3, "Z", struct.pack(">i", 2)))         # ForcedChunkManager.writeBlockPos: X, Y, Z ints
UUID = struct.pack(">i", 4) + bytes(range(16))                     # NbtUtils.createUUID: an int array of 4


def mod_forced(*controllers, key="Controller"):
    """data.ModForced as ForcedChunkManager.writeModForcedChunks writes it (neoforge-21.1.250-universal.jar, javap): a list of
    compounds {Controller: string, ModForced: list of compounds, one per chunk, {Chunk: long, Blocks / TickingBlocks: lists
    of block-pos compounds, Entities / TickingEntities: lists of UUID int arrays}}. Each controller is (id, [chunk dicts
    giving the count per ticket list]). key="Mod" writes the pre-Controller form readModForcedChunks still accepts."""
    entries = []
    for ctl, chunks in controllers:
        per_chunk = []
        for i, counts in enumerate(chunks):
            parts = [named(4, "Chunk", struct.pack(">q", chunk_long(i, 0)))]
            for list_key, kind in (("Blocks", 10), ("TickingBlocks", 10), ("Entities", 11), ("TickingEntities", 11)):
                if list_key in counts:
                    parts.append(named(9, list_key, nbt_list(kind, [BLOCK_POS if kind == 10 else UUID] * counts[list_key])))
            per_chunk.append(compound(*parts))
        entries.append(compound(named(8, key, nbt_string(ctl)), named(9, "ModForced", nbt_list(10, per_chunk))))
    return named(9, "ModForced", nbt_list(10, entries))


def root_file(*data_entries, data_tag=None):
    """A gzip chunks.dat whose `data` compound holds data_entries (or, given data_tag, whose `data` is that named tag)."""
    data = data_tag if data_tag is not None else named(10, "data", compound(*data_entries))
    return gzip.compress(named(10, "", compound(data, named(3, "DataVersion", struct.pack(">i", 3955)))))


def chunks_dat(n, before=b"", after=b"", mod=b""):
    """A chunks.dat holding n forced chunks; `before`/`after` are extra named tags around Forced inside `data`."""
    forced = named(12, "Forced", long_array([chunk_long(i % 16 - 8, i // 16 - 8) for i in range(n)]))
    return root_file(before, forced, mod, after)


def place(run, rel, data):
    path = run / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def count(run, *flags):
    res = subprocess.run([sys.executable, str(SCRIPT), *flags, str(run)], capture_output=True, text=True, timeout=60)
    return res.returncode, res.stdout.splitlines(), res.stderr


def world(run, name="world"):
    (run / name).mkdir(parents=True, exist_ok=True)
    return (run / name).resolve()


# ---- the clean line, and a missing world (M7) --------------------------------------------------------------------------

def test_an_empty_world_has_nothing_forced_and_says_how_many_files_it_read(tmp_path):
    w = world(tmp_path)
    assert count(tmp_path)[:2] == (0, [f"forced chunks: 0 (mod tickets: 0; 0 chunks.dat files read in {w})"])


def test_empty_forced_arrays_count_zero(tmp_path):
    """`forceload remove` leaves the file with an empty Forced array (ForcedChunksSavedData.save writes it always)."""
    place(tmp_path, "world/data/chunks.dat", chunks_dat(0))
    place(tmp_path, "world/dimensions/twilightforest/twilight_forest/data/chunks.dat", chunks_dat(0))
    w = world(tmp_path)
    assert count(tmp_path)[:2] == (0, [f"forced chunks: 0 (mod tickets: 0; 2 chunks.dat files read in {w})"])


def test_a_missing_world_is_an_error_not_a_pass(tmp_path):
    """A server that reached Done has always created its world folder: none there means the reader looked in the wrong place."""
    code, out, err = count(tmp_path)
    assert code == 2 and out == [], out
    assert f"no world at {tmp_path.resolve() / 'world'}" in err, err


def test_a_missing_world_is_reported_but_allowed_where_none_is_expected(tmp_path):
    """--allow-no-world (server_boot.sh --check, whose RUN_DIR may be a failed-boot archive: logs, no world, and no
    server.properties)."""
    code, out, _ = count(tmp_path, "--allow-no-world")
    assert (code, out) == (0, [f"forced chunks: 0 (no world at {tmp_path.resolve() / 'world'})"])


def test_a_missing_world_where_a_server_ran_is_an_error_even_when_allowed(tmp_path):
    """Task 11c fix round 3: a server writes server.properties on its first boot, and a failed-boot archive never holds one.
    A run directory that has it but no world lost its world: --allow-no-world does not cover that."""
    (tmp_path / "server.properties").write_text("level-name=world\n")
    code, out, err = count(tmp_path, "--allow-no-world")
    assert code == 2 and out == [], out
    assert f"no world at {tmp_path.resolve() / 'world'}" in err and "server.properties" in err, err


# ---- counting, and the failure output (M8) -----------------------------------------------------------------------------

def test_the_real_overworld_file_holds_one_forced_chunk(tmp_path):
    f = place(tmp_path, "world/data/chunks.dat", REAL_OVERWORLD).resolve()
    code, out, _ = count(tmp_path)
    assert code == 1 and out[:2] == [f"forced chunks: 1 (mod tickets: 0; 1 chunks.dat files read in {world(tmp_path)})",
                                     f"  minecraft:overworld: 1 forced chunk(s) ({f})"], out


def test_forced_chunks_are_counted_per_dimension_and_fail(tmp_path):
    """DimensionType.getStorageFolder: the Overworld is the world folder itself, the End DIM1, the Nether DIM-1, any other
    dimension dimensions/<namespace>/<path>. A dimension with none is not listed."""
    place(tmp_path, "world/data/chunks.dat", chunks_dat(1))
    place(tmp_path, "world/DIM-1/data/chunks.dat", chunks_dat(3))
    place(tmp_path, "world/DIM1/data/chunks.dat", chunks_dat(0))
    place(tmp_path, "world/dimensions/allthemodium/the_other/data/chunks.dat", chunks_dat(1536))
    place(tmp_path, "world/dimensions/ad_astra/glacio/data/chunks.dat", chunks_dat(256))
    w = world(tmp_path)
    code, out, _ = count(tmp_path)
    assert code == 1
    assert out[0] == f"forced chunks: 1796 (mod tickets: 0; 5 chunks.dat files read in {w})"
    assert sorted(line for line in out if " forced chunk(s) (" in line) == sorted([
        f"  minecraft:overworld: 1 forced chunk(s) ({w}/data/chunks.dat)",
        f"  minecraft:the_nether: 3 forced chunk(s) ({w}/DIM-1/data/chunks.dat)",
        f"  allthemodium:the_other: 1536 forced chunk(s) ({w}/dimensions/allthemodium/the_other/data/chunks.dat)",
        f"  ad_astra:glacio: 256 forced chunk(s) ({w}/dimensions/ad_astra/glacio/data/chunks.dat)",
    ]), out
    assert not any("the_end" in line for line in out)


def test_the_hint_puts_deleting_the_files_first_and_names_the_decision(tmp_path):
    """The console route needs a running server, and its boot re-adds every one of these chunks first: deleting the files
    with the server stopped comes first."""
    place(tmp_path, "world/data/chunks.dat", chunks_dat(2))
    text = "\n".join(count(tmp_path)[1])
    delete, console = text.find("delete"), text.find("forceload remove all")
    assert 0 < delete < console, text
    assert "server stopped" in text and "D136" in text and "probe" in text


def test_mod_tickets_are_counted_per_dimension_and_fail(tmp_path):
    """NeoForge reinstates ModForced tickets at boot (ForcedChunkManager.reinstatePersistentChunks, called from
    MinecraftServer.prepareLevels): a chunk loader left in the world slows the stop like a forceload. Every Blocks,
    TickingBlocks, Entities and TickingEntities entry is one ticket; the controller ids are named."""
    mod = mod_forced(("mekanism:chunk_loader", [{"Blocks": 2, "TickingEntities": 1}, {"Entities": 1}]),
                     ("ftbchunks:force_loading", [{"TickingBlocks": 3}]), key="Controller")
    place(tmp_path, "world/dimensions/undergarden/undergarden/data/chunks.dat", chunks_dat(0, mod=mod))
    legacy = mod_forced(("ae2", [{"Blocks": 1}]), key="Mod")
    place(tmp_path, "world/data/chunks.dat", chunks_dat(0, mod=legacy))
    w = world(tmp_path)
    code, out, _ = count(tmp_path)
    assert code == 1, out
    assert out[0] == f"forced chunks: 0 (mod tickets: 8; 2 chunks.dat files read in {w})"
    assert (f"  undergarden:undergarden: 7 mod ticket(s) from ftbchunks:force_loading, mekanism:chunk_loader "
            f"({w}/dimensions/undergarden/undergarden/data/chunks.dat)") in out, out
    assert f"  minecraft:overworld: 1 mod ticket(s) from ae2:default ({w}/data/chunks.dat)" in out, out


def test_forced_chunks_and_mod_tickets_share_a_dimension_line(tmp_path):
    mod = mod_forced(("mekanism:chunk_loader", [{"Blocks": 1}]))
    place(tmp_path, "world/data/chunks.dat", chunks_dat(4, mod=mod))
    code, out, _ = count(tmp_path)
    assert code == 1
    assert f"  minecraft:overworld: 4 forced chunk(s), 1 mod ticket(s) from mekanism:chunk_loader " \
           f"({world(tmp_path)}/data/chunks.dat)" in out, out


def test_an_empty_mod_forced_list_counts_zero(tmp_path):
    place(tmp_path, "world/data/chunks.dat", chunks_dat(0, mod=mod_forced(("mekanism:chunk_loader", [{"Blocks": 0}]))))
    assert count(tmp_path)[0] == 0


def test_every_other_tag_type_is_skipped(tmp_path):
    """The count reads `Forced` wherever it sits in `data`, past tags of every NBT type."""
    others = b"".join([
        named(1, "b", b"\x01"), named(2, "s", b"\x00\x02"), named(3, "i", b"\x00\x00\x00\x03"), named(4, "l", b"\x00" * 8),
        named(5, "f", b"\x00" * 4), named(6, "d", b"\x00" * 8), named(7, "ba", struct.pack(">i", 3) + b"abc"),
        named(8, "str", nbt_string("hello")), named(9, "list", nbt_list(10, [compound(named(8, "k", nbt_string("v")))])),
        named(9, "empty", nbt_list(0, [])), named(11, "ia", struct.pack(">i", 2) + b"\x00" * 8),
        named(12, "Forcedish", long_array([1, 2, 3])),
    ])
    place(tmp_path, "world/data/chunks.dat", chunks_dat(4, before=others, after=named(10, "c", compound(others))))
    assert count(tmp_path)[1][0].startswith("forced chunks: 4 (mod tickets: 0;")


# ---- level-name (M7) ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("line, folder", [
    ("level-name=other", "other"),
    ("level-name = other", "other"),                 # whitespace around the separator is not part of key or value
    ("  level-name:other", "other"),                 # leading whitespace; ':' separates too
    ("level-name other", "other"),                   # so does whitespace alone
    ("level-name=other  ", "other  "),               # trailing whitespace is part of the value (Java keeps it)
    ("level-name=oth\\\n    er", "other"),           # a continuation line: its leading whitespace is dropped
    ("level-name=\\u006fther", "other"),             # \uXXXX escapes
    ("\\u006cevel-name=other", "other"),             # in the key too (Properties.loadConvert runs on the key as well)
    ("level\\-name=other", "other"),                 # an escaped character in the key stands for itself
], ids=["plain", "spaced", "colon", "space-separator", "trailing-space", "continuation", "unicode-escape",
        "unicode-escape-in-the-key", "escape-in-the-key"])
def test_level_name_is_read_with_java_properties_rules(tmp_path, line, folder):
    """Settings.loadFromFile reads server.properties with java.util.Properties.load, and DedicatedServerProperties takes
    level-name as-is (Settings.get with Function.identity, default "world"): javap of the 1.21.1 server classes."""
    (tmp_path / "server.properties").write_text(f"#Minecraft server properties\n! a comment\nmotd=x\n{line}\n")
    place(tmp_path, "world/data/chunks.dat", chunks_dat(9))
    f = place(tmp_path, f"{folder}/data/chunks.dat", chunks_dat(2)).resolve()
    code, out, _ = count(tmp_path)
    assert (code, out[1]) == (1, f"  minecraft:overworld: 2 forced chunk(s) ({f})"), out


def test_the_last_level_name_wins_and_a_commented_one_does_not_count(tmp_path):
    (tmp_path / "server.properties").write_text("level-name=first\n# level-name=commented\nlevel-name=second\n")
    f = place(tmp_path, "second/data/chunks.dat", chunks_dat(1)).resolve()
    assert count(tmp_path)[1][1] == f"  minecraft:overworld: 1 forced chunk(s) ({f})"


# ---- unreadable means exit 2 (I1, I2) ----------------------------------------------------------------------------------

def deep_nesting(levels=3000):
    inner = named(10, "x", compound())
    for _ in range(levels):
        inner = named(10, "x", compound(inner))
    return root_file(inner, named(12, "Forced", long_array([1])))


def corrupt_deflate():
    """A valid gzip header and a damaged deflate body: zlib.error, not gzip.BadGzipFile (Task 11c review,
    cases/zlib_corrupt)."""
    good = bytearray(chunks_dat(3))
    good[12] ^= 0xFF
    good[13] ^= 0xFF
    return bytes(good)


UNREADABLE = {
    "not-gzip": b"not gzip at all",
    "truncated-nbt": gzip.compress(b"\x0a\x00\x00\x0a\x00\x04da"),
    "empty-file": b"",
    "corrupt-deflate": corrupt_deflate(),
    "deep-nesting": deep_nesting(),
    "root-not-compound": gzip.compress(named(3, "", struct.pack(">i", 1))),
    "no-data": gzip.compress(named(10, "", compound(named(3, "DataVersion", struct.pack(">i", 3955))))),
    "data-not-compound": root_file(data_tag=named(3, "data", struct.pack(">i", 1))),
    "no-forced": root_file(named(3, "other", struct.pack(">i", 1))),
    "forced-is-a-list": root_file(named(9, "Forced", nbt_list(4, [struct.pack(">q", 1)] * 2))),
    "mod-forced-not-a-list": chunks_dat(0, mod=named(10, "ModForced", compound())),
    "mod-forced-of-ints": chunks_dat(0, mod=named(9, "ModForced", nbt_list(3, [struct.pack(">i", 1)]))),
    "controller-missing": chunks_dat(0, mod=named(9, "ModForced", nbt_list(10, [compound(
        named(9, "ModForced", nbt_list(10, [compound(named(4, "Chunk", struct.pack(">q", 0)))])))]))),
    "chunk-missing": chunks_dat(0, mod=named(9, "ModForced", nbt_list(10, [compound(
        named(8, "Controller", nbt_string("a:b")), named(9, "ModForced", nbt_list(10, [compound(
            named(9, "Blocks", nbt_list(10, [BLOCK_POS])))])))]))),
    "blocks-of-uuids": chunks_dat(0, mod=named(9, "ModForced", nbt_list(10, [compound(
        named(8, "Controller", nbt_string("a:b")), named(9, "ModForced", nbt_list(10, [compound(
            named(4, "Chunk", struct.pack(">q", 0)), named(9, "Blocks", nbt_list(11, [UUID])))])))]))),
}


@pytest.mark.parametrize("data", UNREADABLE.values(), ids=UNREADABLE.keys())
def test_an_unreadable_file_is_an_error_not_a_pass(tmp_path, data):
    place(tmp_path, "world/data/chunks.dat", chunks_dat(5))
    bad = place(tmp_path, "world/dimensions/undergarden/undergarden/data/chunks.dat", data).resolve()
    code, out, err = count(tmp_path)
    assert code == 2 and out == [], out
    assert f"cannot read {bad}" in err and "Traceback" not in err, err


@pytest.mark.parametrize("levels, code", [(500, 1), (600, 2)])
def test_nesting_is_held_to_minecrafts_own_limit(tmp_path, levels, code):
    """NbtAccounter.MAX_STACK_DEPTH is 512: a file nested deeper is one Minecraft itself would refuse, whatever Python's own
    recursion limit allows."""
    place(tmp_path, "world/data/chunks.dat", deep_nesting(levels))
    got, out, err = count(tmp_path)
    assert got == code, (out, err)
    assert ("nested deeper than 512" in err) == (code == 2), err


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 directory anyway")
def test_a_dimension_folder_it_cannot_list_is_an_error_not_a_pass(tmp_path):
    """pathlib's glob skips a directory it cannot read without a word; the reader walks with os.walk and fails instead."""
    place(tmp_path, "world/dimensions/undergarden/undergarden/data/chunks.dat", chunks_dat(5))
    locked = tmp_path / "world" / "dimensions" / "undergarden"
    locked.chmod(0)
    try:
        code, out, err = count(tmp_path)
    finally:
        locked.chmod(0o755)
    assert code == 2 and out == [], out
    assert "cannot list" in err and str(locked.resolve()) in err, err


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads a mode-000 directory anyway")
@pytest.mark.parametrize("locked", ["world/data", "world", "world/DIM-1"])
def test_a_vanilla_folder_it_cannot_search_is_an_error_not_a_pass(tmp_path, locked):
    """Task 11c fix round 3: Path.is_file() and is_dir() answer False when stat fails with EACCES, so a mode-000 world/data
    holding a forced chunk read as `forced chunks: 0`. Only a path that does not exist is absent; any other stat failure is
    unreadable, exit 2."""
    place(tmp_path, "world/data/chunks.dat", chunks_dat(3))
    place(tmp_path, "world/DIM-1/data/chunks.dat", chunks_dat(4))
    folder = tmp_path / locked
    folder.chmod(0)
    try:
        code, out, err = count(tmp_path)
    finally:
        folder.chmod(0o755)
    assert code == 2 and out == [], out
    assert "cannot stat" in err and str(folder.resolve()) in err and "Traceback" not in err, err


def test_a_missing_run_dir_is_a_usage_error(tmp_path):
    code, out, err = count(tmp_path / "nope")
    assert code == 2 and out == [] and "no such directory" in err


def test_the_reader_runs_on_the_python_the_boot_uses():
    """server_boot.sh calls `python3 tools/count_forced_chunks.py`: stdlib only."""
    src = SCRIPT.read_text()
    imports = {line.split()[1].split(".")[0] for line in src.splitlines() if line.startswith(("import ", "from "))}
    assert imports <= {"gzip", "os", "stat", "struct", "sys", "pathlib"}, imports
