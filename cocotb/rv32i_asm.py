"""Mini ensamblador RV32I + simulador de referencia (ISS) para las pruebas de programa.

Soporta exactamente el subconjunto que implementa el CPU del repo (28 instrucciones):
    R:  add sub and or xor sll srl sra slt sltu
    I:  addi andi ori xori slli srli srai slti sltiu  lw  jalr
    S:  sw        B: beq bne blt bge        J: jal        U: lui
Pseudo-instrucciones: li, mv, j, ret, nop.

Uso típico:
    asm = Assembler()
    asm.li("a0", 5)
    asm.label("loop")
    asm.addi("a0", "a0", -1)
    asm.bne("a0", "zero", "loop")
    program = asm.assemble()          # {dirección: palabra de 32 bits}

    iss = ReferenceModel(program)
    iss.run(stop=lambda m: ...)       # ejecuta el mismo programa en Python
    iss.dmem_writes                   # traza esperada de escrituras a memoria

El ISS es una implementación independiente del ISA (no comparte código con el
CPU en SystemVerilog ni con los codificadores de test_rv32i.py), así que sirve
como "golden model" para comparar contra lo que hace el hardware.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

MASK32 = 0xFFFF_FFFF

# ---------------------------------------------------------------------------
# Registros (nombres ABI y xN)
# ---------------------------------------------------------------------------
ABI_NAMES = (
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
)
REGISTERS = {name: index for index, name in enumerate(ABI_NAMES)}
REGISTERS.update({f"x{index}": index for index in range(32)})
REGISTERS["fp"] = 8


def reg(name: str | int) -> int:
    if isinstance(name, int):
        if 0 <= name < 32:
            return name
    elif name in REGISTERS:
        return REGISTERS[name]
    raise ValueError(f"Registro inválido: {name!r}")


def to_signed(value: int) -> int:
    value &= MASK32
    return value - (1 << 32) if value & 0x8000_0000 else value


def sign_extend(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


# ---------------------------------------------------------------------------
# Tablas de codificación
# ---------------------------------------------------------------------------
OP_LOAD, OP_IMM, OP_STORE, OP_REG = 0x03, 0x13, 0x23, 0x33
OP_LUI, OP_BRANCH, OP_JALR, OP_JAL = 0x37, 0x63, 0x67, 0x6F

R_TYPE = {  # mnemónico: (funct3, funct7)
    "add": (0, 0x00), "sub": (0, 0x20), "sll": (1, 0x00), "slt": (2, 0x00),
    "sltu": (3, 0x00), "xor": (4, 0x00), "srl": (5, 0x00), "sra": (5, 0x20),
    "or": (6, 0x00), "and": (7, 0x00),
}
I_ALU = {"addi": 0, "slti": 2, "sltiu": 3, "xori": 4, "ori": 6, "andi": 7}
I_SHIFT = {"slli": (1, 0x00), "srli": (5, 0x00), "srai": (5, 0x20)}
BRANCH = {"beq": 0, "bne": 1, "blt": 4, "bge": 5}

SUPPORTED = (
    "add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu",
    "addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu",
    "beq", "bne", "blt", "bge", "jal", "jalr", "lui", "lw", "sw",
)


def _check_range(value: int, bits: int, signed: bool, what: str) -> None:
    low, high = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    if not low <= value <= high:
        raise ValueError(f"{what}={value} fuera de rango [{low}, {high}]")


def _r(funct7, rs2, rs1, funct3, rd):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | OP_REG


def _i(imm, rs1, funct3, rd, opcode):
    _check_range(imm, 12, True, "inmediato I")
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def _s(imm, rs2, rs1, funct3):
    _check_range(imm, 12, True, "inmediato S")
    imm &= 0xFFF
    return ((imm >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | ((imm & 0x1F) << 7) | OP_STORE


def _b(offset, rs2, rs1, funct3):
    _check_range(offset, 13, True, "offset de branch")
    if offset & 1:
        raise ValueError(f"offset de branch impar: {offset}")
    imm = offset & 0x1FFF
    return (
        (((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20) | (rs1 << 15)
        | (funct3 << 12) | (((imm >> 1) & 0xF) << 8) | (((imm >> 11) & 1) << 7) | OP_BRANCH
    )


def _j(offset, rd):
    _check_range(offset, 21, True, "offset de jal")
    if offset & 1:
        raise ValueError(f"offset de jal impar: {offset}")
    imm = offset & 0x1F_FFFF
    return (
        (((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21) | (((imm >> 11) & 1) << 20)
        | (((imm >> 12) & 0xFF) << 12) | (rd << 7) | OP_JAL
    )


# ---------------------------------------------------------------------------
# Ensamblador con etiquetas
# ---------------------------------------------------------------------------
@dataclass
class _Line:
    mnemonic: str
    operands: tuple
    address: int


class Assembler:
    """Ensamblador de dos pasadas. Cada método agrega una instrucción."""

    def __init__(self, base_address: int = 0):
        self.base = base_address
        self.lines: list[_Line] = []
        self.labels: dict[str, int] = {}

    # --- utilidades -------------------------------------------------------
    @property
    def pc(self) -> int:
        return self.base + 4 * len(self.lines)

    def label(self, name: str) -> None:
        if name in self.labels:
            raise ValueError(f"Etiqueta duplicada: {name}")
        self.labels[name] = self.pc

    def address_of(self, name: str) -> int:
        return self.labels[name]

    def _emit(self, mnemonic: str, *operands) -> None:
        self.lines.append(_Line(mnemonic, operands, self.pc))

    def __getattr__(self, mnemonic: str):
        # Permite escribir asm.add("t0", "t1", "t2"), asm.and_(...), asm.or_(...)
        name = mnemonic.rstrip("_")
        if name in SUPPORTED:
            return lambda *operands: self._emit(name, *operands)
        raise AttributeError(mnemonic)

    # --- pseudo-instrucciones ---------------------------------------------
    def li(self, rd, value: int) -> None:
        """Carga una constante de 32 bits (1 o 2 instrucciones)."""
        value = to_signed(value)
        if -2048 <= value <= 2047:
            self._emit("addi", rd, "zero", value)
            return
        low = sign_extend(value, 12)
        high = ((value - low) >> 12) & 0xFFFFF
        self._emit("lui", rd, high)
        if low:
            self._emit("addi", rd, rd, low)

    def mv(self, rd, rs) -> None:
        self._emit("addi", rd, rs, 0)

    def j(self, target: str) -> None:
        self._emit("jal", "zero", target)

    def ret(self) -> None:
        self._emit("jalr", "zero", "ra", 0)

    def nop(self) -> None:
        self._emit("addi", "zero", "zero", 0)

    # --- segunda pasada -----------------------------------------------------
    def _target(self, target, pc: int) -> int:
        if isinstance(target, str):
            if target not in self.labels:
                raise ValueError(f"Etiqueta no definida: {target}")
            return self.labels[target] - pc
        return target

    def _encode(self, line: _Line) -> int:
        m, ops, pc = line.mnemonic, line.operands, line.address
        if m in R_TYPE:
            funct3, funct7 = R_TYPE[m]
            rd, rs1, rs2 = ops
            return _r(funct7, reg(rs2), reg(rs1), funct3, reg(rd))
        if m in I_ALU:
            rd, rs1, imm = ops
            return _i(imm, reg(rs1), I_ALU[m], reg(rd), OP_IMM)
        if m in I_SHIFT:
            funct3, funct7 = I_SHIFT[m]
            rd, rs1, shamt = ops
            _check_range(shamt, 5, False, "shamt")
            return _i((funct7 << 5) | shamt, reg(rs1), funct3, reg(rd), OP_IMM)
        if m == "lw":          # lw rd, offset, rs1   ==  lw rd, offset(rs1)
            rd, offset, rs1 = ops
            return _i(offset, reg(rs1), 2, reg(rd), OP_LOAD)
        if m == "sw":          # sw rs2, offset, rs1  ==  sw rs2, offset(rs1)
            rs2, offset, rs1 = ops
            return _s(offset, reg(rs2), reg(rs1), 2)
        if m in BRANCH:
            rs1, rs2, target = ops
            return _b(self._target(target, pc), reg(rs2), reg(rs1), BRANCH[m])
        if m == "jal":
            rd, target = ops
            return _j(self._target(target, pc), reg(rd))
        if m == "jalr":
            rd, rs1, imm = ops
            return _i(imm, reg(rs1), 0, reg(rd), OP_JALR)
        if m == "lui":
            rd, imm20 = ops
            _check_range(imm20, 20, False, "inmediato U")
            return (imm20 << 12) | (reg(rd) << 7) | OP_LUI
        raise ValueError(f"Instrucción no soportada: {m}")

    def assemble(self) -> dict[int, int]:
        program = {}
        for line in self.lines:
            try:
                program[line.address] = self._encode(line)
            except ValueError as error:
                raise ValueError(f"0x{line.address:04x}: {line.mnemonic} {line.operands}: {error}") from None
        return program

    def listing(self) -> str:
        """Listado legible (dirección, palabra, instrucción) para depurar."""
        program = self.assemble()
        names = {address: name for name, address in self.labels.items()}
        out = []
        for line in self.lines:
            if line.address in names:
                out.append(f"{names[line.address]}:")
            ops = ", ".join(str(op) for op in line.operands)
            out.append(f"  {line.address:04x}: {program[line.address]:08x}  {line.mnemonic} {ops}")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Decodificador + simulador de referencia (golden model)
# ---------------------------------------------------------------------------
def decode_mnemonic(word: int) -> str:
    """Devuelve el mnemónico de una palabra, o 'illegal' si no está soportada."""
    opcode, funct3, funct7 = word & 0x7F, (word >> 12) & 7, word >> 25
    if opcode == OP_REG:
        for name, (f3, f7) in R_TYPE.items():
            if (f3, f7) == (funct3, funct7):
                return name
    elif opcode == OP_IMM:
        for name, f3 in I_ALU.items():
            if f3 == funct3:
                return name
        for name, (f3, f7) in I_SHIFT.items():
            if (f3, f7) == (funct3, funct7):
                return name
    elif opcode == OP_LOAD and funct3 == 2:
        return "lw"
    elif opcode == OP_STORE and funct3 == 2:
        return "sw"
    elif opcode == OP_BRANCH:
        for name, f3 in BRANCH.items():
            if f3 == funct3:
                return name
    elif opcode == OP_JALR and funct3 == 0:
        return "jalr"
    elif opcode == OP_JAL:
        return "jal"
    elif opcode == OP_LUI:
        return "lui"
    return "illegal"


@dataclass
class ReferenceModel:
    """Simulador de conjunto de instrucciones RV32I (subconjunto del repo)."""

    program: dict[int, int]
    data: dict[int, int] = field(default_factory=dict)
    pc: int = 0
    regs: list[int] = field(default_factory=lambda: [0] * 32)
    dmem_writes: list[tuple[int, int]] = field(default_factory=list)
    dmem_reads: list[int] = field(default_factory=list)
    executed: Counter = field(default_factory=Counter)
    branches: Counter = field(default_factory=Counter)  # (mnemónico, tomado?) -> veces
    steps: int = 0

    def __post_init__(self):
        self.data = dict(self.data)

    def step(self) -> None:
        pc, word = self.pc, self.program.get(self.pc, 0)
        name = decode_mnemonic(word)
        if name == "illegal":
            raise RuntimeError(f"ISS: instrucción ilegal 0x{word:08x} en PC=0x{pc:08x}")

        rd, rs1, rs2 = (word >> 7) & 0x1F, (word >> 15) & 0x1F, (word >> 20) & 0x1F
        a, b = self.regs[rs1], self.regs[rs2]
        imm_i = sign_extend(word >> 20, 12)
        imm_s = sign_extend(((word >> 25) << 5) | ((word >> 7) & 0x1F), 12)
        imm_b = sign_extend(
            (((word >> 31) & 1) << 12) | (((word >> 7) & 1) << 11)
            | (((word >> 25) & 0x3F) << 5) | (((word >> 8) & 0xF) << 1), 13)
        imm_j = sign_extend(
            (((word >> 31) & 1) << 20) | (((word >> 12) & 0xFF) << 12)
            | (((word >> 20) & 1) << 11) | (((word >> 21) & 0x3FF) << 1), 21)
        shamt_r, shamt_i = b & 0x1F, (word >> 20) & 0x1F

        next_pc, result = pc + 4, None
        alu = {
            "add": lambda: a + b, "sub": lambda: a - b, "and": lambda: a & b,
            "or": lambda: a | b, "xor": lambda: a ^ b, "sll": lambda: a << shamt_r,
            "srl": lambda: a >> shamt_r, "sra": lambda: to_signed(a) >> shamt_r,
            "slt": lambda: int(to_signed(a) < to_signed(b)), "sltu": lambda: int(a < b),
            "addi": lambda: a + imm_i, "andi": lambda: a & (imm_i & MASK32),
            "ori": lambda: a | (imm_i & MASK32), "xori": lambda: a ^ (imm_i & MASK32),
            "slli": lambda: a << shamt_i, "srli": lambda: a >> shamt_i,
            "srai": lambda: to_signed(a) >> shamt_i,
            "slti": lambda: int(to_signed(a) < imm_i),
            "sltiu": lambda: int(a < (imm_i & MASK32)),
            "lui": lambda: word & 0xFFFFF000,
        }
        if name in alu:
            result = alu[name]()
        elif name in BRANCH:
            taken = {
                "beq": a == b, "bne": a != b,
                "blt": to_signed(a) < to_signed(b), "bge": to_signed(a) >= to_signed(b),
            }[name]
            self.branches[(name, taken)] += 1
            if taken:
                next_pc = pc + imm_b
        elif name == "jal":
            result, next_pc = pc + 4, pc + imm_j
        elif name == "jalr":
            result, next_pc = pc + 4, (a + imm_i) & ~1
        elif name == "lw":
            address = (a + imm_i) & MASK32
            if address & 3:
                raise RuntimeError(f"ISS: lw desalineado a 0x{address:08x} en PC=0x{pc:08x}")
            self.dmem_reads.append(address)
            result = self.data.get(address, 0)
        elif name == "sw":
            address = (a + imm_s) & MASK32
            if address & 3:
                raise RuntimeError(f"ISS: sw desalineado a 0x{address:08x} en PC=0x{pc:08x}")
            self.data[address] = b
            self.dmem_writes.append((address, b))

        if result is not None and rd != 0:
            self.regs[rd] = result & MASK32
        self.pc = next_pc & MASK32
        self.executed[name] += 1
        self.steps += 1

    def run(self, stop: Callable[["ReferenceModel"], bool], max_steps: int = 1_000_000) -> None:
        while not stop(self):
            if self.steps >= max_steps:
                raise RuntimeError(f"ISS: el programa no terminó en {max_steps} instrucciones")
            self.step()
