module mem_complex (
    // Write Port 0: Synchronous, Positive edge, Byte-enabled (2-bit mask)
    input wire clk_w0,
    input wire [1:0] we_w0,
    input wire [5:0] addr_w0,
    input wire [15:0] data_w0,

    // Write Port 1: Synchronous, Negative edge, Full word
    input wire clk_w1,
    input wire we_w1,
    input wire [5:0] addr_w1,
    input wire [15:0] data_w1,

    // Read Port 0: Asynchronous (Combinational)
    input wire [5:0] addr_r0,
    output wire [15:0] data_r0,

    // Read Port 1: Synchronous, Positive edge, Clock Enable taking priority over Sync Reset
    input wire clk_r1,
    input wire ce_r1,
    input wire srst_r1,
    input wire [5:0] addr_r1,
    output reg [15:0] data_r1,

    // Read Port 2: Synchronous, Negative edge, Transparent (Write-First) with Write Port 1
    input wire [5:0] addr_r2,
    output reg [15:0] data_r2,

    // Read Port 3: Wide Read (Synchronous, reads 32 bits from 16-bit memory)
    input wire clk_r3,
    input wire [4:0] addr_r3, // Note: 5 bits instead of 6, as it accesses 2 words at a time
    output reg [31:0] data_r3
);

    // Core Geometry: WIDTH = 16, ABITS = 6, SIZE = 64, OFFSET = 10
    reg [15:0] ram [10:73];

    // Initialization Parameters
    initial begin
        // Infers RD_INIT_VALUE for the synchronous read ports
        data_r1 = 16'hCAFE;
        data_r2 = 16'h0000;
        data_r3 = 32'h00000000;
    end

    // Write Port 0 Logic
    always @(posedge clk_w0) begin
        // Infers a 2-bit WR_EN mask instead of a 1-bit toggle
        if (we_w0[0]) ram[addr_w0][7:0]  <= data_w0[7:0];
        if (we_w0[1]) ram[addr_w0][15:8] <= data_w0[15:8];
    end

    // Write Port 1 & Read Port 2 Logic (Transparency Inference)
    always @(negedge clk_w1) begin
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
    always @(posedge clk_r1) begin
        if (ce_r1) begin
            // Because the reset is nested INSIDE the clock enable,
            // Yosys sets RD_CE_OVER_SRST = 1 for this port.
            if (srst_r1) begin
                data_r1 <= 16'hDEAD; // Sets RD_SRST_VALUE
            end else begin
                data_r1 <= ram[addr_r1];
            end
        end
    end

    // Read Port 3 Logic (Wide Port Inference)
    always @(posedge clk_r3) begin
        // Reading adjacent, aligned addresses concatonated together.
        // Yosys's `memory_wide` pass will absorb this into a single read port
        // that is twice as wide as the base RAM width.
        data_r3 <= {ram[{addr_r3, 1'b1}], ram[{addr_r3, 1'b0}]};
    end

endmodule
