class rv32i_beq extends rv32i_instruction;

    virtual function execution_result_t execute();
        return advance_pc((source_1 == source_2)
            ? pc + immediate_b : pc + INSTRUCTION_BYTES);
    endfunction
endclass
