module clock_gate #(

    parameter WIDTH = 1,        // Data width of FF
    parameter EN_POLARITY = 1,  // Polarity of FF enable port (1 = Active High, 0 = Active Low)
    parameter CLK_POLARITY = 1, // Polarity of FF clk port (1 = REdge sensitive, 0 = FEdge sensitive)
    ) (
    output  GC_O,               // New gated D-FF clock
    input   CLK_I,              // Original D-FF clock
    input   EN,                 // D-FF enable signal
    input   [WIDTH-1:0] Q,      // D-FF data output
    input   [WIDTH-1:0] D       // D-FF data input (new data)
);

// Additional internal wire to adjust the enable signal, if the input port of
// the dff enable signal is inverted (i. e. EN_POLARITY = 0). Otherwise just
// pass the EN signal to the internal enable signal.
wire    dff_en_correct_pol;
assign  dff_en_correct_pol  =   EN_POLARITY     ?   EN      :   !EN;

// Additional internal wire to adjust the clk signal, if the input port of
// the dff clk signal is inverted (i. e. CLK_POLARITY = 0). Otherwise just
// pass the CLK_I signal to the internal clk signal.
wire    dff_clk_correct_pol;
assign  dff_clk_correct_pol =   CLK_POLARITY    ?   CLK_I   :   !CLK_I;

// The result of the comparison of the FFs input and output data will be
// stored in here
//
// comparison_result = 0:   D and Q are equal, the FF will not change its value
// comparison_result = 1:   the FF will change its value in the next cycle
reg     comparison_result;
assign  comparison_result   =   |(D ^ Q);

// Signal to enable the gated clock. To prevent timing issues, cut clock cycles
// and deadlocks, this signal must be latched and only updated at falling clock
// edges, so it is already present when the system clock cycle arrives.
//
// latched_enable_gc = 0:   D and Q are equal (FF will not change its state) or
//                          the enable signal from the FF is 0
// latched_enable_gc = 1:   the clock should now reach the FF since it will
//                          change its state in the next cycle
reg     latched_enable_gc;
always  @(dff_clk_correct_pol or comparison_result or dff_en_correct_pol) begin
    if (~dff_clk_correct_pol) begin
        latched_enable_gc   <=  comparison_result & dff_en_correct_pol;
    end
end

// New gated clock is activated whenever a rising edge of the original clock
// arrives and the clock gating signal does allow the clock to pass.
assign  GC_O                =   CLK_I & latched_enable_gc;

endmodule
