"""Independent reference model for bf16_mul (see docs/spec.md).

It does NOT copy the RTL's algorithm. Instead it uses NumPy float32 hardware
arithmetic and then applies the spec's rules. Two different implementations
agreeing is what gives the test its value.

Why float32 is exact here: each bf16 significand has 8 bits, so the product
has at most 16 significant bits, which fits in float32's 24 bits. float32 also
has the same exponent range as bf16, so no spurious overflow or rounding
happens before we apply round-toward-zero ourselves.
"""
import random

import numpy as np

ONE = 0x3F80
NEG_ONE = 0xBF80
MAX_FINITE = 0x7F7F


def bf16_to_f32(x: int) -> np.float32:
    return np.array([x << 16], dtype=np.uint32).view(np.float32)[0]


def bf16_to_float(x: int) -> float:
    """For readable log messages."""
    if (x >> 7) & 0xFF == 0:
        return -0.0 if x >> 15 else 0.0
    return float(bf16_to_f32(x))


def ref_mul(a: int, b: int) -> int:
    s = (a >> 15) ^ (b >> 15)
    ea, eb = (a >> 7) & 0xFF, (b >> 7) & 0xFF
    assert ea != 0xFF and eb != 0xFF, "R3: Inf/NaN inputs are out of scope"

    if ea == 0 or eb == 0:                       # R2
        return s << 15

    with np.errstate(over="ignore", under="ignore"):
        prod = bf16_to_f32(a) * bf16_to_f32(b)  # exact (see docstring)

    if np.isinf(prod):                           # R7: saturate
        return (s << 15) | MAX_FINITE

    bits = int(np.array([prod], dtype=np.float32).view(np.uint32)[0])
    r = bits >> 16                               # R5: truncate = toward zero
    if (r >> 7) & 0xFF == 0:                     # R6: flush underflow
        return s << 15
    return r


# ---------------------------------------------------------------- stimulus
def rand_bf16(rng: random.Random, exp_lo=1, exp_hi=254, zero_prob=0.0) -> int:
    """Random legal bf16 (never exponent 255)."""
    if rng.random() < zero_prob:
        # zero or subnormal: exponent 0, any mantissa (R2 says flush)
        return (rng.getrandbits(1) << 15) | rng.getrandbits(7)
    s = rng.getrandbits(1)
    e = rng.randint(exp_lo, exp_hi)
    m = rng.getrandbits(7)
    return (s << 15) | (e << 7) | m


def edge_pair(rng: random.Random):
    """Pick exponents so the product lands right at the underflow or
    overflow boundary, where bugs live."""
    target = rng.choice([127, 128, 381, 382])    # esum boundaries in the RTL
    ea = rng.randint(max(1, target - 254), min(254, target - 1))
    eb = target - ea - rng.getrandbits(1)        # +/- the normalise bit
    eb = min(254, max(1, eb))
    a = (rng.getrandbits(1) << 15) | (ea << 7) | rng.getrandbits(7)
    b = (rng.getrandbits(1) << 15) | (eb << 7) | rng.getrandbits(7)
    return a, b


# Hand-picked cases: (a, b, why)
DIRECTED = [
    (0x3F80, 0x3F80, "1.0 * 1.0 = 1.0"),
    (0x4000, 0x4040, "2.0 * 3.0 = 6.0"),
    (0xBFC0, 0x4000, "-1.5 * 2.0 = -3.0"),
    (0x3FC0, 0x3FC0, "1.5 * 1.5 = 2.25 (normalise shift)"),
    (0x3FFF, 0x3FFF, "largest significands: truncation"),
    (0x0000, 0x4000, "+0 * 2"),
    (0x8000, 0x4000, "-0 * 2 = -0"),
    (0x0001, 0x3F80, "subnormal flushed to zero"),
    (0x7F7F, 0x4000, "max * 2 overflows -> saturate"),
    (0xFF7F, 0x7F7F, "-max * max -> -saturate"),
    (0x0080, 0x3F00, "min normal * 0.5 underflows -> 0"),
    (0x0080, 0x3F80, "min normal * 1 stays normal"),
    (0x1F80, 0x1F80, "2^-64 * 2^-64 = 2^-128 underflows"),
    (0x5F80, 0x5F80, "2^64 * 2^64 = 2^128 overflows"),
    (0x5F00, 0x5F80, "2^63 * 2^64 = 2^127 fits"),
]
