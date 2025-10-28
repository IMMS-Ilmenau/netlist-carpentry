module simple_clock_gate (
    output  GC_O,               // New gated D-FF clock
    input   CLK_I,              // Original D-FF clock
    input   EN                  // Enable signal to make clock-gate transparent
);

// Signal to enable the gated clock. To prevent timing issues, cut clock cycles
// and deadlocks, this signal must be latched and only updated at falling clock
// edges, so it is already present when the system clock cycle arrives.
//
// latched_en = 0:  D and Q are equal (FF will not change its state) or
//                  the enable signal from the FF is 0
// latched_en = 1:  the clock should now reach the FF since it will
//                  change its state in the next cycle
reg     latched_en;
always  @(CLK_I or EN) begin
    if (~CLK_I) begin
        latched_en   <=  EN;
    end
end

// New gated clock is activated whenever a rising edge of the original clock
// arrives and the clock gating signal does allow the clock to pass.
assign  GC_O                =   CLK_I & latched_en;

endmodule
