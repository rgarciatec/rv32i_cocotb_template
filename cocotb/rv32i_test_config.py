import os


ALL_INSTRUCTIONS = (
    "add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu",
    "addi", "andi", "ori", "xori", "slli", "srli", "srai", "slti", "sltiu",
    "beq", "bne", "blt", "bge", "jal", "jalr", "lui", "lw", "sw", "illegal",
)

INSTRUCTION_GROUPS = {
    "alu": ALL_INSTRUCTIONS[:19],
    "branch": ALL_INSTRUCTIONS[19:23],
    "jump": ALL_INSTRUCTIONS[23:25],
    "upper": ("lui",),
    "memory": ("lw", "sw"),
    "invalid": ("illegal",),
}


def _selected_names() -> tuple[str, ...]:
    requested = os.environ.get("RV32I_INSTRUCTIONS", "all").strip().lower()
    if requested == "all":
        return ALL_INSTRUCTIONS

    selected = []
    for name in requested.split(","):
        name = name.strip()
        if name in INSTRUCTION_GROUPS:
            selected.extend(INSTRUCTION_GROUPS[name])
        elif name in ALL_INSTRUCTIONS:
            selected.append(name)
        else:
            valid = ", ".join((*ALL_INSTRUCTIONS, *INSTRUCTION_GROUPS))
            raise ValueError(f"Unknown instruction/group '{name}'. Choose from: {valid}")

    if not selected:
        raise ValueError("RV32I_INSTRUCTIONS must select at least one instruction or group")

    return tuple(name for name in ALL_INSTRUCTIONS if name in selected)


def selected_instructions() -> tuple[str, ...]:
    selected = set(_selected_names())
    return tuple(name for name in ALL_INSTRUCTIONS if name in selected)


def selected_tests() -> tuple[str, ...]:
    return _selected_names()
