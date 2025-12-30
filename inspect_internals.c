#include <stdio.h>
#include "quickjs.h"
#include "quickjs.c"

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