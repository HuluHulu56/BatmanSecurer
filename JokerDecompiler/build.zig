const std = @import("std");

pub fn build(b: *std.Build) void {
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

    //old api had these on the compile step
    if (@hasDecl(@TypeOf(exe.root_module.*), "addIncludePath")) {
        exe.root_module.addIncludePath(b.path("."));
        exe.root_module.addIncludePath(b.path("dependencies/quickjs"));
    } else {
        exe.addIncludePath(b.path("."));
        exe.addIncludePath(b.path("dependencies/quickjs"));
    }

    if (@hasField(@TypeOf(exe.root_module.*), "link_libc")) {
        exe.root_module.link_libc = true;
    }

    var c_flags_buf: [3][]const u8 = undefined;
    var c_flags_len: usize = 0;
    c_flags_buf[c_flags_len] = "-std=c11";
    c_flags_len += 1;
    if (enable_bignum) {
        c_flags_buf[c_flags_len] = "-DCONFIG_BIGNUM";
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

    if (@hasDecl(@TypeOf(exe.root_module.*), "addCSourceFiles")) {
        exe.root_module.addCSourceFiles(.{
            .root = b.path("."),
            .files = &c_files,
            .flags = c_flags_buf[0..c_flags_len],
        });
    } else {
        exe.addCSourceFiles(.{ .files = &c_files, .flags = c_flags_buf[0..c_flags_len] });
    }

    if (target.result.os.tag != .windows) {
        if (@hasDecl(@TypeOf(exe.root_module.*), "linkSystemLibrary")) {
            exe.root_module.linkSystemLibrary("m", .{});
            exe.root_module.linkSystemLibrary("dl", .{});
        } else {
            exe.linkSystemLibrary("m");
            exe.linkSystemLibrary("dl");
        }
    }

    b.installArtifact(exe);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    if (b.args) |args| run_cmd.addArgs(args);

    const run_step = b.step("run", "Run inspect");
    run_step.dependOn(&run_cmd.step);
}
