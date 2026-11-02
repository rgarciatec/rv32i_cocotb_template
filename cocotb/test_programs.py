"""Pruebas a nivel de programa para el CPU RV32I.

Cada prueba ejecuta un programa completo en el CPU, espera a que termine y
compara los resultados que dejó en memoria contra Python puro.
"""

import math
from functools import reduce

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


# ---------------------------------------------------------------------------
# Programa 2: generador xorshift32 + estadísticas
# ---------------------------------------------------------------------------
SEED = 0x12345678
COUNT = 16
NUMBERS = 0x100        # numbers[16]  (0x100 .. 0x13C)
ABS = 0x140            # abs[16]      (0x140 .. 0x17C) = NUMBERS + 64
STATS = 0x180          # max_s, min_s, max_u, negativos, low<128, ceros, and, or, checksum
MASK_0F = 0x0F0F0F0F


def build_xorshift():
    asm = Assembler()
    asm.li("s0", SEED)                  # x (estado del generador)        -> lui + addi
    asm.li("s1", NUMBERS)               # puntero
    asm.li("s2", COUNT)                 # contador
    asm.li("s3", 13)                    # cantidades de desplazamiento en registros
    asm.li("s4", 17)
    asm.li("s5", 5)
    asm.li("a6", 3)
    asm.lui("s6", 0x80000)              # max con signo = 0x80000000 (el más negativo)
    asm.li("s7", 0x7FFFFFFF)            # min con signo                    -> lui + addi
    asm.li("s8", 0)                     # max sin signo
    asm.li("s9", 0)                     # cantidad de negativos
    asm.li("s10", 0)                    # cantidad con byte bajo < 128
    asm.li("s11", -1)                   # AND acumulado
    asm.li("t6", 0)                     # OR acumulado
    asm.li("a7", 0)                     # checksum
    asm.li("a5", 0)                     # cantidad de ceros
    asm.li("t5", MASK_0F)               # constante de 32 bits                -> lui + addi

    asm.label("loop")
    # xorshift32: x ^= x << 13; x ^= x >> 17; x ^= x << 5
    asm.sll("t0", "s0", "s3")
    asm.xor("s0", "s0", "t0")
    asm.srl("t0", "s0", "s4")
    asm.xor("s0", "s0", "t0")
    asm.sll("t0", "s0", "s5")
    asm.xor("s0", "s0", "t0")
    asm.sw("s0", 0, "s1")               # numbers[i] = x

    # |x| sin branches: m = x >> 31 (aritmético); abs = (x ^ m) - m
    asm.srai("t1", "s0", 31)
    asm.xor("t2", "s0", "t1")
    asm.sub("t2", "t2", "t1")
    asm.sw("t2", ABS - NUMBERS, "s1")   # abs[i]

    # máximo con signo
    asm.slt("t3", "s6", "s0")
    asm.beq("t3", "zero", "skip_max")
    asm.mv("s6", "s0")
    asm.label("skip_max")
    # mínimo con signo
    asm.slt("t3", "s0", "s7")
    asm.beq("t3", "zero", "skip_min")
    asm.mv("s7", "s0")
    asm.label("skip_min")
    # máximo sin signo
    asm.sltu("t3", "s8", "s0")
    asm.beq("t3", "zero", "skip_maxu")
    asm.mv("s8", "s0")
    asm.label("skip_maxu")

    asm.slti("t3", "s0", 0)             # ¿negativo?
    asm.add("s9", "s9", "t3")
    asm.andi("t4", "s0", 0xFF)
    asm.sltiu("t3", "t4", 128)          # ¿byte bajo < 128?
    asm.add("s10", "s10", "t3")
    asm.sltiu("t3", "s0", 1)            # ¿x == 0? (sin signo: x < 1)
    asm.add("a5", "a5", "t3")
    asm.and_("s11", "s11", "s0")        # AND acumulado
    asm.or_("t6", "t6", "s0")           # OR acumulado

    # checksum = ~((cs ^ (x >> 3 aritmético)) + (x >>> 16) + (x & 0x0F0F0F0F)) | 1
    asm.sra("t0", "s0", "a6")
    asm.xor("a7", "a7", "t0")
    asm.srli("t0", "s0", 16)
    asm.add("a7", "a7", "t0")
    asm.and_("t0", "s0", "t5")
    asm.add("a7", "a7", "t0")
    asm.xori("a7", "a7", -1)
    asm.ori("a7", "a7", 1)

    asm.addi("s1", "s1", 4)
    asm.addi("s2", "s2", -1)
    asm.bne("s2", "zero", "loop")

    for i, register in enumerate(("s6", "s7", "s8", "s9", "s10", "a5", "s11", "t6", "a7")):
        asm.sw(register, STATS + 4 * i, "zero")
    asm.li("t0", 1)
    asm.sw("t0", DONE_ADDRESS, "zero")  # fin
    asm.label("halt")
    asm.j("halt")
    return asm


def xorshift_python():
    """Mismo cálculo en Python puro."""
    signed = lambda v: v - (1 << 32) if v & 0x8000_0000 else v
    x, numbers = SEED, []
    for _ in range(COUNT):
        x ^= (x << 13) & MASK32
        x ^= x >> 17
        x ^= (x << 5) & MASK32
        numbers.append(x)

    checksum = 0
    for n in numbers:
        checksum ^= (signed(n) >> 3) & MASK32
        checksum = (checksum + (n >> 16) + (n & MASK_0F)) & MASK32
        checksum = (~checksum & MASK32) | 1

    stats = [
        max(signed(n) for n in numbers) & MASK32,
        min(signed(n) for n in numbers) & MASK32,
        max(numbers),
        sum(signed(n) < 0 for n in numbers),
        sum((n & 0xFF) < 128 for n in numbers),
        sum(n == 0 for n in numbers),
        reduce(lambda a, b: a & b, numbers, MASK32),
        reduce(lambda a, b: a | b, numbers, 0),
        checksum,
    ]
    absolutes = [abs(signed(n)) & MASK32 for n in numbers]
    return numbers, absolutes, stats


@cocotb.test()
async def xorshift(dut):
    """Generador xorshift32 + estadísticas con signo/sin signo, comparado contra Python."""
    memory = await run_program(dut, build_xorshift(), max_cycles=100_000)

    numbers, absolutes, stats = xorshift_python()
    checks = {
        "números": ([memory.get(NUMBERS + 4 * i) for i in range(COUNT)], numbers),
        "valores absolutos": ([memory.get(ABS + 4 * i) for i in range(COUNT)], absolutes),
        "estadísticas": ([memory.get(STATS + 4 * i) for i in range(len(stats))], stats),
    }
    for name, (got, expected) in checks.items():
        assert got == expected, (
            f"Las {name} del CPU no coinciden con Python:\n  CPU:    {got}\n  Python: {expected}"
        )
    dut._log.info("Estadísticas CPU:    %s", [hex(v) for v in checks["estadísticas"][0]])
    dut._log.info("Estadísticas Python: %s", [hex(v) for v in stats])