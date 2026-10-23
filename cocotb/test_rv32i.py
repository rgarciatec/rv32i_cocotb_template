"""Cocotb tests for the RV32I arithmetic, control-flow, and word-memory subset."""

from dataclasses import dataclass
from typing import Callable

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

from rv32i_coverage import sample_instruction
from rv32i_test_config import selected_tests


BUS_LATENCY = 3
MAX_CYCLES = 300
MASK32 = 0xFFFF_FFFF
RESULT_ADDRESS = 0x100


@dataclass(frozen=True)
class Case:
    name: str
    group: str
    operation: str


CASES = (
    Case("add", "alu", "add"),
    Case("sub", "alu", "sub"),
    Case("and", "alu", "and"),
    Case("or", "alu", "or"),
    Case("xor", "alu", "xor"),
    Case("sll", "alu", "sll"),
    Case("srl", "alu", "srl"),
    Case("sra", "alu", "sra"),
    Case("slt", "alu", "slt"),
    Case("sltu", "alu", "sltu"),
    Case("addi", "alu", "addi"),
    Case("andi", "alu", "andi"),
    Case("ori", "alu", "ori"),
    Case("xori", "alu", "xori"),
    Case("slli", "alu", "slli"),
    Case("srli", "alu", "srli"),
    Case("srai", "alu", "srai"),
    Case("slti", "alu", "slti"),
    Case("sltiu", "alu", "sltiu"),
    Case("beq", "branch", "beq"),
    Case("bne", "branch", "bne"),
    Case("blt", "branch", "blt"),
    Case("bge", "branch", "bge"),
    Case("jal", "jump", "jal"),
    Case("jalr", "jump", "jalr"),
    Case("lui", "upper", "lui"),
    Case("lw", "memory", "lw"),
    Case("sw", "memory", "sw"),
    Case("illegal", "invalid", "illegal"),
)
SELECTED_TESTS = set(selected_tests())


def u32(value: int) -> int:
    return value & MASK32


def encode_i(imm: int, rs1: int, funct3: int, rd: int, opcode: int = 0x13) -> int:
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def encode_r(funct7: int, rs2: int, rs1: int, funct3: int, rd: int) -> int:
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0x33


def encode_s(imm: int, rs2: int, rs1: int, funct3: int = 2) -> int:
    immediate = imm & 0xFFF
    return (
        ((immediate >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | ((immediate & 0x1F) << 7)
        | 0x23
    )


def encode_b(imm: int, rs2: int, rs1: int, funct3: int) -> int:
    immediate = imm & 0x1FFF
    return (
        (((immediate >> 12) & 1) << 31)
        | (((immediate >> 5) & 0x3F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (((immediate >> 1) & 0xF) << 8)
        | (((immediate >> 11) & 1) << 7)
        | 0x63
    )


def encode_j(imm: int, rd: int) -> int:
    immediate = imm & 0x1F_FFFF
    return (
        (((immediate >> 20) & 1) << 31)
        | (((immediate >> 1) & 0x3FF) << 21)
        | (((immediate >> 11) & 1) << 20)
        | (((immediate >> 12) & 0xFF) << 12)
        | (rd << 7)
        | 0x6F
    )


def addi(rd: int, rs1: int, immediate: int) -> int:
    return encode_i(immediate, rs1, 0, rd)


def program_map(words: list[int]) -> dict[int, int]:
    return {4 * index: word for index, word in enumerate(words)}


def make_alu_program(operation: str) -> tuple[dict[int, int], int]:
    lhs, rhs = -173, 45
    words: list[int] = [addi(1, 0, lhs)]
    r_funct = {
        "add": (0, 0),
        "sub": (0, 0x20),
        "sll": (1, 0),
        "slt": (2, 0),
        "sltu": (3, 0),
        "xor": (4, 0),
        "srl": (5, 0),
        "sra": (5, 0x20),
        "or": (6, 0),
        "and": (7, 0),
    }
    i_funct = {
        "addi": 0,
        "slli": 1,
        "slti": 2,
        "sltiu": 3,
        "xori": 4,
        "srli": 5,
        "srai": 5,
        "ori": 6,
        "andi": 7,
    }
    immediate = operation in i_funct
    if not immediate:
        words.append(addi(2, 0, rhs))

    if immediate:
        right = 13 if operation in ("slli", "srli", "srai") else rhs
        encoded_imm = (((0x20 if operation == "srai" else 0) << 5) | right) if operation in (
            "slli", "srli", "srai"
        ) else right
        words.append(encode_i(encoded_imm, 1, i_funct[operation], 3))
    else:
        right = rhs
        funct3, funct7 = r_funct[operation]
        words.append(encode_r(funct7, 2, 1, funct3, 3))
    words.append(encode_s(0x100, 3, 0))

    unsigned_lhs, unsigned_rhs = u32(lhs), u32(right)
    if operation in ("add", "addi"):
        expected = lhs + right
    elif operation == "sub":
        expected = lhs - right
    elif operation in ("and", "andi"):
        expected = unsigned_lhs & unsigned_rhs
    elif operation in ("or", "ori"):
        expected = unsigned_lhs | unsigned_rhs
    elif operation in ("xor", "xori"):
        expected = unsigned_lhs ^ unsigned_rhs
    elif operation in ("sll", "slli"):
        expected = unsigned_lhs << (right & 0x1F)
    elif operation in ("srl", "srli"):
        expected = unsigned_lhs >> (right & 0x1F)
    elif operation in ("sra", "srai"):
        expected = lhs >> (right & 0x1F)
    elif operation in ("slt", "slti"):
        expected = int(lhs < right)
    else:
        expected = int(unsigned_lhs < unsigned_rhs)
    return program_map(words), u32(expected)


class BusModel:
    def __init__(self, program: dict[int, int], data: dict[int, int] | None = None):
        self.program = program
        self.data = data or {}
        self.imem_fetches: list[int] = []
        self.dmem_reads: list[int] = []
        self.dmem_writes: list[tuple[int, int]] = []

    async def run_imem(self, dut) -> None:
        pending = None
        remaining = 0
        while True:
            await FallingEdge(dut.clk)
            dut.imem_ready.value = 0

            if pending is None and int(dut.imem_valid.value):
                address = int(dut.imem_addr.value)
                pending = address
                remaining = BUS_LATENCY
                self.imem_fetches.append(address)

            if pending is not None:
                remaining -= 1
                if remaining == 0:
                    dut.imem_rdata.value = self.program.get(pending, 0)
                    dut.imem_ready.value = 1
                    await RisingEdge(dut.clk)
                    dut.imem_ready.value = 0
                    pending = None

    async def run_dmem(self, dut) -> None:
        pending = None
        remaining = 0
        while True:
            await FallingEdge(dut.clk)
            dut.dmem_ready.value = 0

            if pending is None and int(dut.dmem_valid.value):
                address = int(dut.dmem_addr.value)
                write = int(dut.dmem_we.value)
                write_data = int(dut.dmem_wdata.value)
                pending = (address, write, write_data)
                remaining = BUS_LATENCY
                if not write:
                    self.dmem_reads.append(address)

            if pending is not None:
                remaining -= 1
                if remaining == 0:
                    address, write, write_data = pending
                    if write:
                        self.dmem_writes.append((address, write_data))
                        self.data[address] = write_data
                    dut.dmem_rdata.value = 0 if write else self.data.get(address, 0)
                    dut.dmem_ready.value = 1
                    await RisingEdge(dut.clk)
                    dut.dmem_ready.value = 0
                    pending = None

    async def run(self, dut) -> None:
        cocotb.start_soon(self.run_imem(dut))
        cocotb.start_soon(self.run_dmem(dut))


async def start_cpu(dut, model: BusModel) -> None:
    dut.imem_ready.value = 0
    dut.imem_rdata.value = 0
    dut.dmem_ready.value = 0
    dut.dmem_rdata.value = 0
    dut.reset.value = 1
    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.reset.value = 0
    await RisingEdge(dut.clk)
    cocotb.start_soon(model.run(dut))


async def wait_for(dut, model: BusModel, predicate: Callable[[], bool], message: str) -> None:
    for _ in range(MAX_CYCLES):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if predicate():
            return
    raise AssertionError(f"Timed out after {MAX_CYCLES} cycles: {message}")


async def check_store(dut, program: dict[int, int], data=None) -> tuple[int, int]:
    model = BusModel(program, data)
    await start_cpu(dut, model)
    await wait_for(
        dut,
        model,
        lambda: any(address == RESULT_ADDRESS for address, _ in model.dmem_writes),
        f"CPU did not write the result to 0x{RESULT_ADDRESS:08x}",
    )
    return next(pair for pair in model.dmem_writes if pair[0] == RESULT_ADDRESS)


async def test_alu(dut, operation: str) -> None:
    program, expected = make_alu_program(operation)
    address, actual = await check_store(dut, program)
    assert address == RESULT_ADDRESS
    assert actual == expected, (
        f"FAIL: {operation.upper()} expected 0x{expected:08x}, got 0x{actual:08x}"
    )


async def test_branch(dut, operation: str) -> None:
    lhs, rhs = -7, 4
    condition = {
        "beq": lhs == rhs,
        "bne": lhs != rhs,
        "blt": lhs < rhs,
        "bge": lhs >= rhs,
    }[operation]
    funct3 = {"beq": 0, "bne": 1, "blt": 4, "bge": 5}[operation]
    words = [
        addi(1, 0, lhs),
        addi(2, 0, rhs),
        encode_b(8, 2, 1, funct3),
        addi(3, 0, 99),
        addi(3, 0, 11),
    ]
    model = BusModel(program_map(words))
    await start_cpu(dut, model)
    branch_pc = 8
    expected_pc = branch_pc + (8 if condition else 4)
    await wait_for(
        dut,
        model,
        lambda: model.imem_fetches.count(expected_pc) > 0,
        f"{operation.upper()} did not fetch expected PC 0x{expected_pc:08x}",
    )
    assert expected_pc in model.imem_fetches


async def test_jump(dut, operation: str) -> None:
    words = [addi(1, 0, 0x21), addi(2, 0, 7)]
    if operation == "jal":
        words.append(encode_j(12, 3))
        expected_pc = 20
    else:
        words.append(encode_i(0, 1, 0, 3, opcode=0x67))
        expected_pc = 0x20
    model = BusModel(program_map(words))
    await start_cpu(dut, model)
    await wait_for(
        dut,
        model,
        lambda: expected_pc in model.imem_fetches,
        f"{operation.upper()} did not fetch expected PC 0x{expected_pc:08x}",
    )


async def run_lui(dut) -> None:
    value = 0xABCDE000
    program = program_map([((0xABCDE << 12) | (3 << 7) | 0x37), encode_s(0x100, 3, 0)])
    address, actual = await check_store(dut, program)
    assert address == RESULT_ADDRESS
    assert actual == value, f"FAIL: LUI expected 0x{value:08x}, got 0x{actual:08x}"


async def run_lw(dut) -> None:
    expected = 0x89AB_CDEF
    words = [addi(1, 0, 0x180), encode_i(12, 1, 2, 3, opcode=0x03), encode_s(0x100, 3, 0)]
    address, actual = await check_store(dut, program_map(words), {0x18C: expected})
    assert address == RESULT_ADDRESS
    assert actual == expected, f"FAIL: LW expected 0x{expected:08x}, got 0x{actual:08x}"


async def run_sw(dut) -> None:
    expected = 0x5A3
    words = [addi(1, 0, 0x188), addi(2, 0, expected), encode_s(12, 2, 1)]
    model = BusModel(program_map(words))
    await start_cpu(dut, model)
    await wait_for(
        dut,
        model,
        lambda: (0x194, expected) in model.dmem_writes,
        "SW did not write the expected address and data",
    )


async def run_illegal(dut) -> None:
    model = BusModel(program_map([0x0000_0000]))
    await start_cpu(dut, model)
    await wait_for(
        dut,
        model,
        lambda: int(dut.illegal_instruction.value) == 1,
        "CPU did not assert illegal_instruction for an unsupported encoding",
    )
    assert not model.dmem_writes, "Illegal instruction caused a memory write"


async def run_case(dut, case: Case) -> None:
    if case.group == "alu":
        await test_alu(dut, case.operation)
        return
    if case.group == "branch":
        await test_branch(dut, case.operation)
        return
    if case.group == "jump":
        await test_jump(dut, case.operation)
        return
    if case.operation == "lui":
        await run_lui(dut)
        return
    if case.operation == "lw":
        await run_lw(dut)
        return
    if case.operation == "illegal":
        await run_illegal(dut)
        return
    await run_sw(dut)


def register_tests() -> None:
    for case in CASES:
        if case.name not in SELECTED_TESTS:
            continue

        async def test(dut, selected_case=case):
            await run_case(dut, selected_case)
            sample_instruction(selected_case.name)

        test.__name__ = f"test_{case.name}"
        globals()[test.__name__] = cocotb.test(name=case.name)(test)


register_tests()
