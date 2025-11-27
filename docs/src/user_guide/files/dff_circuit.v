module Top (
    input CLK,
    input RSTN,
    input A,
    input [7:0] B,
    input C,
    output D,
    output [7:0] E
);
    wire w1, w2, w3, w4;

    M1 m1(.CLK(CLK), .RSTN(RSTN), .A(A), .B(C), .W(w1), .Y(w2));
    M1 m2(.CLK(CLK), .RSTN(RSTN), .A(A), .B(C), .W(w3), .Y(w4));
    M2 m3(.CLK(CLK), .RSTN(RSTN), .A(B), .B(C), .W(), .Y(E));

    assign D = w1 & w3 | w2 & w4;

endmodule

module M1 (
    input CLK,
    input RSTN,
    input A,
    input B,
    output W,
    output Y
);
    always @(posedge CLK or negedge RSTN) begin
        if (~RSTN) begin
            Y <= 0;
        end else if (B) begin
            Y <= A;
        end
    end

    always @(posedge CLK) begin
        W <= B;
    end
endmodule

module M2 (
    input CLK,
    input RSTN,
    input [7:0] A,
    input B,
    output W,
    output [7:0] Y
);
    wire w1, w2;
    always @(posedge CLK) begin
        w1 <= A[0] & A[7];
    end

    M21 m21(.CLK(CLK), .A(w1), .Y(w2));
    M22 m22(.CLK(CLK), .RSTN(RSTN), .A(A), .B(B), .Y(Y));

    assign W = ~w2;
endmodule

module M21 (
    input CLK,
    input A,
    output Y
);
    always @(negedge CLK) begin
        Y <= A;
    end
endmodule

module M22 (
    input CLK,
    input RSTN,
    input [7:0] A,
    input B,
    output [7:0] Y
);
    wire w1;
    wire [7:0] w2;
    always @(posedge CLK or negedge RSTN) begin
        if (~RSTN) begin
            w1 <= 0;
        end else begin
            w1 <= B;
        end
    end
    always @(posedge CLK or negedge RSTN) begin
        if (~RSTN) begin
            w2 <= 8'b0;
        end else if (w1) begin
            w2 <= w2 + 1;
        end
    end

    always @(posedge CLK or negedge RSTN) begin
        if (~RSTN) begin
            Y <= 8'b0;
        end else if (B & w2[7]) begin
            Y <= w2;
        end
    end
endmodule
