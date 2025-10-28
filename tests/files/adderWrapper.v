/* =====================================================================
-- Copyright 2025
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Wrapper for Simple Adder
-- ---------------------------------------------------------------------
-- Associated Filename: adderWrapper.v
-- Description:
--   This module instantiates the simple adder and reduces its output to
--   1 bit. There is no logical reason behind this wrapper. Its only
--   purpose is to emulate a hierarchical design for test cases.
-- =====================================================================
*/

module adderWrapper #(parameter WIDTH = 4) (
    input [WIDTH:1] in1,
    input [4:WIDTH+3] in2,
    input               clk,
    input               rst,
    output              out
);
wire [WIDTH:0]          internal_out;

simpleAdder #(.WIDTH(WIDTH)) adder(
    .in1(in1),
    .in2(in2),
    .clk(clk),
    .rst(rst),
    .out(internal_out)
    );

assign      out             =    |internal_out;
endmodule
