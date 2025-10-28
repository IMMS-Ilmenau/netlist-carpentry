/* =====================================================================
-- Copyright 2021
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Decoder Basic Blocks
-- ---------------------------------------------------------------------
-- Associated Filename: decentral_mux.v
-- Description: A variety of decoder implementation
-- Assumption: external signals
-- Limitation: clk frequency
-- =====================================================================
*/

`timescale 1ns/1ps

module decentral_mux #(
    parameter DATA_WIDTH = 1,
    parameter ADR_WIDTH = 8,
    parameter NINPUTS = 16
)
(
    //-- Inputs
    input wire [ADR_WIDTH-1:0] SELECT_I,    //-- Selection of column
    input wire [NINPUTS*DATA_WIDTH-1:0] DATA_I,
    //-- Outputs
    output wire [DATA_WIDTH-1:0] DATA_O
);

//-- Internal Register Declaration
reg [DATA_WIDTH-1:0] data_sel [NINPUTS-1:0];
reg [DATA_WIDTH-1:0] nxt_data [NINPUTS-1:0];
reg [DATA_WIDTH-1:0] nxt_out_data;

//-- Internal Pointer
integer i;

always @(*)
begin
    for (i=0; i<NINPUTS; i=i+1)
    begin
        if (i == SELECT_I)
        begin
            data_sel[i] <= {DATA_WIDTH{1'b1}};
        end
        else begin
            data_sel[i] <= {DATA_WIDTH{1'b0}};
        end
    end

    for (i=0; i<NINPUTS; i=i+1)
    begin
        nxt_data[i] <= data_sel[i] & DATA_I[i*DATA_WIDTH +: DATA_WIDTH];
    end

    //-- Default pixel value
    nxt_out_data = {DATA_WIDTH{1'b0}};

    for (i=0; i<NINPUTS; i=i+1)
    begin
        nxt_out_data = nxt_out_data | nxt_data[i];
    end
end

//-- Concurrent Output Assignment
assign DATA_O = nxt_out_data;

endmodule
