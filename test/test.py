# cocotb test for the Tiny Tapeout wrapper. Same reference model as the core
# tests, but driven through the 8-bit pin protocol a real user would use.
# The Tiny Tapeout GitHub Action also runs this against the gate-level
# netlist after hardening (GATES=yes), so keep it fast.
import os
import random
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

sys.path.insert(0, os.path.dirname(__file__))
from bf16_ref import DIRECTED, rand_bf16, ref_mul  # noqa: E402

LOAD, SEL = 0x01, 0x02


async def multiply(dut, a, b):
    """Load four bytes, wait one cycle, read both result bytes."""
    for byte in (a >> 8, a & 0xFF, b >> 8, b & 0xFF):
        await FallingEdge(dut.clk)
        dut.ui_in.value = byte
        dut.uio_in.value = LOAD
    await FallingEdge(dut.clk)        # 4th byte captured at the last edge
    dut.uio_in.value = 0
    await FallingEdge(dut.clk)        # p registered one edge later
    lo = dut.uo_out.value.to_unsigned()
    dut.uio_in.value = SEL
    await FallingEdge(dut.clk)
    hi = dut.uo_out.value.to_unsigned()
    dut.uio_in.value = 0
    return (hi << 8) | lo


@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())   # 50 MHz

    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1

    cases = [(a, b) for a, b, _ in DIRECTED]
    rng = random.Random(7)
    cases += [(rand_bf16(rng, 100, 154), rand_bf16(rng, 100, 154)) for _ in range(200)]

    for a, b in cases:
        got = await multiply(dut, a, b)
        exp = ref_mul(a, b)
        assert got == exp, f"a=0x{a:04x} b=0x{b:04x}: got 0x{got:04x}, expected 0x{exp:04x}"
    dut._log.info(f"{len(cases)} multiplies checked")
    # Let the last pin write settle before the test returns. cocotb 2.1.0.dev0
    # + Icarus 14 segfault on exit if a test ends with a write still pending.
    await FallingEdge(dut.clk)
