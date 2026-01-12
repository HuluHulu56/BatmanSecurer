# BatmanSecurer

## Table of Contents

1. [Requirements](#requirements)
2. [Configuration (`config.json`)](#configuration-configjson)
3. [Build Process Overview](#build-process-overview)
4. [Interactive Prompts](#interactive-prompts)
5. [Custom Compilers](#custom-compilers)
6. [Gadget `loadBytecode` Usage](#gadget-loadbytecode-usage)
7. [Artifacts & Backups](#artifacts--backups)
8. [Usage](#usage)
9. [FAQ](#faq)

---

## Requirements

* Python 3.10+
* `git` command-line tool
* Standard build tools (`cc`, `make`, `cmake`, `ninja`)
* `rich` Python module

Optional:

* Tarball `deps/quickjs.tar.gz` if QuickJS is not already present

---

## Configuration (`config.json`)

The build system is fully driven by a JSON configuration. Here’s a breakdown of all fields:

```json
{
  "frida_version": "16.6.6",
  "compile": {
    "server": true,
    "gadget": true,
    "tools": false,
    "python": false,
    "portal": false
  },
  "options": {
    "disable_v8": true
  },
  "build_custom_compiler": true,
  "build_custom_dihcompiler": true,
  "output_dir": "frida-16.6.6",
  "shuffle_opcodes": true,
  "atoms": {
    "custom_encryption_key": "jonkler no teeth"
  }
}
```

### Fields

**General Options**

| Key                        | Type   | Description                                                  |
| -------------------------- | ------ | ------------------------------------------------------------ |
| `frida_version`            | `str`  | Git tag or branch to clone from Frida repository.            |
| `build_custom_compiler`    | `bool` | If `true`, builds a custom QuickJS compiler (`comper`).      |
| `build_custom_dihcompiler` | `bool` | If `true`, builds a custom QuickJS decompiler (`dihcomper`). |
| `output_dir`               | `str`  | Directory where Frida sources will be cloned and compiled.   |

**Compile Options**

| Key          | Type   | Description                                                                                                          |
| ------------ | ------ | -------------------------------------------------------------------------------------------------------------------- |
| `server`     | `bool` | Build Frida Server                                                                                                   |
| `gadget`     | `bool` | Build Frida Gadget library (note: final gadget works only with scripts compiled via `comper` and `loadBytecode`)     |
| `tools`      | `bool` | Build Frida CLI tools (e.g., frida-ps, frida-trace).                                                                 |
| `python`     | `bool` | Build Frida Python bindings.                                                                                         |
| `portal`     | `bool` | Build Frida Portal server.                                                                                           |
| `disable_v8` | `bool` | Disable V8 support in Frida/GumJS. This reduces gadget size by ~50%, but may very rarely cause compatibility issues. |

**Extra Features**

| Key                           | Type   | Description                                                                                                                                    |
| ----------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `shuffle_opcodes`             | `bool` | Enable opcode shuffling in QuickJS to prevent reproducible builds, reverse engineering, and the dumping or decompilation of compiled bytecode. |
| `atoms.custom_encryption_key` | `str`  | Custom secret key used to encrypt QuickJS atoms (strings, identifiers, literals), preventing readable recovery of compiled scripts.            |

---

## Build Process Overview

1. **Configuration validation:**
   Ensures all required config fields exist and are valid.

2. **Display summary:**
   Shows a rich table summarizing configuration. Confirmation is required to proceed.

3. **Clone Frida repository:**

   * Clones the specified `frida_version`.
   * Skips if `output_dir` exists.

4. **Patch Frida source:**

   * Runs `gum_quick_patcher.py` to add `loadBytecode` support.
   * Replaces QuickJS dependency in `meson.build`.

5. **QuickJS setup:**

   * Extracts QuickJS from `deps/quickjs.tar.gz` if missing.
   * Removes `quickjs.wrap` if present.

6. **Optional features:**

   * Shuffle QuickJS opcodes (`quickjs-opcode.h`)
   * Generate `stuff.h` using `atoms.custom_encryption_key`

7. **Custom compiler builds:**

   * `comper` → QuickJS compiler
   * `dihcomper` → QuickJS decompiler

8. **Build Frida:**

   * Runs `./configure` only if build directory is new or user chooses to reconfigure.
   * Runs `make -jN` with parallel jobs.

9. **Fetch built artifacts:**

   * Copies binaries and backups to `/built`.
   * Backups include `quickjs-opcode.h` and `stuff.h` with `WHAT_ARE_THESE.md`.

---

## Interactive Prompts

| Prompt                                                             | Default   | Effect if Yes                                                                                              |
| ------------------------------------------------------------------ | --------- | ---------------------------------------------------------------------------------------------------------- |
| `[?] Are these configuration options correct?`                     | Yes       | Continues build with the provided configuration.                                                           |
| `Do you want to reshuffle opcodes?`                                | No        | Runs `shuffler.py` to generate a new shuffled `quickjs-opcode.h`.                                          |
| `Do you want to generate a NEW stuff.h?`                           | No        | Generates a new `stuff.h` using your custom encryption key.                                                |
| `Do you want to build the custom QuickJS compiler (comper)?`       | No        | Compiles `comper` binary inside `quickjs/` and copies to `/built/custom_compiler`.                         |
| `Do you want to build the custom QuickJS Dihcompiler (dihcomper)?` | No        | Compiles `dihcomper` binary inside `quickjs/` and copies to `/built/custom_dihcompiler`.                   |
| `[?] Build directory exists: ...`                                  | 1 (reuse) | Option to either reuse existing build or wipe and reconfigure. Wiping removes `build/` directory entirely. |

**Note:**
Selecting **Yes** or **Wipe** may overwrite previously compiled files (`stuff.h`, `quickjs-opcode.h`, build directory contents).

---

## Custom Compilers

**Comper**:

* Compiles QuickJS bytecode using your patched QuickJS.
* Output: `/built/custom_compiler/comper`

**Dihcompiler**:

* Generates QuickJS decompiled output or bytecode dumps.
* Output: `/built/custom_dihcompiler/dihcomper`

---

## Gadget `loadBytecode` Usage

**Purpose:** Execute already compiled QuickJS bytecode directly from a gadget script, without recompiling the gadget or injecting scripts.

**Usage:**

```js
Script.loadBytecode("anyname", bytecode, () => {
    console.log("Bytecode script executed!");
});
```

* `bytecode` is an array of bytes, compiled via `./comper`.
* Bytecode can be hardcoded, downloaded from a server, or transferred over network.
* This allows direct execution of precompiled scripts inside your gadget.

**Note:** The final gadget built is only compatible with bytecode executed this way.

---

## Artifacts & Backups

```
built/
├─ server/                  → frida-server binary
├─ gadget/                  → frida-gadget.so
├─ custom_compiler/         → comper binary
├─ custom_dihcompiler/      → dihcomper binary
├─ backups/                 → quickjs-opcode.h, stuff.h, WHAT_ARE_THESE.md
```

* `WHAT_ARE_THESE.md` explains the purpose of backups and why they must be kept for reproducible builds.
* Artifact copies are logged clearly with `From →` and `To →` in the terminal.

---

## Usage

```bash
python3 frida_builder.py config.json
```

Steps executed:

1. Validate config and display summary table
2. Clone Frida repository (if missing)
3. Patch source files (`gum_quick_patcher.py` + `meson.build`)
4. Setup QuickJS (extract tarball if missing)
5. Optional: shuffle opcodes, generate `stuff.h`
6. Optional: build `comper` and/or `dihcomper`
7. Build Frida with selected components
8. Fetch and organize artifacts into `/built`

---

## FAQ

**Q: Why does my Gadget crash?**

* This usually happens because the script you are running or feeding your gadget was **not compiled with our custom `comper` tool**. Only bytecode produced by `comper` is compatible with the final gadget. Scripts compiled using the official `frida-compile` Python API or other methods are **not** compatible, thus causing a crash.

**Q: Why can `./dihcomper` decompile my custom-compiled scripts?**

* `dihcomper` is built with the same internal layout as your gadget and `comper`, so it can read the bytecode your custom compiler produces. Its goal is **verification**, not general decompilation. For decompiling scripts produced by standard compilers (not `comper`), use the dedicated JokerDecompiler tool: [JokerDecompiler](https://github.com/HuluHulu56/BatmanSecurer/tree/main/JokerDecompiler).

**Q: What happens if I run the builder twice?**

* Existing output directories are preserved unless you wipe.
* Backups and binaries are not overwritten unless explicitly rebuilt.

**Q: Can I skip custom compiler or dihcompiler builds?**

* Yes. You will be prompted for each.

**Q: Why shuffle opcodes?**

* Prevents predictable bytecode layout and reverse engineering.

**Q: What is `stuff.h`?**

* Contains key material derived from `atoms.custom_encryption_key`.
* Used by QuickJS for internal atom encryption.

**Q: Can I reuse the existing build?**

* Yes. Choose `[1] Reuse existing build`. Only `make` will run.

**Q: How do I use `loadBytecode`?**

* See [Gadget `loadBytecode` Usage](#gadget-loadbytecode-usage).

**Q: What about disabling V8?**

* Reduces gadget size by ~50%. Minor chance of compatibility issues.
