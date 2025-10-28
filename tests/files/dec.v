/* =====================================================================
-- Copyright 2021
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Decoder Basic Blocks
-- ---------------------------------------------------------------------
-- Associated Filename: dec.v
-- Description: A variety of decoder implementation
-- Assumption: external signals
-- Limitation: clk frequency
-- =====================================================================
*/

`timescale 1ns/1ps

/*
-- ---------------------------------------------------------------------
-- One-Hot Decoder
-- ---------------------------------------------------------------------
*/

module dec_one_hot #(
    //-- Decoder Width
    parameter PTR_BIT_WIDTH = 3,
    parameter DEC_BIT_WIDTH = 8
)
(
    //-- Inputs
    input wire [PTR_BIT_WIDTH-1:0] PTR,
    //-- Outputs
    output reg [DEC_BIT_WIDTH-1:0] Q
);

//-- Output selection
always @(*)
begin

    //-- Default selection
    Q = {DEC_BIT_WIDTH{1'b0}};

    //-- Valid value for pointer
    if (PTR < DEC_BIT_WIDTH)
    begin
        Q = 1'b1 << PTR;
    end
end

endmodule

/*
-- ---------------------------------------------------------------------
-- One-to-N Decoder
-- ---------------------------------------------------------------------
*/

module dec_one_to_N #(
    //-- Decoder Width
    parameter PTR_BIT_WIDTH = 3,
    parameter DEC_BIT_WIDTH = 8
)
(
    //-- Inputs
    input wire [PTR_BIT_WIDTH-1:0] PTR,
    input wire D,
    //-- Outputs
    output reg [DEC_BIT_WIDTH-1:0] Q
);

//-- Output selection
always @(*)
begin

    //-- Default selection
    Q = {DEC_BIT_WIDTH{1'b0}};

    //-- Valid value for pointer
    if (PTR < DEC_BIT_WIDTH)
    begin
        Q = D << PTR;
    end
end

endmodule
