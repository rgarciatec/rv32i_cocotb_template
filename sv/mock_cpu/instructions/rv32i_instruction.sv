virtual class rv32i_instruction;

    typedef enum logic [6:0] {
        OPCODE_LOAD      = 7'h03,
        OPCODE_IMMEDIATE = 7'h13,
        OPCODE_STORE     = 7'h23,
        OPCODE_REGISTER  = 7'h33,
        OPCODE_LUI       = 7'h37,
        OPCODE_BRANCH    = 7'h63,
        OPCODE_JALR      = 7'h67,
        OPCODE_JAL       = 7'h6f
    } opcode_t;

    typedef enum logic [2:0] {
        FUNCT3_ADD_SUB = 3'h0,
        FUNCT3_SLL     = 3'h1,
        FUNCT3_SLT     = 3'h2,
        FUNCT3_SLTU    = 3'h3,
        FUNCT3_XOR     = 3'h4,
        FUNCT3_SHIFT   = 3'h5,
        FUNCT3_OR      = 3'h6,
        FUNCT3_AND     = 3'h7
    } funct3_t;

    typedef enum logic [2:0] {
        LOAD_FUNCT3_WORD = 3'b010
    } load_funct3_t;

    typedef enum logic [2:0] {
        STORE_FUNCT3_WORD = 3'b010
    } store_funct3_t;

    typedef enum logic [6:0] {
        FUNCT7_BASE = 7'h00,
        FUNCT7_ALT  = 7'h20
    } funct7_t;

    typedef enum logic [5:0] {
        INSN_INVALID,
        INSN_ADD,
        INSN_SUB,
        INSN_AND,
        INSN_OR,
        INSN_XOR,
        INSN_SLL,
        INSN_SRL,
        INSN_SRA,
        INSN_SLT,
        INSN_SLTU,
        INSN_ADDI,
        INSN_ANDI,
        INSN_ORI,
        INSN_XORI,
        INSN_SLLI,
        INSN_SRLI,
        INSN_SRAI,
        INSN_SLTI,
        INSN_SLTIU,
        INSN_BEQ,
        INSN_BNE,
        INSN_BLT,
        INSN_BGE,
        INSN_JAL,
        INSN_JALR,
        INSN_LUI,
        INSN_LW,
        INSN_SW
    } instruction_id_t;

    typedef enum logic [1:0] {
        INSTRUCTION_FIELD_WIDTH_12 = 2'd0,
        INSTRUCTION_FIELD_WIDTH_13 = 2'd1,
        INSTRUCTION_FIELD_WIDTH_20 = 2'd2,
        INSTRUCTION_FIELD_WIDTH_21 = 2'd3
    } instruction_field_width_t;

    typedef struct packed {
        logic        valid;
        logic        register_write;
        logic [4:0]  rd;
        logic [31:0] writeback_data;
        logic        pc_write;
        logic [31:0] next_pc;
        logic        memory_read;
        logic        memory_write;
        logic        illegal_instruction;
        logic [31:0] memory_address;
        logic [31:0] store_data;
    } execution_result_t;

    localparam logic [31:0] INSTRUCTION_BYTES = 32'd4;
    localparam logic [31:0] JALR_ALIGNMENT_MASK = 32'hffff_fffe;

    logic [4:0] rd;
    logic [31:0] pc;
    logic [31:0] source_1;
    logic [31:0] source_2;
    logic [31:0] immediate_i;
    logic [31:0] immediate_s;
    logic [31:0] immediate_b;
    logic [31:0] immediate_u;
    logic [31:0] immediate_j;
    logic [4:0] shift_amount;

    virtual function void decode(
        input logic [31:0] instruction_word,
        input logic [31:0] current_pc,
        input logic [31:0] current_source_1,
        input logic [31:0] current_source_2
    );
        rd = instruction_word[11:7];
        pc = current_pc;
        source_1 = current_source_1;
        source_2 = current_source_2;

        immediate_i = {{20{instruction_word[31]}}, instruction_word[31:20]};
        immediate_s = {{20{instruction_word[31]}}, instruction_word[31:25],
                       instruction_word[11:7]};
        immediate_b = {{19{instruction_word[31]}}, instruction_word[31],
                       instruction_word[7], instruction_word[30:25],
                       instruction_word[11:8], 1'b0};
        immediate_u = {instruction_word[31:12], 12'b0};
        immediate_j = {{11{instruction_word[31]}}, instruction_word[31],
                       instruction_word[19:12], instruction_word[20],
                       instruction_word[30:21], 1'b0};
        shift_amount = instruction_word[24:20];
    endfunction

    virtual function execution_result_t write_register(input logic [31:0] value);
        execution_result_t result;
        result = '0;
        result.valid = 1'b1;
        result.register_write = (rd != 5'd0);
        result.rd = rd;
        result.writeback_data = value;
        result.pc_write = 1'b1;
        result.next_pc = pc + INSTRUCTION_BYTES;
        return result;
    endfunction

    virtual function execution_result_t advance_pc(input logic [31:0] next_pc);
        execution_result_t result;
        result = '0;
        result.valid = 1'b1;
        result.pc_write = 1'b1;
        result.next_pc = next_pc;
        return result;
    endfunction

    pure virtual function execution_result_t execute();

endclass
