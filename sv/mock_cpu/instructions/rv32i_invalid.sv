class rv32i_invalid extends rv32i_instruction;

    virtual function execution_result_t execute();
        execution_result_t result;
        result = '0;
        result.valid = 1'b1;
        result.illegal_instruction = 1'b1;
        return result;
    endfunction
endclass
