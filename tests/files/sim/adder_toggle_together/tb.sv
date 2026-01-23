`timescale 1us/100ns

module tb_adder_basics;
reg clk;
reg rst_n;
reg [7:0] in1;
reg [7:0] in2;
wire [8:0] out;

simpleAdder adder(
    .rst (rst_n),
    .clk (clk),
    .in1 (in1),
    .in2 (in2),
    .out (out)
);

localparam CLK_PERIOD = 10;
always #(CLK_PERIOD/2) clk=~clk;

initial begin
    $dumpfile("../tb_adder_basics.vcd");
    $dumpvars(0, tb_adder_basics);
end

initial begin
    #1 rst_n<=1'bx;clk<=1'bx;
    #(CLK_PERIOD*3) rst_n<=1;
    #(CLK_PERIOD*3) rst_n<=0;clk<=0;
    repeat(5) @(posedge clk);
    rst_n<=1;
    @(posedge clk);
    repeat(2) @(posedge clk);
    in1=8'b10100101;
    in2=8'b10100101;
    repeat(2) @(posedge clk);
    in1=8'b00001111;
    in2=8'b00001111;
    repeat(2) @(posedge clk);
    in1=8'b10001111;
    in2=8'b10001111;
    repeat(2) @(posedge clk);
    in1=8'b00001011;
    in2=8'b00001011;
    repeat(2) @(posedge clk);
    in1=8'b00110011;
    in2=8'b00110011;
    repeat(2) @(posedge clk);
    $finish(2);
end

endmodule
