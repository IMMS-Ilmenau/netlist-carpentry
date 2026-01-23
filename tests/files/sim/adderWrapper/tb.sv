`timescale 1us/100ns

module tb_adderWrapper;
reg clk;
reg rst_n;
reg [3:0] in1;
reg [3:0] in2;
wire [4:0] out;

adderWrapper I_adderWrapper(
    .rst (~rst_n),
    .clk (clk),
    .in1 (in1),
    .in2 (in2),
    .out (out)
);

localparam CLK_PERIOD = 10;
always #(CLK_PERIOD/2) clk=~clk;

initial begin
    $dumpfile("../tb_adderWrapper.vcd");
    $dumpvars(0, tb_adderWrapper);
end

initial begin
    #1 rst_n<=1'bx;clk<=1'bx;
    #(CLK_PERIOD*3) rst_n<=1;
    #(CLK_PERIOD*3) rst_n<=0;clk<=0;
    repeat(5) @(posedge clk);
    rst_n<=1;
    @(posedge clk);
    repeat(2) @(posedge clk);
    in1=8'b0101;
    in2=8'b0011;
    repeat(20) @(posedge clk);
    $finish(2);
end

endmodule
