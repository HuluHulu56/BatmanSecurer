# BatmanSecurer


## Overview

BatmanSecurer is a project dedicated to securing QuickJS bytecode against reverse engineering. It achieves this by modifying QuickJS to use custom opcode tables and encryption, making standard analysis tools fail.

This repository contains the Securer itself, along with a proof-of-concept Decompiler to verify the hardening results.

<img width="1344" height="768" alt="image" src="https://github.com/user-attachments/assets/280a010d-5f54-4d5a-afe2-8813e28090ae" />
<small>(epic fight scene for ilustration purposes)</small>

---

## Components

### BatmanSecurer

The core security tool. It builds a customized Frida gadget (or server) with:
*   Opcode Shuffling: Randomizes instruction mapping.
*   Atom Encryption: Encrypts strings and identifiers.
*   Hardened Runtime: Prevents standard QuickJS tools from parsing the bytecode.
*   loadBytecode: javascript API to load and execute compiled scripts directly from javascript

[Go to BatmanSecurer](./BatmanSecurer/README.md)

### JokerDecompiler

A proof-of-concept inspection tool intended to function as a "standard" decompiler. Use this to test the effectiveness of your BatmanSecurer build. If BatmanSecurer is working correctly, JokerDecompiler should fail to produce correct output for your secured scripts. The entire integration of JokerDecompiler is based on open source code that has been sitting on the internet for the past 6 years.

[Go to JokerDecompiler](./JokerDecompiler/README.md)

---

### ToDo
*  Update the Proof-of-Concept decompiler (Joker) to reconstruct opcodes back into "readable" javascript (in progress)
*  Proof-of-Concept reverse a Proof-of-Concept (Joker v2)
*  Protect against Proof-of-Concepted Proof-of-Concept by making byte level obfuscation on top of Batman (Batman v2)

---

