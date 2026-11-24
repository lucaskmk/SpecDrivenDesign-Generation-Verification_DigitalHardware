import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM source used by this test."""
    labels = {}
    instructions = []
    pc = 0

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = pc
            line = line.strip()
            if not line:
                continue

        instructions.append((pc, line))
        pc += 4

    def reg_number(token):
        match = re.fullmatch(r"x([0-9]|[12][0-9]|3[01])", token.strip())
        if not match:
            raise ValueError(f"Invalid register: {token}")
        return int(match.group(1))

    program = {}
    for address, line in instructions:
        mnemonic, _, operands = line.partition(" ")
        args = [arg.strip() for arg in operands.split(",")]

        if mnemonic == "remu" and len(args) == 3:
            rd, rs1, rs2 = map(reg_number, args)
            word = (
                (0b0000001 << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0b111 << 12)
                | (rd << 7)
                | 0x33
            )
        elif mnemonic == "sw" and len(args) == 2:
            rs2 = reg_number(args[0])
            match = re.fullmatch(r"(-?\d+)\s*\(\s*(x\d+)\s*\)", args[1])
            if not match:
                raise ValueError(f"Invalid store operand: {args[1]}")
            immediate = int(match.group(1))
            rs1 = reg_number(match.group(2))
            imm = immediate & 0xFFF
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0b010 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal" and len(args) == 2:
            rd = reg_number(args[0])
            if args[1] not in labels:
                raise ValueError(f"Unknown jump label: {args[1]}")
            offset = labels[args[1]] - address
            imm = offset & 0x1FFFFF
            word = (
                (((imm >> 20) & 0x1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 0x1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction: {line}")

        program[address] = word

    return program


@cocotb.test()
async def remu_zero_dividend_and_divisor_stores_zero(dut):
    program = assemble_rv32im(
        """
        remu x3, x0, x0
        sw x3, 0(x0)
    halt: jal x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(2, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    await FallingEdge(dut.clk)

    memory = {}
    store_committed = False

    for _ in range(3):
        address = int(dut.instr_addr.value)
        assert address in program, (
            f"Expected a program instruction at 0x{address:08X}"
        )
        dut.instr_data.value = program[address]
        await Timer(1, unit="ns")

        is_store = address == 0x00000004
        observed_write = int(dut.data_write.value)
        expected_write = 1 if is_store else 0
        assert observed_write == expected_write, (
            f"Expected data_write={expected_write} at PC=0x{address:08X}, "
            f"observed {observed_write}"
        )

        if is_store:
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed "
                f"0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected REMU result/store data 0x00000000, observed "
                f"0x{observed_data:08X}"
            )

        await RisingEdge(dut.clk)
        if is_store:
            memory[0x00000000] = observed_data & 0xFFFFFFFF
            store_committed = True
            break
        await FallingEdge(dut.clk)

    assert store_committed, "Expected the REMU result to be committed by a store"
    observed_memory = memory[0x00000000]
    assert observed_memory == 0x00000000, (
        f"Expected stored REMU result 0x00000000, observed "
        f"0x{observed_memory:08X}"
    )
