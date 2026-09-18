# Lista os devices Cyclone V de verdade instalados na imagem (ADR-016).
# Existe porque um datasheet/placa pode citar um codigo de pedido
# (ex.: "5CEBA4F23C7N") que o campo DEVICE do Quartus nao aceita -- so a
# ferramenta de verdade sabe a string exata. Rodar com:
#   docker run --rm -v "$PWD/docker/quartus_smoketest:/workspace" \
#     quartus-lite:25.1 -t list_parts.tcl
set parts [get_part_list -family "Cyclone V"]
puts "COUNT=[llength $parts]"
foreach p $parts { puts $p }
