"""Count what keeps chunks loaded in a run world: forced chunks and NeoForge mod tickets (v0.3 Task 11c, D136).

  python3 tools/count_forced_chunks.py [--allow-no-world] RUN_DIR

Each dimension saves its chunk tickets in data/chunks.dat (ForcedChunksSavedData, FILE_ID "chunks"; javap of the class in
neoforge-21.1.250-server.jar). SavedData.save(File) wraps the data in a `data` compound (offsets 16-30). Inside it,
ForcedChunksSavedData.save always writes `Forced`, a long array with one ChunkPos long per `forceload add` chunk
(offsets 0-12, no branch), and then calls ForcedChunkManager.writeModForcedChunks (offsets 15-24). That method, in
neoforge-21.1.250-universal.jar, writes `ModForced` only when a mod's ticket controller holds tickets (offsets 0-11). It is
a list of compounds {Controller: string, ModForced: list of compounds, one per chunk, {Chunk: long, Blocks and
TickingBlocks: lists of block-pos compounds, Entities and TickingEntities: lists of UUID int arrays}} (offsets 51-186;
writeForcedChunkOwners; lambda$writeForcedChunkOwners$14 for Chunk). readModForcedChunks also accepts the older form, which
has `Mod` (read as <mod>:default) in place of Controller (offsets 30-73). Each entry in one of the four lists is one ticket.
Both kinds come back at every boot: MinecraftServer.prepareLevels re-adds the Forced chunks, and it calls
ForcedChunkManager.reinstatePersistentChunks (offset 260) for the mod tickets. A SIGTERM or `stop` that arrives while
they load must wait in stopServer until every one is loaded and unloaded. The 5,121 forced chunks leaked by
tools/probe_worldgen.sh and tools/probe_loot.sh made the stop take 25-199 s (SERVER DID NOT STOP), against 1.3-1.4 s
without them (Task 11c A/B).

The world is RUN_DIR/<level-name>. Settings.loadFromFile reads server.properties with java.util.Properties.load, and
DedicatedServerProperties takes level-name through Settings.get(key, "world") with Function.identity, so the value is used
exactly as Properties parses it (trailing whitespace kept). The world folder's dimension folders are where
DimensionType.getStorageFolder puts them: the Overworld is the world folder itself, the Nether DIM-1, the End DIM1, and any
other dimension dimensions/<namespace>/<path>.

Exit 0 when nothing is forced. It prints
`forced chunks: 0 (mod tickets: 0; N chunks.dat files read in <world>)`.

Exit 1 when F forced chunks or M mod tickets are found (F + M > 0). It prints `forced chunks: F (mod tickets: M; ...)`, one
line per dimension that holds any, with absolute paths, and how to clear them.

Exit 2 for anything it could not read, named on stderr. That covers a file that is not gzip, a corrupt deflate body, NBT
nested deeper than NbtAccounter's MAX_STACK_DEPTH of 512, and an unexpected shape: no `data` compound, no `Forced` long
array, or a malformed `ModForced`. It also covers a directory it cannot list, a usage error, and no world folder at all,
since a server that reached Done has always created one. So exit 1 means only "counted more than 0".

With --allow-no-world, a missing world folder prints `forced chunks: 0 (no world at <world>)` and exits 0, as long as RUN_DIR
has no server.properties. This is for server_boot.sh --check, whose RUN_DIR may be a failed-boot archive: it holds logs, and
never a world or server.properties (server_boot.sh copies only the logs and the recipe dump). A server writes
server.properties when it first boots, so a RUN_DIR that has one but no world has lost its world: still exit 2.

Exists or not is decided by os.stat, never by Path.is_file() or is_dir(), which answer False when stat fails for any reason:
only FileNotFoundError and NotADirectoryError mean absent, and any other failure (EACCES on a mode-000 folder) exits 2.
"""
import gzip
import os
import stat
import struct
import sys
from pathlib import Path

VANILLA = {(): "minecraft:overworld", ("DIM-1",): "minecraft:the_nether", ("DIM1",): "minecraft:the_end"}
FIXED_SIZE = {1: ">b", 2: ">h", 3: ">i", 4: ">q", 5: ">f", 6: ">d"}
ARRAY_ITEM = {7: ">b", 11: ">i", 12: ">q"}            # byte, int and long arrays: an int length, then the items
MAX_DEPTH = 512                                       # NbtAccounter.MAX_STACK_DEPTH (net/minecraft/nbt/NbtAccounter, javap)
TICKET_LISTS = (("Blocks", 10), ("TickingBlocks", 10), ("Entities", 11), ("TickingEntities", 11))


class Unreadable(Exception):
    pass


class Reader:
    """A whole-file NBT parse. A compound is a dict of name -> (tag, value), a list is (element tag, [values]), and an
    array is a list."""

    def __init__(self, data):
        self.data, self.at = data, 0

    def take(self, n):
        if n < 0 or self.at + n > len(self.data):
            raise Unreadable(f"truncated NBT at byte {self.at}")
        chunk, self.at = self.data[self.at:self.at + n], self.at + n
        return chunk

    def unpack(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        return self.take(self.unpack(">H")).decode("utf-8", "replace")

    def value(self, tag, depth):
        if depth > MAX_DEPTH:
            raise Unreadable(f"NBT nested deeper than {MAX_DEPTH}")
        if tag in FIXED_SIZE:
            return self.unpack(FIXED_SIZE[tag])
        if tag in ARRAY_ITEM:
            n = self.unpack(">i")
            size = struct.calcsize(ARRAY_ITEM[tag])
            if n < 0:
                raise Unreadable(f"negative array length at byte {self.at}")
            return list(struct.unpack(f">{n}{ARRAY_ITEM[tag][1]}", self.take(n * size)))
        if tag == 8:
            return self.string()
        if tag == 9:
            item, n = self.unpack(">b"), self.unpack(">i")
            if n < 0 or (n and item == 0):
                raise Unreadable(f"bad list header at byte {self.at}")
            return item, [self.value(item, depth + 1) for _ in range(n)]
        if tag == 10:
            entries = {}
            while True:
                inner = self.unpack(">b")
                if inner == 0:
                    return entries
                name = self.string()
                entries[name] = (inner, self.value(inner, depth + 1))
        raise Unreadable(f"unknown NBT tag type {tag} at byte {self.at - 1}")


def need(compound, key, tag, where):
    if key not in compound or compound[key][0] != tag:
        raise Unreadable(f"{where} has no {key} of NBT type {tag}")
    return compound[key][1]


def need_list(compound, key, element, where):
    item, values = need(compound, key, 9, where)
    if values and item != element:
        raise Unreadable(f"{where}.{key} is a list of NBT type {item}, not {element}")
    return values


def tickets(path):
    """(forced chunks, mod tickets, {controller id: tickets}) of one chunks.dat."""
    r = Reader(gzip.decompress(path.read_bytes()))
    if r.unpack(">b") != 10:
        raise Unreadable("the root tag is not a compound")
    r.string()
    root = r.value(10, 1)
    data = need(root, "data", 10, "the root")
    forced = len(need(data, "Forced", 12, "data"))
    owners = {}
    if "ModForced" in data:
        for entry in need_list(data, "ModForced", 10, "data"):
            if "Controller" in entry:
                controller = need(entry, "Controller", 8, "a ModForced entry")
            else:
                controller = need(entry, "Mod", 8, "a ModForced entry without Controller") + ":default"
            n = 0
            for chunk in need_list(entry, "ModForced", 10, controller):
                need(chunk, "Chunk", 4, f"a {controller} chunk")
                for key, element in TICKET_LISTS:
                    if key in chunk:
                        n += len(need_list(chunk, key, element, f"a {controller} chunk"))
            if n:
                owners[controller] = owners.get(controller, 0) + n
    return forced, sum(owners.values()), owners


def dimension(world, path):
    parts = path.parent.parent.relative_to(world).parts
    if parts in VANILLA:
        return VANILLA[parts]
    if len(parts) >= 3 and parts[0] == "dimensions":
        return f"{parts[1]}:{'/'.join(parts[2:])}"
    return "/".join(parts)


def kind(path):
    """"dir", "file" or "other" for a path that exists, None for one that does not; any other stat failure is Unreadable."""
    try:
        mode = os.stat(path).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as e:
        raise Unreadable(f"cannot stat {path}: {e.strerror}") from None
    return "dir" if stat.S_ISDIR(mode) else "file" if stat.S_ISREG(mode) else "other"


def chunk_files(world):
    """Every <dimension folder>/data/chunks.dat. os.walk with an onerror that raises: a folder it cannot list fails the count
    (pathlib's glob would skip it without a word)."""
    def fail(error):
        raise Unreadable(f"cannot list {error.filename}: {error.strerror}")

    found = [world / d / "data" / "chunks.dat" for d in ("", "DIM-1", "DIM1")]
    walk = os.walk(world / "dimensions", onerror=fail) if kind(world / "dimensions") == "dir" else ()
    for top, dirs, files in walk:
        dirs.sort()
        if Path(top).name == "data" and "chunks.dat" in files:
            found.append(Path(top) / "chunks.dat")
    return sorted(p for p in found if kind(p) is not None)     # one that is not a file fails when it is read


ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


def java_properties(text):
    """java.util.Properties.load: logical lines (a line ending in an odd number of backslashes continues on the next, whose
    leading whitespace is dropped), comments (# or ! first), the key ends at the first unescaped =, : or whitespace,
    whitespace around the separator is skipped, the value keeps its trailing whitespace, \\uXXXX and \\t \\n \\r \\f escapes,
    any other escaped character stands for itself. A later key overrides an earlier one."""
    props, logical = {}, None
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.lstrip(" \t\f")            # every natural line, a continuation's too, loses its leading whitespace
        if logical is None:
            if not line or line[0] in "#!":
                continue
            logical = ""
        trailing = len(line) - len(line.rstrip("\\"))
        if trailing % 2:
            logical += line[:-1]
            continue
        logical += line
        key, value = split_property(logical)
        props[key] = value
        logical = None
    if logical is not None:
        key, value = split_property(logical)
        props[key] = value
    return props


def split_property(line):
    i, key = 0, []
    while i < len(line) and line[i] not in "=: \t\f":
        step = 2 if line[i] == "\\" and i + 1 < len(line) else 1    # an escape stays whole, for unescape to read once
        key.append(line[i:i + step])
        i += step
    while i < len(line) and line[i] in " \t\f":
        i += 1
    if i < len(line) and line[i] in "=:":
        i += 1
        while i < len(line) and line[i] in " \t\f":
            i += 1
    return unescape("".join(key)), unescape(line[i:])


def unescape(text):
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "u" and i + 6 <= len(text):
                out.append(chr(int(text[i + 2:i + 6], 16)))
                i += 6
                continue
            out.append(ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def level_name(props):
    try:
        text = props.read_text(encoding="utf-8")
    except UnicodeDecodeError:                # Settings.loadFromFile falls back to ISO-8859-1 the same way
        text = props.read_text(encoding="iso-8859-1")
    return java_properties(text).get("level-name", "world")


def main(argv):
    args = argv[1:]
    allow_no_world = "--allow-no-world" in args
    args = [a for a in args if a != "--allow-no-world"]
    if len(args) != 1:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    run = Path(args[0])
    props = run / "server.properties"
    try:
        if kind(run) != "dir":
            print(f"forced chunks: no such directory: {run}", file=sys.stderr)
            return 2
        server_ran = kind(props) is not None
        world = (run / (level_name(props) if server_ran else "world")).resolve()
        world_kind = kind(world)
    except Exception as e:                    # a run folder or server.properties it cannot read is unreadable too
        print(f"forced chunks: cannot read {run}: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    if world_kind != "dir":
        if world_kind is None and allow_no_world and not server_ran:
            print(f"forced chunks: 0 (no world at {world})")
            return 0
        why = ("it is not a folder" if world_kind else
               f"but {props} is: a server ran here, and one that reached Done has always created its world" if server_ran
               else "a server that reached Done has always created it")
        print(f"forced chunks: no world at {world} ({why})", file=sys.stderr)
        return 2
    try:
        files = chunk_files(world)
    except Exception as e:
        print(f"forced chunks: {e}", file=sys.stderr)
        return 2
    rows, errors = [], 0
    for path in files:
        try:
            rows.append((dimension(world, path), *tickets(path), path))
        except Exception as e:                # every per-file failure is "unreadable": exit 2, never a count
            print(f"forced chunks: cannot read {path}: {type(e).__name__}: {e}", file=sys.stderr)
            errors += 1
    if errors:
        return 2
    forced, mod = sum(r[1] for r in rows), sum(r[2] for r in rows)
    print(f"forced chunks: {forced} (mod tickets: {mod}; {len(files)} chunks.dat files read in {world})")
    if forced + mod == 0:
        return 0
    for dim, f, m, owners, path in rows:
        parts = ([f"{f} forced chunk(s)"] if f else []) + ([f"{m} mod ticket(s) from {', '.join(sorted(owners))}"] if m else [])
        if parts:
            print(f"  {dim}: {', '.join(parts)} ({path})")
    print("  A probe or a chunk loader left these in the world (D136). Every boot re-adds them, and a stop that arrives while")
    print("  they load waits for all of them (25-199 s, SERVER DID NOT STOP). Clear them:")
    print("    1. with the server stopped, delete the data/chunks.dat files above. Do this first: the console route needs a")
    print("       running server, and that boot re-adds every one of them before any command runs;")
    print("    2. or, on a running server, `execute in <dimension> run forceload remove all` for each dimension above. That")
    print("       clears forced chunks only (ForceLoadCommand.removeAll); a mod ticket is released by the mod that owns it.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
