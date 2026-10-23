class rv32i_jalr extends rv32i_instruction;

    virtual function execution_result_t execute();
        execution_result_t result;
        result = write_register(pc + INSTRUCTION_BYTES);
        result.next_pc = (source_1 + immediate_i) & JALR_ALIGNMENT_MASK;
        return result;
    endfunction
endclass
