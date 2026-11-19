// bf16_mul_core.v — combinational bfloat16 multiplier.
// Behaviour is defined in docs/spec.md (requirement IDs in comments).
`default_nettype none

module bf16_mul_core (
    input  wire [15:0] a,
    input  wire [15:0] b,
    output wire [15:0] p
);
    // ---- unpack -------------------------------------------------------
    wire       sa = a[15];
    wire       sb = b[15];
    wire [7:0] ea = a[14:7];
    wire [7:0] eb = b[14:7];
    wire [6:0] ma = a[6:0];
    wire [6:0] mb = b[6:0];

    wire       s       = sa ^ sb;                 // R4
    wire       zero_in = (ea == 8'd0) | (eb == 8'd0); // R2: flush subnormals

    // ---- significand multiply: 1.ma x 1.mb ----------------------------
    // Each significand is 8 bits with the hidden 1, so the product is
    // 16 bits and lies in [2^14, 2^16): bit 15 tells us if it is >= 2.0.
    wire [15:0] prod = {1'b1, ma} * {1'b1, mb};
    wire        norm = prod[15];

    // R5: round toward zero = keep the top 7 fraction bits, drop the rest.
    wire [6:0] m = norm ? prod[14:8] : prod[13:7];

    // ---- exponent -----------------------------------------------------
    // Result exponent (biased) = ea + eb + norm - 127. Unsigned throughout.
    //
    // Timing optimisation: `norm` comes out of the multiplier late. Instead
    // of feeding it into the adder (v1: esum = ea + eb + norm, which put the
    // whole adder and both comparisons after the multiplier), compute the
    // result for norm=0 AND norm=1 in parallel with the multiply, then let
    // `norm` pick one with a final mux. Same function, shorter critical path.
    wire [9:0] esum = {2'b00, ea} + {2'b00, eb};   // independent of norm

    // norm = 0 case                         // norm = 1 case (esum + 1)
    wire       uflow0 = (esum <= 10'd127);   wire       uflow1 = (esum <= 10'd126); // R6
    wire       oflow0 = (esum >= 10'd382);   wire       oflow1 = (esum >= 10'd381); // R7
    wire [9:0] eres0  = esum - 10'd127;      wire [9:0] eres1  = esum - 10'd126;

    wire       uflow = norm ? uflow1 : uflow0;
    wire       oflow = norm ? oflow1 : oflow0;
    wire [7:0] eres  = norm ? eres1[7:0] : eres0[7:0];

    // Dropped bits are intentional, so tell the linter: prod[6:0] is the
    // truncated fraction (R5), and eres*[9:8] are always 0 when eres is used.
    wire _unused = &{1'b0, prod[6:0], eres0[9:8], eres1[9:8]};

    // ---- pack ---------------------------------------------------------
    assign p = (zero_in | uflow) ? {s, 15'd0}                 // R2, R6
             : oflow             ? {s, 8'hFE, 7'h7F}          // R7
             :                     {s, eres, m};

endmodule

`default_nettype wire
