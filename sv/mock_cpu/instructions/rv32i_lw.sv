class rv32i_lw extends rv32i_instruction;

    virtual function execution_result_t execute();
        execution_result_t result;
        result = '0;
        result.valid = 1'b1;
        result.memory_read = 1'b1;
        result.rd = rd;
        result.memory_address = source_1 + immediate_i;
        return result;
    endfunction
endclass
