# BatmanSecurer

## Table of Contents

1. [Overview](#overview)
2. [Components](#components)

---

## Overview

BatmanSecurer is a project dedicated to securing QuickJS bytecode against reverse engineering. It achieves this by modifying the QuickJS VM to use custom opcode tables and encryption, making standard analysis tools fail.

This repository contains the Securer itself, along with a proof-of-concept Decompiler to verify the hardening results.

---

## Components

### BatmanSecurer

The core security tool. It builds a customized Frida gadget (or server) with:
*   Opcode Shuffling: Randomizes instruction mapping.
*   Atom Encryption: Encrypts strings and identifiers.
*   Hardened Runtime: Prevents standard QuickJS tools from parsing the bytecode.

[Go to BatmanSecurer](./BatmanSecurer/README.md)

### JokerDecompiler

A proof-of-concept inspection tool intended to function as a "standard" decompiler. Use this to test the effectiveness of your BatmanSecurer build. If BatmanSecurer is working correctly, JokerDecompiler should fail to produce readable output for your secured scripts.

[Go to JokerDecompiler](./JokerDecompiler/README.md)
