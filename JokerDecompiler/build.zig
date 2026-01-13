const std = @import("std");

//feature detection for API changes across Zig versions
const use_modern_api = @hasField(std.Build.ExecutableOptions, "root_module");

//helper to handle the transition from CrossTarget (0.11) to ResolvedTarget (0.12), cuz im a moron
fn getOsTag(t: anytype) std.Target.Os.Tag {
    const T = @TypeOf(t);
    if (@hasField(T, "result")) {
        return t.result.os.tag;
    }
    return t.getOsTag();
}

pub fn build(b: *std.Build) void {
    if (use_modern_api) {
        Modern.build(b);
    } else {
        Legacy.build(b);
    }
}

const Legacy = if (!use_modern_api) struct {
    pub fn build(b: anytype) void {
        const target = b.standardTargetOptions(.{});
        const optimize = b.standardOptimizeOption(.{});
        const enable_bignum = b.option(bool, "bignum", "Enable CONFIG_BIGNUM (requires libbf)") orelse false;

        const exe = b.addExecutable(.{
            .name = "inspect",
            .root_source_file = .{ .path = "inspect.zig" },
            .target = target,
            .optimize = optimize,
        });

        exe.addIncludePath(.{ .path = "." });
        exe.addIncludePath(.{ .path = "dependencies/quickjs" });
        exe.linkLibC();

        var c_flags_buf: [10][]const u8 = undefined;
        var c_flags_len: usize = 0;
        c_flags_buf[c_flags_len] = "-std=c11";
        c_flags_len += 1;
        //force undefine AVX2 to avoid FMA requirement (VMs often don't expose FMA)
        c_flags_buf[c_flags_len] = "-U__AVX2__";
        c_flags_len += 1;

        if (enable_bignum) {
            //CONFIG_BIGNUM automatically enables USE_BF_DEC in libbf.c
            c_flags_buf[c_flags_len] = "-DCONFIG_BIGNUM";
            c_flags_len += 1;
        } else {
            //need USE_BF_DEC for bfdec functions used by bf_atof
            c_flags_buf[c_flags_len] = "-DUSE_BF_DEC";
            c_flags_len += 1;
        }

        if (getOsTag(target) != .windows) {
            c_flags_buf[c_flags_len] = "-D_GNU_SOURCE";
            c_flags_len += 1;
        }

        const c_files = [_][]const u8{
            "inspect_internals.c",
            "dependencies/quickjs/quickjs-libc.c",
            "dependencies/quickjs/libregexp.c",
            "dependencies/quickjs/libunicode.c",
            "dependencies/quickjs/libbf.c",
            "dependencies/quickjs/cutils.c",
        };

        const flags = c_flags_buf[0..c_flags_len];

        //handle both old API (2 args) and new API (1 struct arg) cuz im a moron
        for (c_files) |file| {
            const CSourceFile = std.Build.Module.CSourceFile;
            if (@hasField(CSourceFile, "file")) {
                // New API: single struct argument with .file field
                exe.addCSourceFile(.{
                    .file = .{ .path = file },
                    .flags = flags,
                });
            } else {
                //use old API: two separate arguments
                exe.addCSourceFile(.{ .path = file }, flags);
            }
        }

        if (getOsTag(target) != .windows) {
            exe.linkSystemLibrary("m");
            exe.linkSystemLibrary("dl");
        }

        b.installArtifact(exe);

        const run_cmd = b.addRunArtifact(exe);
        run_cmd.step.dependOn(b.getInstallStep());
        if (b.args) |args| run_cmd.addArgs(args);

        const run_step = b.step("run", "Run inspect");
        run_step.dependOn(&run_cmd.step);
    }
} else struct {
    pub fn build(b: anytype) void {
        _ = b;
    }
};

const Modern = if (use_modern_api) struct {
    pub fn build(b: anytype) void {
        const target = b.standardTargetOptions(.{});
        const optimize = b.standardOptimizeOption(.{});
        const enable_bignum = b.option(bool, "bignum", "Enable CONFIG_BIGNUM (requires libbf)") orelse false;

        const exe_mod = b.createModule(.{
            .root_source_file = b.path("inspect.zig"),
            .target = target,
            .optimize = optimize,
        });

        const exe = b.addExecutable(.{
            .name = "inspect",
            .root_module = exe_mod,
        });

        exe.root_module.addIncludePath(b.path("."));
        exe.root_module.addIncludePath(b.path("dependencies/quickjs"));
        exe.root_module.link_libc = true;

        var c_flags_buf: [10][]const u8 = undefined;
        var c_flags_len: usize = 0;
        c_flags_buf[c_flags_len] = "-std=c11";
        c_flags_len += 1;
        //force undefine AVX2 to avoid FMA requirement (VMs often don't expose FMA)
        c_flags_buf[c_flags_len] = "-U__AVX2__";
        c_flags_len += 1;

        if (enable_bignum) {
            //CONFIG_BIGNUM automatically enables USE_BF_DEC in libbf.c
            c_flags_buf[c_flags_len] = "-DCONFIG_BIGNUM";
            c_flags_len += 1;
        } else {
            //need USE_BF_DEC for bfdec functions used by bf_atof
            c_flags_buf[c_flags_len] = "-DUSE_BF_DEC";
            c_flags_len += 1;
        }

        if (target.result.os.tag != .windows) {
            c_flags_buf[c_flags_len] = "-D_GNU_SOURCE";
            c_flags_len += 1;
        }

        const c_files = [_][]const u8{
            "inspect_internals.c",
            "dependencies/quickjs/quickjs-libc.c",
            "dependencies/quickjs/libregexp.c",
            "dependencies/quickjs/libunicode.c",
            "dependencies/quickjs/libbf.c",
            "dependencies/quickjs/cutils.c",
        };

        exe.root_module.addCSourceFiles(.{
            .root = b.path("."),
            .files = &c_files,
            .flags = c_flags_buf[0..c_flags_len],
        });

        if (target.result.os.tag != .windows) {
            exe.root_module.linkSystemLibrary("m", .{});
            exe.root_module.linkSystemLibrary("dl", .{});
        }

        b.installArtifact(exe);

        const run_cmd = b.addRunArtifact(exe);
        run_cmd.step.dependOn(b.getInstallStep());
        if (b.args) |args| run_cmd.addArgs(args);

        const run_step = b.step("run", "Run inspect");
        run_step.dependOn(&run_cmd.step);
    }
} else struct {
    pub fn build(b: anytype) void {
        _ = b;
    }
};
