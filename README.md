# Intro
idk.. like BatmanSecurer and JokerDecompiler... pretty self explenatory... JokerDecompiler decompiles your qjs bytecode into opcodes and reconstructs them... BatmanSecurer makes this impossible generating a gadget that uses custom opcodes.. so JokerDecompiler or any other decompiler will fail
<img width="1344" height="768" alt="image" src="https://github.com/user-attachments/assets/280a010d-5f54-4d5a-afe2-8813e28090ae" />



# Build

## Windows
```bash
zig build -Dtarget=x86_64-windows-gnu -Doptimize=ReleaseFast -Dbignum=true
```

## Linux
```bash
zig build -Doptimize=ReleaseFast -Dbignum=true
```


