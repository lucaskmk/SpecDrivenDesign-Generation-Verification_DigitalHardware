import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


def assemble_rv32im(source):
    """Assemble the small RV32IM subset used by this test."""
    labels = {}
    statements = []
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
        statements.append((pc, line))
        pc += 4

    def reg(token):
        token = token.strip().lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected register, got {token}")
        return int(token[1:])

    def immediate(token):
        return int(token.strip(), 0)

    words = {}
    for pc, line in statements:
        parts = line.replace(",", " ").replace("(", " ").replace(")", " ").split()
        op = parts[0].lower()

        if op == "addi":
            rd, rs1, imm = reg(parts[1]), reg(parts[2]), immediate(parts[3])
            words[pc] = (
                ((imm & 0xFFF) << 20)
                | (rs1 << 15)
                | (rd << 7)
                | 0x13
            )
        elif op == "beq":
            rs1, rs2 = reg(parts[1]), reg(parts[2])
            offset = labels[parts[3]] - pc
            imm = offset & 0x1FFF
            words[pc] = (
                (((imm >> 12) & 1) << 31)
                | (((imm >> 5) & 0x3F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (((imm >> 1) & 0xF) << 8)
                | (((imm >> 11) & 1) << 7)
                | 0x63
            )
        elif op == "sw":
            rs2 = reg(parts[1])
            imm = immediate(parts[2])
            rs1 = reg(parts[3])
            imm &= 0xFFF
            words[pc] = (
                (((imm >> 5) & 0x7F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (0x2 << 12)
                | ((imm & 0x1F) << 7)
                | 0x23
            )
        elif op == "jal":
            rd = reg(parts[1])
            offset = labels[parts[2]] - pc
            imm = offset & 0x1FFFFF
            words[pc] = (
                (((imm >> 20) & 1) << 31)
                | (((imm >> 1) & 0x3FF) << 21)
                | (((imm >> 11) & 1) << 20)
                | (((imm >> 12) & 0xFF) << 12)
                | (rd << 7)
                | 0x6F
            )
        else:
            raise ValueError(f"Unsupported instruction in test program: {op}")

    return words, labels


@cocotb.test()
async def beq_taken_branch_reaches_store(dut):
    program, labels = assemble_rv32im(
        """
        addi x1, x0, 0
        beq x0, x1, success
    fail:
        jal x0, fail
    success:
        addi x2, x0, 64
        addi x3, x0, 85
        sw x3, 0(x2)
    halt:
        jal x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    memory_bytes = {}
    store_count = 0
    branch_checked = False
    saw_expected_store = False

    for _ in range(40):
        await FallingEdge(dut.clk)
        pc = int(dut.instr_addr.value)
        assert pc in program, f"Expected a program instruction at PC=0x{pc:08X}"
        dut.instr_data.value = program[pc]
        await Timer(1, unit="ns")

        write = int(dut.data_write.value)
        store = None
        if write:
            address = int(dut.data_addr.value)
            width = int(dut.data_width.value)
            data = int(dut.data_write_data.value)
            assert address == 0x00000040, (
                f"Expected store address=0x00000040, observed 0x{address:08X}"
            )
            assert width == 0x2, f"Expected store width=0x2, observed 0x{width:X}"
            assert data == 0x00000055, (
                f"Expected store data=0x00000055, observed 0x{data:08X}"
            )
            store = (address, width, data)

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        if pc == labels["success"] - 4:
            observed_pc = int(dut.instr_addr.value)
            assert observed_pc == labels["success"], (
                f"Expected taken BEQ target PC=0x{labels['success']:08X}, "
                f"observed 0x{observed_pc:08X}"
            )
            branch_checked = True

        if store is not None:
            address, width, data = store
            store_count += 1
            for lane in range(1 << width):
                memory_bytes[address + lane] = (data >> (8 * lane)) & 0xFF
            saw_expected_store = True
            break

    assert branch_checked, "Expected the BEQ instruction to execute and reach its target"
    assert saw_expected_store, "Expected the taken BEQ path to produce its witness store"
    assert store_count == 1, f"Expected one store, observed {store_count}"
    observed_word = sum(memory_bytes.get(0x40 + lane, 0) << (8 * lane) for lane in range(4))
    assert observed_word == 0x00000055, (
        f"Expected memory word=0x00000055, observed 0x{observed_word:08X}"
    )
