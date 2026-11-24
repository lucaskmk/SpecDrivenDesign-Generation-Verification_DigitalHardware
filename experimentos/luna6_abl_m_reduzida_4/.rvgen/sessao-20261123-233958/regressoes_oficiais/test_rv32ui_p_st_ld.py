import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small legal RV32IM subset used by this test."""
    words = []

    def reg(token):
        token = token.strip().lower()
        if not re.fullmatch(r"x(?:[0-9]|[12][0-9]|3[01])", token):
            raise ValueError(f"Unsupported register: {token}")
        return int(token[1:])

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        mnemonic, _, operands = line.partition(" ")
        args = [arg.strip() for arg in operands.split(",")]
        mnemonic = mnemonic.lower()

        if mnemonic == "lui":
            rd = reg(args[0])
            imm20 = int(args[1], 0) & 0xFFFFF
            word = (imm20 << 12) | (rd << 7) | 0x37
        elif mnemonic == "addi":
            rd, rs1 = reg(args[0]), reg(args[1])
            imm = int(args[2], 0) & 0xFFF
            word = (imm << 20) | (rs1 << 15) | (rd << 7) | 0x13
        elif mnemonic in ("lb", "sb", "sw"):
            rt = reg(args[0])
            match = re.fullmatch(r"\s*(-?(?:0x[0-9a-fA-F]+|[0-9]+))\s*\(\s*(x(?:[0-9]|[12][0-9]|3[01]))\s*\)\s*", args[1])
            if not match:
                raise ValueError(f"Invalid memory operand: {args[1]}")
            imm = int(match.group(1), 0) & 0xFFF
            base = reg(match.group(2))
            if mnemonic == "lb":
                word = (imm << 20) | (base << 15) | (rt << 7) | 0x03
            else:
                funct3 = 0 if mnemonic == "sb" else 2
                word = (
                    ((imm >> 5) << 25)
                    | (rt << 20)
                    | (base << 15)
                    | (funct3 << 12)
                    | ((imm & 0x1F) << 7)
                    | 0x23
                )
        else:
            raise ValueError(f"Unsupported instruction: {mnemonic}")

        words.append(word)

    return words


@cocotb.test()
async def signed_byte_store_then_load(dut):
    program = assemble_rv32im(
        """
        lui  x1, 0x1
        addi x2, x0, -35
        sb   x2, 0(x1)
        lb   x3, 0(x1)
        sw   x3, 4(x1)
        """
    )

    # Byte-addressed external memory, initially zero.
    memory = {}

    def read_word(address):
        base = address & 0xFFFFFFFC
        return sum((memory.get(base + lane, 0) & 0xFF) << (8 * lane) for lane in range(4))

    def commit_store(address, width, value):
        byte_count = {0: 1, 1: 2, 2: 4}[width]
        for lane in range(byte_count):
            memory[address + lane] = (value >> (8 * lane)) & 0xFF

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset PC 0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected PC 0x00000000 during reset, observed 0x{int(dut.instr_addr.value):08X}"
    )

    await FallingEdge(dut.clk)
    dut.rst.value = 0

    expected_pc = 0
    for cycle, instruction in enumerate(program):
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        assert pc == expected_pc, (
            f"Expected instruction PC 0x{expected_pc:08X}, observed 0x{pc:08X}"
        )

        dut.instr_data.value = instruction
        await Timer(1, unit="ns")
        address = int(dut.data_addr.value)
        dut.data_read_data.value = read_word(address & 0xFFFFFFFC)
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        width = int(dut.data_width.value)
        write_data = int(dut.data_write_data.value)

        if cycle == 2:  # SB of 0xFFFFFFDD to the test byte.
            assert write == 1, f"Expected SB write enable 1, observed {write}"
            assert address == 0x00000100, (
                f"Expected SB address 0x00000100, observed 0x{address:08X}"
            )
            assert width == 0x0, f"Expected byte width 0x0, observed 0x{width:X}"
            assert write_data == 0xFFFFFFDD, (
                f"Expected unshifted store data 0xFFFFFFDD, observed 0x{write_data:08X}"
            )
        elif cycle == 3:  # LB reads the byte just written and must sign-extend it.
            assert write == 0, f"Expected no write during LB, observed {write}"
            assert address == 0x00000100, (
                f"Expected LB address 0x00000100, observed 0x{address:08X}"
            )
            assert width == 0x2, f"Expected non-memory width 0x2, observed 0x{width:X}"
        elif cycle == 4:  # Architectural witness of the LB result.
            assert write == 1, f"Expected witness SW write enable 1, observed {write}"
            assert address == 0x00000104, (
                f"Expected witness SW address 0x00000104, observed 0x{address:08X}"
            )
            assert width == 0x2, f"Expected word width 0x2, observed 0x{width:X}"
            assert write_data == 0xFFFFFFDD, (
                f"Expected signed LB result 0xFFFFFFDD, observed 0x{write_data:08X}"
            )

        store = (write, address, width, write_data)
        await RisingEdge(dut.clk)
        if store[0]:
            commit_store(store[1], store[2], store[3])
        await Timer(1, unit="ns")
        expected_pc = (expected_pc + 4) & 0xFFFFFFFF

    assert memory.get(0x00000104, 0) == 0xDD, (
        f"Expected final witness byte 0xDD, observed 0x{memory.get(0x00000104, 0):02X}"
    )
    assert memory.get(0x00000105, 0) == 0xFF, (
        f"Expected sign-extended witness byte 0xFF, observed 0x{memory.get(0x00000105, 0):02X}"
    )
