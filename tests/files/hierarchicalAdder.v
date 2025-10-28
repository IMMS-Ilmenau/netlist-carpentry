module hierarchicalAdder #(parameter WIDTH = 8) (
    input wire clk,             //  The clock signal for the module.
    input wire rst,             //  The reset signal for the module.The reset signal for the module. When high, the output will be set to zero.
    input wire [WIDTH-1:0] in1, //  The first 8-bit operand for the addition.
    input wire [WIDTH-1:0] in2, //  The second 8-bit operand for the addition.
    output reg [WIDTH:0] out    //  The result of the addition, a 9-bit value.
);
    simpleAdder adder(
        .clk(clk),
        .rst(rst),
        .in1(in1),
        .in2(in2),
        .out(out)
    );
endmodule
