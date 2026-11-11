// priority: 1
// The dev flag (v1.0 spec docs/superpowers/specs/2026-11-11-v1.0-catalyst-tier-design.md §7.2, A16). tools/server_boot.sh
// appends -Dconfluence.dev=true to the local run folder's user_jvm_args.txt; production's start.sh never sets it. dump.js,
// tagcheck.js and routeexport.js register their handlers only when this is true, and otherwise log one
// '<name>: skipped (confluence.dev unset)' line, which tools/ptero_wait.py evidence expects on production and
// tools/check_tags.py rejects locally. Boolean.getBoolean(name) is true only when the system property equals "true" (JDK 21).
// KubeJS lets scripts load the class: kubejs-neoforge-2101.7.2-build.377.jar!kubejs.classfilter.txt denies java.lang on line 2
// and allows java.lang.Boolean on line 12 (v1.0 plan Task 3 Step 1). `!!` keeps the value a JS boolean under Rhino. Under the
// node test runner `Java` is an inert, truthy stand-in, so the flag reads true there and the handlers are recorded.
const CONFLUENCE_DEV = !!Java.loadClass('java.lang.Boolean').getBoolean('confluence.dev')
