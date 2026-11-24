import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def _reg(token):
    assert token.startswith("x"), f"Expected register name, observed {token}"
    value = int(token[1:])
    assert 0 <= value < 32, f"Register index out of range: {token}"
    return value


def _u32(value):
    """Return a value constrained to the width of an RV32 word."""
    return value & 0xFFFFFFFF


def _assemble(source):
    """Assemble the small RV32I program used by this diagnostic."""
    instructions = []
    labels = {}

    for line in source:
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = 4 * len(instructions)
            line = line.strip()
            if not line:
                continue
        instructions.append(line)

    words = []
    for pc, line in enumerate(instructions):
        address = 4 * pc
        parts = line.replace(",", " ").replace("(", " ").replace(")", " ").split()
        mnemonic = parts[0].lower()

        if mnemonic == "addi":
            rd, rs1 = _reg(parts[1]), _reg(parts[2])
            imm = int(parts[3], 0) & 0xFFF
            word = (imm << 20) | (rs1 << 15) | (rd << 7) | 0x13

        elif mnemonic == "sw":
            rs2, imm, rs1 = _reg(parts[1]), int(parts[2], 0), _reg(parts[3])
            imm &= 0xFFF
            word = (
                ((imm >> 5) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )

        elif mnemonic == "lui":
            rd = _reg(parts[1])
            upper_imm = int(parts[2], 0) & 0xFFFFF
            word = (upper_imm << 12) | (rd << 7) | 0x37

        elif mnemonic == "jal":
            rd = _reg(parts[1])
            target = labels[parts[2]]
            imm = target - address
            assert -(1 << 20) <= imm < (1 << 20), "JAL target is out of range"
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
            raise AssertionError(f"Unsupported diagnostic instruction: {line}")

        words.append(_u32(word))

    return {4 * index: word for index, word in enumerate(words)}


@cocotb.test()
async def diagnose_lui_value_at_store_boundary(dut):
    program = _assemble(
        [
            "addi x1, x0, 1",
            "sw x1, 0(x0)",
            "lui x1, 0x8",
            "sw x1, 4(x0)",
            "halt: jal x0, halt",
        ]
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = _u32(program[0x00000000])
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    # Keep reset asserted asynchronously, then execute the first instruction.
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    stores = []
    lui_alu_result = None

    # The first ADDI has executed; run SW, LUI, SW, and the halt instruction.
    for _ in range(4):
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        instruction = program.get(pc, program[0x00000010])
        dut.instr_data.value = _u32(instruction)
        dut.data_read_data.value = 0x00000000
        await Timer(1, unit="ns")

        if pc == 0x00000008:
            # Direct read of the simulator-confirmed internal ALU result.
            lui_alu_result = int(dut.alu_result.value)

        if int(dut.data_write.value) == 1:
            stores.append(
                (
                    int(dut.data_addr.value),
                    int(dut.data_write_data.value),
                    int(dut.data_width.value),
                )
            )

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

    expected_first = (0x00000000, 0x00000001, 0x2)
    observed_first = stores[0] if stores else None
    assert observed_first == expected_first, (
        f"Expected control store {expected_first}, observed {observed_first}"
    )

    expected_lui_store = (0x00000004, 0x00008000, 0x2)
    observed_lui_store = stores[1] if len(stores) > 1 else None
    assert observed_lui_store == expected_lui_store, (
        f"Expected LUI-boundary store {expected_lui_store}, observed "
        f"{observed_lui_store}; internal dut.alu_result during LUI was "
        f"{None if lui_alu_result is None else f'0x{lui_alu_result:08X}'}. "
        "A correct control store followed by an incorrect LUI store supports "
        "the stated LUI hypothesis; this does not establish an ADD defect."
    )
