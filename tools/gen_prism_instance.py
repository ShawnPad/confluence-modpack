"""Build dist/confluence-prism.zip: a Prism Launcher "Export Instance" zip whose
pre-launch command runs packwiz-installer-bootstrap, so the pack installs and
auto-updates on every launch.

Every key, uid and value below comes from research/phase6-prism-instance.md
(cited inline as "prism §N") or research/phase6-tooling-worldgen-quests.md §1g
(cited as "tooling §1g"). Nothing here is from memory.

Zip layout (prism §3, §6): instance.cfg, mmc-pack.json and minecraft/ sit at the
zip root with no wrapper folder, exactly what Prism's own Export Instance writes
(ExportToZipTask with destinationPrefix ""). Stdlib only.
"""
import json
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "confluence-prism.zip"

# tooling §1g: latest release v0.0.3 of packwiz-installer-bootstrap.
BOOTSTRAP_URL = (
    "https://github.com/packwiz/packwiz-installer-bootstrap/releases/download/"
    "v0.0.3/packwiz-installer-bootstrap.jar"
)
BOOTSTRAP_JAR = "packwiz-installer-bootstrap.jar"
# The pack.toml the installer follows (plan Task 7, Step 1).
PACK_TOML_URL = "https://raw.githubusercontent.com/ShawnPad/confluence-modpack/main/pack.toml"

MC_VERSION = "1.21.1"          # prism §2 (this pack's versions, per tooling §2)
NEOFORGE_VERSION = "21.1.250"  # prism §2 (this pack's versions, per tooling §2)
LWJGL_VERSION = "3.3.3"        # prism §2: net.minecraft 1.21.1 suggests org.lwjgl3 3.3.3

# prism §4: the documented client pre-launch command, "$INST_JAVA" -jar <bootstrap> <pack.toml>.
# prism §1 (issue #1134): the embedded double quotes MUST be written backslash-escaped in
# the INI value, or Qt's INI writer flattens the quoting the first time Prism re-saves it.
MIN_MEM_MIB = 2048
MAX_MEM_MIB = 6144

PRE_LAUNCH_COMMAND = f'\\"$INST_JAVA\\" -jar {BOOTSTRAP_JAR} {PACK_TOML_URL}'

INSTANCE_CFG = "\n".join([
    "[General]",            # prism §1: the implicit General group, the header Prism itself writes
    "ConfigVersion=1.3",    # prism §1: the version INIFile::saveFile writes
    "InstanceType=OneSix",  # prism §1: must be "" or exactly "OneSix", else the instance is rejected
    "name=Confluence",      # prism §1 "name" (prism §5: the importer replaces it with the user's choice)
    "iconKey=default",      # prism §1 "iconKey", default value
    # prism §1 "notes" is free text; §6 uses an em dash, written here as "-" to keep the file ASCII.
    "notes=Confluence - NeoForge progression modpack (auto-updates via packwiz)",
    "OverrideCommands=true",  # prism §1: must be true for the instance's PreLaunchCommand to apply
    f"PreLaunchCommand={PRE_LAUNCH_COMMAND}",  # prism §1 key, §4 value
    # prism §1 (MinecraftInstance.cpp L184-213): OverrideMemory gates MinMemAlloc/MaxMemAlloc (integers, MiB).
    # Prism's default 4096 MiB heap ran out on a 128-mod singleplayer world (issue #1, crash-2026-09-12_19.29.24-server:
    # `java.lang.OutOfMemoryError: Java heap space`, `-Xmx4096m`), so the instance asks for 6 GiB. Prism reads
    # instance.cfg once at import; instances imported before 0.1.3 set it by hand (PLAYTEST.md, Setup).
    "OverrideMemory=true",
    f"MinMemAlloc={MIN_MEM_MIB}",
    f"MaxMemAlloc={MAX_MEM_MIB}",
]) + "\n"

# prism §2 / §6: the minimal generator shape (no cached* fields); formatVersion must be the
# integer 1; org.lwjgl3 listed explicitly (dependencyOnly) per §2's recommendation so the
# first launch does not depend on Prism's online resolve step injecting it.
MMC_PACK = {
    "components": [
        {"dependencyOnly": True, "uid": "org.lwjgl3", "version": LWJGL_VERSION},
        {"important": True, "uid": "net.minecraft", "version": MC_VERSION},
        {"uid": "net.neoforged", "version": NEOFORGE_VERSION},
    ],
    "formatVersion": 1,
}


def download_bootstrap(dest_dir: Path) -> Path:
    """Fetch the bootstrap jar (tooling §1g) into dest_dir and return its path."""
    dest = Path(dest_dir) / BOOTSTRAP_JAR
    req = urllib.request.Request(BOOTSTRAP_URL, headers={"User-Agent": "confluence-modpack-tools"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if not data.startswith(b"PK"):  # a jar is a zip; anything else is an error page
        raise RuntimeError(f"{BOOTSTRAP_URL} did not return a jar ({len(data)} bytes)")
    dest.write_bytes(data)
    return dest


def build_zip(out_path: Path, bootstrap_jar: Path) -> Path:
    """Write the instance zip with the three entries at the root (prism §3, §6)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("instance.cfg", INSTANCE_CFG)                       # prism §1
        zf.writestr("mmc-pack.json", json.dumps(MMC_PACK, indent=4) + "\n")  # prism §2
        zf.write(bootstrap_jar, arcname=f"minecraft/{BOOTSTRAP_JAR}")   # prism §3: "minecraft/", no dot
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    out = Path(args[0]) if args else DEFAULT_OUT
    with tempfile.TemporaryDirectory() as tmp:
        jar = download_bootstrap(Path(tmp))
        build_zip(out, jar)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
