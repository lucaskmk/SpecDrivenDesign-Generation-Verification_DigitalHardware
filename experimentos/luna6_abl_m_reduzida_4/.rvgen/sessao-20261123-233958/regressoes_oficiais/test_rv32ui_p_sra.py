import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM source subset used by this test."""
    entries = []
    labels = {}
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
        entries.append((pc, line))
        pc += 4

    def reg(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected integer register, got {token}")
        number = int(token[1:], 10)
        if not 0 <= number < 32:
            raise ValueError(f"Register out of range: {token}")
        return number

    words = []
    for address, line in entries:
        mnemonic, _, operands = line.partition(" ")
        args = [arg.strip() for arg in operands.split(",")]
        mnemonic = mnemonic.lower()

        if mnemonic == "lui":
            rd = reg(args[0])
            imm = int(args[1], 0)
            word = ((imm & 0xFFFFF) << 12) | (rd << 7) | 0x37
        elif mnemonic == "addi":
            rd, rs1 = reg(args[0]), reg(args[1])
            imm = int(args[2], 0) & 0xFFF
            word = (imm << 20) | (rs1 << 15) | (rd << 7) | 0x13
        elif mnemonic == "sra":
            rd, rs1, rs2 = reg(args[0]), reg(args[1]), reg(args[2])
            word = (
                (0x20 << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x5 << 12)
                | (rd << 7)
                | 0x33
            )
        elif mnemonic == "sw":
            rd = reg(args[0])
            match = re.fullmatch(r"\s*(-?(?:0x[0-9a-fA-F]+|\d+))\s*\(\s*(x\d+)\s*\)\s*", args[1])
            if match is None:
                raise ValueError(f"Invalid store address operand: {args[1]}")
            imm = int(match.group(1), 0) & 0xFFF
            rs1 = reg(match.group(2))
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rd << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        elif mnemonic == "jal":
            rd = reg(args[0])
            target = labels[args[1]]
            imm = target - address
            encoded = imm & 0x1FFFFF
            word = (
                (((encoded >> 20) & 1) << 31)
                | (((encoded >> 1) & 0x3FF) << 21)
                | (((encoded >> 11) & 1) << 20)
                | (((encoded >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

        words.append(word)

    return words


@cocotb.test()
async def sra_with_zero_shift_preserves_positive_value(dut):
    program = assemble_rv32im(
        """
        lui  x1, 0x80000
        addi x1, x1, -1
        sra  x3, x1, x0
        sw   x3, 0(x0)
    halt: jal  x0, halt
        """
    )
    instruction_memory = {4 * index: word for index, word in enumerate(program)}
    data_memory = {}

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    for _ in range(len(program) + 1):
        pc = int(dut.instr_addr.value)
        assert pc in instruction_memory, f"Expected a program instruction at 0x{pc:08X}"
        dut.instr_data.value = instruction_memory[pc]
        await Timer(1, unit="ns")

        is_store = int(dut.data_write.value) == 1
        if is_store:
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected word-store width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x7FFFFFFF, (
                f"Expected SRA result 0x7FFFFFFF, observed 0x{observed_data:08X}"
            )

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if is_store:
            data_memory[observed_addr] = observed_data
            assert data_memory[0x00000000] == 0x7FFFFFFF, (
                f"Expected committed word 0x7FFFFFFF, observed "
                f"0x{data_memory[0x00000000]:08X}"
            )
            break
    else:
        assert False, "Expected the program to reach its result store"
