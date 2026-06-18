module dff_types (
    input CLK,
    input RST,
    input EN,
    input CLR,
    input SET,
    input [3:0] D,
    output [3:0] Q1,
    output [3:0] Q2,
    output [3:0] Q3,
    output [3:0] Q4,
    output [3:0] Q5,
    output [3:0] Q6,
    output [3:0] Q7,
    output [3:0] Q8,
    output [3:0] Q9
);
    always @(posedge CLK) begin // DFF
        Q1 <= D;
    end
    always @(negedge CLK or negedge RST) begin // ADFF
        if (~RST) begin
            Q2 <= 4'b1010;
        end else begin
            Q2 <= D;
        end
    end
    always @(negedge CLK or posedge RST) begin // ADFFE
        if (RST) begin
            Q3 <= 4'b1010;
        end else if (EN) begin
            Q3 <= D;
        end
    end
    always @(posedge CLK) begin // DFFE
        if (~EN) begin
            Q4 <= D;
        end
    end

    always @(posedge CLK) begin // SDFF
        if (~RST) begin
            Q5 <= 4'b1010;
        end else begin
            Q5 <= D;
        end
    end
    always @(posedge CLK) begin // SDFFCE
        if (EN) begin
            if (~RST) begin
                Q6 <= 4'b1010;
            end else begin
                Q6 <= D;
            end
        end
    end
    always @(posedge CLK) begin // SDFFE
        if (RST) begin
            Q7 <= 4'b1010;
        end else if (~EN) begin
            Q7 <= D;
        end
    end

    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin
            always @(posedge CLK or posedge CLR or posedge SET) begin // DFFSR
                if (CLR) begin
                    Q8[i] <= 0;
                end else if (SET) begin
                    Q8[i] <= 1;
                end else begin
                    Q8[i] <= D[i];
                end
            end
            always @(posedge CLK or posedge CLR or posedge SET) begin // DFFSRE
                if (CLR) begin
                    Q9[i] <= 0;
                end else if (SET) begin
                    Q9[i] <= 1;
                end else if (~EN) begin
                    Q9[i] <= D[i];
                end
            end
        end
    endgenerate


endmodule
