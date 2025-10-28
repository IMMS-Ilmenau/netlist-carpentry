/* =====================================================================
-- Copyright 2021
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Thermo Encoder
-- ---------------------------------------------------------------------
-- Associated Filename: thermo_enc.v
-- =====================================================================
*/

module thermo_enc #(
    parameter D_WIDTH = 4,
    parameter Q_WIDTH = 2**D_WIDTH
)(
    input  wire [D_WIDTH-1:0] D,
    output reg  [Q_WIDTH-1:0] Q
);

//-- Internal bit pointer
integer i;

always @(*)
begin
    //-- Default register value
    Q = {Q_WIDTH{1'b0}};

    for (i=0; i<Q_WIDTH; i=i+1)
    begin
        if (i >= D)
        begin
            Q[i] = 1'b1;
        end
    end
end

endmodule
