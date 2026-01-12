const std = @import("std");

const c = @cImport({
    @cInclude("quickjs.h");
    @cInclude("quickjs-libc.h");
    @cInclude("stdio.h");
});

extern fn inspect_obj_recursive(ctx: ?*c.JSContext, v: c.JSValue) void;
extern fn qjs_bc_version() c_int;
extern fn inspect_set_dump_file(path: [*:0]const u8) c_int;
extern fn inspect_close_dump_file() void;

fn dumpException(ctx: *c.JSContext) void {
    const exc = c.JS_GetException(ctx);
    defer c.JS_FreeValue(ctx, exc);

    const cstr = c.JS_ToCString(ctx, exc);
    if (cstr == null) {
        std.debug.print("error\n", .{});
        return;
    }
    defer c.JS_FreeCString(ctx, cstr);

    std.debug.print("{s}\n", .{std.mem.span(cstr)});
}

fn readAll(allocator: std.mem.Allocator, path: []const u8) ![]u8 {
    const zpath = try allocator.dupeZ(u8, path);
    defer allocator.free(zpath);

    const fp = c.fopen(zpath.ptr, "rb");
    if (fp == null) return error.FileOpen;
    defer _ = c.fclose(fp);

    if (c.fseek(fp, 0, c.SEEK_END) != 0) return error.FileSeek;
    const end_pos = c.ftell(fp);
    if (end_pos < 0) return error.FileTell;
    if (c.fseek(fp, 0, c.SEEK_SET) != 0) return error.FileSeek;

    const size: usize = @intCast(end_pos);
    const buf = try allocator.alloc(u8, size);
    errdefer allocator.free(buf);

    const got = c.fread(buf.ptr, 1, buf.len, fp);
    if (got != buf.len) return error.FileRead;

    return buf;
}

fn makeArgv(allocator: std.mem.Allocator, args: []const []const u8) !struct {
    argv: [][*c]u8,
    zargs: [][:0]u8,
} {
    const zargs = try allocator.alloc([:0]u8, args.len);
    errdefer {
        for (zargs) |z| allocator.free(z);
        allocator.free(zargs);
    }

    const argv = try allocator.alloc([*c]u8, args.len);
    errdefer allocator.free(argv);

    for (args, 0..) |a, i| {
        const z = try allocator.dupeZ(u8, a);
        zargs[i] = z;
        argv[i] = @ptrCast(z.ptr);
    }

    return .{ .argv = argv, .zargs = zargs };
}

fn splitDirBase(path: []const u8) struct { dir: []const u8, base: []const u8 } {
    var last_sep: ?usize = null;
    for (path, 0..) |ch, i| {
        if (ch == '/' or ch == '\\') last_sep = i;
    }

    if (last_sep) |idx| {
        return .{ .dir = path[0..idx], .base = path[idx + 1 ..] };
    }
    return .{ .dir = "", .base = path };
}

fn stemNoExt(base: []const u8) []const u8 {
    var last_dot: ?usize = null;
    for (base, 0..) |ch, i| {
        if (ch == '.') last_dot = i;
    }
    if (last_dot) |idx| {
        if (idx == 0) return base;
        return base[0..idx];
    }
    return base;
}

fn makeDumpPath(allocator: std.mem.Allocator, input_path: []const u8) ![]u8 {
    const parts = splitDirBase(input_path);
    const stem = stemNoExt(parts.base);
    const out_name = try std.mem.concat(allocator, u8, &.{ stem, "-dump.txt" });
    errdefer allocator.free(out_name);

    if (parts.dir.len == 0) return out_name;

    const sep: []const u8 = std.fs.path.sep_str;
    if (parts.dir.len > 0 and (parts.dir[parts.dir.len - 1] == '/' or parts.dir[parts.dir.len - 1] == '\\')) {
        const out_path = try std.mem.concat(allocator, u8, &.{ parts.dir, out_name });
        allocator.free(out_name);
        return out_path;
    }

    const out_path = try std.mem.concat(allocator, u8, &.{ parts.dir, sep, out_name });
    allocator.free(out_name);
    return out_path;
}

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    if (args.len < 2) {
        std.debug.print("usage: {s} <bytecode-file>\n", .{args[0]});
        std.process.exit(1);
    }

    const path = args[1];
    const data = try readAll(allocator, path);
    defer allocator.free(data);

    if (data.len == 0) {
        std.debug.print("error: empty input file\n", .{});
        std.process.exit(1);
    }

    const expected_bc_version: u8 = @intCast(qjs_bc_version());
    if (data[0] != expected_bc_version) {
        std.debug.print(
            "error: bytecode version {d} but this build expects {d}. " ++
                "this is usually a CONFIG_BIGNUM mismatch. Rebuild with -Dbignum=true (for version 2) or without it (for version 1).\n",
            .{ data[0], expected_bc_version },
        );
        std.process.exit(1);
    }

    const rt = c.JS_NewRuntime() orelse return error.RuntimeInitFailed;
    defer c.JS_FreeRuntime(rt);

    const ctx = c.JS_NewContext(rt) orelse return error.ContextInitFailed;
    defer c.JS_FreeContext(ctx);

    const carg = try makeArgv(allocator, args);
    defer {
        for (carg.zargs) |z| allocator.free(z);
        allocator.free(carg.zargs);
        allocator.free(carg.argv);
    }

    c.js_std_add_helpers(ctx, @intCast(args.len), @ptrCast(carg.argv.ptr));
    c.js_std_init_handlers(rt);
    defer c.js_std_free_handlers(rt);

    const obj = c.JS_ReadObject(ctx, data.ptr, data.len, c.JS_READ_OBJ_BYTECODE);
    if (c.JS_IsException(obj) != 0) {
        c.js_std_dump_error(ctx);
        std.process.exit(1);
    }
    defer c.JS_FreeValue(ctx, obj);

    const dump_path = try makeDumpPath(allocator, path);
    defer allocator.free(dump_path);
    const dump_z = try allocator.dupeZ(u8, dump_path);
    defer allocator.free(dump_z);

    if (inspect_set_dump_file(dump_z.ptr) != 0) {
        std.debug.print("error: could not open dump file: {s}\n", .{dump_path});
        std.process.exit(1);
    }
    defer inspect_close_dump_file();

    inspect_obj_recursive(ctx, obj);
}
