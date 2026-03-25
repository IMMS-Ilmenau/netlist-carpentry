module chains_orig (
    input A,
    input B,
    input C,
    input D,
    output Y
);
    wire _000_;
    wire _001_;

    assign _000_ = A | B;
    assign _001_ = _000_ | C;
    assign Y = _001_ | D;
endmodule
