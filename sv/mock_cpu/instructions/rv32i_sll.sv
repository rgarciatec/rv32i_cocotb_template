class rv32i_sll extends rv32i_instruction;

    virtual function execution_result_t execute();
        return write_register(source_1 << source_2[4:0]);
    endfunction
endclass
