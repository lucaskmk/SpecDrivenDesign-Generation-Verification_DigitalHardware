#!/usr/bin/env python3

import os
import random
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotb_tools.runner import get_runner

@cocotb.test()
async def test_demux(dut):
    select_values = [0, 1]

    for _ in range(3):
        I_val = random.randint(0, 1)

        dut.I.value = I_val

        for sel in select_values:
            dut.S.value = sel
            await Timer(1, units="ns")

            for output_idx in range(2):
                expected = I_val if output_idx == sel else 0
                got = int(getattr(dut, f'O{output_idx}').value)
                assert got == expected, f"S={sel}: expected O{output_idx}={expected}, got {got}"
