module rv32i_cpu #(
    parameter int EXEC_LATENCY = 2
) (
    input  logic        clk,
    input  logic        reset,
    output logic        imem_valid,
    input  logic        imem_ready,
    output logic [31:0] imem_addr,
    input  logic [31:0] imem_rdata,
    output logic        dmem_valid,
    input  logic        dmem_ready,
    output logic [31:0] dmem_addr,
    output logic        dmem_we,
    output logic [31:0] dmem_wdata,
    input  logic [31:0] dmem_rdata,
    output logic        illegal_instruction
);

    import rv32i_pkg::*;

    typedef enum logic [2:0] {
        CPU_FETCH,
        CPU_EXECUTE,
        CPU_COMMIT,
        CPU_LOAD,
        CPU_STORE
    } cpu_state_t;

    typedef rv32i_instruction::execution_result_t execution_result_t;

    cpu_state_t state_reg;
    cpu_state_t state_next;
    execution_result_t execution_result;
    cpu_model model;
    rv32i_instruction instruction;

    logic [31:0] pc;
    logic [31:0] raw_instruction;
    logic [31:0] register_file [0:31];
    logic [31:0] memory_address;
    logic [31:0] store_data;
    logic [4:0] pending_rd;
    int latency_count;

    assign imem_valid = state_reg == CPU_FETCH;
    assign imem_addr = pc;
    assign dmem_valid = state_reg inside {CPU_LOAD, CPU_STORE};
    assign dmem_we = state_reg == CPU_STORE;
    assign dmem_addr = memory_address;
    assign dmem_wdata = store_data;

    initial model = new();

    always_comb begin
        state_next = state_reg;

        case (state_reg)
            CPU_FETCH: begin
                if (imem_ready) begin
                    state_next = CPU_EXECUTE;
                end
            end
            CPU_EXECUTE: begin
                if (latency_count == 0) begin
                    state_next = CPU_COMMIT;
                end
            end
            CPU_COMMIT: begin
                if (execution_result.memory_read) begin
                    state_next = CPU_LOAD;
                end else begin
                    if (execution_result.memory_write) begin
                        state_next = CPU_STORE;
                    end else begin
                        state_next = CPU_FETCH;
                    end
                end
            end
            CPU_LOAD: begin
                if (dmem_ready) begin
                    state_next = CPU_FETCH;
                end
            end
            CPU_STORE: begin
                if (dmem_ready) begin
                    state_next = CPU_FETCH;
                end
            end
            default: begin
                state_next = CPU_FETCH;
            end
        endcase
    end

    always_ff @(posedge clk or posedge reset) begin
        if (reset) begin
            state_reg <= CPU_FETCH;
            pc <= 32'd0;
            raw_instruction <= 32'd0;
            memory_address <= 32'd0;
            store_data <= 32'd0;
            pending_rd <= 5'd0;
            latency_count <= 0;
            execution_result <= '0;
            illegal_instruction <= 1'b0;
            foreach (register_file[register_index])
                register_file[register_index] <= 32'd0;
        end else begin
            state_reg <= state_next;
            illegal_instruction <= 1'b0;
            register_file[0] <= 32'd0;

            case (state_reg)
                CPU_FETCH: begin
                    if (imem_ready) begin
                        raw_instruction <= imem_rdata;
                        latency_count <= EXEC_LATENCY;
                    end
                end

                CPU_EXECUTE: begin
                    if (latency_count > 0) begin
                        latency_count <= latency_count - 1;
                    end else begin
                        instruction = model.create_instruction(
                            raw_instruction,
                            pc,
                            register_file[raw_instruction[19:15]],
                            register_file[raw_instruction[24:20]]
                        );
                        execution_result <= instruction.execute();
                    end
                end

                CPU_COMMIT: begin
                    illegal_instruction <= execution_result.illegal_instruction;
                    if (execution_result.memory_read) begin
                        memory_address <= execution_result.memory_address;
                        pending_rd <= execution_result.rd;
                    end else begin
                        if (execution_result.memory_write) begin
                            memory_address <= execution_result.memory_address;
                            store_data <= execution_result.store_data;
                        end else begin
                            if (execution_result.register_write) begin
                                register_file[execution_result.rd] <= execution_result.writeback_data;
                            end
                            if (execution_result.pc_write) begin
                                pc <= execution_result.next_pc;
                            end
                        end
                    end
                end

                CPU_LOAD: begin
                    if (dmem_ready) begin
                        if (pending_rd != 5'd0)
                            register_file[pending_rd] <= dmem_rdata;
                        pc <= pc + 32'd4;
                    end
                end

                CPU_STORE: begin
                    if (dmem_ready) begin
                        pc <= pc + 32'd4;
                    end
                end

                default: begin
                end
            endcase
        end
    end

endmodule
