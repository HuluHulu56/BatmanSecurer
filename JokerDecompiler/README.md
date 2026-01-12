# JokerDecompiler

## Table of Contents

1. [Intro](#intro)
2. [Building](#building)
3. [Usage](#usage)
4. [Output](#output)

---

## Intro

JokerDecompiler is a proof-of-concept tool used to verify the security of `BatmanSecurer`. It attempts to deconstruct QuickJS bytecode by dumping atoms, objects, and function instructions. Use this to check if your bytecode is still readable or if `BatmanSecurer` has successfully obfuscated it.

---

## Building

### Requirements

* Zig Compiler (latest stable)
* QuickJS sources (located in `dependencies/quickjs/`)

### Windows

```bash
cd JokerDecompiler
zig build -Dtarget=x86_64-windows-gnu -Doptimize=ReleaseFast -Dbignum=true
```

### Linux

```bash
cd JokerDecompiler
zig build -Doptimize=ReleaseFast -Dbignum=true
```

**Note:** The `-Dbignum` flag must match the setting used when the bytecode was compiled.

---

## Usage

The binary is output to `zig-out/bin/inspect`.

```bash
./zig-out/bin/inspect [options] <file.js.compiled>
```

| Flag | Description |
| :--- | :--- |
| `-a` | Dump atoms |
| `-o` | Dump objects |
| `-f` | Dump function bytecode |
| `-h` | Help |

---

## Output

Running the tool generates a dump file `<scriptname>-dump.txt` in the same directory as the input script. All output is also printed to stdout.


