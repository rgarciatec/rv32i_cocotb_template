"""Pruebas a nivel de programa para el CPU RV32I.

En lugar de probar instrucción por instrucción, cada prueba ejecuta un programa
completo en el CPU y lo verifica en tres niveles:

1. Traza de memoria: TODAS las escrituras a dmem (dirección, dato y orden) deben
   coincidir con las de un simulador de referencia en Python (rv32i_asm.ReferenceModel)
   que ejecuta el mismo programa.
2. Resultado funcional: los resultados se comparan contra Python "puro"
   (por ejemplo math.factorial), independiente del ISS.
3. Invariantes del programa: pila balanceada, direcciones de retorno válidas, etc.

Solo se usan los puertos del CPU (imem_*, dmem_*), así que funciona con el mock
o con cualquier CPU que respete la interfaz del README.
"""

import math
import os
from collections import Counter

import cocotb
from cocotb.triggers import RisingEdge

from rv32i_asm import MASK32, SUPPORTED, Assembler, ReferenceModel
from test_rv32i import BusModel, start_cpu

# Mapa de memoria de datos común a los programas
DONE_ADDRESS = 0x1FC       # el programa escribe aquí al terminar
CYCLES_PER_INSTRUCTION_LIMIT = int(os.environ.get("RV32I_CPI_LIMIT", "60"))


# ---------------------------------------------------------------------------
# Infraestructura común
# ---------------------------------------------------------------------------
def _done(writes) -> bool:
    return any(address == DONE_ADDRESS for address, _ in writes)


async def run_program(dut, asm: Assembler, data: dict[int, int] | None = None):
    """Ejecuta el programa en el ISS y en el CPU, y compara la traza de escrituras."""
    program = asm.assemble()
    data = data or {}

    # 1) Modelo de referencia: qué DEBERÍA pasar
    golden = ReferenceModel(program, data)
    golden.run(stop=lambda m: _done(m.dmem_writes))
    max_cycles = max(5_000, golden.steps * CYCLES_PER_INSTRUCTION_LIMIT)
    dut._log.info(
        "Programa: %d instrucciones estáticas, %d ejecutadas en el ISS, %d escrituras esperadas",
        len(program), golden.steps, len(golden.dmem_writes),
    )

    # 2) CPU real
    model = BusModel(program, dict(data))
    await start_cpu(dut, model)
    actual, expected = model.dmem_writes, golden.dmem_writes
    checked = 0
    cycles = 0
    done = False
    while not done:
        await RisingEdge(dut.clk)
        cycles += 1
        done = _done(actual)
        # 3) Cada escritura se compara apenas ocurre (dirección, dato y orden),
        #    así un error se reporta en el punto exacto donde aparece.
        while checked < len(actual):
            got = actual[checked]
            assert checked < len(expected), (
                f"Escritura extra #{checked}: CPU sw [0x{got[0]:08x}] = 0x{got[1]:08x} "
                f"(el programa de referencia solo hace {len(expected)})"
            )
            want = expected[checked]
            assert got == want, (
                f"Escritura #{checked} distinta (ciclo {cycles}): "
                f"CPU sw [0x{got[0]:08x}] = 0x{got[1]:08x}, "
                f"esperado sw [0x{want[0]:08x}] = 0x{want[1]:08x}"
            )
            checked += 1
        if not done and cycles >= max_cycles:
            last_pc = model.imem_fetches[-1] if model.imem_fetches else None
            raise AssertionError(
                f"Timeout: el CPU no terminó en {max_cycles} ciclos. "
                f"Escrituras correctas: {checked}/{len(expected)}, "
                f"último fetch: {hex(last_pc) if last_pc is not None else 'ninguno'}"
            )

    assert checked == len(expected), (
        f"Cantidad de escrituras distinta: CPU {checked}, esperado {len(expected)}"
    )

    _report(dut, golden, cycles)
    return model, golden


def _report(dut, golden: ReferenceModel, cycles: int) -> None:
    used = [name for name in SUPPORTED if golden.executed[name]]
    unused = [name for name in SUPPORTED if not golden.executed[name]]
    dut._log.info(
        "OK: %d instrucciones en %d ciclos (CPI ~ %.1f)", golden.steps, cycles, cycles / golden.steps
    )
    dut._log.info(
        "Instrucciones ejercitadas (%d/%d): %s",
        len(used), len(SUPPORTED), ", ".join(f"{n}x{golden.executed[n]}" for n in used),
    )
    dut._log.info("No ejercitadas: %s", ", ".join(unused) or "ninguna")
    branches = ", ".join(
        f"{name}:{golden.branches[(name, True)]}T/{golden.branches[(name, False)]}NT"
        for name in ("beq", "bne", "blt", "bge") if golden.executed[name]
    )
    dut._log.info("Branches (tomados T / no tomados NT): %s", branches or "-")


# ---------------------------------------------------------------------------
# Programa 1: factorial recursivo
# ---------------------------------------------------------------------------
FACT_RESULTS = 0x100       # fact(0), fact(1), ... fact(N_MAX) como arreglo de words
FACT_SP_REPORT = 0x1F8     # valor final de sp (debe volver al inicial)
FACT_STACK_TOP = 0x1000
FACT_N_MAX = 13            # 13! = 6 227 020 800 > 2^32  ->  prueba el desborde (mod 2^32)


def build_factorial() -> Assembler:
    """Calcula fact(n) para n = 0..FACT_N_MAX con recursión real y multiplicación por software.

        main:  for n in 0..N_MAX:  results[n] = fact(n)
        fact(n):  return 1 if n < 2 else mul(fact(n-1), n)       (marco de pila de 8 bytes)
        mul(a, b): suma y desplazamiento (no hay instrucción mul en RV32I)
    """
    asm = Assembler()
    # ---- main ----
    asm.lui("sp", FACT_STACK_TOP >> 12)          # sp = 0x1000
    asm.li("s0", 0)                              # n
    asm.li("s1", FACT_RESULTS)                   # puntero a results[]
    asm.li("s2", FACT_N_MAX + 1)                 # límite del lazo
    asm.label("main_loop")
    asm.mv("a0", "s0")
    asm.jal("ra", "fact")                        # a0 = fact(n)
    asm.label("ret_main")                        # dirección de retorno esperada desde main
    asm.sw("a0", 0, "s1")                        # results[n] = a0
    asm.addi("s1", "s1", 4)
    asm.addi("s0", "s0", 1)
    asm.blt("s0", "s2", "main_loop")
    asm.sw("sp", FACT_SP_REPORT, "zero")         # reporta sp final
    asm.li("t0", 1)
    asm.sw("t0", DONE_ADDRESS, "zero")           # fin del programa
    asm.label("halt")
    asm.j("halt")

    # ---- fact(a0) -> a0 ----
    asm.label("fact")
    asm.addi("sp", "sp", -8)                     # reserva marco
    asm.sw("ra", 4, "sp")                        # guarda dirección de retorno
    asm.sw("a0", 0, "sp")                        # guarda n
    asm.li("t0", 2)
    asm.bge("a0", "t0", "fact_recurse")          # n >= 2 -> caso recursivo
    asm.li("a0", 1)                              # caso base: fact(0) = fact(1) = 1
    asm.j("fact_return")
    asm.label("fact_recurse")
    asm.addi("a0", "a0", -1)
    asm.jal("ra", "fact")                        # a0 = fact(n-1)
    asm.label("ret_fact")                        # dirección de retorno esperada (recursión)
    asm.lw("a1", 0, "sp")                        # a1 = n (recuperado de la pila)
    asm.jal("ra", "mul")                         # a0 = fact(n-1) * n
    asm.label("fact_return")
    asm.lw("ra", 4, "sp")                        # restaura ra
    asm.addi("sp", "sp", 8)                      # libera marco
    asm.ret()

    # ---- mul(a0, a1) -> a0 = a0 * a1 (mod 2^32) ----
    asm.label("mul")
    asm.li("t1", 0)                              # acumulador
    asm.label("mul_loop")
    asm.beq("a1", "zero", "mul_done")
    asm.andi("t2", "a1", 1)
    asm.beq("t2", "zero", "mul_skip")
    asm.add("t1", "t1", "a0")
    asm.label("mul_skip")
    asm.slli("a0", "a0", 1)
    asm.srli("a1", "a1", 1)
    asm.j("mul_loop")
    asm.label("mul_done")
    asm.mv("a0", "t1")
    asm.ret()
    return asm


@cocotb.test()
async def factorial(dut):
    """Factorial recursivo de 0 a 13 con pila, llamadas y multiplicación por software."""
    asm = build_factorial()
    model, _ = await run_program(dut, asm)
    writes = model.dmem_writes
    memory = dict(writes)  # última escritura en cada dirección

    # Resultado funcional contra Python puro (independiente del ISS)
    for n in range(FACT_N_MAX + 1):
        address = FACT_RESULTS + 4 * n
        expected = math.factorial(n) & MASK32
        actual = memory.get(address)
        assert actual == expected, (
            f"fact({n}) en 0x{address:03x}: esperado {expected} (0x{expected:08x}), obtuvo {actual}"
        )

    # La pila debe quedar balanceada
    assert memory[FACT_SP_REPORT] == FACT_STACK_TOP, (
        f"sp final 0x{memory[FACT_SP_REPORT]:08x}, esperado 0x{FACT_STACK_TOP:08x}"
    )

    # Profundidad máxima de recursión: fact(13) abre 13 marcos de 8 bytes
    stack_writes = [(a, d) for a, d in writes if a < FACT_STACK_TOP and a >= FACT_STACK_TOP - 0x200]
    deepest = min(a for a, _ in stack_writes)
    assert deepest == FACT_STACK_TOP - 8 * FACT_N_MAX, f"marco más profundo en 0x{deepest:08x}"

    # Cada ra guardado en la pila debe ser una dirección de retorno válida (verifica jal rd=ra)
    valid_returns = {asm.address_of("ret_main"), asm.address_of("ret_fact")}
    saved_ras = [d for a, d in stack_writes if (FACT_STACK_TOP - a) % 8 == 4]
    assert saved_ras and set(saved_ras) <= valid_returns, (
        f"direcciones de retorno inválidas en la pila: {sorted(set(saved_ras) - valid_returns)}"
    )
    calls = Counter(saved_ras)
    dut._log.info(
        "Llamadas a fact desde main: %d, recursivas: %d",
        calls[asm.address_of("ret_main")], calls[asm.address_of("ret_fact")],
    )
    dut._log.info("Resultados: %s", [memory[FACT_RESULTS + 4 * n] for n in range(FACT_N_MAX + 1)])
