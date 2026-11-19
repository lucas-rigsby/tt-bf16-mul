## How it works

How it works: a bfloat16 multiplier that rounds toward zero and flushes subnormal inputs to zero.

## How to test

How to test: load four bytes on ui_in with uio[0]=1, in the order a[15:8], a[7:0], b[15:8], b[7:0]. Wait one clock, then read uo_out with uio[1]=0 for p[7:0] and uio[1]=1 for p[15:8]. Example: 0x3FC0 * 0x4000 (1.5 * 2.0) gives 0x4040 (3.0).

## External hardware

None.
