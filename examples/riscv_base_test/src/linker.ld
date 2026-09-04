/* =============================================================================
 * examples/riscv_base_test/src/linker.ld
 * Linker script of the mandatory RV32I base test -- GOLDEN FIXTURE (FR-18)
 *
 * .text starts at the reset vector (0x00000000) and .rodata follows inside
 * the same 4 KB instruction ROM, so `objcopy -O binary` produces one
 * contiguous image that the .rm converter can turn into the ROM package.
 * The data RAM (0x00FC8000) is never part of the image: this program
 * initialises everything it uses at run time, so there is no .data/.bss to
 * copy and no startup code beyond _start.
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
