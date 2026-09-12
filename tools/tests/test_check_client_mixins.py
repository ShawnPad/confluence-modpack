"""Unit tests for tools/check_client_mixins.py -- no network, no javap, no jars on disk."""
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_client_mixins import (
    MemberResolver,
    classify,
    mixin_classes,
    mixin_configs,
    namespace_of,
    needs_javap,
    normalise_owner,
    package_of,
    parse_client_mods,
    parse_javap_members,
    parse_javap_refs,
    split_javap_classes,
)

SODIUM = "net/caffeinemc/mods/sodium/client/gui/SodiumGameOptions"

# A trimmed but faithful `javap -v -p` dump: constant pool entries plus the three annotation forms.
JAVAP_V = f"""\
Classfile jar:file:///pack/.run/client-jars/iris.jar!/net/irisshaders/iris/compat/sodium/mixin/FooMixin.class
  Last modified Jun 17, 2025; size 3763 bytes
public class net.irisshaders.iris.compat.sodium.mixin.FooMixin
  this_class: #26                         // net/irisshaders/iris/compat/sodium/mixin/FooMixin
  super_class: #2                         // java/lang/Object
Constant pool:
   #1 = Methodref          #2.#3          // java/lang/Object."<init>":()V
   #2 = Class              #4             // java/lang/Object
   #7 = Class              #8             // {SODIUM}
   #9 = Fieldref           #10.#11        // {SODIUM}.quality:L{SODIUM}$QualitySettings;
  #15 = Methodref          #10.#16        // {SODIUM}.defaults:()L{SODIUM};
  #19 = InterfaceMethodref #20.#21        // other/mod/Api.getInstance:()Lother/mod/Api;
  #45 = Class              #46            // [Lother/mod/Widget;
{{}}
    RuntimeVisibleAnnotations:
      0: #33(#34=[e#35.#36])
        org.spongepowered.asm.mixin.Mixin(
          value=[class Lnet/caffeinemc/mods/sodium/client/render/chunk/RenderSectionManager;]
          targets=["net.caffeinemc.mods.sodium.client.gui.SodiumGameOptionPages"]
        )
      1: #40(#41=s#42)
        org.spongepowered.asm.mixin.injection.At(
          target="L{SODIUM};quality:L{SODIUM}$QualitySettings;"
        )
      2: #43(#41=s#44)
        org.spongepowered.asm.mixin.injection.At(
          target="Lother/mod/Api;doThing(I)V"
        )
"""


def refs():
    return parse_javap_refs(JAVAP_V)


# ------------------------------------------------------------------ javap -v reference extraction
def test_constant_pool_class_entry_is_a_bare_class_reference():
    assert (SODIUM, None) in refs()


def test_constant_pool_fieldref_and_methodref_carry_the_member_name():
    assert (SODIUM, "quality") in refs()
    assert (SODIUM, "defaults") in refs()


def test_constant_pool_interfacemethodref_is_picked_up():
    assert ("other/mod/Api", "getInstance") in refs()


def test_quoted_init_member_keeps_no_quotes():
    assert ("java/lang/Object", "<init>") in refs()


def test_array_class_constant_normalises_to_the_element_class():
    assert ("other/mod/Widget", None) in refs()
    assert not any(o.startswith("[") for o, _ in refs())


def test_mixin_value_class_target():
    assert ("net/caffeinemc/mods/sodium/client/render/chunk/RenderSectionManager", None) in refs()


def test_mixin_string_targets_are_dotted_and_normalise_to_slashes():
    assert ("net/caffeinemc/mods/sodium/client/gui/SodiumGameOptionPages", None) in refs()


def test_at_target_field_form_gives_owner_and_member():
    assert (SODIUM, "quality") in refs()


def test_at_target_method_form_gives_owner_and_member():
    assert ("other/mod/Api", "doThing") in refs()


def test_no_descriptor_junk_leaks_into_owners():
    import re as _re

    assert ("Lother/mod/Api", None) not in refs()
    for owner, member in refs():
        assert _re.fullmatch(r"[\w$]+(?:/[\w$]+)*", owner), owner
        assert member is None or _re.fullmatch(r"[\w$<>]+", member), member


def test_multiple_value_classes_in_one_annotation():
    chunk = "          value=[class La/b/C;,class La/b/D;]\n"
    assert parse_javap_refs(chunk) == {("a/b/C", None), ("a/b/D", None)}


def test_value_class_without_descriptor_wrapper():
    assert parse_javap_refs("          value=[class a/b/C]\n") == {("a/b/C", None)}


# ------------------------------------------------------------------------- descriptor normalisation
def test_normalise_owner_forms():
    assert normalise_owner("Lfoo/Bar;") == "foo/Bar"
    assert normalise_owner("[Lfoo/Bar;") == "foo/Bar"
    assert normalise_owner("[[Lfoo/Bar;") == "foo/Bar"
    assert normalise_owner("foo/Bar") == "foo/Bar"
    assert normalise_owner("foo.Bar$Inner") == "foo/Bar$Inner"
    assert normalise_owner('"[Ljava/lang/Object;"') == "java/lang/Object"


def test_normalise_owner_rejects_primitives_and_noise():
    assert normalise_owner("I") is None
    assert normalise_owner("[I") is None
    assert normalise_owner("") is None
    assert normalise_owner("(I)V") is None


def test_namespace_and_package_helpers():
    assert namespace_of(SODIUM) == "net/caffeinemc"
    assert package_of(SODIUM) == "net/caffeinemc/mods/sodium/client/gui"
    assert package_of("TopLevel") == ""


# --------------------------------------------------------------------------- multi-class javap -v
def test_split_javap_classes_uses_this_class():
    out = JAVAP_V + JAVAP_V.replace("FooMixin", "BarMixin")
    chunks = split_javap_classes(out)
    assert set(chunks) == {
        "net/irisshaders/iris/compat/sodium/mixin/FooMixin",
        "net/irisshaders/iris/compat/sodium/mixin/BarMixin",
    }
    assert "SodiumGameOptionPages" in chunks["net/irisshaders/iris/compat/sodium/mixin/BarMixin"]


def test_split_javap_classes_falls_back_to_the_header_path():
    out = "Classfile jar:file:///x.jar!/a/b/C.class\n  stuff\n"
    assert set(split_javap_classes(out)) == {"a/b/C"}


# ----------------------------------------------------------------------------- byte-scan prefilter
def test_needs_javap_false_when_only_ignored_and_own_paths_appear():
    raw = b"\x00net/minecraft/core/BlockPos\x00Lnet/minecraft/world/level/Level;\x00my/mod/Thing\x00"
    assert needs_javap(raw, {"my/mod/Thing"}) is False


def test_needs_javap_true_for_a_foreign_package_path():
    raw = b"\x00net/minecraft/core/BlockPos\x00" + SODIUM.encode() + b"\x00"
    assert needs_javap(raw, {"my/mod/Thing"}) is True


def test_needs_javap_ignores_the_L_descriptor_prefix():
    raw = b"\x00Lorg/spongepowered/asm/mixin/injection/callback/CallbackInfo;\x00"
    assert needs_javap(raw, set()) is False


# --------------------------------------------------------------------------- owner classification
INDEX = {SODIUM.replace("SodiumGameOptions", "SodiumOptions"): "sodium.jar",
         "other/mod/Api": "other.jar",
         "me/shedaniel/clothconfig2/api/Thing": "cloth.jar"}
NAMESPACES = {"net/caffeinemc": "sodium.jar", "other/mod": "other.jar", "me/shedaniel": "cloth.jar"}
PACKAGES = {"net/caffeinemc/mods/sodium/client/gui": "sodium.jar",
            "other/mod": "other.jar",
            "me/shedaniel/clothconfig2/api": "cloth.jar"}
OWN = {"my/mod/Thing"}


def verdict(owner):
    return classify(owner, OWN, INDEX, NAMESPACES, PACKAGES)


def test_minecraft_and_library_owners_are_ignored():
    assert verdict("net/minecraft/core/BlockPos") == "ignored"
    assert verdict("org/spongepowered/asm/mixin/Mixin") == "ignored"
    assert verdict("com/google/common/collect/ImmutableList") == "ignored"


def test_own_jar_owner_is_skipped():
    assert verdict("my/mod/Thing") == "own"


def test_indexed_owner_is_checked():
    assert verdict("other/mod/Api") == "indexed"


def test_missing_class_in_a_shipped_package_is_the_iris_sodium_case():
    assert verdict(SODIUM) == "missing_class"
    assert verdict(SODIUM + "$PerformanceSettings") == "missing_class"


def test_absent_namespace_is_optional_compat():
    assert verdict("dev/nobody/absentmod/Thing") == "absent_namespace"


def test_sibling_mod_in_a_shared_vendor_namespace_is_not_a_break():
    """me/shedaniel is in the pack (Cloth Config) but me/shedaniel/rei (REI) is not shipped."""
    assert verdict("me/shedaniel/rei/impl/client/ClientHelperImpl") == "absent_namespace"


# ----------------------------------------------------------------------------- javap -p member scan
JAVAP_P = """\
Compiled from "SodiumOptions.java"
public class net.caffeinemc.mods.sodium.client.gui.SodiumOptions extends a.b.Base implements a.b.Iface, a.b.Other {
  private static final java.lang.String DEFAULT_FILE_NAME;
  public final net.caffeinemc.mods.sodium.client.gui.SodiumOptions$QualitySettings quality;
  private net.caffeinemc.mods.sodium.client.gui.SodiumOptions();
  public static net.caffeinemc.mods.sodium.client.gui.SodiumOptions defaults();
  public static void writeToDisk(net.caffeinemc.mods.sodium.client.gui.SodiumOptions) throws java.io.IOException;
  public <T> T pick(java.util.List<T>);
  static {};
}
Compiled from "Base.java"
public abstract class a.b.Base<T extends java.lang.Comparable<T>> {
  protected int inherited;
  public void fromTheSuperclass();
}
"""


def test_parse_javap_members_fields_methods_ctor_and_clinit():
    parsed = parse_javap_members(JAVAP_P)
    members, supers = parsed["net/caffeinemc/mods/sodium/client/gui/SodiumOptions"]
    assert {"DEFAULT_FILE_NAME", "quality", "defaults", "writeToDisk", "pick", "<init>", "<clinit>"} <= members
    assert supers == {"a/b/Base", "a/b/Iface", "a/b/Other"}


def test_parse_javap_members_strips_class_level_generics():
    parsed = parse_javap_members(JAVAP_P)
    assert "a/b/Base" in parsed
    assert parsed["a/b/Base"][0] == {"inherited", "fromTheSuperclass"}


# ------------------------------------------------------------------------------- member resolution
def resolver(info, index):
    r = MemberResolver(index, {}, Path("/nonexistent"))
    r.info = info
    return r


def test_member_present_on_the_owner():
    r = resolver({"a/b/C": ({"doThing"}, set())}, {"a/b/C": "x.jar"})
    assert r.exists("a/b/C", "doThing") is True


def test_member_inherited_from_an_in_pack_supertype():
    r = resolver({"a/b/C": (set(), {"a/b/Base"}), "a/b/Base": ({"fromTheSuperclass"}, set())},
                 {"a/b/C": "x.jar", "a/b/Base": "x.jar"})
    assert r.exists("a/b/C", "fromTheSuperclass") is True


def test_member_absent_everywhere_in_the_pack_is_a_miss():
    r = resolver({"a/b/C": ({"other"}, {"a/b/Base"}), "a/b/Base": ({"more"}, set())},
                 {"a/b/C": "x.jar", "a/b/Base": "x.jar"})
    assert r.exists("a/b/C", "doThing") is False


def test_supertype_outside_the_pack_makes_absence_unprovable():
    r = resolver({"a/b/C": (set(), {"net/minecraft/world/entity/Entity"})}, {"a/b/C": "x.jar"})
    assert r.exists("a/b/C", "anythingAtAll") is True


def test_an_owner_javap_could_not_read_is_not_reported_as_a_miss():
    r = resolver({"a/b/C": None}, {"a/b/C": "x.jar"})
    assert r.exists("a/b/C", "doThing") is True


def test_object_members_and_constructors_are_always_fine():
    r = resolver({"a/b/C": (set(), set())}, {"a/b/C": "x.jar"})
    assert r.exists("a/b/C", "<init>") is True
    assert r.exists("a/b/C", "hashCode") is True


# ------------------------------------------------------------------------- mixin config discovery
def build_jar(entries) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    buf.seek(0)
    return zipfile.ZipFile(buf)


def sample_jar():
    return build_jar({
        "META-INF/neoforge.mods.toml": (
            '[[mods]]\nmodId="example"\n\n[[mixins]]\nconfig = "example.mixins.json"\n'
        ),
        "META-INF/MANIFEST.MF": "Manifest-Version: 1.0\nMixinConfigs: manifest.mixins.json, gone.json\n",
        "example.mixins.json": json.dumps(
            {"package": "com.example.mixin", "mixins": ["FooMixin"], "client": ["client.BarMixin"],
             "server": ["ServerOnlyMixin"]}
        ),
        "manifest.mixins.json": json.dumps({"package": "com.example.extra", "mixins": ["BazMixin"]}),
        "client-mixin-overrides.json": json.dumps({"package": "com.example.over", "client": ["QuxMixin"]}),
        "assets/example/not-a-mixin.json": json.dumps({"package": "com.nope", "mixins": ["NopeMixin"]}),
        "com/example/mixin/FooMixin.class": b"\xca\xfe\xba\xbe",
        "com/example/mixin/client/BarMixin.class": b"\xca\xfe\xba\xbe",
        "com/example/extra/BazMixin.class": b"\xca\xfe\xba\xbe",
        "com/example/over/QuxMixin.class": b"\xca\xfe\xba\xbe",
    })


def test_mixin_configs_from_mods_toml_manifest_and_top_level_json():
    with sample_jar() as z:
        assert mixin_configs(z) == {
            "example.mixins.json", "manifest.mixins.json", "client-mixin-overrides.json"
        }


def test_mixin_config_named_in_the_manifest_but_absent_from_the_jar_is_dropped():
    with sample_jar() as z:
        assert "gone.json" not in mixin_configs(z)


def test_a_mixin_json_under_assets_is_not_a_config():
    with sample_jar() as z:
        assert "assets/example/not-a-mixin.json" not in mixin_configs(z)


def test_mixin_classes_are_package_prefixed_across_mixins_client_and_server():
    with sample_jar() as z:
        assert mixin_classes(z) == {
            "com/example/mixin/FooMixin",
            "com/example/mixin/client/BarMixin",
            "com/example/extra/BazMixin",
            "com/example/over/QuxMixin",
        }


def test_a_declared_mixin_class_missing_from_the_jar_is_skipped():
    """example.mixins.json lists ServerOnlyMixin, but the jar ships no such class."""
    with sample_jar() as z:
        assert not any(c.endswith("ServerOnlyMixin") for c in mixin_classes(z))


# ------------------------------------------------------------------------------ pw.toml parsing
def test_parse_client_mods_picks_only_client_side_entries(tmp_path):
    (tmp_path / "sodium.pw.toml").write_text(
        'name = "Sodium"\n'
        'filename = "sodium-neoforge-0.8.13+mc1.21.1.jar"\n'
        'side = "client"\n\n'
        "[download]\n"
        'url = "https://cdn.modrinth.com/data/AANobbMI/versions/uMOpc5uV/sodium.jar"\n'
        'hash-format = "sha512"\n'
        'hash = "4F537696AF"\n'
    )
    (tmp_path / "mekanism.pw.toml").write_text(
        'name = "Mekanism"\nfilename = "mekanism.jar"\n\n[download]\nurl = "https://x/mekanism.jar"\n'
    )
    (tmp_path / "server-only.pw.toml").write_text(
        'name = "Server Thing"\nfilename = "s.jar"\nside = "server"\n\n[download]\nurl = "https://x/s.jar"\n'
    )
    mods = parse_client_mods(tmp_path)
    assert [m["name"] for m in mods] == ["Sodium"]
    only = mods[0]
    assert only["filename"] == "sodium-neoforge-0.8.13+mc1.21.1.jar"
    assert only["url"].endswith("/sodium.jar")
    assert only["hash"] == "4f537696af"       # lower-cased for comparison against hashlib output
    assert only["hash_format"] == "sha512"


def test_parse_client_mods_tolerates_a_client_mod_with_no_download_block(tmp_path):
    (tmp_path / "weird.pw.toml").write_text('name = "Weird"\nfilename = "w.jar"\nside = "client"\n')
    mods = parse_client_mods(tmp_path)
    assert mods[0]["url"] == "" and mods[0]["hash"] == ""
