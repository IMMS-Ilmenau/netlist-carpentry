module test_mem #(
    parameter DATA_WIDTH = 8,
    parameter ADDR_WIDTH = 4
)(
    input  wire                  clk,

    // Write Port
    input  wire                  we,          // Write Enable
    input  wire [ADDR_WIDTH-1:0] write_addr,
    input  wire [DATA_WIDTH-1:0] write_data,

    // Read Port
    input  wire [ADDR_WIDTH-1:0] read_addr,
    output reg  [DATA_WIDTH-1:0] read_data
);

    // Memory array
    reg [DATA_WIDTH-1:0] ram[0:(1<<ADDR_WIDTH)-1];

    // Synchronous Write Port
    always @(posedge clk) begin
        if (we) begin
            ram[write_addr] <= write_data;
        end
    end

    // Synchronous Read Port
    always @(posedge clk) begin
        read_data <= ram[read_addr];
    end

endmodule
