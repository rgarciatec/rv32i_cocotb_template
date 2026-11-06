"""Mini ensamblador RV32I con etiquetas.

Reutiliza los codificadores de test_rv32i.py; solo agrega nombres de registros
y etiquetas para no calcular a mano los offsets de los saltos.

    asm = Assembler()
    asm.li("t0", 5)
    asm.label("loop")
    asm.addi("t0", "t0", -1)
    asm.bne("t0", "zero", "loop")
    program = asm.assemble()      # {dirección: instrucción de 32 bits}
"""

from test_rv32i import encode_b, encode_i, encode_j, encode_r, encode_s

ABI = ("zero ra sp gp tp t0 t1 t2 s0 s1 a0 a1 a2 a3 a4 a5 "
       "a6 a7 s2 s3 s4 s5 s6 s7 s8 s9 s10 s11 t3 t4 t5 t6").split()
REG = {name: i for i, name in enumerate(ABI)} | {f"x{i}": i for i in range(32)}

R_TYPE = {"add": (0, 0), "sub": (0, 0x20), "sll": (1, 0), "slt": (2, 0), "sltu": (3, 0),
          "xor": (4, 0), "srl": (5, 0), "sra": (5, 0x20), "or": (6, 0), "and": (7, 0)}
I_TYPE = {"addi": 0, "slti": 2, "sltiu": 3, "xori": 4, "ori": 6, "andi": 7}
SHIFTS = {"slli": (1, 0), "srli": (5, 0), "srai": (5, 0x20)}
BRANCH = {"beq": 0, "bne": 1, "blt": 4, "bge": 5}


class Assembler:
    def __init__(self):
        self.lines = []    # (mnemónico, operandos, dirección)
        self.labels = {}

    def label(self, name):
        self.labels[name] = 4 * len(self.lines)

    def __getattr__(self, mnemonic):
        # asm.add(...), asm.lw(...), etc.  (and/or se escriben and_ / or_)
        return lambda *ops: self.lines.append((mnemonic.rstrip("_"), ops, 4 * len(self.lines)))

    # Pseudo-instrucciones
    def li(self, rd, value):
        if -2048 <= value <= 2047:
            self.addi(rd, "zero", value)
        else:
            low = ((value & 0xFFF) ^ 0x800) - 0x800          # 12 bits bajos con signo
            self.lui(rd, ((value - low) >> 12) & 0xFFFFF)
            if low:
                self.addi(rd, rd, low)

    def mv(self, rd, rs):
        self.addi(rd, rs, 0)

    def j(self, target):
        self.jal("zero", target)

    def ret(self):
        self.jalr("zero", "ra", 0)

    def _encode(self, m, ops, pc):
        r = lambda name: REG[name]
        offset = lambda target: self.labels[target] - pc
        if m in R_TYPE:
            rd, rs1, rs2 = ops
            return encode_r(R_TYPE[m][1], r(rs2), r(rs1), R_TYPE[m][0], r(rd))
        if m in I_TYPE:
            rd, rs1, imm = ops
            return encode_i(imm, r(rs1), I_TYPE[m], r(rd))
        if m in SHIFTS:
            rd, rs1, shamt = ops
            return encode_i((SHIFTS[m][1] << 5) | shamt, r(rs1), SHIFTS[m][0], r(rd))
        if m == "lw":                       # lw rd, offset, rs1   ->  lw rd, offset(rs1)
            rd, imm, rs1 = ops
            return encode_i(imm, r(rs1), 2, r(rd), opcode=0x03)
        if m == "sw":                       # sw rs2, offset, rs1  ->  sw rs2, offset(rs1)
            rs2, imm, rs1 = ops
            return encode_s(imm, r(rs2), r(rs1))
        if m in BRANCH:
            rs1, rs2, target = ops
            return encode_b(offset(target), r(rs2), r(rs1), BRANCH[m])
        if m == "jal":
            rd, target = ops
            return encode_j(offset(target), r(rd))
        if m == "jalr":
            rd, rs1, imm = ops
            return encode_i(imm, r(rs1), 0, r(rd), opcode=0x67)
        if m == "lui":
            rd, imm20 = ops
            return (imm20 << 12) | (r(rd) << 7) | 0x37
        raise ValueError(f"Instrucción no soportada: {m}")

    def assemble(self):
        return {pc: self._encode(m, ops, pc) for m, ops, pc in self.lines}