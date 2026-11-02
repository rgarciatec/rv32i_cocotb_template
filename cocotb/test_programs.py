"""Pruebas a nivel de programa para el CPU RV32I.

Cada prueba ejecuta un programa completo en el CPU, espera a que termine y
compara los resultados que dejó en memoria contra Python puro.
"""

import math

import cocotb
from cocotb.triggers import RisingEdge

from rv32i_asm import Assembler
from test_rv32i import BusModel, start_cpu

DONE_ADDRESS = 0x1FC   # el programa escribe aquí al terminar
MASK32 = 0xFFFF_FFFF


async def run_program(dut, asm, max_cycles, data=None):
    """Corre el programa hasta que escriba en DONE_ADDRESS y devuelve la memoria de datos."""
    model = BusModel(asm.assemble(), dict(data or {}))
    await start_cpu(dut, model)
    for _ in range(max_cycles):
        await RisingEdge(dut.clk)
        if DONE_ADDRESS in model.data:
            return model.data
    raise AssertionError(f"El programa no terminó en {max_cycles} ciclos")


# ---------------------------------------------------------------------------
# Programa 1: factorial recursivo de 0 a 13
# ---------------------------------------------------------------------------
RESULTS = 0x100        # results[n] = fact(n)
N_MAX = 13             # 13! no cabe en 32 bits: también prueba el desborde


def build_factorial():
    asm = Assembler()
    # main: for n in 0..N_MAX: results[n] = fact(n)
    asm.lui("sp", 0x1)                  # sp = 0x1000 (tope de la pila)
    asm.li("s0", 0)                     # n
    asm.li("s1", RESULTS)               # puntero a results[]
    asm.li("s2", N_MAX + 1)
    asm.label("loop")
    asm.mv("a0", "s0")
    asm.jal("ra", "fact")
    asm.sw("a0", 0, "s1")
    asm.addi("s1", "s1", 4)
    asm.addi("s0", "s0", 1)
    asm.blt("s0", "s2", "loop")
    asm.li("t0", 1)
    asm.sw("t0", DONE_ADDRESS, "zero")  # fin
    asm.label("halt")
    asm.j("halt")

    # fact(a0): return 1 si n < 2, si no mul(fact(n-1), n)
    asm.label("fact")
    asm.addi("sp", "sp", -8)
    asm.sw("ra", 4, "sp")
    asm.sw("a0", 0, "sp")
    asm.li("t0", 2)
    asm.bge("a0", "t0", "recurse")
    asm.li("a0", 1)
    asm.j("fact_end")
    asm.label("recurse")
    asm.addi("a0", "a0", -1)
    asm.jal("ra", "fact")               # a0 = fact(n-1)
    asm.lw("a1", 0, "sp")               # a1 = n
    asm.jal("ra", "mul")                # a0 = a0 * a1
    asm.label("fact_end")
    asm.lw("ra", 4, "sp")
    asm.addi("sp", "sp", 8)
    asm.ret()

    # mul(a0, a1): multiplicación por suma y desplazamiento (RV32I no tiene mul)
    asm.label("mul")
    asm.li("t1", 0)
    asm.label("mul_loop")
    asm.beq("a1", "zero", "mul_end")
    asm.andi("t2", "a1", 1)
    asm.beq("t2", "zero", "mul_skip")
    asm.add("t1", "t1", "a0")
    asm.label("mul_skip")
    asm.slli("a0", "a0", 1)
    asm.srli("a1", "a1", 1)
    asm.j("mul_loop")
    asm.label("mul_end")
    asm.mv("a0", "t1")
    asm.ret()
    return asm


@cocotb.test()
async def factorial(dut):
    """Factorial recursivo de 0 a 13, comparado contra math.factorial."""
    memory = await run_program(dut, build_factorial(), max_cycles=100_000)

    got = [memory.get(RESULTS + 4 * n) for n in range(N_MAX + 1)]
    expected = [math.factorial(n) & MASK32 for n in range(N_MAX + 1)]
    dut._log.info("CPU:    %s", got)
    dut._log.info("Python: %s", expected)
    assert got == expected, "El factorial calculado por el CPU no coincide con Python"