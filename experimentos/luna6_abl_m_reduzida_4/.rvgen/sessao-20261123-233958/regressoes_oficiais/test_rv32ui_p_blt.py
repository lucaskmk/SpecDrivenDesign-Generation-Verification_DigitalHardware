import importlib

import cocotb
from cocotb.triggers import Timer


def _get_assembler():
    for module_name in (
        "rvgen",
        "rvgen.assembler",
        "assembler",
        "assemble_rv32im",
        "riscv_assembler",
    ):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        assembler = getattr(module, "assemble_rv32im", None)
        if assembler is not None:
            return assembler
    raise ImportError("Could not find assemble_rv32im")


def _to_word_map(result):
    if isinstance(result, dict):
        for key in ("instructions", "machine_code", "words"):
            if key in result:
                result = result[key]
                break
        else:
            return {
                int(address, 0) if isinstance(address, str) else int(address): int(word, 0)
                if isinstance(word, str)
                else int(word)
                for address, word in result.items()
            }

    if isinstance(result, (bytes, bytearray)):
        if len(result) % 4:
            raise ValueError("Assembler output must contain complete 32-bit instructions")
        return {
            offset: int.from_bytes(result[offset : offset + 4], "little")
            for offset in range(0, len(result), 4)
        }

    if isinstance(result, str):
        result = [line.strip() for line in result.splitlines() if line.strip()]

    words = {}
    for index, item in enumerate(result):
        if isinstance(item, str):
            text = item.strip()
            word = int(text, 2) if len(text) == 32 and set(text) <= {"0", "1"} else int(text, 0)
        else:
            word = int(item)
        words[index * 4] = word
    return words


@cocotb.test()
async def signed_blt_takes_branch_and_reaches_store(dut):
    source = """
        addi x1, x0, -1
        addi x2, x0, 1
        blt x1, x2, pass
        jal x0, halt
    pass:
        addi x3, x0, 1
        sw x3, 0(x0)
    halt:
        jal x0, halt
    """
    program = _to_word_map(_get_assembler()(source))

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected instr_addr=0x00000000 during reset, observed 0x{observed_pc:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    committed_store = None
    for _ in range(20):
        dut.clk.value = 0
        address = int(dut.instr_addr.value)
        dut.instr_data.value = program.get(address, 0x00000013)
        await Timer(1, unit="ns")

        if int(dut.data_write.value) == 1:
            observed_addr = int(dut.data_addr.value)
            observed_width = int(dut.data_width.value)
            observed_data = int(dut.data_write_data.value)

            assert observed_addr == 0x00000000, (
                f"Expected store address 0x00000000, observed 0x{observed_addr:08X}"
            )
            assert observed_width == 0x2, (
                f"Expected store width 0x2, observed 0x{observed_width:X}"
            )
            assert observed_data == 0x00000001, (
                f"Expected store data 0x00000001, observed 0x{observed_data:08X}"
            )

            dut.clk.value = 1
            committed_store = (observed_addr, observed_width, observed_data)
            await Timer(1, unit="ns")
            break

        dut.clk.value = 1
        await Timer(1, unit="ns")
        dut.clk.value = 0
        await Timer(1, unit="ns")

    assert committed_store == (0x00000000, 0x2, 0x00000001), (
        "Expected the taken signed BLT path to commit SW at address 0x00000000 "
        f"with data 0x00000001, observed {committed_store}"
    )
