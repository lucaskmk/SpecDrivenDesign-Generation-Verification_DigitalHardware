/* =============================================================================
 * software/ext_m_test/src/linker.ld
 * REQ: FR-13 (pipeline:FR-20)
 *
 * Same layout contract as the golden base test: .text at the reset vector,
 * .rodata right after it inside the same 4 KB instruction ROM. This program
 * has no .rodata, but the section is kept so both programs go through an
 * identical link step.
 * =========================================================================== */

ENTRY(_start)

MEMORY
{
    ROM (rx) : ORIGIN = 0x00000000, LENGTH = 4K
}

SECTIONS
{
    .text : {
        *(.text)
        *(.text.*)
    } > ROM

    .rodata ALIGN(4) : {
        *(.rodata)
        *(.rodata.*)
    } > ROM

    /DISCARD/ : {
        *(.comment)
        *(.note*)
        *(.riscv.attributes)
        *(.eh_frame*)
    }
}
