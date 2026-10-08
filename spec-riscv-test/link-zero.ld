ENTRY(_start)
SECTIONS
{
  . = 0x00000000;
  .text.init : { *(.text.init) }
  .text : { *(.text .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  .data : { *(.data .data.*) }
  .bss : { *(.bss .bss.* COMMON) }
  .tohost ALIGN(8) : { *(.tohost) }
  . = ALIGN(16);
  _end = .;
}
