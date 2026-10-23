class rv32i_sw extends rv32i_instruction;

    virtual function execution_result_t execute();
        execution_result_t result;
        result = '0;
        result.valid = 1'b1;
        result.memory_write = 1'b1;
        result.memory_address = source_1 + immediate_s;
        result.store_data = source_2;
        return result;
    endfunction
endclass
