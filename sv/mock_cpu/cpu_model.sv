class cpu_model;

    typedef rv32i_instruction::instruction_id_t instruction_id_t;
    typedef logic [9:0] opcode_funct3_key_t;
    typedef logic [16:0] instruction_key_t;

    instruction_id_t opcode_funct3_lookup[opcode_funct3_key_t];
    instruction_id_t instruction_lookup[instruction_key_t];
    instruction_id_t opcode_lookup[rv32i_instruction::opcode_t];

    function new();
        instruction_lookup = '{
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_ADD_SUB, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_ADD,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_ADD_SUB, rv32i_instruction::FUNCT7_ALT}: rv32i_instruction::INSN_SUB,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_SLL, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_SLL,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_SLT, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_SLT,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_SLTU, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_SLTU,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_XOR, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_XOR,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_SHIFT, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_SRL,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_SHIFT, rv32i_instruction::FUNCT7_ALT}: rv32i_instruction::INSN_SRA,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_OR, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_OR,
            {rv32i_instruction::OPCODE_REGISTER, rv32i_instruction::FUNCT3_AND, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_AND,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_SLL, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_SLLI,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_SHIFT, rv32i_instruction::FUNCT7_BASE}: rv32i_instruction::INSN_SRLI,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_SHIFT, rv32i_instruction::FUNCT7_ALT}: rv32i_instruction::INSN_SRAI
        };
        opcode_funct3_lookup = '{
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_ADD_SUB}: rv32i_instruction::INSN_ADDI,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_SLT}: rv32i_instruction::INSN_SLTI,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_SLTU}: rv32i_instruction::INSN_SLTIU,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_XOR}: rv32i_instruction::INSN_XORI,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_OR}: rv32i_instruction::INSN_ORI,
            {rv32i_instruction::OPCODE_IMMEDIATE, rv32i_instruction::FUNCT3_AND}: rv32i_instruction::INSN_ANDI,
            {rv32i_instruction::OPCODE_BRANCH, rv32i_instruction::FUNCT3_ADD_SUB}: rv32i_instruction::INSN_BEQ,
            {rv32i_instruction::OPCODE_BRANCH, rv32i_instruction::FUNCT3_SLL}: rv32i_instruction::INSN_BNE,
            {rv32i_instruction::OPCODE_BRANCH, rv32i_instruction::FUNCT3_XOR}: rv32i_instruction::INSN_BLT,
            {rv32i_instruction::OPCODE_BRANCH, rv32i_instruction::FUNCT3_SHIFT}: rv32i_instruction::INSN_BGE,
            {rv32i_instruction::OPCODE_LOAD, rv32i_instruction::LOAD_FUNCT3_WORD}: rv32i_instruction::INSN_LW,
            {rv32i_instruction::OPCODE_STORE, rv32i_instruction::STORE_FUNCT3_WORD}: rv32i_instruction::INSN_SW,
            {rv32i_instruction::OPCODE_JALR, rv32i_instruction::FUNCT3_ADD_SUB}: rv32i_instruction::INSN_JALR
        };
        opcode_lookup = '{
            rv32i_instruction::OPCODE_JAL: rv32i_instruction::INSN_JAL,
            rv32i_instruction::OPCODE_LUI: rv32i_instruction::INSN_LUI
        };
    endfunction

    virtual function instruction_id_t decode_type(input logic [31:0] instruction_word);
        rv32i_instruction::opcode_t opcode;
        rv32i_instruction::funct3_t funct3;
        instruction_id_t instruction_type;
        opcode_funct3_key_t key;
        instruction_key_t instruction_key;

        opcode = rv32i_instruction::opcode_t'(instruction_word[6:0]);
        funct3 = rv32i_instruction::funct3_t'(instruction_word[14:12]);
        instruction_key = {opcode, funct3, instruction_word[31:25]};
        instruction_type = rv32i_instruction::INSN_INVALID;

        if (instruction_lookup.exists(instruction_key)) begin
            instruction_type = instruction_lookup[instruction_key];
        end else begin
            key = {opcode, funct3};
            if (opcode_funct3_lookup.exists(key)) begin
                instruction_type = opcode_funct3_lookup[key];
            end else begin
                if (opcode_lookup.exists(opcode)) begin
                    instruction_type = opcode_lookup[opcode];
                end
            end
        end

        return instruction_type;
    endfunction

    virtual function rv32i_instruction create_instruction(
        input logic [31:0] instruction_word,
        input logic [31:0] current_pc,
        input logic [31:0] source_1,
        input logic [31:0] source_2
    );
        rv32i_instruction instruction;

        instruction = rv32i_instruction_factory::create_by_type(decode_type(instruction_word));
        instruction.decode(instruction_word, current_pc, source_1, source_2);
        return instruction;
    endfunction

endclass
