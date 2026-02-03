module uniquify_module (
    input wire [3:0] A,
    input wire [3:0] B,
    input wire CLK,
    input wire RST,
    output wire [3:0] Y
);
    inner_module I1(.A(A[0]), .B(B[0]), .CLK(CLK), .RST(RST), .Y(Y[0]));
    inner_module I2(.A(A[1]), .B(B[1]), .CLK(CLK), .RST(RST), .Y(Y[1]));
    inner_module I3(.A(A[2]), .B(B[2]), .CLK(CLK), .RST(RST), .Y(Y[2]));
    inner_module I4(.A(A[3]), .B(B[3]), .CLK(CLK), .RST(RST), .Y(Y[3]));
endmodule


module inner_module (
    input wire A,
    input wire B,
    input wire CLK,
    input wire RST,
    output reg Y
);
    always @(posedge CLK or posedge RST) begin
        if (RST) begin
            Y <= 0;
        end else begin
            Y <= A & B;
        end
    end
endmodule
