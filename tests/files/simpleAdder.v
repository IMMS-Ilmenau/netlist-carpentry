/* =====================================================================
-- Copyright 2025
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Simple Adder
-- ---------------------------------------------------------------------
-- Associated Filename: simpleAdder.v
-- Description:
--   This module implements a simple 8-bit adder.
--   It takes two 8-bit inputs (in1 and in2) and adds them together,
--   producing a 9-bit output (out). The addition is performed on every
--   positive clock edge. If the reset signal (rst) is high, the output
--   is set to zero.
-- =====================================================================
*/

module simpleAdder #(parameter WIDTH = 8) (
    input wire clk,             //  The clock signal for the module.
    input wire rst,             //  The reset signal for the module.The reset signal for the module. When high, the output will be set to zero.
    input wire [WIDTH-1:0] in1, //  The first 8-bit operand for the addition.
    input wire [WIDTH-1:0] in2, //  The second 8-bit operand for the addition.
    output reg [WIDTH:0] out    //  The result of the addition, a 9-bit value.
);

// This always block performs the addition on every positive clock edge or reset signal.
always @(posedge clk or posedge rst) begin
    if (rst) begin
        out = 0;            //  If the reset signal is high, set the output to zero.
    end else begin
        out = in1 + in2;    //  Perform the addition of in1 and in2 on every positive clock edge.
    end
end

endmodule
