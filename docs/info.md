## How it works

A bfloat16 multiplier: `p = a × b` for two 16-bit bfloat16 operands (1 sign bit, 8 exponent
bits with bias 127, 7 fraction bits). The product is rounded toward zero. Zero and subnormal
inputs are treated as zero, a product below 2^-126 becomes a signed zero, and a product of
2^128 or more saturates to ±0x7F7F, the largest finite value. The sign is always
`a[15] ^ b[15]`. Inputs with exponent 255 (Inf/NaN) are not supported.

The chip has 8 input and 8 output pins, so the 32 operand bits are shifted in one byte at a
time and the 16-bit product is read one byte at a time. Inside, a 32-bit shift register feeds a
combinational multiplier, and the product is registered on every clock edge.

| Pin | Use |
|---|---|
| `ui_in[7:0]` | operand byte |
| `uio_in[0]` | LOAD: on each rising edge with LOAD = 1, `ui_in` is shifted in |
| `uio_in[1]` | SEL: `uo_out` shows `p[7:0]` when 0, `p[15:8]` when 1 |
| `uo_out[7:0]` | selected result byte |

## How to test

Clock: up to 25 MHz. Change the inputs between rising clock edges.

1. Hold `rst_n` low for a few clocks, then release it. The result reads 0.
2. Set LOAD (`uio_in[0]`) = 1 and present four bytes on `ui_in`, one per rising edge, in this
   order: `a[15:8]`, `a[7:0]`, `b[15:8]`, `b[7:0]`.
3. Set LOAD = 0 and wait one rising edge: the product is now registered.
4. Read `uo_out` with SEL (`uio_in[1]`) = 0 for `p[7:0]`, then with SEL = 1 for `p[15:8]`.

Examples:

| a | b | p |
|---|---|---|
| 0x3FC0 (1.5) | 0x4000 (2.0) | 0x4040 (3.0) |
| 0xBFC0 (−1.5) | 0x4000 (2.0) | 0xC040 (−3.0) |
| 0x3FC0 (1.5) | 0x3FC0 (1.5) | 0x4010 (2.25) |
| 0x0001 (subnormal) | 0x3F80 (1.0) | 0x0000 |

## External hardware

None.
