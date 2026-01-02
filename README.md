# Build

## Windows
```bash
cd JokerDecompiler
zig build -Dtarget=x86_64-windows-gnu -Doptimize=ReleaseFast -Dbignum=true
```

## Linux
```bash
cd JokerDecompiler
zig build -Doptimize=ReleaseFast -Dbignum=true
```