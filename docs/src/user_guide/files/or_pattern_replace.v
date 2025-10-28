// This module implements a digital logic circuit that performs an OR operation
// on four input signals using a tree-like structure.
module or_pattern_replace #(
    parameter WIDTH = 1
) (
    input   [ WIDTH-1 : 0 ] in1,   // Input signal 1, first pair
    input   [ WIDTH-1 : 0 ] in2,   // Input signal 2, first pair
    input   [ WIDTH-1 : 0 ] in3,   // Input signal 1, second pair
    input   [ WIDTH-1 : 0 ] in4,   // Input signal 2, second pair
    output  [ WIDTH-1 : 0 ] out     // Output of the OR operation
);
    // Intermediate wire to store result of both OR operations
    wire    [ WIDTH-1 : 0 ] new_or1;
    wire    [ WIDTH-1 : 0 ] new_or2;

    // Perform OR operations on pairs of inputs using a tree structure,
    // which reduces propagation delay compared to cascading the operations.
    assign new_or1  =   in1 | in2; // First pair: in1 OR in2
    assign new_or2  =   in3 | in4; // Second pair: in3 OR in4
    assign out  =   new_or1  | new_or2;  // Final result: (in1 OR in2) OR (in3 OR in4)
endmodule
