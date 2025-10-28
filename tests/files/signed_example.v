module signed_example (
    input signed [8:5] inA,
    input signed [6:3] inB,
    output [4:1] c
);
    reg signed c;
    always @* begin
        c <= $signed(inA) - $signed(inB);
    end
endmodule
