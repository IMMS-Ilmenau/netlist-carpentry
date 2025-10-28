/* =====================================================================
-- Copyright 2025
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Simple Or Chain
-- ---------------------------------------------------------------------
-- Associated Filename: simple_or_structure.v
-- Description:
--   This module implements a chain of logical OR operations 8 1-bit
--   signals. This module is used as an example of a module that can be
--   improved using patterns. In this specific case, the cascading OR
--   gate instances could be replaced by a tree-like structure. This
--   leads to a performance increase, since the total gate runtime could
--   be reduced drastically.
-- =====================================================================
*/
module simple_or_structure #(
    parameter WIDTH = 1
) (
    input in1,
    input in2,
    input in3,
    input in4,
    input in5,
    input in6,
    input in7,
    input in8,
    output out
);
wire or1, or2, or3, or4, or5, or6;

// Cascading OR gates:
//
//        in2   in3   in4   in5   in6   in7   in8
//         V     V     V     V     V     V     V
//  in1 > or1 > or2 > or3 > or4 > or5 > or6 > out

assign or1 = in1 | in2;
assign or2 = or1 | in3;
assign or3 = or2 | in4;
assign or4 = or3 | in5;
assign or5 = or4 | in6;
assign or6 = or5 | in7;
assign out = or6 | in8;

endmodule
