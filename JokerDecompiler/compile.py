from frida.core import *
import frida

session = frida.attach(0)

script = open("script.js", "rb").read().decode("utf-8")

bytecode = session.compile_script(script, "zupa")

with open("scriptcompiled.js", "wb") as file:
    file.write(bytecode)