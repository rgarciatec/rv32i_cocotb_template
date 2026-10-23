class rv32i_xor extends rv32i_instruction;

    virtual function execution_result_t execute();
        return write_register(source_1 ^ source_2);
    endfunction
endclass
