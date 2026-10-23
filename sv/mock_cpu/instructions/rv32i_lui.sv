class rv32i_lui extends rv32i_instruction;

    virtual function execution_result_t execute();
        return write_register(immediate_u);
    endfunction
endclass
