/* =====================================================================
-- Copyright 2025
-- IMMS GmbH
-- All rights reserved
--
-- ---------------------------------------------------------------------
-- Title: Pattern To find OR Chains
-- ---------------------------------------------------------------------
-- Associated Filename: or_pattern_find.v
-- Description:
--   This module implements a circuit that performs an OR operation
--   on four input signals using a structure with cascading operations.
-- =====================================================================
*/

module or_pattern_find #(
    parameter WIDTH = 1
) (
    input   [ WIDTH-1 : 0 ] in1,
    input   [ WIDTH-1 : 0 ] in2,
    input   [ WIDTH-1 : 0 ] in3,
    input   [ WIDTH-1 : 0 ] in4,
    output  [ WIDTH-1 : 0 ] out // Result of the OR operation on all input signals
);

    // Intermediate wires to hold the result of both OR operations
    wire    [ WIDTH-1 : 0 ] or1;
    wire    [ WIDTH-1 : 0 ] or2;

    // The following lines implement a cascading OR-gate structure, where each subsequent gate's input depends on the previous gate's output.
    // While this approach works, it can be optimized into a tree-like structure for better performance and reduced latency.

    // First, perform an OR operation between in1 and in2
    assign or1  =   in1 | in2;
    // Next, perform an OR operation between the result of the previous step (or1) and in3
    assign or2  =   or1 | in3;
    // Finally, perform an OR operation between the result of the previous step (or2) and in4 to get the final output
    assign out  =   or2 | in4;

endmodule
