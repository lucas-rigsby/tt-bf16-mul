/*
 * Tiny Tapeout wrapper for bf16_mul_core.
 * SPDX-License-Identifier: Apache-2.0
 *
 * The chip has only 8 inputs (ui_in) and 8 outputs (uo_out), but the
 * multiplier needs 32 input bits and produces 16. So operands are loaded one
 * byte at a time and the result is read one byte at a time.
 *
 * Pins
 *   ui_in[7:0]   data byte to load
 *   uio_in[0]    LOAD: on each rising clk edge with LOAD=1, shift ui_in in.
 *                Load order: a[15:8], a[7:0], b[15:8], b[7:0]
 *   uio_in[1]    SEL:  0 -> uo_out = p[7:0], 1 -> uo_out = p[15:8]
 *   uo_out[7:0]  selected result byte
 *
 * Timing: p is registered, so it is valid one clock after the 4th load.
 *
 * Rename the module to tt_um_<your_github_username>_bf16 before submitting:
 * Tiny Tapeout requires a unique top-module name.
 */
`default_nettype none

module tt_um_lucas_rigsby_bf16 (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);
    wire load = uio_in[0];
    wire sel  = uio_in[1];

    reg  [31:0] ops;            // {a, b}
    reg  [15:0] p_q;
    wire [15:0] p_d;

    bf16_mul_core u_core (.a(ops[31:16]), .b(ops[15:0]), .p(p_d));

    always @(posedge clk) begin
        if (!rst_n) begin
            ops <= 32'd0;
            p_q <= 16'd0;
        end else begin
            if (load) ops <= {ops[23:0], ui_in};
            p_q <= p_d;
        end
    end

    assign uo_out  = sel ? p_q[15:8] : p_q[7:0];
    assign uio_out = 8'd0;
    assign uio_oe  = 8'd0;      // all bidirectional pins are inputs

    wire _unused = &{ena, uio_in[7:2], 1'b0};

endmodule

`default_nettype wire
