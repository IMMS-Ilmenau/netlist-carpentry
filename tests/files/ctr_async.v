/* =====================================================================
-- Copyright 2021
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Asynchronous Counter
-- ---------------------------------------------------------------------
-- Associated Filename: cnt_async.v
-- Description: Implementation of a simple asynchronous counter
-- =====================================================================
*/

`timescale 1ns/1ps

module ctr_async #(
    parameter BIT_WIDTH = 16,
    parameter [BIT_WIDTH-1:0] RESET_VAL = 'h0
)(
    //-- Clock-/Reset- signal bundle
    input  wire CLK_I,
    input  wire RST_ASYNC_I,
    //-- Counter Output
    output wire [BIT_WIDTH-1:0] CNT_O
);

//-- Internal signal declaration
reg [BIT_WIDTH:0] intr_ctr_state;

wire overflow_flg = &(intr_ctr_state[BIT_WIDTH:1]);

//-- Next state
always @(*)
begin
    intr_ctr_state[0] <= ~CLK_I;
end

//-- Define variable for hardware loop
genvar i;

//-- Evaluate next counter state
for (i=1; i<BIT_WIDTH+1; i=i+1)
begin
    always @(posedge RST_ASYNC_I or negedge intr_ctr_state[i-1])
    begin
        if (RST_ASYNC_I)
        begin
            if (2**i<=(RESET_VAL << 1))
            begin
                intr_ctr_state[i] <= 1'b1;
            end
            else begin
                intr_ctr_state[i] <= 1'b0;
            end
        end
        else
        begin
            if (~overflow_flg)
            begin
                intr_ctr_state[i] <= ~intr_ctr_state[i];
            end
        end
    end
end

//-- Output assignment
assign CNT_O = intr_ctr_state[BIT_WIDTH:1];

endmodule
