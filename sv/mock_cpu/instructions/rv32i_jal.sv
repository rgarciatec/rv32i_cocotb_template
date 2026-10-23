class rv32i_jal extends rv32i_instruction;

    virtual function execution_result_t execute();
        execution_result_t result;
        result = write_register(pc + INSTRUCTION_BYTES);
        result.next_pc = pc + immediate_j;
        return result;
    endfunction
endclass
