module mem_complex_small (
    // Write Port 0: Synchronous, Positive edge, Chunk-enabled (2-bit mask, 2 bits per chunk)
    input wire clk,
    input wire [1:0] we_w0,
    input wire [4:0] addr_w0,
    input wire [3:0] data_w0,

    // Write Port 1: Synchronous, Negative edge, Full word
    input wire we_w1,
    input wire [4:0] addr_w1,
    input wire [3:0] data_w1,

    // Read Port 0: Asynchronous (Combinational)
    input wire [4:0] addr_r0,
    output wire [3:0] data_r0,

    // Read Port 1: Synchronous, Positive edge, Clock Enable taking priority over Sync Reset
    input wire ce_r1,
    input wire srst_r1,
    input wire [4:0] addr_r1,
    output reg [3:0] data_r1,

    // Read Port 2: Synchronous, Negative edge, Transparent (Write-First) with Write Port 1
    input wire [4:0] addr_r2,
    output reg [3:0] data_r2,

    // Read Port 3: Wide Read (Synchronous, reads 8 bits from 4-bit memory)
    input wire [3:0] addr_r3, // Note: 4 bits instead of 5, as it accesses 2 words at a time
    output reg [7:0] data_r3
);

    // Core Geometry: WIDTH = 4, ABITS = 5 (max index 25), SIZE = 16, OFFSET = 10
    reg [3:0] ram [10:25];

    // Handle writing colisions
    wire collision      = we_w1 && (addr_w0 == addr_w1);
    wire [1:0] we_w0_s  = we_w0 & {2{~collision}};

    // Initialization Parameters
    initial begin
        // Infers RD_INIT_VALUE for the synchronous read ports
        data_r1 = 4'hA;
        data_r2 = 4'h9;
        data_r3 = 8'hC3;
    end

    // Write Port 0 Logic
    always @(posedge clk) begin
        // Infers a 2-bit WR_EN mask instead of a 1-bit toggle
        if (we_w0_s[0]) ram[addr_w0][1:0] <= data_w0[1:0];
        if (we_w0_s[1]) ram[addr_w0][3:2] <= data_w0[3:2];
    end

    // Write Port 1 & Read Port 2 Logic (Transparency Inference)
    always @(posedge clk) begin
        // Write logic
        if (we_w1) begin
            ram[addr_w1] <= data_w1;
        end

        // Read logic with a bypass.
        // Yosys detects this exact MUX pattern and absorbs it into the memory cell
        // by setting the RD_TRANSPARENT parameter to true for this Read/Write port pair.
        if (we_w1 && (addr_w1 == addr_r2)) begin
            data_r2 <= data_w1;
        end else begin
            data_r2 <= ram[addr_r2];
        end
    end

    // Read Port 0 Logic (Asynchronous)
    assign data_r0 = ram[addr_r0];

    // Read Port 1 Logic (Complex Reset/Enable Priority)
    always @(posedge clk) begin
        if (ce_r1) begin
            // Because the reset is nested INSIDE the clock enable,
            // Yosys sets RD_CE_OVER_SRST = 1 for this port.
            if (srst_r1) begin
                data_r1 <= 4'hD; // Sets RD_SRST_VALUE
            end else begin
                data_r1 <= ram[addr_r1];
            end
        end
    end

    // Read Port 3 Logic (Wide Port Inference)
    always @(posedge clk) begin
        // Reading adjacent, aligned addresses concatonated together.
        // Yosys's `memory_wide` pass will absorb this into a single read port
        // that is twice as wide as the base RAM width.
        data_r3 <= {ram[{addr_r3, 1'b1}], ram[{addr_r3, 1'b0}]};
    end

endmodule
