#!/usr/bin/env python3
import re
import random
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()
LOG_COLOR = {
    "info": "cyan",
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "step": "magenta",
}

# --------------------------
# Command-line / input handling
# --------------------------
if len(sys.argv) != 2:
    console.print("[error] Usage: shuffler.py <frida_root_dir>", style=LOG_COLOR["error"])
    sys.exit(1)

FRIDA_ROOT = Path(sys.argv[1]).expanduser().resolve()
INPUT_FILE = Path("./deps/quickjs-opcode.h")
OUTPUT_FILE = FRIDA_ROOT / "subprojects/frida-gum/subprojects/quickjs/quickjs-opcode.h"

console.print(Panel(f"[step] Frida root: {FRIDA_ROOT}\n[step] Input file: {INPUT_FILE}\n[step] Output file: {OUTPUT_FILE}", style=LOG_COLOR["step"]))

# --------------------------
# Regex
# --------------------------
DEF_RE = re.compile(r"^\s*DEF\(\s*([A-Za-z0-9_]+)")

# --------------------------
# Groups
# --------------------------
GROUPS = [
    {
        "name": "GENERAL",
        "targets": [
            "push_i32","push_atom_value","private_symbol","undefined","null",
            "push_this","push_false","push_true","object","special_object","rest",
            "sub","mod","nip1","dup","dup1","dup2","dup3",
            "insert2","insert3","insert4","perm3","perm4","perm5",
            "swap","swap2","rot3l","rot3r","rot4l","rot5l",
            "apply","return","return_undef","check_ctor_return","check_ctor","check_brand",
            "add_brand","return_async","throw","throw_error","eval","apply_eval",
            "regexp","get_super","import","get_ref_value","put_ref_value",
            "define_var", ["check_define_var","define_func","get_field","get_field2","put_field","get_private_field"],
            ["put_private_field","define_private_field","get_array_el","get_array_el2","put_array_el","get_super_value"],
            ["put_super_value","define_field","set_name","set_name_computed","set_proto","set_home_object"],
            ["define_array_el","append","copy_data_properties","define_class_computed","to_object","to_propkey"],
            # "to_propkey2","make_loc_ref","make_arg_ref","make_var_ref_ref","make_var_ref","for_in_start",
            # "for_of_start","for_await_of_start","for_in_next","for_of_next","iterator_check_object","iterator_get_value_done",
            # "iterator_close","iterator_next","iterator_call","initial_yield","yield","yield_star",
            # "async_yield_star","await","neg","plus","dec","inc",
            ["post_dec", "post_inc"],
            "dec_loc","inc_loc", "add_loc",
            "not","lnot","typeof","delete","delete_var","drop","nip",
            "add","div","mul","pow","shl","sar",
            "shr","lt","lte","gt","gte","instanceof",
            "in","eq","neq","strict_eq","strict_neq","and",
            "xor","or","is_undefined_or_null","private_in"
        ],
        "reorder_list": [],
        "ccb": {"push_const", "call_constructor", "check_var", "get_loc", "if_false", "with_get_var"},
        "cca": {"fclosure", "array_from", "put_var_strict", "set_var_ref", "nip_catch", "put_var_ref_check_init", "with_get_ref_undef"},
        "reorder_prob": 0.67
    },
    {
        "name": "CONFIG_BIGNUM",
        "targets": {"mul_pow10", "math_mod"},
        "reorder_list": [],
        "reorder_prob": 0.0
    },
    {
        "name": "SHORT_OPCODES",
        "targets": [
            ["push_minus1","push_0","push_1","push_2","push_3","push_4","push_5","push_6","push_7"],
            # "push_i8","push_i16",
            # "push_empty_string",
            ["get_loc8","put_loc8","set_loc8"],
            ["get_loc0","get_loc1","get_loc2","get_loc3"],
            ["put_loc0","put_loc1","put_loc2","put_loc3"],
            ["set_loc0","set_loc1","set_loc2","set_loc3"],
            ["get_arg0","get_arg1","get_arg2","get_arg3"],
            ["put_arg0","put_arg1","put_arg2","put_arg3"],
            ["set_arg0","set_arg1","set_arg2","set_arg3"],
            ["get_var_ref0","get_var_ref1","get_var_ref2","get_var_ref3"],
            ["put_var_ref0","put_var_ref1","put_var_ref2","put_var_ref3"],
            ["set_var_ref0","set_var_ref1","set_var_ref2","set_var_ref3"],
            "get_length",
            "goto16",
            ["call0","call1","call2","call3"],
            "is_undefined","is_null","typeof_is_undefined","typeof_is_function"
        ],
        "reorder_list": [],
        "ccb": {"if_false8","push_const8"},
        "cca": {"goto8","fclosure8"},
        "reorder_prob": 0.4
    }
]

# --------------------------
# Helpers
# --------------------------
def extract_opcode(line: str) -> str | None:
    m = DEF_RE.match(line)
    return m.group(1) if m else None

def opcode_index(lines: list[str]) -> dict[str,int]:
    return {
        extract_opcode(l): i
        for i, l in enumerate(lines)
        if extract_opcode(l)
    }

# --------------------------
# Read input
# --------------------------
console.print(f"[step] Reading input file: {INPUT_FILE}", style=LOG_COLOR["step"])
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()
console.print(f"[info] {len(lines)} lines loaded", style=LOG_COLOR["info"])

# --------------------------
# Process each group
# --------------------------
for group in GROUPS:
    console.print(f"[step] Processing group: {group['name']}", style=LOG_COLOR["step"])

    # separate shuffle-only targets and relocate-only blocks
    normal_targets = [t for t in group["targets"] if isinstance(t, str)]
    relocate_blocks = [t for t in group["targets"] if isinstance(t, list)]

    # -------- shuffle-only targets (shuffle within file) --------
    targets = [(idx, line) for idx, line in enumerate(lines) if extract_opcode(line) in normal_targets]
    bucket = [l for _, l in targets]
    random.shuffle(bucket)
    for (idx, _), new_line in zip(targets, bucket):
        lines[idx] = new_line
    if targets:
        console.print(f"[success] Shuffled {len(targets)} normal targets", style=LOG_COLOR["success"])

    # -------- reorder_list targets (reorder OR fallback shuffle) --------
    fallback_shuffle_ops = []

    for op in group.get("reorder_list", []):
        if random.random() > group.get("reorder_prob", 0):
            fallback_shuffle_ops.append(op)
            continue

        idx_map = opcode_index(lines)
        if op not in idx_map:
            continue

        cur_idx = idx_map[op]
        line = lines.pop(cur_idx)

        anchors = []
        for a in group.get("cca", set()):
            if a in idx_map:
                anchors.append(idx_map[a])
        for b in group.get("ccb", set()):
            if b in idx_map:
                anchors.append(idx_map[b] - 1)

        insert_at = random.choice(anchors) if anchors else cur_idx
        insert_at = max(0, min(insert_at, len(lines)))
        lines.insert(insert_at, line)

    # -------- fallback shuffle (IDENTICAL to normal targets) --------
    fallback_positions = [i for i, line in enumerate(lines) if extract_opcode(line) in fallback_shuffle_ops]
    fallback_bucket = [lines[i] for i in fallback_positions]
    random.shuffle(fallback_bucket)
    for i, new_line in zip(fallback_positions, fallback_bucket):
        lines[i] = new_line
    if fallback_positions:
        console.print(f"[success] Applied fallback shuffle for {len(fallback_positions)} ops", style=LOG_COLOR["success"])

    # -------- relocate-only blocks from targets --------
    for block in relocate_blocks:
        idx_map = opcode_index(lines)
        block_lines = []
        block_indices = []
        for op in block:
            if op in idx_map:
                i = idx_map[op]
                block_lines.append(lines[i])
                block_indices.append(i)
        for i in sorted(block_indices, reverse=True):
            lines.pop(i)

        idx_map = opcode_index(lines)
        anchors = []
        for a in group.get("cca", set()):
            if a in idx_map:
                anchors.append(idx_map[a] + 1)
        for b in group.get("ccb", set()):
            if b in idx_map:
                anchors.append(idx_map[b])

        insert_at = random.choice(anchors) if anchors else random.randint(0, len(lines))
        lines[insert_at:insert_at] = block_lines
        if block_lines:
            console.print(f"[success] Relocated block with {len(block_lines)} opcodes", style=LOG_COLOR["success"])

# --------------------------
# Comment fixup
# --------------------------
def fix_multiline_trailing_comments(lines: list[str]) -> list[str]:
    fixed = []
    inside_comment = False
    for line in lines:
        l = line.rstrip("\n")
        if "*/" in l and "/*" not in l and not inside_comment:
            l = "/* " + l
        if inside_comment and (re.match(r"^\s*DEF\(", l) or re.match(r"^\s*#", l)):
            fixed.append(" */\n")
            inside_comment = False
        if "/*" in l and "*/" not in l:
            inside_comment = True
        if "*/" in l:
            inside_comment = False
        fixed.append(l + "\n")
    if inside_comment:
        fixed.append(" */\n")
    return fixed

lines = fix_multiline_trailing_comments(lines)
console.print(f"[info] Fixed multiline trailing comments", style=LOG_COLOR["info"])

# --------------------------
# Write output
# --------------------------
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.writelines(lines)
console.print(Panel(f"[✓] Shuffled, relocated, and comment-fixed file written to:\n{OUTPUT_FILE}", style=LOG_COLOR["success"]))
