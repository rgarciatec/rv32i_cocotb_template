class rv32i_bge extends rv32i_instruction;

    virtual function execution_result_t execute();
        return advance_pc(($signed(source_1) >= $signed(source_2))
            ? pc + immediate_b : pc + INSTRUCTION_BYTES);
    endfunction
endclass
