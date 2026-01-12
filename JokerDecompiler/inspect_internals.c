#include <stdio.h>
#include <stdarg.h>
#include "quickjs.h"

static FILE *g_dump_fp;

int inspect_set_dump_file(const char *path)
{
    if (g_dump_fp) {
        fclose(g_dump_fp);
        g_dump_fp = NULL;
    }

    if (!path)
        return -1;

    g_dump_fp = fopen(path, "wb");
    if (!g_dump_fp)
        return -1;

    return 0;
}

void inspect_close_dump_file(void)
{
    if (!g_dump_fp)
        return;
    fclose(g_dump_fp);
    g_dump_fp = NULL;
}

static int tee_printf(const char *fmt, ...)
{
    va_list ap1;
    va_list ap2;
    int ret;

    va_start(ap1, fmt);
    va_copy(ap2, ap1);

    ret = vfprintf(stdout, fmt, ap1);
    if (g_dump_fp) {
        vfprintf(g_dump_fp, fmt, ap2);
        fflush(g_dump_fp);
    }

    fflush(stdout);

    va_end(ap2);
    va_end(ap1);

    return ret;
}

#define printf tee_printf
#include "quickjs.c"
#undef printf

#undef malloc
#undef free

typedef struct JSFunctionBytecode JSFunctionBytecode;
void js_dump_function_bytecode(JSContext *ctx, JSFunctionBytecode *b);

void inspect_obj_recursive(JSContext *ctx, JSValue v)
{
    int tag = JS_VALUE_GET_TAG(v);

    if (tag != JS_TAG_OBJECT && tag != JS_TAG_FUNCTION_BYTECODE)
        return;

    if (tag == JS_TAG_FUNCTION_BYTECODE) {
        JSFunctionBytecode *bc = JS_VALUE_GET_PTR(v);
        if (bc)
            js_dump_function_bytecode(ctx, bc);
    }

    if (tag == JS_TAG_FUNCTION_BYTECODE) {
        JSFunctionBytecode *bc = JS_VALUE_GET_PTR(v);
        if (bc) {
            for (int i = 0; i < bc->cpool_count; i++)
                inspect_obj_recursive(ctx, bc->cpool[i]);
        }
    }
}

int qjs_bc_version(void)
{
    return BC_VERSION;
}