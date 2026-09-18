#!/bin/sh
# REQ: FR-RV-41 -- despacha "analyze" pro wrapper Python; qualquer outro
# argumento continua indo direto pro quartus_sh, exatamente como antes
# (ver "Existing Basic Docker Usage" em
# docker/quartus-docker-fpga-analysis-plan.md e o uso ja validado em
# docker/quartus_smoketest/README.md, TRV-8.3 a TRV-8.6). Nao muda
# comportamento nenhum que ja funcionava.
if [ "$1" = "analyze" ]; then
    shift
    exec python3 /usr/local/bin/quartus_analyze.py "$@"
fi
exec quartus_sh "$@"
