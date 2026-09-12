#!/usr/bin/env python3
"""Static cross-mod mixin reference check -- catches client-only mod pair mismatches.

Why this exists (D73)
---------------------
A client-only mod pair can be mutually incompatible while every server-side check stays green.
Iris 1.8.12 was built against Sodium 0.6 and its compat mixins name
`net.caffeinemc.mods.sodium.client.gui.SodiumGameOptions`; the pack shipped Sodium 0.8.13, which
renamed that class to `SodiumOptions`. Result: every client crashed at world join with a mixin
apply failure, while `tools/server_boot.sh` booted clean -- a headless server never loads a
`side = "client"` mod, so it cannot see the break.

What it checks
--------------
Jar set: the installed server jars in `.run/server/mods/`, every `side = "client"` mod declared in
`mods/*.pw.toml` (downloaded once into `.run/client-jars/` and hash-verified against the toml), any
`--jar` given on the command line, and the nested `META-INF/jarjar/*.jar` of all of those.

For every jar:
  1. discover its mixin configs -- `[[mixins]] config = "..."` in `META-INF/neoforge.mods.toml` or
     `META-INF/mods.toml`, `MixinConfigs:` in `META-INF/MANIFEST.MF`, and any top-level `*.json`
     whose name contains "mixin" -- and collect the classes listed under `mixins`, `client` and
     `server` (prefixed with the config's `package`);
  2. for each mixin class, pull out every reference: constant-pool `Class` / `Fieldref` /
     `Methodref` / `InterfaceMethodref` entries plus the `@Mixin(value=[class ...])`,
     `@Mixin(targets=["..."])` and `@At(target="Lowner;name...")` targets, read out of `javap -v -p`.
     A cheap byte scan of the class file runs first; javap only runs when the class bytes mention a
     package path that is neither ignored nor part of the mod's own jar;
  3. classify each referenced owner class:
       - ignored (Minecraft, NeoForge, the JDK, Mixin/ASM, and the usual shaded libraries), or
         inside the mixin's own jar (or one of its nested jars)      -> skip;
       - in the index (another pack mod owns the class)              -> check the referenced member
         name exists on it or on one of its in-pack supertypes (`javap -p`; `<init>`/`<clinit>` and
         `java.lang.Object` members are always fine);
       - NOT in the index, but its namespace (first two path segments, e.g. `net/caffeinemc`) IS,
         *and* so is its own package (`net/caffeinemc/mods/sodium/client/gui`)
         -> MISSING CLASS. A pack mod ships that exact package but not that class: a version
         mismatch, exactly the Iris/Sodium case;
       - namespace absent entirely -> optional compat for a mod that is not in the pack; skipped.
         The package condition is what keeps sibling mods apart: a vendor namespace is shared by
         unrelated mods (`me/shedaniel/rei` vs `me/shedaniel/clothconfig2`,
         `org/embeddedt/embeddium` vs `org/embeddedt/modernfix`,
         `net/fabricmc/fabric/impl` vs `net/fabricmc/fabric/api`), so namespace presence alone
         reports optional compat code for absent mods as a break. Those land in the same
         skipped bucket.

Exit code 1 iff anything is missing.

Run it
------
    python3 tools/check_client_mixins.py                      # from the pack directory
    python3 tools/check_client_mixins.py --verbose             # list every cross-mod ref checked
    python3 tools/check_client_mixins.py --jar path/to/x.jar   # repeatable, ad-hoc extra jars

Needs `javap` (from JAVA_HOME, else Homebrew openjdk@21) and network access only the first time a
client jar is downloaded. Run `tools/server_boot.sh` first so `.run/server/mods/` is populated.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER_MODS = ROOT / ".run" / "server" / "mods"
CLIENT_JARS = ROOT / ".run" / "client-jars"
MODS_DIR = ROOT / "mods"

JAVA_HOME = os.environ.get("JAVA_HOME") or "/opt/homebrew/opt/openjdk@21"
JAVAP = os.path.join(JAVA_HOME, "bin", "javap")

# Owners we never check: they are Minecraft, the loader, the JDK, the mixin machinery itself, or a
# library that every second mod shades. Nothing here can be a cross-mod version mismatch.
IGNORED_PREFIXES = (
    "net/minecraft/",
    "com/mojang/",
    "net/neoforged/",
    "cpw/mods/",
    "java/",
    "javax/",
    "jdk/",
    "sun/",
    "org/spongepowered/",
    "org/objectweb/",
    "it/unimi/",
    "org/joml/",
    "com/google/",
    "org/lwjgl/",
    "io/netty/",
    "org/apache/",
    "org/slf4j/",
    "kotlin/",
    "org/jetbrains/",
)

# java.lang.Object is not in the index, so its members have to be known or every inherited-member
# lookup would end in "cannot prove it is missing".
OBJECT_MEMBERS = {
    "equals", "hashCode", "toString", "getClass", "clone", "notify", "notifyAll", "wait",
    "finalize", "registerNatives",
}

ALWAYS_OK_MEMBERS = {"<init>", "<clinit>"}

JAVAP_BATCH = 100

# A package path in raw class bytes: used only as a cheap "is javap worth running" prefilter.
CANDIDATE_RE = re.compile(rb"[A-Za-z_$][A-Za-z0-9_$]*(?:/[A-Za-z0-9_$]+)+")

CP_RE = re.compile(r"=\s+(Class|Fieldref|Methodref|InterfaceMethodref)\s+#\d+(?:[.:]#\d+)?\s+//\s+(\S+)")
MIXIN_VALUE_RE = re.compile(r"value=\[([^\]]*)\]")
MIXIN_VALUE_CLASS_RE = re.compile(r"class ([\[\w/$.;]+)")
MIXIN_TARGETS_RE = re.compile(r"targets=\[([^\]]*)\]")
AT_TARGET_RE = re.compile(r'target="\[*L([\w/$]+);([\w$<>]*)')
THIS_CLASS_RE = re.compile(r"this_class:\s+#\d+\s+//\s+(\S+)")
CLASSFILE_RE = re.compile(r"^Classfile\s+(.*)$")


# --------------------------------------------------------------------------------------- pure bits
def is_ignored(owner: str) -> bool:
    """True for owners that can never be a cross-mod mismatch (MC, loader, JDK, mixin, shaded libs)."""
    return owner.startswith(IGNORED_PREFIXES)


def namespace_of(owner: str) -> str:
    """First two path segments of a class name: the vendor/mod namespace, e.g. `net/caffeinemc`."""
    parts = owner.split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else owner


def package_of(owner: str) -> str:
    """Everything before the class's own name: `net/caffeinemc/mods/sodium/client/gui`."""
    return owner.rsplit("/", 1)[0] if "/" in owner else ""


def normalise_owner(token: str):
    """Normalise anything javap prints as a type into `pkg/Name` form, or None if it is not a class.

    Handles `Lfoo/Bar;`, `[Lfoo/Bar;`, `[[Lfoo/Bar;`, `foo/Bar`, `foo.Bar`, quoted forms, and
    primitive/array-of-primitive descriptors (which are not classes at all).
    """
    t = token.strip().strip('"')
    while t.startswith("["):
        t = t[1:]
    if not t:
        return None
    if len(t) == 1 and t in "BCDFIJSZV":  # primitive descriptor
        return None
    if t.startswith("L") and t.endswith(";"):
        t = t[1:-1]
    t = t.rstrip(";")
    t = t.replace(".", "/")
    if not t or not re.fullmatch(r"[\w/$]+", t):
        return None
    return t


def needs_javap(raw: bytes, own_classes) -> bool:
    """Cheap prefilter: does this class file mention any package path worth disassembling?

    Every candidate path in the class bytes that is neither under an ignored prefix nor a class of
    the mod's own jar means javap has something to find. Both `foo/Bar` and descriptor `Lfoo/Bar`
    spellings are considered, so `Lnet/minecraft/...` counts as ignored.
    """
    for m in CANDIDATE_RE.finditer(raw):
        cand = m.group(0).decode("ascii", "replace")
        variants = [cand]
        if len(cand) > 1 and cand[0] == "L":
            variants.append(cand[1:])
        if any(is_ignored(v) or v in own_classes for v in variants):
            continue
        return True
    return False


def split_javap_classes(out: str) -> dict:
    """Split a multi-class `javap -v` dump into {class name in slash form: its chunk}.

    The class name comes from the chunk's `this_class:` comment, falling back to the path on the
    `Classfile ...` header line.
    """
    blocks = []   # (header path, lines)
    for line in out.splitlines():
        m = CLASSFILE_RE.match(line)
        if m:
            blocks.append((m.group(1), [line]))
        elif blocks:
            blocks[-1][1].append(line)
    named = {}
    for header, lines in blocks:
        chunk = "\n".join(lines)
        m = THIS_CLASS_RE.search(chunk)
        if m:
            name = m.group(1)
        else:
            name = header.split("!/")[-1]
            name = name[:-6] if name.endswith(".class") else name
            name = name.lstrip("/")
        named[name] = chunk
    return named


def parse_javap_refs(chunk: str):
    """Every (owner, member-or-None) reference in one class's `javap -v -p` output."""
    refs = set()
    for kind, ref in CP_RE.findall(chunk):
        if kind == "Class":
            owner = normalise_owner(ref)
            if owner:
                refs.add((owner, None))
            continue
        m = re.match(r'^(.*?)\.("?[\w$<>]+"?):', ref)
        if not m:
            continue
        owner = normalise_owner(m.group(1))
        if owner:
            refs.add((owner, m.group(2).strip('"')))
    for block in MIXIN_VALUE_RE.findall(chunk):
        for tok in MIXIN_VALUE_CLASS_RE.findall(block):
            owner = normalise_owner(tok)
            if owner:
                refs.add((owner, None))
    for block in MIXIN_TARGETS_RE.findall(chunk):
        for tok in re.findall(r'"([^"]+)"', block):
            owner = normalise_owner(tok)
            if owner:
                refs.add((owner, None))
    for owner_raw, member in AT_TARGET_RE.findall(chunk):
        owner = normalise_owner(owner_raw)
        if owner:
            refs.add((owner, member or None))
    return refs


def mixin_configs(z: zipfile.ZipFile):
    """Mixin config file names declared by a jar (mods.toml, MANIFEST MixinConfigs, top-level json)."""
    names = set(z.namelist())
    cfgs = set()
    for meta in ("META-INF/neoforge.mods.toml", "META-INF/mods.toml"):
        if meta in names:
            text = z.read(meta).decode("utf-8", "replace")
            cfgs.update(re.findall(r'config\s*=\s*"([^"]+)"', text))
    if "META-INF/MANIFEST.MF" in names:
        text = z.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
        m = re.search(r"MixinConfigs:\s*([^\r\n]+)", text)
        if m:
            cfgs.update(x.strip() for x in m.group(1).split(",") if x.strip())
    cfgs.update(n for n in names if "/" not in n and n.endswith(".json") and "mixin" in n.lower())
    return {c for c in cfgs if c in names}


def mixin_classes(z: zipfile.ZipFile):
    """Mixin classes a jar declares, in slash form, restricted to those actually present in the jar."""
    names = set(z.namelist())
    found = set()
    for cfg_name in mixin_configs(z):
        try:
            cfg = json.loads(z.read(cfg_name).decode("utf-8", "replace"))
        except Exception:
            continue
        if not isinstance(cfg, dict):
            continue
        pkg = str(cfg.get("package", "")).replace(".", "/")
        for key in ("mixins", "client", "server"):
            for cls in cfg.get(key) or []:
                if not isinstance(cls, str):
                    continue
                path = f"{pkg}/{cls.replace('.', '/')}" if pkg else cls.replace(".", "/")
                if path + ".class" in names:
                    found.add(path)
    return found


def parse_javap_members(out: str) -> dict:
    """Parse a multi-class `javap -p` dump into {class: (member names, supertypes)}, slash form."""
    result = {}
    cur = None
    decl = re.compile(r"^(?!\s)(?:[\w@]+\s+)*(class|interface|enum|record|@interface)\s+(.*)$")
    for line in out.splitlines():
        if not line.strip():
            continue
        m = decl.match(line)
        if m:
            rest = strip_generics(m.group(2))
            rest = rest.rstrip("{ ").strip()
            head = re.split(r"\s+extends\s+|\s+implements\s+", rest)[0].strip()
            name = head.replace(".", "/")
            supers = set()
            for pattern in (r"\sextends\s+(.*?)(?:\simplements\s+|$)", r"\simplements\s+(.*)$"):
                mm = re.search(pattern, rest)
                if not mm:
                    continue
                for part in mm.group(1).split(","):
                    owner = normalise_owner(part.strip())
                    if owner:
                        supers.add(owner)
            cur = name
            result[cur] = (set(), supers)
            continue
        if cur is None:
            continue
        member = parse_member_line(line, cur)
        if member:
            result[cur][0].add(member)
    return result


def strip_generics(text: str) -> str:
    """Drop balanced <...> sections so `Foo<T extends Bar> extends Baz` parses cleanly."""
    out, depth = [], 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def parse_member_line(line: str, owner: str):
    """Member name declared by one line of `javap -p` output, or None."""
    s = strip_generics(line.strip())
    if s in ("}", "{"):
        return None
    if s.startswith("static {"):
        return "<clinit>"
    s = re.split(r"\s+throws\s+", s)[0].strip().rstrip(";").strip()
    if "(" in s:
        head = s.split("(", 1)[0].strip()
        tok = head.split()[-1] if head.split() else ""
        if not tok:
            return None
        if tok.replace(".", "/") == owner or tok.split(".")[-1] == owner.split("/")[-1]:
            return "<init>"
        return tok.split(".")[-1]
    toks = s.split()
    if len(toks) < 2:
        return None
    name = toks[-1]
    return name if re.fullmatch(r"[\w$]+", name) else None


def parse_client_mods(mods_dir: Path):
    """Every `side = "client"` mod in mods/*.pw.toml as {name, filename, url, hash, hash_format}."""
    out = []
    for toml_path in sorted(Path(mods_dir).glob("*.pw.toml")):
        with open(toml_path, "rb") as fh:
            doc = tomllib.load(fh)
        if doc.get("side") != "client":
            continue
        dl = doc.get("download") or {}
        out.append({
            "toml": toml_path.name,
            "name": doc.get("name", toml_path.stem),
            "filename": doc.get("filename", ""),
            "url": dl.get("url", ""),
            "hash": (dl.get("hash") or "").lower(),
            "hash_format": (dl.get("hash-format") or "").lower(),
        })
    return out


def classify(owner: str, own_classes, index, namespaces, packages) -> str:
    """One of: ignored | own | indexed | missing_class | absent_namespace.

    `missing_class` needs both the vendor namespace and the class's own package to be shipped by
    some jar in the pack; a namespace hit on its own is a sibling mod we do not ship.
    """
    if is_ignored(owner):
        return "ignored"
    if owner in own_classes:
        return "own"
    if owner in index:
        return "indexed"
    if namespace_of(owner) in namespaces and package_of(owner) in packages:
        return "missing_class"
    return "absent_namespace"


# ------------------------------------------------------------------------------------- jar plumbing
@dataclass
class Jar:
    label: str
    group: str
    classes: set = field(default_factory=set)
    path: Path = None          # on disk, for top-level jars
    container: Path = None     # containing jar, for nested ones
    entry: str = None          # entry name inside the container
    _materialised: Path = None

    def jar_path(self, tmpdir: Path) -> Path:
        if self.path is not None:
            return self.path
        if self._materialised is None:
            safe = re.sub(r"[^\w.+-]", "_", f"{self.group}__{Path(self.entry).name}")
            out = tmpdir / safe
            with zipfile.ZipFile(self.container) as z:
                out.write_bytes(z.read(self.entry))
            self._materialised = out
        return self._materialised

    def open(self):
        if self.path is not None:
            return zipfile.ZipFile(self.path)
        with zipfile.ZipFile(self.container) as z:
            return zipfile.ZipFile(io.BytesIO(z.read(self.entry)))


def collect_jars(paths):
    """Build the Jar list for every top-level jar plus its nested META-INF/jarjar jars."""
    jars, used = [], set()
    for path in paths:
        label = Path(path).name
        while label in used:
            label += "+"
        used.add(label)
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                top = Jar(label=label, group=label, path=Path(path),
                          classes={n[:-6] for n in names if n.endswith(".class")})
                jars.append(top)
                for n in names:
                    if n.startswith("META-INF/jarjar/") and n.endswith(".jar"):
                        try:
                            with zipfile.ZipFile(io.BytesIO(z.read(n))) as nz:
                                nested_names = nz.namelist()
                        except zipfile.BadZipFile:
                            continue
                        nlabel = f"{label} :: {Path(n).name}"
                        jars.append(Jar(label=nlabel, group=label, container=Path(path), entry=n,
                                        classes={x[:-6] for x in nested_names if x.endswith(".class")}))
        except zipfile.BadZipFile:
            print(f"warn: not a jar, skipped: {path}", file=sys.stderr)
    return jars


def download_client_jars(mods, dest: Path):
    """Download every client-side mod jar into dest, skipping ones already present with a good hash."""
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for mod in mods:
        if not mod["filename"] or not mod["url"]:
            print(f"warn: {mod['toml']} has no filename/url, skipped", file=sys.stderr)
            continue
        target = dest / mod["filename"]
        algo = mod["hash_format"] or "sha512"
        if target.exists() and (not mod["hash"] or file_hash(target, algo) == mod["hash"]):
            out.append(target)
            continue
        print(f"downloading {mod['filename']}", file=sys.stderr)
        with urllib.request.urlopen(mod["url"], timeout=120) as resp, open(target, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        if mod["hash"]:
            got = file_hash(target, algo)
            if got != mod["hash"]:
                sys.exit(f"FATAL: {algo} mismatch for {mod['filename']}\n  want {mod['hash']}\n  got  {got}")
        out.append(target)
    return out


def file_hash(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().lower()


def run_javap(args):
    proc = subprocess.run([JAVAP, *args], capture_output=True, text=True)
    return proc.stdout


def javap_verbose(jar_path: Path, classes):
    """`javap -v -p` over a jar's classes, batched, returned as {class: chunk}."""
    result = {}
    ordered = sorted(classes)
    for i in range(0, len(ordered), JAVAP_BATCH):
        batch = ordered[i:i + JAVAP_BATCH]
        out = run_javap(["-v", "-p", "-cp", str(jar_path), *[c.replace("/", ".") for c in batch]])
        result.update(split_javap_classes(out))
    return result


def javap_declarations(jar_path: Path, classes):
    """`javap -p` over a jar's classes, batched, returned as {class: (members, supers)}."""
    result = {}
    ordered = sorted(classes)
    for i in range(0, len(ordered), JAVAP_BATCH):
        batch = ordered[i:i + JAVAP_BATCH]
        out = run_javap(["-p", "-cp", str(jar_path), *[c.replace("/", ".") for c in batch]])
        result.update(parse_javap_members(out))
    return result


class MemberResolver:
    """Answers "does this class (or an in-pack supertype) declare this member?", batching javap."""

    def __init__(self, index, by_label, tmpdir):
        self.index = index
        self.by_label = by_label
        self.tmpdir = tmpdir
        self.info = {}

    def resolve(self, owners, rounds=8):
        wanted = {o for o in owners if o in self.index}
        for _ in range(rounds):
            todo = {o for o in wanted if o not in self.info}
            if not todo:
                break
            by_jar = {}
            for owner in todo:
                by_jar.setdefault(self.index[owner], set()).add(owner)
            for label, group in by_jar.items():
                jar = self.by_label[label]
                parsed = javap_declarations(jar.jar_path(self.tmpdir), group)
                for owner in group:
                    # None means javap could not read it: absence is then unprovable, not a miss.
                    self.info[owner] = parsed.get(owner)
                self.info.update({k: v for k, v in parsed.items() if k not in group})
            for owner in todo:
                info = self.info.get(owner)
                for sup in (info[1] if info else ()):
                    if sup in self.index:
                        wanted.add(sup)

    def exists(self, owner: str, name: str) -> bool:
        """True if the member exists, or if absence cannot be proved (supertype outside the pack)."""
        if name in ALWAYS_OK_MEMBERS:
            return True
        seen, queue = set(), [owner]
        while queue:
            cur = queue.pop()
            if cur in seen:
                continue
            seen.add(cur)
            if cur == "java/lang/Object":
                if name in OBJECT_MEMBERS:
                    return True
                continue
            if cur not in self.index:
                return True            # supertype is Minecraft/JDK/absent: cannot prove a miss
            info = self.info.get(cur)
            if info is None:
                return True            # javap could not read the owner: cannot prove a miss either
            members, supers = info
            if name in members:
                return True
            queue.extend(supers)
        # An interface-only chain never reaches java/lang/Object, whose members it still inherits.
        return name in OBJECT_MEMBERS


# ------------------------------------------------------------------------------------------- report
@dataclass
class Finding:
    kind: str
    mixin: str
    owner: str
    member: str = None
    note: str = ""

    def line(self):
        target = f"{self.owner}.{self.member}" if self.member else self.owner
        tag = "MISSING CLASS " if self.kind == "class" else "MISSING MEMBER"
        return f"   {tag} {self.mixin.split('/')[-1]} -> {target}{self.note}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verbose", action="store_true", help="list every cross-mod reference checked")
    ap.add_argument("--jar", action="append", default=[], help="extra jar to include (repeatable)")
    args = ap.parse_args(argv)

    started = time.monotonic()
    if not os.access(JAVAP, os.X_OK):
        sys.exit(f"FATAL: javap not found at {JAVAP} (set JAVA_HOME)")

    paths = sorted(SERVER_MODS.glob("*.jar")) if SERVER_MODS.is_dir() else []
    if not paths:
        print(f"warn: no jars in {SERVER_MODS} -- run tools/server_boot.sh first", file=sys.stderr)
    paths += download_client_jars(parse_client_mods(MODS_DIR), CLIENT_JARS)
    for extra in args.jar:
        p = Path(extra)
        if not p.is_file():
            sys.exit(f"FATAL: --jar {extra} does not exist")
        paths.append(p)

    tmpdir = Path(tempfile.mkdtemp(prefix="mixincheck-", dir=os.environ.get("TMPDIR") or None))
    try:
        jars = collect_jars(paths)
        by_label = {j.label: j for j in jars}
        index, namespaces, packages = {}, {}, {}
        for jar in jars:
            for cls in jar.classes:
                index.setdefault(cls, jar.label)
                namespaces.setdefault(namespace_of(cls), jar.label)
                packages.setdefault(package_of(cls), jar.label)
        own_by_group = {}
        for jar in jars:
            own_by_group.setdefault(jar.group, set()).update(jar.classes)

        scanned_classes = 0
        checked = skipped = 0
        findings = {}
        verbose_lines = []
        pending = []   # (label, mixin, owner, member)

        for jar in jars:
            try:
                z = jar.open()
            except zipfile.BadZipFile:
                continue
            with z:
                mixins = mixin_classes(z)
                if not mixins:
                    continue
                own = own_by_group[jar.group]
                interesting = []
                for cls in sorted(mixins):
                    scanned_classes += 1
                    raw = z.read(cls + ".class")
                    if needs_javap(raw, own):
                        interesting.append(cls)
            if not interesting:
                continue
            chunks = javap_verbose(jar.jar_path(tmpdir), interesting)
            for cls in interesting:
                chunk = chunks.get(cls)
                if chunk is None:
                    continue
                for owner, member in sorted(parse_javap_refs(chunk), key=lambda r: (r[0], r[1] or "")):
                    verdict = classify(owner, own, index, namespaces, packages)
                    if verdict in ("ignored", "own"):
                        continue
                    if verdict == "absent_namespace":
                        skipped += 1
                        continue
                    checked += 1
                    if verdict == "missing_class":
                        home = packages[package_of(owner)]
                        findings.setdefault(jar.label, []).append(
                            Finding("class", cls, owner, None,
                                    f"   [{package_of(owner)} is in {home}]"))
                    else:
                        home = index[owner]
                        pending.append((jar.label, cls, owner, member))
                    if args.verbose:
                        target = f"{owner}.{member}" if member else owner
                        verbose_lines.append(
                            f"   ref {jar.label}: {cls.split('/')[-1]} -> {target}   [{home}]")

        resolver = MemberResolver(index, by_label, tmpdir)
        resolver.resolve({owner for _l, _c, owner, member in pending if member})
        for label, cls, owner, member in pending:
            if member and not resolver.exists(owner, member):
                findings.setdefault(label, []).append(
                    Finding("member", cls, owner, member, f"   [{owner} is in {index[owner]}]"))

        if args.verbose:
            for line in verbose_lines:
                print(line)
        missing = 0
        for label in sorted(findings):
            lines = sorted({f.line() for f in findings[label]})
            missing += len(lines)
            print(f"## {label}: {len(lines)} missing")
            for line in lines:
                print(line)
        print(f"client mixins: {len(jars)} jars, {scanned_classes} mixin classes scanned, "
              f"{checked} cross-mod references checked, {skipped} optional-compat skipped, "
              f"{missing} missing")
        print(f"elapsed: {time.monotonic() - started:.1f}s")
        return 1 if missing else 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
