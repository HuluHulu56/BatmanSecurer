#!/usr/bin/env python3
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()

RELATIVE_TARGET = (
    "subprojects/frida-gum/bindings/gumjs/gumquickcore.c"
)

ENTRY_TO_ADD = '  JS_CFUNC_DEF ("loadBytecode", 0, gumjs_script_load_bytecode),\n'
DECLARE_LINE = 'GUMJS_DECLARE_FUNCTION (gumjs_script_load_bytecode)\n'

FUNC_BODY_VARIANT_1 = r'''
    name_copy = g_strdup(name);
    g_hash_table_insert(
            es_assets,
            name_copy,
            gum_es_asset_new(name_copy, NULL, 0, NULL)
    );
'''

FUNC_BODY_VARIANT_2 = r'''
    name_copy = g_strdup(name);
    g_hash_table_insert(
        es_assets,
        name_copy,
        gum_es_asset_new_take(name_copy, NULL, 0)
    );
'''


def die(msg: str) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(1)


def build_function(variant_body: str) -> str:
    return r'''
GUMJS_DEFINE_FUNCTION (gumjs_script_load_bytecode)
{
    GHashTable * es_assets = core->program->es_assets;
    const gchar * name;
    JSValue byte_val, perform_init, module;
    gchar * name_copy;
    GumQuickModuleInitOperation * op;
    GSource * gsource;

    if (!_gum_quick_args_parse(args, "sOF", &name, &byte_val, &perform_init))
        return JS_EXCEPTION;

    if (g_hash_table_contains(es_assets, name))
        return _gum_quick_throw(ctx, "module '%s' already exists", name);

    uint8_t *buf = NULL;
    size_t buf_len = 0;

    buf = JS_GetArrayBuffer(ctx, &buf_len, byte_val);

    if (buf == NULL) {
        size_t byte_offset = 0;
        size_t byte_length = 0;
        size_t bytes_per_elem = 0;

        JSValue ab = JS_GetTypedArrayBuffer(
                ctx,
                byte_val,
                &byte_offset,
                &byte_length,
                &bytes_per_elem
        );

        if (JS_IsException(ab)) {
            return _gum_quick_throw(ctx,
                "expected ArrayBuffer or TypedArray containing QuickJS bytecode");
        }

        size_t abuf_len = 0;
        uint8_t *abuf = JS_GetArrayBuffer(ctx, &abuf_len, ab);
        JS_FreeValue(ctx, ab);

        if (abuf == NULL) {
            return _gum_quick_throw(ctx,
                "invalid TypedArray: could not get underlying ArrayBuffer");
        }

        buf = abuf + byte_offset;
        buf_len = byte_length;
    }

    module = JS_ReadObject(
            ctx,
            buf,
            buf_len,
            JS_READ_OBJ_BYTECODE | JS_READ_OBJ_REFERENCE | JS_READ_OBJ_SAB
    );

    if (JS_IsException(module)) {
        return _gum_quick_script_rethrow_parse_error_with_decorations(
                core->script, ctx, name);
    }
''' + variant_body + r'''
    op = g_slice_new(GumQuickModuleInitOperation);
    op->module = module;
    op->perform_init = JS_DupValue(ctx, perform_init);
    op->core = core;

    gsource = g_idle_source_new();
    g_source_set_callback(
            gsource,
            (GSourceFunc) gum_quick_core_init_module,
            op,
            NULL
    );
    g_source_attach(
            gsource,
            gum_script_scheduler_get_js_context(core->scheduler)
    );
    g_source_unref(gsource);

    _gum_quick_core_pin(core);

    return JS_UNDEFINED;
}
'''.lstrip("\n")


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 1
    i = open_pos + 1
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def detect_variant(text: str) -> str:
    """Return '1' or '2' depending on which allocator the source uses"""
    if "gum_es_asset_new_take" in text:
        console.print("[*] Detected gum_es_asset_new_take → using variant 2", style="yellow")
        return '2'
    elif "gum_es_asset_new" in text:
        console.print("[*] Detected gum_es_asset_new → using variant 1", style="yellow")
        return '1'
    else:
        die("Cannot detect allocator variant in gumquickcore.c")


def main() -> None:
    if len(sys.argv) != 2:
        die("Usage: script.py <frida_root_dir>")

    root_arg = sys.argv[1]

    script_dir = Path(__file__).resolve().parent
    root_dir = Path(root_arg).expanduser()
    if not root_dir.is_absolute():
        root_dir = (script_dir / root_dir).resolve()

    target_file = root_dir / RELATIVE_TARGET
    if not target_file.exists():
        die(f"Target file not found: {target_file}")

    text = target_file.read_text(encoding="utf-8")

    # ---- Auto-detect variant -----------------------------------------------
    variant = detect_variant(text)
    if variant == '1':
        function_impl = build_function(FUNC_BODY_VARIANT_1)
    else:
        function_impl = build_function(FUNC_BODY_VARIANT_2)

    # ---- PATCH 1: JS function entry ----------------------------------------
    if ENTRY_TO_ADD not in text:
        marker = "static const JSCFunctionListEntry gumjs_script_entries[] ="
        mpos = text.find(marker)
        if mpos == -1:
            die("gumjs_script_entries not found")

        open_brace = text.find("{", mpos)
        if open_brace == -1:
            die("Opening brace for gumjs_script_entries not found")

        close_brace = find_matching_brace(text, open_brace)
        if close_brace == -1:
            die("Closing brace for gumjs_script_entries not found")

        insert_pos = close_brace
        text = text[:insert_pos] + ENTRY_TO_ADD + text[insert_pos:]
        console.print("[+] Added JS_CFUNC_DEF(loadBytecode) inside gumjs_script_entries", style="green")
    else:
        console.print("[=] JS_CFUNC_DEF(loadBytecode) already present", style="cyan")

    # ---- PATCH 2: Declaration ----------------------------------------------
    if DECLARE_LINE not in text:
        anchor = "GUMJS_DECLARE_FUNCTION (gumjs_script_unbind_weak)"
        idx = text.find(anchor)
        if idx == -1:
            die("Declaration anchor not found")

        insert_pos = text.find("\n", idx) + 1
        text = text[:insert_pos] + DECLARE_LINE + text[insert_pos:]
        console.print("[+] Added GUMJS_DECLARE_FUNCTION(load_bytecode)", style="green")
    else:
        console.print("[=] GUMJS_DECLARE_FUNCTION(load_bytecode) already present", style="cyan")

    # ---- PATCH 3: Implementation -------------------------------------------
    if "GUMJS_DEFINE_FUNCTION (gumjs_script_load_bytecode)" not in text:
        anchor = "GUMJS_DEFINE_FUNCTION (gumjs_script_unbind_weak)"
        idx = text.find(anchor)
        if idx == -1:
            die("Function anchor not found")

        open_brace = text.find("{", idx)
        close_brace = find_matching_brace(text, open_brace)
        if close_brace == -1:
            die("Failed to locate end of anchor function")

        insert_pos = close_brace + 1
        text = text[:insert_pos] + "\n\n" + function_impl + "\n" + text[insert_pos:]
        console.print("[+] Added gumjs_script_load_bytecode implementation", style="green")
    else:
        console.print("[=] gumjs_script_load_bytecode already implemented", style="cyan")

    target_file.write_text(text, encoding="utf-8")
    console.print(Panel("[✓] gum_quick_patcher.py patch complete", style="bold green"))


if __name__ == "__main__":
    main()
