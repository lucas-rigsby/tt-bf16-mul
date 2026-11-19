![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# bfloat16 multiplier for Tiny Tapeout

A bfloat16 (bf16) multiplier on a single Tiny Tapeout tile in GlobalFoundries 180 nm
(gf180mcuD). Operands go in one byte at a time and the 16-bit product comes out one byte at a
time, because a Tiny Tapeout project has only 8 input and 8 output pins.

- Top module: `tt_um_lucas_rigsby_bf16`
- Clock: 25 MHz (`clock_hz` in [info.yaml](info.yaml))
- Datasheet page: [docs/info.md](docs/info.md)

## What it computes

bfloat16 is the top 16 bits of an IEEE float32: 1 sign bit, 8 exponent bits (bias 127) and
7 fraction bits. It keeps float32's range with 8 bits of precision, which is why ML accelerators
use it.

| Case | Result |
|---|---|
| Normal × normal | product, **rounded toward zero** (extra fraction bits are truncated) |
| Either input zero or subnormal (exponent 0) | signed zero; subnormals are flushed |
| Product below 2^-126 | signed zero; the output is never subnormal |
| Product ≥ 2^128 | saturates to ±`0x7F7F`, the largest finite value |
| Sign | always `a[15] ^ b[15]` |

Inputs with exponent 255 (Inf/NaN) are out of scope and must not be applied. Like many ML
accelerators, it has no round-to-nearest-even and no exception flags.

## How it works

```
ui_in ──LOAD──▶ ops[31:0] shift register ──▶ bf16_mul_core ──▶ p_q[15:0] ──SEL──▶ uo_out
               (a = ops[31:16], b = ops[15:0])  (combinational)    register
```

- **`src/project.v`**: the Tiny Tapeout wrapper. While `uio_in[0]` (LOAD) is 1, each rising
  clock edge shifts `ui_in` into a 32-bit register. The product is registered into `p_q` on
  every edge, and `uio_in[1]` (SEL) picks which byte of `p_q` drives `uo_out`.
- **`src/bf16_mul_core.v`**: the multiplier, purely combinational. It multiplies the 8-bit
  significands (hidden 1 included), uses the product's top bit to normalise, and adds the
  exponents. Both possible exponent outcomes (normalised or not) are computed in parallel with
  the multiply, so the late normalise bit only drives a final select.

## Pinout

| Pin | Direction | Use |
|---|---|---|
| `ui_in[7:0]` | in | operand byte to load |
| `uo_out[7:0]` | out | selected result byte: `p[7:0]` when SEL = 0, `p[15:8]` when SEL = 1 |
| `uio[0]` | in | LOAD: on each rising edge with LOAD = 1, shift `ui_in` in |
| `uio[1]` | in | SEL: result byte select |
| `uio[7:2]` | in | unused |

All bidirectional pins are inputs (`uio_oe = 0`).

## How to use it

1. Hold `rst_n` low for a few clocks, then release it. The operand and result registers clear to 0.
2. With LOAD = 1, present four bytes on `ui_in`, one per rising edge, in this order:
   `a[15:8]`, `a[7:0]`, `b[15:8]`, `b[7:0]`. Change inputs between rising edges, not on them.
3. Set LOAD = 0. On the next rising edge the product is registered.
4. Read `uo_out` with SEL = 0 for `p[7:0]`, then with SEL = 1 for `p[15:8]`.

Examples:

| a | b | p |
|---|---|---|
| `0x3FC0` (1.5) | `0x4000` (2.0) | `0x4040` (3.0) |
| `0x4000` (2.0) | `0x4040` (3.0) | `0x40C0` (6.0) |
| `0xBFC0` (−1.5) | `0x4000` (2.0) | `0xC040` (−3.0) |
| `0x3FC0` (1.5) | `0x3FC0` (1.5) | `0x4010` (2.25) |
| `0x0001` (subnormal) | `0x3F80` (1.0) | `0x0000` |

## Testing

The cocotb test in [test/](test/) drives the chip's pins exactly as above and checks 215
products against an independent reference model (`test/bf16_ref.py`, built on NumPy float32
arithmetic rather than the RTL's algorithm): directed cases for every rule in the table above,
then 200 random pairs.

```sh
cd test
make                        # RTL simulation
make GATES=yes              # gate-level, with the hardened netlist as gate_level_netlist.v
```

The `test` workflow runs the RTL simulation on every push, and the `gl_test` job reruns it on
the post-layout netlist after the `gds` workflow hardens the design. Requirements: Icarus
Verilog and the packages in `test/requirements.txt` (cocotb, pytest, numpy).

## Results (gds run on commit 9d1e6b2)

| | |
|---|---|
| Area | 2,318 cells, 35.2% of one 1×1 tile |
| Timing at 25 MHz, typical corner (25 °C, 3.3 V) | setup slack +18.91 ns (≈ 47 MHz achievable), hold slack +1.07 ns |
| Timing at 25 MHz, slow corner (125 °C, 3.0 V) | setup slack −2.60 ns (≈ 23.5 MHz). Tiny Tapeout signs off timing at the typical corner. |
| Power | ≈ 1.4 mW (estimate with default switching activity) |
| Sign-off checks | DRC (Magic, KLayout) 0, LVS 0, antenna 0, latches 0; precheck and gate-level test pass |

Before this repository, the design was also checked with Verilator lint, cocotb simulation,
100% code coverage, mutation testing (44/44 injected bugs caught), an ECP5 FPGA build (111 MHz),
and a SymbiYosys formal proof over all 2^32 input pairs of commutativity, the sign rule, ×1.0
and ×−1.0, zero inputs, and that the output is never subnormal, Inf or NaN.

## Repository layout

| Path | Contents |
|---|---|
| `src/project.v` | Tiny Tapeout wrapper (`tt_um_lucas_rigsby_bf16`) |
| `src/bf16_mul_core.v` | combinational bf16 multiplier |
| `src/config.json` | LibreLane settings (`CLOCK_PERIOD` 40 ns) |
| `test/` | cocotb testbench, reference model, test Makefile |
| `docs/info.md` | datasheet page |
| `info.yaml` | project metadata and pinout |

---

## About Tiny Tapeout

Tiny Tapeout is an educational project that aims to make it easier and cheaper than ever to get
digital and analog designs manufactured on a real chip. To learn more and get started, visit
https://tinytapeout.com.

### How this repository builds

This repository was created from the
[Tiny Tapeout GF180 Verilog template](https://github.com/TinyTapeout/ttgf-verilog-template).
GitHub Actions do the work on every push:

- **gds**: hardens the design with [LibreLane](https://www.zerotoasiccourse.com/terminology/librelane/)
  (synthesis, placement, clock tree, routing, DRC, LVS), then runs **precheck** (Tiny Tapeout's
  rule checks), **gl_test** (the cocotb test on the gate-level netlist) and **viewer** (an
  interactive layout view on GitHub Pages).
- **test**: the RTL cocotb test.
- **docs**: builds the datasheet from `docs/info.md`.
- **fpga**: an FPGA build of the project.

The viewer job needs GitHub Pages: see
[Enabling GitHub Pages](https://tinytapeout.com/faq/#my-github-action-is-failing-on-the-pages-part).

### Resources

- [FAQ](https://tinytapeout.com/faq/)
- [Digital design lessons](https://tinytapeout.com/digital_design/)
- [Learn how semiconductors work](https://tinytapeout.com/siliwiz/)
- [Join the community](https://tinytapeout.com/discord)
- [Build your design locally](https://www.tinytapeout.com/guides/local-hardening/)
- [Submit a design to the next shuttle](https://app.tinytapeout.com/)
