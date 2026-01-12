#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tarfile
import hashlib
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel


# =========================
# GLOBALS
# =========================
console = Console()
LOG_COLOR = {
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green",
    "step": "magenta",
    "run": "blue",
}

REQUIRED_KEYS = {
    "frida_version": str,
    "compile": dict,
    "output_dir": str,
    "options": dict,
}

COMPILE_KEYS = {
    "server": bool,
    "gadget": bool,
    "tools": bool,
    "python": bool,
    "portal": bool,
}

OPTION_KEYS = {
    "disable_v8": bool,
}

ATOM_KEYS = {
    "custom_encryption_key": str,
}

QUICKJS_REPLACEMENT = """\
  # _PATCHED_
  cdata.set('HAVE_QUICKJS', 1)
  quickjs_sp = subproject('quickjs',
      default_options: quickjs_options
  )
  quickjs_dep = quickjs_sp.get_variable('quickjs_dep')

  quickjs_native_sp = subproject('quickjs',
      native: true,
      default_options: quickjs_options
  )
  quickjs_dep_native = quickjs_native_sp.get_variable('quickjs_dep')

  gumjs_extra_requires += 'quickjs'
  # _PATCHED_
"""


# =========================
# UTILITIES
# =========================
# def run_with_rich_spinner(cmd, cwd=None, description="Building..."):
#     with Progress(
#         SpinnerColumn(),
#         TextColumn("[progress.description]{task.description}"),
#         console=console,
#         transient=True
#     ) as progress:
#         task = progress.add_task(description, start=False)
#         progress.start_task(task)
#         try:
#             subprocess.run(cmd, cwd=cwd, check=True)
#         except subprocess.CalledProcessError as e:
#             console.print(f"[red]Error:[/red] {e}")
#             raise

def die(msg: str) -> None:
    console.print(f"[{LOG_COLOR['error']}][FATAL][/]: {msg}")
    sys.exit(1)

# def run(cmd: list[str], cwd: Optional[Path] = None) -> None:
#     console.print(f"[{LOG_COLOR['run']}][RUN][/]: {' '.join(cmd)}")
#     try:
#         subprocess.check_call(cmd, cwd=cwd)
#     except subprocess.CalledProcessError as e:
#         die(f"Command failed: {e}")
def run(cmd: list[str], cwd: Optional[Path] = None, placeholder: Optional[str] = None, placeholder_column: Optional[str] = "Executing...") -> None:
    if placeholder is not None:
        console.print(f"[dim]{placeholder}[/dim]")
        console.print()  # blank line before spinner

        with Progress(
            SpinnerColumn(style="cyan"),
            TextColumn(placeholder_column),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("", start=True)
            subprocess.run(cmd, cwd=cwd, check=True)
    else:
        subprocess.run(cmd, cwd=cwd, check=True)

def read_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        die(f"Failed to read JSON config {path}: {e}")

def log_step(msg: str) -> None:
    console.print(f"[{LOG_COLOR['step']}][STEP][/]: {msg}")

def log_info(msg: str) -> None:
    console.print(f"[{LOG_COLOR['info']}][INFO][/]: {msg}")

def log_warn(msg: str) -> None:
    console.print(f"[{LOG_COLOR['warning']}][WARNING][/]: {msg}")

def log_success(msg: str) -> None:
    console.print(f"[{LOG_COLOR['success']}][DONE][/]: {msg}")


# =========================
# CONFIG VALIDATION
# =========================
def validate_config(cfg: Dict[str, Any]) -> None:
    for k, t in REQUIRED_KEYS.items():
        if k not in cfg or not isinstance(cfg[k], t):
            die(f"Missing or invalid config key: {k}")
    for k, t in COMPILE_KEYS.items():
        if k not in cfg["compile"] or not isinstance(cfg["compile"][k], t):
            die(f"Missing or invalid compile.{k}")
    for k, t in OPTION_KEYS.items():
        if k not in cfg["options"] or not isinstance(cfg["options"][k], t):
            die(f"Missing or invalid options.{k}")
    if "atoms" in cfg:
        if not isinstance(cfg["atoms"], dict):
            die("atoms must be a dictionary")
        for k, t in ATOM_KEYS.items():
            if k in cfg["atoms"] and not isinstance(cfg["atoms"][k], t):
                die(f"Invalid atoms.{k}")

def display_intro(cfg: Dict[str, Any]) -> None:
    console.rule("[bold green]Frida Builder Configuration Overview[/]")

    def add_table(title: str, data: Dict[str, Any], bool_color=True):
        if not data:
            return
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Option", style="cyan")
        table.add_column("Value", style="yellow")
        for k, v in data.items():
            if isinstance(v, bool) and bool_color:
                val = "[green]True[/]" if v else "[red]False[/]"
            else:
                val = str(v)
            table.add_row(str(k), val)
        console.print(f"[bold underline]{title}[/]")
        console.print(table)

    # ---- General Options (excluding shuffle_opcodes & custom_encryption_key) ----
    general_keys = [
        "frida_version",
        "build_custom_compiler",
        "build_custom_dihcompiler",
        "output_dir",
    ]
    general_opts = {k: cfg[k] for k in general_keys if k in cfg}
    add_table("General Options", general_opts)

    # ---- Compile (compile flags + disable_v8) ----
    compile_opts = cfg.get("compile", {}).copy()
    if "options" in cfg and "disable_v8" in cfg["options"]:
        compile_opts["disable_v8"] = cfg["options"]["disable_v8"]
    add_table("Compile", compile_opts)

    # ---- Extra Features (shuffle_opcodes + custom_encryption_key) ----
    extra_opts = {}
    if "shuffle_opcodes" in cfg:
        extra_opts["shuffle_opcodes"] = cfg["shuffle_opcodes"]
    if "atoms" in cfg and "custom_encryption_key" in cfg["atoms"]:
        extra_opts["custom_encryption_key"] = cfg["atoms"]["custom_encryption_key"]
    add_table("Extra Features", extra_opts, bool_color=False)

    # ---- Confirmation ----
    if not Confirm.ask("[?] Are these configuration options correct?", default=True):
        die("User aborted. Please update config and retry.")


# =========================
# FRIDA CLONE & PATCHING
# =========================
def clone_frida(version: str, out_dir: Path) -> None:
    if out_dir.exists():
        log_info(f"Output directory exists, skipping clone: {out_dir}")
        return
    run([
        "git", "clone",
        "--branch", version,
        "--depth", "1",
        "--recursive",
        "https://github.com/frida/frida.git",
        str(out_dir)
    ])

def is_meson_already_patched(meson_file: Path) -> bool:
    return "# _PATCHED_" in meson_file.read_text()

def patch_meson_build(frida_dir: Path) -> None:
    meson_file = frida_dir / "subprojects/frida-gum/meson.build"
    if not meson_file.exists():
        die(f"Meson build file not found: {meson_file}")
    if is_meson_already_patched(meson_file):
        log_info("Meson build already patched, skipping")
        return

    lines = meson_file.read_text().splitlines()
    new_lines = []
    skip = False
    found = False
    for line in lines:
        if "quickjs_dep = dependency('quickjs'" in line:
            skip = True
            found = True
            continue
        if skip and line.strip() == "endif":
            skip = False
            new_lines.append(QUICKJS_REPLACEMENT)
            continue
        if not skip:
            new_lines.append(line)
    if not found:
        die("Failed to find QuickJS dependency block")
    meson_file.write_text("\n".join(new_lines) + "\n")
    log_success("Meson QuickJS dependency replaced")

def setup_quickjs(frida_dir: Path) -> None:
    sp_dir = frida_dir / "subprojects/frida-gum/subprojects"
    quickjs_dir = sp_dir / "quickjs"
    if quickjs_dir.exists():
        log_info("QuickJS already present, skipping extraction")
        return

    deps_tar = Path(__file__).parent / "deps/quickjs.tar.gz"
    if not deps_tar.exists():
        die(f"QuickJS tarball not found: {deps_tar}")

    sp_dir.mkdir(parents=True, exist_ok=True)
    log_step(f"Extracting QuickJS from {deps_tar}")

    def safe_filter(tarinfo, path):
        if tarinfo.name.startswith("/") or ".." in tarinfo.name:
            return None
        return tarinfo

    with tarfile.open(deps_tar, "r:gz") as tar:
        temp_dir = sp_dir / "__quickjs_tmp__"
        temp_dir.mkdir(exist_ok=True)
        tar.extractall(temp_dir, filter=safe_filter)

        items = list(temp_dir.iterdir())
        if len(items) == 1 and items[0].is_dir():
            items[0].rename(quickjs_dir)
        else:
            quickjs_dir.mkdir()
            for item in items:
                item.rename(quickjs_dir / item.name)
        temp_dir.rmdir()

    log_success("QuickJS extracted successfully")

def remove_quickjs_wrap(frida_dir: Path) -> None:
    wrap = frida_dir / "subprojects/frida-gum/subprojects/quickjs.wrap"
    if wrap.exists():
        wrap.unlink()
        log_success("Removed quickjs.wrap")


# =========================
# BUILD
# =========================
def ask_reconfigure() -> str:
    console.print("[?] Build directory exists")
    console.print("    [1] Reuse existing build (default)")
    console.print("    [2] Wipe and reconfigure")
    choice = Prompt.ask("Select", choices=["1","2"], default="1")
    return "wipe" if choice == "2" else "skip"

def build(frida_dir: Path, cfg: Dict[str, Any]) -> None:
    build_dir = frida_dir / "build"
    configure_flags = ["./configure", "--host=android-arm64"]

    # Add compile flags based on cfg
    for key, opt in [
        ("server", "--enable-server"),
        ("gadget", "--enable-gadget"),
        ("tools", "--enable-frida-tools"),
        ("python", "--enable-frida-python"),
        ("portal", "--enable-portal"),
    ]:
        if cfg["compile"].get(key, False):
            configure_flags.append(opt)

    # Additional devkit flags
    configure_flags += [
        "--",
        "-Dfrida-gum:devkits=gum,gumjs",
        "-Dfrida-core:devkits=core",
        "-Dfrida-gumjs:quickjs=enabled",
        "-Dfrida-gum:quickjs=enabled",
    ]

    # V8 flags
    if cfg["options"].get("disable_v8", False):
        configure_flags += ["-Dfrida-gum:v8=disabled", "-Dfrida-gumjs:v8=disabled"]
    else:
        configure_flags += ["-Dfrida-gum:v8=enabled", "-Dfrida-gumjs:v8=enabled"]

    # ---- Determine if configure is needed ----
    run_configure = True
    if build_dir.exists():
        console.print(f"[!] Build directory already exists: {build_dir}", style="yellow")
        choice = ask_reconfigure()
        if choice == "wipe":
            console.print("[*] Removing existing build directory...", style="yellow")
            shutil.rmtree(build_dir)
        else:
            console.print("[*] Keeping existing build directory, skipping configure.", style="cyan")
            run_configure = False

    # ---- Run configure if needed ----
    if run_configure:
        console.print(f"[*] Running configure with flags: {' '.join(configure_flags)}", style="cyan")
        run(configure_flags, cwd=frida_dir)

    # ---- Run make ----
    make_jobs = max(1, int(os.cpu_count() / 2))
    console.print(f"[*] Running make with {make_jobs} parallel jobs...", style="cyan")
    run(["make", f"-j{make_jobs}"], cwd=frida_dir)

    console.print("[✓] Frida build completed successfully", style="green")


# =========================
# OPCODE SHUFFLE
# =========================
def maybe_shuffle_opcodes(cfg: Dict[str, Any], out_dir: Path) -> None:
    if not cfg.get("shuffle_opcodes", False):
        return

    # shuffle_script = Path(__file__).parent / "shuffler.py"
    shuffle_script = Path(__file__).parent / "patchers/shuffler.py"
    if not shuffle_script.exists():
        die(f"shuffler.py not found: {shuffle_script}")

    log_warn("Opcode shuffling is ENABLED in config")
    opcode_path = out_dir / "subprojects/frida-gum/subprojects/quickjs/quickjs-opcode.h"
    log_warn(f"It is strongly recommended to back up: {opcode_path}")

    if not Confirm.ask("Do you want to reshuffle opcodes?", default=False):
        log_info("Opcode shuffling skipped")
        return

    log_step("Executing shuffler.py")
    run([sys.executable, str(shuffle_script), str(out_dir)])


# =========================
# GENERATE STUFF.H
# =========================
def generate_stuff_h(cfg: Dict[str, Any], out_dir: Path) -> None:
    atoms = cfg.get("atoms", {})
    key = atoms.get("custom_encryption_key")
    if not key:
        return
    quickjs_dir = out_dir / "subprojects/frida-gum/subprojects/quickjs"
    if not quickjs_dir.exists():
        die(f"QuickJS directory not found: {quickjs_dir}")

    out_file = quickjs_dir / "stuff.h"
    log_warn("Custom encryption key material is configured")
    if out_file.exists():
        log_warn(f"Existing file: {out_file}")
    else:
        log_warn("No existing stuff.h found")

    if not Confirm.ask("Do you want to generate a NEW stuff.h?", default=False):
        log_info("stuff.h generation skipped")
        return

    key_bytes = key.encode("utf-8")
    out_len = secrets.randbelow(96) + 64
    salt = secrets.token_bytes(secrets.randbelow(32) + 64)
    noise = secrets.token_bytes(secrets.randbelow(48) + 86)
    state = bytearray()
    state.extend(hashlib.sha256(key_bytes + salt).digest())
    state.extend(hashlib.sha512(key_bytes[::-1] + noise).digest())
    rounds = secrets.randbelow(7) + 6
    for r in range(rounds):
        rnd_noise = secrets.token_bytes(32)
        mix = bytearray()
        for i, b in enumerate(state):
            n = rnd_noise[i % len(rnd_noise)]
            k = key_bytes[i % len(key_bytes)]
            mix.append((b ^ n ^ k ^ r) & 0xFF)
        state = bytearray(hashlib.sha512(mix + secrets.token_bytes(16)).digest())
        state.extend(hashlib.sha256(state + secrets.token_bytes(8)).digest())
    for _ in range(len(state)//2):
        i, j = secrets.randbelow(len(state)), secrets.randbelow(len(state))
        state[i], state[j] = state[j], state[i]
    final = bytearray()
    while len(final) < out_len:
        final.extend(hashlib.sha512(state + secrets.token_bytes(32)).digest())
    final = final[:out_len]
    bytes_list = ", ".join(f"0x{b:02x}" for b in final)
    version_macro = cfg["frida_version"].replace(".", "_")
    header_guard = f"FRIDA_{version_macro}_STUFF_H"

    sbox = list(range(256))

    sbox_entropy = (
        state +
        secrets.token_bytes(64) +
        hashlib.sha256(final).digest() +
        hashlib.sha512(key_bytes).digest()
    )

    prng_state = hashlib.sha512(sbox_entropy).digest()
    prng_idx = 0

    def prng_byte():
        nonlocal prng_state, prng_idx
        if prng_idx >= len(prng_state):
            prng_state = hashlib.sha512(prng_state + secrets.token_bytes(32)).digest()
            prng_idx = 0
        b = prng_state[prng_idx]
        prng_idx += 1
        return b

    rounds = 5 + (prng_state[0] & 0x07)  # 5–12 rounds

    for r in range(rounds):
        for i in range(255, 0, -1):
            j = prng_byte() % (i + 1)
            sbox[i], sbox[j] = sbox[j], sbox[i]
        # diffuse between rounds
        prng_state = hashlib.sha512(
            prng_state +
            bytes(sbox[:64]) +
            r.to_bytes(1, "little")
        ).digest()
        prng_idx = 0

    sbox_list = ", ".join(f"0x{b:02x}" for b in sbox)

    content = f"""#ifndef {header_guard}
#define {header_guard}

#include <stdint.h>
#include <stddef.h>

#define STUFF_KEY_RAW {{{bytes_list}}}

const uint8_t qjs_sbox[256] = {{
    {sbox_list}
}};

#endif // {header_guard}
"""

    out_file.write_text(content)
    log_success(f"Generated new stuff.h ({len(final)} bytes) at {out_file}")


# =========================
# CUSTOM (DIH)COMPILER BUILD
# =========================
def maybe_build_custom_compiler(cfg: Dict[str, Any], out_dir: Path) -> None:
    if not cfg.get("build_custom_compiler", False):
        return
    quickjs_dir = out_dir / "subprojects/frida-gum/subprojects/quickjs"
    if not quickjs_dir.exists():
        die(f"QuickJS directory not found: {quickjs_dir}")
    log_warn("build_custom_compiler is ENABLED in config")
    if not Confirm.ask("Do you want to build the custom QuickJS compiler (comper)?", default=False):
        log_info("Custom compiler build skipped")
        return

    log_step("Building QuickJS custom compiler (comper)")

    cmd = [
        "cc",
        "-O2",
        "-D_GNU_SOURCE",
        "-DCONFIG_BIGNUM",
        "-DCONFIG_VERSION=\"\\\"2025.01\\\"\"",
        "comper.c",
        "quickjs-libc.c",
        "libregexp.c",
        "libunicode.c",
        "libbf.c",
        "cutils.c",
        "-I.",
        "-lm",
        "-ldl",
        "-o",
        "comper",
    ]

    run(cmd, cwd=quickjs_dir, placeholder="Building QuickJS custom compiler...", placeholder_column="Compiling...")

    compiler_path = quickjs_dir / "comper"
    if not compiler_path.exists():
        die("Custom compiler build completed but comper was not produced")
    log_success(f"Custom QuickJS compiler built at {compiler_path.resolve()}")

def maybe_build_custom_dihcompiler(cfg: Dict[str, Any], out_dir: Path) -> None:
    if not cfg.get("build_custom_dihcompiler", False):
        return
    quickjs_dir = out_dir / "subprojects/frida-gum/subprojects/quickjs"
    if not quickjs_dir.exists():
        die(f"QuickJS directory not found: {quickjs_dir}")
    log_warn("build_custom_dihcompiler is ENABLED in config")
    if not Confirm.ask("Do you want to build the custom QuickJS Dihcompiler (dihcomper)?", default=False):
        log_info("Custom Dihcompiler build skipped")
        return

    log_step("Building QuickJS custom Dihcompiler (dihcomper)")

    cmd = [
        "cc",
        "-O2",
        "-D_GNU_SOURCE",
        "-DCONFIG_BIGNUM",
        "-DCONFIG_VERSION=\"\\\"2025.01\\\"\"",
        "-DDUMP_BYTECODE=63",
        "h2.c",
        "quickjs-libc.c",
        "libregexp.c",
        "libunicode.c",
        "libbf.c",
        "cutils.c",
        "-I.",
        "-lm",
        "-ldl",
        "-o",
        "dihcomper",
    ]

    run(cmd, cwd=quickjs_dir, placeholder="Building QuickJS custom dihcompiler...", placeholder_column="Compiling...")

    dih_path = quickjs_dir / "dihcomper"
    if not dih_path.exists():
        die("Custom Dihcompiler build completed but dihcomper was not produced")
    log_success(f"Custom Dihcompiler built at {dih_path.resolve()}")


def run_gum_quick_patcher(frida_dir: Path) -> None:
    patcher_script = Path(__file__).parent / "patchers/gum_quick_patcher.py"
    if not patcher_script.exists():
        die(f"gum_quick_patcher.py not found at {patcher_script}")

    log_step(f"Running gum_quick_patcher.py on Frida sources at {frida_dir}")
    run([sys.executable, str(patcher_script), str(frida_dir)])
    log_success("gum_quick_patcher.py completed successfully")

def fetch_built_artifacts(cfg: Dict[str, Any], out_dir: Path) -> None:
    root = Path(__file__).parent
    built_dir = root / "built"
    built_dir.mkdir(exist_ok=True)

    log_step("Collecting built Frida artifacts")

    def log_copy(title: str, src: Path, dst: Path) -> None:
        """Logs a copy action with a separator and From/To paths."""
        console.rule(f"[bold green]{title}[/]")
        console.print(f"[yellow]From →[/] {src}\n[yellow]To   →[/] {dst}")

    # ==========================================================
    # Frida Server
    # ==========================================================
    if cfg["compile"].get("server", False):
        server_src = out_dir / "build/subprojects/frida-core/server/frida-server"
        server_dst_dir = built_dir / "server"
        server_dst_dir.mkdir(exist_ok=True)

        if server_src.exists():
            shutil.copy2(server_src, server_dst_dir)
            log_copy("Frida Server copied", server_src, server_dst_dir / server_src.name)
        else:
            log_warn(f"Frida Server enabled but not found: {server_src}")

    # ==========================================================
    # Frida Gadget
    # ==========================================================
    if cfg["compile"].get("gadget", False):
        gadget_src = out_dir / "build/subprojects/frida-core/lib/gadget/frida-gadget.so"
        gadget_dst_dir = built_dir / "gadget"
        gadget_dst_dir.mkdir(exist_ok=True)

        if gadget_src.exists():
            shutil.copy2(gadget_src, gadget_dst_dir)
            log_copy("Frida Gadget copied", gadget_src, gadget_dst_dir / gadget_src.name)
        else:
            log_warn(f"Frida Gadget enabled but not found: {gadget_src}")

    # ==========================================================
    # QuickJS Custom Compiler
    # ==========================================================
    quickjs_dir = out_dir / "subprojects/frida-gum/subprojects/quickjs"
    custom_dir = built_dir / "custom_compiler"
    custom_dir.mkdir(exist_ok=True)

    comper_src = quickjs_dir / "comper"
    if comper_src.exists():
        shutil.copy2(comper_src, custom_dir)
        log_copy("QuickJS custom compiler copied", comper_src, custom_dir / "comper")
    else:
        log_info("QuickJS custom compiler not present (comper not built)")

    # ==========================================================
    # Dihcompiler (if built)
    # ==========================================================
    dih_src = quickjs_dir / "dihcomper"
    if cfg.get("build_custom_dihcompiler", False) and dih_src.exists():
        dih_dst_dir = built_dir / "custom_dihcompiler"
        dih_dst_dir.mkdir(exist_ok=True)
        shutil.copy2(dih_src, dih_dst_dir)
        log_copy("Dihcompiler copied", dih_src, dih_dst_dir / "dihcomper")
    elif cfg.get("build_custom_dihcompiler", False):
        log_warn("Custom Dihcompiler enabled but not found (not built)")

    # ==========================================================
    # Backups: quickjs-opcode.h + stuff.h
    # ==========================================================
    backups_dir = built_dir / "backups"
    backups_dir.mkdir(exist_ok=True)

    backup_files = [
        quickjs_dir / "quickjs-opcode.h",
        quickjs_dir / "stuff.h",
    ]

    for src in backup_files:
        if src.exists():
            shutil.copy2(src, backups_dir)
            log_copy(f"Backup: {src.name}", src, backups_dir / src.name)
        else:
            log_warn(f"Backup target missing: {src}")

    # ---- WHATISTHIS file ----
    whatisthis = backups_dir / "WHAT_ARE_THESE.md"
    if not whatisthis.exists():
        whatisthis.write_text(
            "WHAT ARE THESE?\n"
            "============\n\n"
            "These files are critical build artifacts used by QuickJS and Frida:\n\n"
            "- quickjs-opcode.h\n"
            "- stuff.h\n\n"
            "They represent:\n"
            "  • Your shuffled QuickJS opcode layout\n"
            "  • Secret key material derived from your atom encryption key + a sbox table\n\n"
            "If you reshuffle opcodes or regenerate keys without these backups,\n"
            "you WILL NOT be able to reproduce the exact same QuickJS / Frida build.\n\n"
            "Keep these files safe.\n"
            "They allow you to rebuild Frida exactly as it was produced\n"
            "for this build.\n"
        )
        log_info(f"Created explanation file: {whatisthis}")

    console.print(Panel(f"Artifact collection complete → {built_dir}", style=LOG_COLOR["success"]))


# =========================
# MAIN
# =========================
def main() -> None:
    if len(sys.argv) != 2:
        die("Usage: frida_builder.py <config.json>")

    cfg_path = Path(sys.argv[1])
    cfg = read_json(cfg_path)
    validate_config(cfg)
    display_intro(cfg)
    out_dir = Path(cfg["output_dir"]).resolve()

    log_step("Cloning Frida repository")
    clone_frida(cfg["frida_version"], out_dir)

    run_gum_quick_patcher(out_dir)

    remove_quickjs_wrap(out_dir)
    patch_meson_build(out_dir)
    setup_quickjs(out_dir)

    maybe_shuffle_opcodes(cfg, out_dir)
    generate_stuff_h(cfg, out_dir)
    maybe_build_custom_compiler(cfg, out_dir)
    maybe_build_custom_dihcompiler(cfg, out_dir)
    build(out_dir, cfg)
    fetch_built_artifacts(cfg, out_dir)

if __name__ == "__main__":
    main()
