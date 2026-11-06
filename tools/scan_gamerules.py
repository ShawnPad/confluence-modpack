"""List every call to net/minecraft/world/level/GameRules.register in the server's mod jars, jar-in-jar included, read from the
bytecode (v0.3 Task 11d, D137).

A game rule is registered by an `invokestatic GameRules.register(String, Category, Type)`, or by a method handle to it. Each
class's constant pool is parsed and each method's bytecode walked, so a call site is reported as (jar, class, method,
offset), not as a string hit. A jar inside a jar (META-INF/jarjar/) is named outer!inner. tools/gamerules.toml pins the
call sites and the ids they register, and tools/tests/test_gamerules_jars.py compares them with this scan, so a mod
update that adds, drops or moves a game rule fails a test before a boot does. Not covered: a mixin or an
access-transformed method that registers a rule some other way. The scan of 2026-10-02 found none (D137 evidence,
scan_gamerules.out).

Usage: python3 tools/scan_gamerules.py [MODS_DIR]   (default .run/server/mods). Prints one line per call site:
    <jar> :: <class>.<method> @<offset> registers [<id>, ...]
(the id is the last String an ldc loaded before the call in that method, '?' when there is none), then a count line. Exit
status: 0, or 2 (NO MODS DIRECTORY on stderr) when MODS_DIR is not a directory, which would otherwise read as a clean scan.
"""
import io
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_RULES = "net/minecraft/world/level/GameRules"
INVOKES = {0xb6, 0xb7, 0xb8, 0xb9}   # invokevirtual, invokespecial, invokestatic, invokeinterface
LDC, LDC_W = 0x12, 0x13
ACC_STATIC = 0x0008
EXIT_NO_MODS = 2

# Operand bytes after each opcode (JVMS 6.5); -1 = variable length (tableswitch, lookupswitch, wide).
OPERANDS = [0] * 256
for _op in (0x10, 0x12, 0x15, 0x16, 0x17, 0x18, 0x19, 0x36, 0x37, 0x38, 0x39, 0x3a, 0xa9, 0xbc):
    OPERANDS[_op] = 1
for _op in [0x11, 0x13, 0x14, 0x84, *range(0x99, 0xa9), 0xb2, 0xb3, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xbb, 0xbd, 0xc0, 0xc1,
            0xc6, 0xc7]:
    OPERANDS[_op] = 2
OPERANDS[0xc5] = 3
for _op in (0xb9, 0xba, 0xc8, 0xc9):
    OPERANDS[_op] = 4
OPERANDS[0xaa] = OPERANDS[0xab] = OPERANDS[0xc4] = -1


class ClassFile:
    """The parts of a class file the scan needs: the constant pool, the class name, the fields and each method's code."""

    def __init__(self, b: bytes):
        if b[:4] != b"\xca\xfe\xba\xbe":
            raise ValueError("not a class file")
        n = struct.unpack(">H", b[8:10])[0]
        self.cp = [None] * n
        i, p = 1, 10
        while i < n:
            tag = b[p]
            if tag == 1:
                ln = struct.unpack(">H", b[p + 1:p + 3])[0]
                self.cp[i] = (1, b[p + 3:p + 3 + ln].decode("utf-8", "replace"))
                p += 3 + ln
            elif tag in (3, 4):
                self.cp[i], p = (tag, None), p + 5
            elif tag in (5, 6):                      # long and double take two slots
                self.cp[i], p = (tag, None), p + 9
                i += 1
            elif tag in (7, 8, 16, 19, 20):
                self.cp[i], p = (tag, struct.unpack(">H", b[p + 1:p + 3])[0]), p + 3
            elif tag in (9, 10, 11, 12, 17, 18):
                self.cp[i], p = (tag, struct.unpack(">HH", b[p + 1:p + 5])), p + 5
            elif tag == 15:
                self.cp[i], p = (tag, (b[p + 1], struct.unpack(">H", b[p + 2:p + 4])[0])), p + 4
            else:
                raise ValueError(f"constant pool tag {tag} at byte {p}")
            i += 1
        _, this, _, interfaces = struct.unpack(">HHHH", b[p:p + 8])
        self.name = self.utf8(self.cp[this][1])
        p += 8 + 2 * interfaces
        p, self.fields = self._members(b, p)
        p, self.methods = self._members(b, p)

    def utf8(self, k):
        return self.cp[k][1]

    def _members(self, b, p):
        count = struct.unpack(">H", b[p:p + 2])[0]
        p += 2
        out = []
        for _ in range(count):
            access, name, desc, attrs = struct.unpack(">HHHH", b[p:p + 8])
            p += 8
            code = None
            for _ in range(attrs):
                attr, length = struct.unpack(">HI", b[p:p + 6])
                if self.utf8(attr) == "Code":
                    code_len = struct.unpack(">I", b[p + 10:p + 14])[0]
                    code = b[p + 14:p + 14 + code_len]
                p += 6 + length
            out.append((self.utf8(name), self.utf8(desc), code, access))
        return p, out

    def ref(self, k):
        """(owner, name, descriptor) of a Fieldref, Methodref or InterfaceMethodref."""
        owner, nat = self.cp[k][1]
        name, desc = self.cp[nat][1]
        return self.utf8(self.cp[owner][1]), self.utf8(name), self.utf8(desc)

    def code(self, method):
        """The bytecode of the one method named `method`. Raises KeyError when none or several have code: a caller that names a
        method cannot mean an overload, so class_register_sites walks every method by (name, descriptor) instead."""
        found = [c for n, _, c, _ in self.methods if n == method and c is not None]
        if len(found) != 1:
            raise KeyError(f"{self.name} has {len(found)} methods named {method} with code")
        return found[0]


def instructions(code: bytes):
    """(offset, opcode, operand bytes) for each instruction."""
    pc = 0
    while pc < len(code):
        op = code[pc]
        if op in (0xaa, 0xab):                       # tableswitch, lookupswitch: pad to 4, then a variable table
            q = pc + 1 + (-(pc + 1) % 4)
            if op == 0xaa:
                low, high = struct.unpack(">ii", code[q + 4:q + 12])
                nxt = q + 12 + 4 * (high - low + 1)
            else:
                nxt = q + 8 + 8 * struct.unpack(">i", code[q + 4:q + 8])[0]
        elif op == 0xc4:                             # wide: iinc takes 4 more bytes, the rest 2
            nxt = pc + (6 if code[pc + 1] == 0x84 else 4)
        else:
            nxt = pc + 1 + OPERANDS[op]
        yield pc, op, code[pc + 1:nxt]
        pc = nxt


def _is_register(cf, k):
    owner, name, _ = cf.ref(k)
    return owner == GAME_RULES and name == "register"


def _string_at(cf, op, arg):
    k = arg[0] if op == LDC else struct.unpack(">H", arg)[0]
    entry = cf.cp[k]
    return cf.utf8(entry[1]) if entry and entry[0] == 8 else None


def _code_sites(cf, code):
    """[(offset, id)] for each GameRules.register call in one method's bytecode: the id is the last String an ldc loaded before it
    in that method, after the previous call (None when there is none: the id comes in another way, as in Twilight Forest's
    lambda)."""
    last, out = None, []
    for pc, op, arg in instructions(code):
        if op in (LDC, LDC_W):
            last = _string_at(cf, op, arg) or last
        elif op in INVOKES and _is_register(cf, struct.unpack(">H", arg[:2])[0]):
            out.append((pc, last))
            last = None
    return out


def class_register_sites(b: bytes):
    """[(class, method, descriptor, offset, id)] for each GameRules.register call in the class, walking each method by (name,
    descriptor), so overloads stay apart; a method handle to it is (class, '<method handle>', '', -1, None)."""
    if GAME_RULES.encode() not in b:
        return []
    cf = ClassFile(b)
    out = []
    for k, entry in enumerate(cf.cp):
        if entry and entry[0] == 15 and cf.cp[entry[1][1]][0] in (10, 11) and _is_register(cf, entry[1][1]):
            out.append((cf.name, "<method handle>", "", -1, None))
    for name, desc, code, _ in cf.methods:
        out += [(cf.name, name, desc, pc, rule) for pc, rule in _code_sites(cf, code or b"")]
    return out


def class_register_calls(b: bytes):
    """[(class, method, offset)] of class_register_sites."""
    return [(cls, method, offset) for cls, method, _, offset, _ in class_register_sites(b)]


def ldc_string(b: bytes, method: str, offset: int):
    """The String constant an ldc or ldc_w at `offset` in `method` loads; None for another instruction or constant."""
    cf = ClassFile(b)
    for pc, op, arg in instructions(cf.code(method)):
        if pc == offset:
            return _string_at(cf, op, arg) if op in (LDC, LDC_W) else None
    return None


def register_sites(b: bytes, method: str):
    """[(offset, id)] for each GameRules.register call in the one method named `method`, in order (_code_sites)."""
    cf = ClassFile(b)
    return _code_sites(cf, cf.code(method))


def register_names(b: bytes, method: str):
    """The ids of register_sites(b, method), in order."""
    return [rule for _, rule in register_sites(b, method)]


def static_fields(b: bytes):
    """{field name: descriptor} of the class's static fields."""
    return {name: desc for name, desc, _, access in ClassFile(b).fields if access & ACC_STATIC}


def _scan_zip(label, zf, out):
    for info in zf.infolist():
        if info.filename.endswith(".jar"):
            _scan_zip(f"{label}!{info.filename}", zipfile.ZipFile(io.BytesIO(zf.read(info))), out)
        elif info.filename.endswith(".class"):
            out += [(label, *site) for site in class_register_sites(zf.read(info))]


def register_sites_in(mods: Path):
    """[(jar, class, method, descriptor, offset, id)] for every GameRules.register call site in mods/*.jar, jar-in-jar included,
    sorted by everything but the id (which may be None)."""
    out = []
    for jar in sorted(Path(mods).glob("*.jar")):
        with zipfile.ZipFile(jar) as zf:
            _scan_zip(jar.name, zf, out)
    return sorted(out, key=lambda site: site[:5])


def register_calls(mods: Path):
    """[(jar, class, method, offset)] of register_sites_in."""
    return [(jar, cls, method, offset) for jar, cls, method, _, offset, _ in register_sites_in(mods)]


def read_class(mods: Path, jar: str, cls: str) -> bytes:
    """The bytes of class `cls` (a/b/C) in `jar` under `mods`, where jar is outer.jar or outer.jar!path/inner.jar."""
    outer, *inner = jar.split("!")
    data = (Path(mods) / outer).read_bytes()
    for name in inner:
        data = zipfile.ZipFile(io.BytesIO(data)).read(name)
    return zipfile.ZipFile(io.BytesIO(data)).read(cls + ".class")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    mods = Path(args[0]) if args else ROOT / ".run" / "server" / "mods"
    if not mods.is_dir():
        print(f"NO MODS DIRECTORY {mods}", file=sys.stderr)
        return EXIT_NO_MODS
    sites = register_sites_in(mods)
    for jar, cls, method, _, offset, rule in sites:
        print(f"{jar} :: {cls}.{method} @{offset} registers [{rule or '?'}]")
    print(f"{len(sites)} GameRules.register call site(s) in {len({s[0] for s in sites})} jar(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
