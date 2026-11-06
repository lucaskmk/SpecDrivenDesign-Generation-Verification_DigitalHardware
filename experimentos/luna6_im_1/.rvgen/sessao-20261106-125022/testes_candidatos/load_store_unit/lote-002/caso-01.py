import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the ADDI and LB source instructions used by this test."""
    text = source.strip().lower()

    addi = re.fullmatch(r"addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?\d+)", text)
    if addi:
        rd, rs1, imm = (int(value) for value in addi.groups())
        opcode, funct3 = 0x13, 0x0
    else:
        load = re.fullmatch(
            r"lb\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)", text
        )
        if not load:
            raise ValueError(f"Unsupported instruction source: {source}")
        rd, imm, rs1 = (int(value) for value in load.groups())
        opcode, funct3 = 0x03, 0x0

    if not (0 <= rd <= 31 and 0 <= rs1 <= 31 and -2048 <= imm <= 2047):
        raise ValueError(f"Instruction operand out of range: {source}")

    return (
        ((imm & 0xFFF) << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | opcode
    )


def assemble_rv32im(source):
    """Assemble the RV32I source used here via the RV32I assembler."""
    return assemble_rv32i(source)


@cocotb.test()
async def test_unsupported_instruction_address_passthrough(dut):
    # Establish the recognized-load address pass-through witness.
    dut.instr.value = assemble_rv32i("lb x7, 0(x8)")
    dut.effective_address.value = 0x13579BDA
    dut.store_data_in.value = 0xA1B2C3D4
    dut.data_read_data.value = 0xD3A5C67E
    await Timer(1, unit="ns")

    observed_load_addr = int(dut.data_addr.value)
    assert observed_load_addr == 0x13579BDA, (
        f"expected load data_addr 0x13579BDA, "
        f"observed 0x{observed_load_addr:08X}"
    )

    # ADDI is a legal non-memory instruction; its effective address has the
    # same low-bit offset as the load witness but is otherwise distinct.
    dut.instr.value = assemble_rv32im("addi x5, x6, 17")
    dut.effective_address.value = 0x2468ACE2
    dut.store_data_in.value = 0x5E6F7081
    dut.data_read_data.value = 0x192A3B4C
    await Timer(1, unit="ns")

    observed_addr = int(dut.data_addr.value)
    assert observed_addr == 0x2468ACE2, (
        f"expected unsupported-instruction data_addr 0x2468ACE2, "
        f"observed 0x{observed_addr:08X}"
    )
