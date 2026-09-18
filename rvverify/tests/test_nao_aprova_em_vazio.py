#!/usr/bin/env python3
"""O validador precisa REPROVAR o que esta errado -- e isso e testado.

REQ: NFR-RV-02 (nada declarado como aprovado sem a ferramenta dizer),
FR-RV-21 (exit code != 0 em caso de erro).

## Por que este arquivo existe

Uma suite de conformidade que aprova tudo e pior que nenhuma: ela produz um
selo de qualidade falso. Este teste guarda exatamente essa propriedade.

O bug que ele previne ja aconteceu neste projeto e passou despercebido por uma
rodada inteira de validacao. `cocotb_tools.runner.test()` so confere o XML de
resultados quando detecta que esta rodando SOB PYTEST -- ele olha a variavel de
ambiente PYTEST_CURRENT_TEST. Fora do pytest, que e exatamente o caso de
`python -m rvverify`, ele devolvia o caminho do XML sem olhar, e uma simulacao
REPROVADA retornava normalmente.

O sintoma: com SRA trocado por deslocamento logico no RTL, a CPU monociclo
recebia "15/15 ok, APROVADO". So um teste de mutacao revelou. A correcao esta
em `builder.run_simulation`, que agora confere o resultado explicitamente e
levanta `SimulationFailed`.

Os dois testes abaixo cobrem os dois lados da propriedade: um caso que DEVE
passar passa, e um caso que DEVE reprovar reprova.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE = REPO_ROOT / "examples" / "RISCV32I"
for _p in (REPO_ROOT, EXAMPLE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

pytestmark = pytest.mark.skipif(
    shutil.which("ghdl") is None,
    reason="GHDL nao esta no PATH; a propriedade so pode ser provada com simulador",
)

RAM_BASE = 0x00FC8100

# 6 * 7 = 42. Programa deliberadamente trivial: o que esta sob teste e o
# VALIDADOR, nao a CPU.
PROGRAMA = f"""
    li   x10, 6
    li   x11, 7
    mul  x12, x10, x11
    li   x18, {RAM_BASE}
    sw   x12, 0(x18)
halt:
    j    halt
"""


def _executar(tmp_path: Path, esperado: int):
    """Roda o programa esperando `esperado` na RAM. Devolve o que aconteceu."""
    from rvverify.asm import assemble_with_symbols, find_halt_addresses, write_ram_image
    from rvverify.builder import build_design, run_simulation
    from rvverify.manifest import load_manifest

    manifest = load_manifest(EXAMPLE / "cpu.toml")
    words, _ = assemble_with_symbols(PROGRAMA, base_address=0, allow_m=True)
    image = write_ram_image(words, tmp_path / "p.ram", header="guarda de vacuidade")

    spec = {
        "manifest": str(manifest.path),
        "name": "guarda",
        "requirements": ["NFR-RV-02"],
        "max_cycles": 500,
        "halt_pcs": find_halt_addresses(words),
        "expect_ram": {hex(RAM_BASE): esperado},
        "report_out": str(tmp_path / "report.json"),
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    params: dict[str, object] = {manifest.program.generic: str(image)}
    if manifest.program.size_generic:
        params[manifest.program.size_generic] = manifest.program.size_words
    if manifest.design.rv32m_generic:
        params[manifest.design.rv32m_generic] = "true"

    built = build_design(manifest)
    return run_simulation(built, test_module="rvverify.tb_generic",
                          parameters=params,
                          extra_env={"RVVERIFY_SPEC": str(spec_path)})


def test_resultado_certo_passa(tmp_path):
    """Controle positivo: sem ele, um validador que reprova tudo passaria."""
    resultados = _executar(tmp_path, esperado=42)
    assert resultados.exists(), "a simulacao deveria ter produzido results.xml"


def test_resultado_errado_REPROVA(tmp_path):
    """A propriedade que importa: valor errado nao pode passar em silencio.

    Este teste falharia com a versao anterior do `run_simulation`, que
    devolvia normalmente mesmo com a simulacao reprovada.
    """
    from rvverify.builder import SimulationFailed

    with pytest.raises(SimulationFailed) as exc:
        _executar(tmp_path, esperado=43)      # 6*7 nao e 43

    msg = str(exc.value)
    assert "reprov" in msg, (
        f"a excecao precisa dizer que a simulacao reprovou; veio: {msg}"
    )


def test_mesma_excecao_dentro_e_fora_do_pytest():
    """`SimulationFailed` e o unico tipo levantado, nos dois contextos.

    O runner do cocotb chama `sys.exit()` sob pytest e nao confere nada fora
    dele. `run_simulation` traduz os dois casos para `SimulationFailed`, de
    modo que quem chama trata UM tipo. Se alguem remover essa traducao, este
    teste falha e o motivo fica escrito aqui.
    """
    import inspect

    from rvverify import builder

    fonte = inspect.getsource(builder.run_simulation)
    assert "except SystemExit" in fonte, (
        "a traducao de SystemExit para SimulationFailed sumiu; sem ela, sob "
        "pytest a excecao volta a ser SystemExit e quem so trata "
        "SimulationFailed passa a aprovar em vazio"
    )
    assert "get_results" in fonte, (
        "a checagem explicita do XML de resultados sumiu; sem ela, fora do "
        "pytest uma simulacao reprovada retorna normalmente"
    )
