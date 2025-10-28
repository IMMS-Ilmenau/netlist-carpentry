/* =====================================================================
-- This techmap is used to convert a pmux cell to multiple simple
-- 2-input multiplexer instances. A pmux cell in this context is used to
-- multiplex between many inputs using a one-hot select signal. See
-- https://yosyshq.readthedocs.io/projects/yosys/en/latest/cell/word_mux.html#multiplexers
-- for more information.
--
-- This techmap is based on an answer in a reddit thread:
-- https://www.reddit.com/r/yosys/comments/1t0o5y/is_there_any_option_to_convert_pmux_to_many_mux/
-- =====================================================================
*/
module \$pmux (A, B, S, Y);

wire [1023:0] _TECHMAP_DO_ = "proc; clean";

parameter WIDTH = 1;
parameter S_WIDTH = 1;

input [WIDTH-1:0] A;
input [WIDTH*S_WIDTH-1:0] B;
input [S_WIDTH-1:0] S;
output reg [WIDTH-1:0] Y;

integer i;

always @* begin
	Y <= A;
	for (i = 0; i < S_WIDTH; i=i+1)
		if (S[i]) Y <= B[WIDTH*i +: WIDTH];
end

endmodule
