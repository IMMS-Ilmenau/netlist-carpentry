`timescale 1us/100ns

module tb_unique_signals;
reg clk;
reg a;
reg b;
reg c;


localparam CLK_PERIOD = 10;
always #(CLK_PERIOD/2) clk=~clk;

initial begin
    $dumpfile("../tb_unique_signals.vcd");
    $dumpvars(0, tb_unique_signals);
end

initial begin
    #1 clk<=1'bx;
    #(CLK_PERIOD*3) clk<=0;
    repeat(5) @(posedge clk);
    a=0;
    b=0;
    c=0;
    repeat(2) @(posedge clk);
    a=1;
    b=1;
    c=1;
    repeat(2) @(posedge clk);
    a=0;
    b=1;
    c=1;
    repeat(2) @(posedge clk);
    a=1;
    b=0;
    c=0;
    repeat(2) @(posedge clk);
    a=1;
    b=0;
    c=1;
    repeat(2) @(posedge clk);
    a=0;
    b=1;
    c=0;
    repeat(2) @(posedge clk);
    $finish(2);
end

endmodule
