`timescale 1us/100ns

module tb_no_signals;

localparam CLK_PERIOD = 10;

initial begin
    $dumpfile("../tb_no_signals.vcd");
    $dumpvars(0, tb_no_signals);
end

initial begin
    $finish(2);
end

endmodule
