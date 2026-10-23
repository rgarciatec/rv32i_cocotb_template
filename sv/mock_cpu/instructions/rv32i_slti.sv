class rv32i_slti extends rv32i_instruction;

    virtual function execution_result_t execute();
        return write_register(
            ($signed(source_1) < $signed(immediate_i)) ? 32'd1 : 32'd0);
    endfunction
endclass
