import re

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM source subset used by this test."""
    lines = []
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
        lines.append((pc, line))
        pc += 4

    def reg(token):
        match = re.fullmatch(r"x([0-9]|[12][0-9]|3[01])", token.strip())
        if not match:
            raise ValueError(f"Invalid register: {token}")
        return int(match.group(1))

    words = []
    for pc, line in lines:
        fields = line.replace(",", " ").split()
        op = fields[0].lower()

        if op == "lui":
            rd = reg(fields[1])
            imm = int(fields[2], 0)
            if not 0 <= imm < (1 << 20):
                raise ValueError("LUI immediate is outside the unsigned 20-bit range")
            word = (imm << 12) | (rd << 7) | 0x37

        elif op in ("addi", "xori"):
            rd, rs1 = reg(fields[1]), reg(fields[2])
            imm = int(fields[3], 0)
            if not -(1 << 11) <= imm < (1 << 11):
                raise ValueError(f"{op} immediate is outside the signed 12-bit range")
            funct3 = 0x0 if op == "addi" else 0x4
            word = (
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (funct3 << 12)
                | (rd << 7)
                | 0x13
            )

        elif op == "sw":
            rs2 = reg(fields[1])
            match = re.fullmatch(r"([+-]?(?:0x[0-9a-fA-F]+|[0-9]+))\((x(?:[0-9]|[12][0-9]|3[01]))\)", fields[2])
            if not match:
                raise ValueError(f"Invalid SW address: {fields[2]}")
            imm, rs1 = int(match.group(1), 0), reg(match.group(2))
            if not -(1 << 11) <= imm < (1 << 11):
                raise ValueError("SW immediate is outside the signed 12-bit range")
            imm &= 0xFFF
            word = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        elif op == "jal":
            rd = reg(fields[1])
            target = labels[fields[2]]
            imm = target - pc
            if imm & 1 or not -(1 << 20) <= imm < (1 << 20):
                raise ValueError("JAL target is outside the representable range")
            imm &= 0x1FFFFF
            word = (
                (((imm >> 20) & 0x1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 0x1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )

        else:
            raise ValueError(f"Unsupported instruction in test source: {op}")

        words.append(word)

    return words


@cocotb.test()
async def xori_to_x0_does_not_change_x0(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0

    program = assemble_rv32im(
        """
        lui  x1, 0x00ff0
        addi x1, x1, 0x0ff
        xori x0, x1, 0x70f
        sw   x0, 0(x0)
    halt:
        jal  x0, halt
        """
    )
    rom = {address: instruction for address, instruction in enumerate(program)}
    rom = {address * 4: instruction for address, instruction in rom.items()}

    byte_memory = {}
    committed_stores = []

    def read_word(address):
        base = address & 0xFFFFFFFC
        return sum((byte_memory.get(base + lane, 0) & 0xFF) << (8 * lane)
                   for lane in range(4))

    Clock(dut.clk, 10, unit="ns").start()
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, observed "
        f"0x{int(dut.instr_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    focal_store_pc = 0x0000000C
    while not committed_stores:
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        assert pc in rom, f"Expected a mapped instruction at PC=0x{pc:08X}"
        dut.instr_data.value = rom[pc]
        await Timer(1, unit="ns")

        address = int(dut.data_addr.value)
        dut.data_read_data.value = read_word(address)
        await Timer(1, unit="ns")

        write_enable = int(dut.data_write.value)
        if pc == focal_store_pc:
            assert write_enable == 1, (
                f"Expected focal SW data_write=1, observed {write_enable}"
            )
            observed_address = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)
            assert observed_address == 0x00000000, (
                f"Expected SW data_addr=0x00000000, observed "
                f"0x{observed_address:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected SW data_width=0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000000, (
                f"Expected x0 store data=0x00000000 after XORI, observed "
                f"0x{observed_data:08X}"
            )
        else:
            assert write_enable == 0, (
                f"Expected no store at PC=0x{pc:08X}, observed data_write=1"
            )

        captured = None
        if write_enable:
            captured = (
                int(dut.data_addr.value),
                int(dut.data_width.value),
                int(dut.data_write_data.value),
            )

        await RisingEdge(dut.clk)
        if captured is not None:
            store_address, store_width, store_data = captured
            committed_stores.append(captured)
            byte_count = {0x0: 1, 0x1: 2, 0x2: 4}[store_width]
            for lane in range(byte_count):
                byte_memory[store_address + lane] = (store_data >> (8 * lane)) & 0xFF
        await Timer(1, unit="ns")

    assert committed_stores == [(0x00000000, 0x2, 0x00000000)], (
        f"Expected one committed SW of 0x00000000 at 0x00000000, "
        f"observed {committed_stores}"
    )
