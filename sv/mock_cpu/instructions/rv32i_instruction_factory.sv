class rv32i_instruction_factory;

    typedef rv32i_instruction::instruction_id_t instruction_id_t;

    static function rv32i_instruction create_by_type(input instruction_id_t instruction_type);
        rv32i_instruction instruction;

        case (instruction_type)
            rv32i_instruction::INSN_ADD: begin
                instruction = rv32i_add::new();
            end
            rv32i_instruction::INSN_SUB: begin
                instruction = rv32i_sub::new();
            end
            rv32i_instruction::INSN_AND: begin
                instruction = rv32i_and::new();
            end
            rv32i_instruction::INSN_OR: begin
                instruction = rv32i_or::new();
            end
            rv32i_instruction::INSN_XOR: begin
                instruction = rv32i_xor::new();
            end
            rv32i_instruction::INSN_SLL: begin
                instruction = rv32i_sll::new();
            end
            rv32i_instruction::INSN_SRL: begin
                instruction = rv32i_srl::new();
            end
            rv32i_instruction::INSN_SRA: begin
                instruction = rv32i_sra::new();
            end
            rv32i_instruction::INSN_SLT: begin
                instruction = rv32i_slt::new();
            end
            rv32i_instruction::INSN_SLTU: begin
                instruction = rv32i_sltu::new();
            end
            rv32i_instruction::INSN_ADDI: begin
                instruction = rv32i_addi::new();
            end
            rv32i_instruction::INSN_ANDI: begin
                instruction = rv32i_andi::new();
            end
            rv32i_instruction::INSN_ORI: begin
                instruction = rv32i_ori::new();
            end
            rv32i_instruction::INSN_XORI: begin
                instruction = rv32i_xori::new();
            end
            rv32i_instruction::INSN_SLLI: begin
                instruction = rv32i_slli::new();
            end
            rv32i_instruction::INSN_SRLI: begin
                instruction = rv32i_srli::new();
            end
            rv32i_instruction::INSN_SRAI: begin
                instruction = rv32i_srai::new();
            end
            rv32i_instruction::INSN_SLTI: begin
                instruction = rv32i_slti::new();
            end
            rv32i_instruction::INSN_SLTIU: begin
                instruction = rv32i_sltiu::new();
            end
            rv32i_instruction::INSN_BEQ: begin
                instruction = rv32i_beq::new();
            end
            rv32i_instruction::INSN_BNE: begin
                instruction = rv32i_bne::new();
            end
            rv32i_instruction::INSN_BLT: begin
                instruction = rv32i_blt::new();
            end
            rv32i_instruction::INSN_BGE: begin
                instruction = rv32i_bge::new();
            end
            rv32i_instruction::INSN_JAL: begin
                instruction = rv32i_jal::new();
            end
            rv32i_instruction::INSN_JALR: begin
                instruction = rv32i_jalr::new();
            end
            rv32i_instruction::INSN_LUI: begin
                instruction = rv32i_lui::new();
            end
            rv32i_instruction::INSN_LW: begin
                instruction = rv32i_lw::new();
            end
            rv32i_instruction::INSN_SW: begin
                instruction = rv32i_sw::new();
            end
            default: begin
                instruction = rv32i_invalid::new();
            end
        endcase

        return instruction;
    endfunction

endclass
