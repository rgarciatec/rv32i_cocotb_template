class rv32i_sltiu extends rv32i_instruction;

    virtual function execution_result_t execute();
        return write_register((source_1 < immediate_i) ? 32'd1 : 32'd0);
    endfunction
endclass
