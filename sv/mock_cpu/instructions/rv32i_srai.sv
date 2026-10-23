class rv32i_srai extends rv32i_instruction;

    virtual function execution_result_t execute();
        logic signed [31:0] signed_operand;
        signed_operand = source_1;
        return write_register(signed_operand >>> shift_amount);
    endfunction
endclass
