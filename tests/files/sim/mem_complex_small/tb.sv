`timescale 1ns / 1ps

module tb_mem_complex_small;

    // --------------------------------------------------------
    // Signal Declarations
    // --------------------------------------------------------
    reg clk;

    // Write Port 0
    reg [1:0] we_w0;
    reg [4:0] addr_w0;
    reg [3:0] data_w0;

    // Write Port 1
    reg we_w1;
    reg [4:0] addr_w1;
    reg [3:0] data_w1;

    // Read Port 0
    reg [4:0] addr_r0;
    wire [3:0] data_r0;

    // Read Port 1
    reg ce_r1;
    reg srst_r1;
    reg [4:0] addr_r1;
    wire [3:0] data_r1;

    // Read Port 2
    reg [4:0] addr_r2;
    wire [3:0] data_r2;

    // Read Port 3
    reg [3:0] addr_r3;
    wire [7:0] data_r3;

    // --------------------------------------------------------
    // DUT Instantiation
    // --------------------------------------------------------
    mem_complex_small dut (
        .clk(clk),
        .we_w0(we_w0),
        .addr_w0(addr_w0),
        .data_w0(data_w0),
        .we_w1(we_w1),
        .addr_w1(addr_w1),
        .data_w1(data_w1),
        .addr_r0(addr_r0),
        .data_r0(data_r0),
        .ce_r1(ce_r1),
        .srst_r1(srst_r1),
        .addr_r1(addr_r1),
        .data_r1(data_r1),
        .addr_r2(addr_r2),
        .data_r2(data_r2),
        .addr_r3(addr_r3),
        .data_r3(data_r3)
    );

    // --------------------------------------------------------
    // Clock Generation
    // --------------------------------------------------------
    initial clk = 0;
    always #5 clk = ~clk; // 10ns period (100 MHz)

    // --------------------------------------------------------
    // Self-Checking Utilities
    // --------------------------------------------------------
    integer errors = 0;

    task check_4b;
        input [3:0] actual;
        input [3:0] expected;
        input [80*8:1] msg; // String up to 80 characters
        begin
            if (actual !== expected) begin
                $display("[%0t] FAIL: %0s | Expected: %h, Got: %h", $time, msg, expected, actual);
                errors = errors + 1;
            end else begin
                $display("[%0t] PASS: %0s", $time, msg);
            end
        end
    endtask

    task check_8b;
        input [7:0] actual;
        input [7:0] expected;
        input [80*8:1] msg;
        begin
            if (actual !== expected) begin
                $display("[%0t] FAIL: %0s | Expected: %h, Got: %h", $time, msg, expected, actual);
                errors = errors + 1;
            end else begin
                $display("[%0t] PASS: %0s", $time, msg);
            end
        end
    endtask

    // --------------------------------------------------------
    // Test Sequence
    // --------------------------------------------------------
    initial begin
        // Initialize default safe values
        we_w0 = 0; addr_w0 = 0; data_w0 = 0;
        we_w1 = 0; addr_w1 = 0; data_w1 = 0;
        addr_r0 = 0;
        ce_r1 = 0; srst_r1 = 0; addr_r1 = 0;
        addr_r2 = 0;
        addr_r3 = 0;

        // VCD Dump for waveform viewing
        $dumpfile("tb_mem_complex_small.vcd");
        $dumpvars(0, tb_mem_complex_small);

        // 1. Check Module Initializations
        #1; // Delay slightly to allow initial blocks to run
        $display("\n--- Testing Initial State ---");
        check_4b(data_r1, 4'hA, "Init RD_INIT_VALUE data_r1");
        check_4b(data_r2, 4'h9, "Init RD_INIT_VALUE data_r2");
        check_8b(data_r3, 8'hC3, "Init RD_INIT_VALUE data_r3");

        // 2. Test WP0 Chunked Write & RP0 Async Read
        $display("\n--- Testing WP0 (Chunk-enabled) and Async RP0 ---");
        @(negedge clk);
        we_w0 = 2'b11; addr_w0 = 10; data_w0 = 4'h0; // Clear address 10
        @(negedge clk);
        we_w0 = 2'b01; data_w0 = 4'hA; // 4'hA = 1010. Mask 01 writes bottom half (10 -> 2).
        @(negedge clk);
        addr_r0 = 10;
        #1; check_4b(data_r0, 4'h2, "WP0 chunk write lower half (A -> 2)");

        we_w0 = 2'b10; data_w0 = 4'hE; // 4'hE = 1110. Mask 10 writes upper half (11 -> 3).
        @(negedge clk);
        we_w0 = 2'b00;
        #1; check_4b(data_r0, 4'hE, "WP0 chunk write upper half (Mem becomes E)");

        // 3. Test Collision Priorities (WP1 overriding WP0)
        $display("\n--- Testing Collision Priority (WP1 over WP0) ---");
        @(negedge clk);
        addr_w0 = 11; we_w0 = 2'b11; data_w0 = 4'h5; // Try writing 5
        addr_w1 = 11; we_w1 = 1'b1;  data_w1 = 4'h9; // Try writing 9 (Wins)
        @(negedge clk);
        we_w0 = 2'b00; we_w1 = 1'b0;
        addr_r0 = 11;
        #1; check_4b(data_r0, 4'h9, "Collision override: WP1 (9) wins over WP0 (5)");

        // 4. Test RP2 Transparency (Bypass Logic)
        $display("\n--- Testing RP2 Transparency (Bypass) ---");
        @(negedge clk);
        addr_w1 = 12; we_w1 = 1'b1; data_w1 = 4'h7;
        addr_r2 = 12; // Simultaneous read-while-write on the same address
        @(negedge clk);
        we_w1 = 1'b0;
        check_4b(data_r2, 4'h7, "RP2 transparent bypass (Immediately reads 7)");

        // Double check standard read (no bypass)
        addr_r2 = 10;
        @(negedge clk);
        check_4b(data_r2, 4'hE, "RP2 normal read (Reads E from Address 10)");

        // 5. Test RP1 CE and SRST Priorities
        $display("\n--- Testing RP1 Priority (CE > SRST) ---");
        @(negedge clk);
        addr_r1 = 12; ce_r1 = 0; srst_r1 = 1; // Try to reset while disabled
        @(negedge clk);
        check_4b(data_r1, 4'hA, "RP1 CE=0, SRST=1 (Disabled, init value holds)");

        @(negedge clk);
        ce_r1 = 1; srst_r1 = 1; // Reset while enabled
        @(negedge clk);
        check_4b(data_r1, 4'hD, "RP1 CE=1, SRST=1 (SRST applied, reads D)");

        @(negedge clk);
        ce_r1 = 1; srst_r1 = 0; // Normal read logic
        @(negedge clk);
        check_4b(data_r1, 4'h7, "RP1 CE=1, SRST=0 (Normal read, grabs 7 from Addr 12)");

        // 6. Test RP3 Wide Port Emulation
        $display("\n--- Testing RP3 Wide Port ---");
        // Address r3 = 5 effectively requests standard addresses {11, 10}
        // At this point: ram[11] == 4'h9, ram[10] == 4'hE
        @(negedge clk);
        addr_r3 = 5;
        @(negedge clk);
        check_8b(data_r3, 8'h9E, "RP3 Wide Read (Retrieves ram[11] and ram[10] -> 9E)");

        // --------------------------------------------------------
        // End of Simulation Summary
        // --------------------------------------------------------
        $display("\n=================================");
        if (errors == 0) begin
            $display("   ALL TESTS PASSED! (0 Errors)");
            $display("=================================\n");
            $finish;
        end else begin
            $display("   SIMULATION FAILED with %0d errors.", errors);
            $display("=================================\n");
            $fatal(1);
        end
    end

endmodule
