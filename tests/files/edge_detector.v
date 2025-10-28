/* =====================================================================
-- Copyright 2021
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Edge Detector Basic Blocks
-- ---------------------------------------------------------------------
-- Associated Filename: edge_detector.v
-- Description: Implementation of a simple edge detector
-- Assumption: external signals
-- Limitation: clk frequency
-- =====================================================================
*/

`timescale 1ns/1ps

/*
-- ---------------------------------------------------------------------
-- Simple Edge Detector
-- ---------------------------------------------------------------------
*/

module edge_detector_simple#(
    //-- Reset Value
    parameter RESET_VALUE = 1'b0
)(
    //-- Global Signals
    input wire  CLK_I,
    input wire  RST_ASYNC_I,
    //-- Inputs
    input wire  SIG_I,
    //-- Outputs
    output wire SIG_REDGE_O,
    output wire SIG_FEDGE_O
);

//-- Internal Register Declaration
reg [1:0] sig_sr;

//-- Shift-Register
always @(posedge CLK_I or posedge RST_ASYNC_I)
begin
    if (RST_ASYNC_I)
    begin
        sig_sr <= {2{RESET_VALUE}};
    end
    else
    begin
        sig_sr <= {sig_sr[0], SIG_I};
    end
end

//-- Evaluate Falling/Rising Edges
assign SIG_REDGE_O = (sig_sr == 2'b01);
assign SIG_FEDGE_O = (sig_sr == 2'b10);

endmodule

/*
-- ---------------------------------------------------------------------
-- Fast Edge Detector
-- ---------------------------------------------------------------------
*/

module edge_detector_fast #(
    //-- Reset Value
    parameter RESET_VALUE = 1'b0
)(
    //-- Global Signals
    input wire  CLK_I,
    input wire  RST_ASYNC_I,
    //-- Inputs
    input wire  SIG_I,
    //-- Outputs
    output wire SIG_REDGE_O,
    output wire SIG_FEDGE_O
);

//-- Internal Register Declaration
reg _sig_sync;

//-- Shift-Register
always @(posedge CLK_I or posedge RST_ASYNC_I)
begin
    if (RST_ASYNC_I)
    begin
        _sig_sync <= RESET_VALUE;
    end
    else
    begin
        _sig_sync <= SIG_I;
    end
end

//-- Evaluate Falling/Rising Edges
assign SIG_REDGE_O = (_sig_sync == 1'b0) && (SIG_I == 1'b1);
assign SIG_FEDGE_O = (_sig_sync == 1'b1) && (SIG_I == 1'b0);

endmodule

/*
-- ---------------------------------------------------------------------
-- Advanced Edge Detector
-- ---------------------------------------------------------------------
*/

module edge_detector_advanced #(
    parameter BIT_WIDTH = 4,
    //-- Reset Value
    parameter RESET_VALUE = 1'b0
)(
    //-- Clock-/Reset-Signal Bundle
    input wire CLK_I,
    input wire RST_ASYNC_I,
    //-- Monitored input signal
    input wire SIG_I,
    //-- Detected edges output signals
    output wire SIG_REDGE_O,
    output wire SIG_REDGE_ASYNC_O,
    output wire SIG_FEDGE_O,
    output wire SIG_FEDGE_ASYNC_O,
    output wire SIG_HIGH_STABLE_O,
    output wire SIG_ZERO_STABLE_O
);

reg [BIT_WIDTH-1:0] sig_sreg;

always @(posedge CLK_I or posedge RST_ASYNC_I)
begin
    if (RST_ASYNC_I)
    begin
        sig_sreg <= {BIT_WIDTH{RESET_VALUE}};
    end
    else begin
        sig_sreg <= {sig_sreg[BIT_WIDTH-2:0], SIG_I};
    end
end

assign SIG_REDGE_O          = (sig_sreg[1:0] == 2'b01);
assign SIG_FEDGE_O          = (sig_sreg[1:0] == 2'b10);
assign SIG_HIGH_STABLE_O    = (sig_sreg[BIT_WIDTH-1:0] == {BIT_WIDTH{1'b1}});
assign SIG_ZERO_STABLE_O    = (sig_sreg[BIT_WIDTH-1:0] == {BIT_WIDTH{1'b0}});

assign SIG_REDGE_ASYNC_O = (~RST_ASYNC_I) & (
    (SIG_I == 1'b1) & (sig_sreg[0] == 1'b0));
assign SIG_FEDGE_ASYNC_O = (~RST_ASYNC_I) & (
    (SIG_I == 1'b0) & (sig_sreg[0] == 1'b1));

endmodule
