class rv32i_andi extends rv32i_instruction;

    virtual function execution_result_t execute();
        return write_register(source_1 & immediate_i);
    endfunction
endclass
