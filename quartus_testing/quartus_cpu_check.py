#!/usr/bin/env python3
"""Testa uma CPU no Quartus Prime Lite, pela imagem Docker do projeto.

Recebe a pasta de uma CPU (a que tem o `cpu.toml`) e responde, com numero
tirado de execucao real do Quartus e nunca estimado por fora:

  1. compila ou nao -- e, se nao compila, em que etapa parou e qual o erro
     (arquivo e linha quando o Quartus diz);
  2. frequencia     -- Fmax, slack de setup/hold, fechamento de timing contra
     o clock do `cpu.toml` e o caminho critico;
  3. recursos       -- ALMs, LUTs (ALUTs), registradores, memoria em bloco
     (M10K/MLAB), DSP, PLLs, pinos, LABs;
  4. potencia       -- estatica, dinamica, de E/S e total, sempre rotulada
     como ESTIMATIVA (FR-RV-39).

Alem disso roda, sobre a mesma CPU, as checagens que ja existiam para o
Quartus no repositorio (docker/quartus-lite/quartus_smoketest/ e o wrapper
`analyze`, TRV-8.2 a TRV-8.7): versao da imagem, device instalado, fluxo
completo, Fmax, potencia, caminho critico, netlist RTL sem GUI e `.sof`.

    python quartus_testing/quartus_cpu_check.py cpus/rv32i_pipeline
    python quartus_testing/quartus_cpu_check.py entregas/fulano --isa ambas
    python quartus_testing/quartus_cpu_check.py <pasta> --device 5CEFA9F23C7 --roteamento-agressivo

O projeto Quartus e GERADO a partir do `cpu.toml` -- as mesmas fontes, na
mesma ordem de analise, sem gerar nem inferir fonte nova (FR-RV-36) -- numa
pasta de saida (default `quartus_testing/resultados/<nome>/`), e o Quartus
roda dentro da imagem `quartus-lite:25.1` (ADR-015). Nada disto toca o
veredito do `rvverify` (NFR-RV-06): e uma analise aditiva.

Saida: `relatorio.json` (machine-readable), `relatorio.md` (para gente) e as
evidencias de cada revisao em `quartus_output_<revisao>/`, no mesmo formato
do wrapper `analyze` (FR-RV-41).

Exit code: 0 = todas as revisoes compilam; 1 = alguma nao compila;
2 = problema de entrada ou de ambiente (cpu.toml, Docker, imagem, device).

REQ (repositorio): FR-RV-36 a FR-RV-41, NFR-RV-02, NFR-RV-06.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info < (3, 11):  # pragma: no cover - depende do interpretador
    sys.exit(
        "quartus_cpu_check.py precisa de Python 3.11+ (usa tomllib, como o "
        f"rvverify); este e {sys.version.split()[0]}."
    )

import tomllib

AQUI = Path(__file__).resolve().parent
RAIZ_REPO = AQUI.parent

# Os parsers de fit.summary, sta.summary, pow.summary e da saida de
# report_clock_fmax_summary ja existem no wrapper `analyze` da imagem, e foram
# conferidos contra relatorios reais do Quartus 25.1 (TRV-8.7). Reaproveitados
# daqui, nao reescritos: um formato, um parser.
ANALYZE_PY = RAIZ_REPO / "docker" / "quartus-lite" / "quartus_analyzer" / "analyze.py"

# Nome local que o docker/README.md manda usar, depois o publicado no Docker
# Hub -- quem so deu `docker pull` nao precisa dar `docker tag`.
IMAGENS_PADRAO = ("quartus-lite:25.1", "gabrielgalazzi/imagens_projeto_descomp:25.1")

DEVICE_PADRAO = "5CEBA4F23C7"  # FR-RV-37, ADR-016
MANIFESTO = "cpu.toml"
MARCADOR_SAIDA = ".quartus_testing"
RC_TEMPO_ESGOTADO = 124

# --std do GHDL -> VHDL_INPUT_VERSION do Quartus. O Quartus Lite so conhece
# 1987, 1993 e 2008; 2000/2002 caem em 1993 e 2019 cai em 2008, e o relatorio
# diz qual foi usado.
VHDL_STD = {
    "87": "VHDL_1987",
    "93": "VHDL_1993",
    "93c": "VHDL_1993",
    "00": "VHDL_1993",
    "02": "VHDL_1993",
    "08": "VHDL_2008",
    "19": "VHDL_2008",
}

ETAPA_SINTESE = "Analysis & Synthesis"
ETAPA_FITTER = "Fitter"


class ErroDeEntrada(Exception):
    """cpu.toml ausente/incoerente ou argumento invalido -- exit code 2."""


class ErroDeAmbiente(Exception):
    """Docker, imagem ou device indisponivel -- exit code 2."""


def _carregar_analyze():
    if not ANALYZE_PY.exists():
        raise ImportError(
            f"nao encontrei o wrapper analyze em {ANALYZE_PY}; esta ferramenta "
            "reaproveita os parsers dele e precisa rodar de dentro do repositorio."
        )
    spec = importlib.util.spec_from_file_location("quartus_analyze", ANALYZE_PY)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


analyze = _carregar_analyze()


# --------------------------------------------------------------------------
# cpu.toml -> o que o Quartus precisa
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CpuQuartus:
    """So o pedaco do `cpu.toml` que importa para sintese: fontes, topo,
    generics e clock. [observe], [halt] etc. sao do simulador e ficam de fora
    de proposito -- uma CPU que ainda nao fechou o manifesto de simulacao
    continua podendo ser sintetizada."""

    pasta: Path
    manifesto: Path
    nome: str
    top: str
    std: str
    fontes: tuple[Path, ...]
    generics: dict[str, Any]
    rv32m_generic: str | None
    clock: str
    periodo_ns: float
    # True/False: o topo tem/nao tem porta out/inout/buffer. None: a entidade
    # do topo nao foi achada nas fontes (e o pos-teste de logica removida que
    # pega o caso).
    top_tem_saida: bool | None = None


_RE_COMENTARIO_VHDL = re.compile(r"--[^\n]*")


def top_tem_saida(fontes: tuple[Path, ...], top: str) -> bool | None:
    """O topo declara alguma porta de saida? As CPUs de referencia (e as que
    saem de entregas/_modelo) so tem `clk` e `rst`: o cocotb le tudo por
    dentro da hierarquia. Para a sintese isso e um design sem nada
    observavel, e o Quartus remove TODA a logica -- cpus/rv32i_pipeline
    compilou para 1 ALM e 0 registradores antes desta checagem."""
    re_entidade = re.compile(rf"\bentity\s+{re.escape(top)}\s+is\b(.*?)\bend\b", re.IGNORECASE | re.DOTALL)
    for fonte in fontes:
        texto = _RE_COMENTARIO_VHDL.sub("", fonte.read_text(encoding="utf-8", errors="replace"))
        m = re_entidade.search(texto)
        if not m:
            continue
        portas = re.search(r"\bport\s*\((.*)", m.group(1), re.IGNORECASE | re.DOTALL)
        if not portas:
            return False
        return bool(re.search(r":\s*(out|inout|buffer)\b", portas.group(1), re.IGNORECASE))
    return None


def carregar_cpu(pasta: Path) -> CpuQuartus:
    pasta = Path(pasta)
    if not pasta.is_dir():
        raise ErroDeEntrada(f"{pasta} nao e uma pasta.")
    manifesto = pasta / MANIFESTO
    if not manifesto.exists():
        raise ErroDeEntrada(
            f"{pasta} nao tem {MANIFESTO}. As fontes, a ordem de analise, o topo "
            "e o clock vem dele (FR-RV-36); nada e adivinhado. Copie "
            "entregas/_modelo/cpu.toml e preencha [design] e [clock]."
        )
    try:
        raw = tomllib.loads(manifesto.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ErroDeEntrada(f"{manifesto}: TOML invalido: {exc}") from exc

    design = raw.get("design")
    if not isinstance(design, dict):
        raise ErroDeEntrada(f"{manifesto}: falta a tabela [design].")
    for chave in ("name", "top", "sources"):
        if chave not in design:
            raise ErroDeEntrada(f"{manifesto}: falta [design].{chave}.")
    fontes_rel = design["sources"]
    if not isinstance(fontes_rel, list) or not fontes_rel or not all(
        isinstance(s, str) and s.strip() for s in fontes_rel
    ):
        raise ErroDeEntrada(f"{manifesto}: [design].sources deve ser uma lista nao vazia de caminhos.")
    fontes = tuple((pasta / s).resolve() for s in fontes_rel)
    faltando = [s for s, p in zip(fontes_rel, fontes) if not p.is_file()]
    if faltando:
        raise ErroDeEntrada(
            f"{manifesto}: [design].sources aponta para arquivo(s) que nao existem: "
            + ", ".join(faltando)
        )

    generics = design.get("generics", {})
    if not isinstance(generics, dict):
        raise ErroDeEntrada(f"{manifesto}: [design.generics] deve ser uma tabela.")

    clock = raw.get("clock")
    if not isinstance(clock, dict) or "signal" not in clock or "period_ns" not in clock:
        raise ErroDeEntrada(
            f"{manifesto}: falta [clock] com `signal` e `period_ns` -- sem o clock "
            "nao ha .sdc, e sem .sdc nenhum Fmax significa nada (FR-RV-38)."
        )
    periodo = clock["period_ns"]
    if isinstance(periodo, bool) or not isinstance(periodo, (int, float)) or periodo <= 0:
        raise ErroDeEntrada(f"{manifesto}: [clock].period_ns deve ser um numero positivo.")

    std = str(design.get("std", "08"))
    if std not in VHDL_STD:
        raise ErroDeEntrada(
            f"{manifesto}: [design].std = {std!r} nao tem equivalente no Quartus "
            f"(aceitos: {', '.join(VHDL_STD)})."
        )

    return CpuQuartus(
        pasta=pasta.resolve(),
        manifesto=manifesto.resolve(),
        nome=str(design["name"]),
        top=str(design["top"]),
        std=std,
        fontes=fontes,
        generics=dict(generics),
        rv32m_generic=design.get("rv32m_generic"),
        clock=str(clock["signal"]),
        periodo_ns=float(periodo),
        top_tem_saida=top_tem_saida(fontes, str(design["top"])),
    )


@dataclass(frozen=True)
class Revisao:
    nome: str
    generics: dict[str, Any]
    descricao: str


def revisoes_para(cpu: CpuQuartus, isa: str) -> list[Revisao]:
    """`padrao` sintetiza com os generics do manifesto e os defaults do VHDL.
    `rv32i`/`rv32im` alternam o rv32m_generic como o rvverify faz, e `ambas`
    poe a baseline RV32I antes da RV32IM (constituicao, principio 9)."""
    if isa == "padrao":
        return [Revisao("padrao", dict(cpu.generics), "generics do cpu.toml e defaults do VHDL")]
    if not cpu.rv32m_generic:
        raise ErroDeEntrada(
            f"{cpu.manifesto}: --isa {isa} precisa de [design].rv32m_generic, "
            "que este cpu.toml nao declara. Use --isa padrao."
        )
    g = cpu.rv32m_generic
    rv32i = Revisao("rv32i", {**cpu.generics, g: False}, f"{g} = false (baseline RV32I)")
    rv32im = Revisao("rv32im", {**cpu.generics, g: True}, f"{g} = true (RV32IM)")
    return {"rv32i": [rv32i], "rv32im": [rv32im], "ambas": [rv32i, rv32im]}[isa]


def familia_do_device(device: str) -> str | None:
    d = device.upper()
    for prefixo, familia in (("5C", "Cyclone V"), ("10M", "MAX 10"),
                             ("10CL", "Cyclone 10 LP"), ("EP4CE", "Cyclone IV E")):
        if d.startswith(prefixo):
            return familia
    return None


def nome_quartus(texto: str) -> str:
    nome = re.sub(r"[^A-Za-z0-9_]", "_", texto).strip("_") or "cpu"
    return nome if nome[0].isalpha() else f"cpu_{nome}"


# --------------------------------------------------------------------------
# projeto Quartus gerado
# --------------------------------------------------------------------------

def _valor_tcl(valor: Any) -> str | None:
    """Valor de generic para `set_parameter`. Booleano como true/false (o
    formato que ja compilou em implemetation_tests/opus_5_RISCVIM/fpga).
    String vazia volta None: o Quartus recusa `set_parameter` com string vazia
    (Error 125042, visto la), e o default do VHDL e o mesmo caminho."""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, str):
        if valor == "":
            return None
        return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise ErroDeEntrada(f"generic com valor de tipo nao suportado: {valor!r}")


@dataclass
class Projeto:
    pasta: Path
    nome: str
    sdc: str
    fontes: dict[str, str]          # nome copiado em src/ -> caminho original
    generics_ignorados: dict[str, list[str]] = field(default_factory=dict)
    preservar_logica: bool = False


def gerar_projeto(cpu: CpuQuartus, pasta: Path, revisoes: list[Revisao], *,
                  device: str, familia: str, periodo_ns: float,
                  roteamento_agressivo: bool, preservar_logica: bool = False) -> Projeto:
    """Escreve <nome>.qpf, comum.tcl, uma .qsf por revisao, o .sdc e copia as
    fontes para src/, na ordem do cpu.toml.

    Copiar (e nao apontar para fora) deixa o projeto montavel sozinho no
    container: o cpu.toml de uma entrega aponta para ../../cpus/..., e montar
    so a pasta da CPU deixaria essas fontes fora do alcance do Quartus. O
    conteudo e byte a byte o mesmo -- FR-RV-36 continua valendo.

    Mesmo desenho de implemetation_tests/opus_5_RISCVIM/fpga: tudo o que e
    comum fica num so comum.tcl, e cada revisao so declara seus generics --
    o A/B RV32I x RV32IM so vale se essa for a unica diferenca."""
    nome = nome_quartus(cpu.nome)
    src = pasta / "src"
    src.mkdir(parents=True, exist_ok=True)
    copiadas: dict[str, str] = {}
    for i, fonte in enumerate(cpu.fontes):
        destino = fonte.name if fonte.name not in copiadas else f"{i:02d}_{fonte.name}"
        shutil.copy2(fonte, src / destino)
        copiadas[destino] = _relativo(fonte)

    sdc = f"{nome}.sdc"
    (pasta / sdc).write_text(
        "# Gerado por quartus_testing/quartus_cpu_check.py a partir de [clock]\n"
        f"# de {_relativo(cpu.manifesto)}. REQ: FR-RV-38 -- sem esta restricao o\n"
        "# Quartus inventa um clock de 1 ns e nenhum Fmax significa nada.\n"
        f"create_clock -name {{{cpu.clock}}} -period {periodo_ns:.3f} [get_ports {{{cpu.clock}}}]\n"
        "derive_clock_uncertainty\n",
        encoding="utf-8",
    )

    linhas = [
        "# Gerado por quartus_testing/quartus_cpu_check.py -- comum a todas as revisoes.",
        f"# Fontes e ordem de analise: [design].sources de {_relativo(cpu.manifesto)}.",
        f'set_global_assignment -name FAMILY "{familia}"',
        f"set_global_assignment -name DEVICE {device}",
        f"set_global_assignment -name TOP_LEVEL_ENTITY {cpu.top}",
        "set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files",
        "set_global_assignment -name MIN_CORE_JUNCTION_TEMP 0",
        "set_global_assignment -name MAX_CORE_JUNCTION_TEMP 85",
        f"set_global_assignment -name VHDL_INPUT_VERSION {VHDL_STD[cpu.std]}",
        "set_global_assignment -name VHDL_SHOW_LMF_MAPPING_MESSAGES OFF",
    ]
    if roteamento_agressivo:
        # A opcao que o proprio Quartus recomenda no Critical Warning 188026
        # (falha de roteamento). Opcao de FERRAMENTA: o RTL nao muda.
        linhas += [
            "set_global_assignment -name ROUTER_TIMING_OPTIMIZATION_LEVEL MAXIMUM",
            "set_global_assignment -name FITTER_AGGRESSIVE_ROUTABILITY_OPTIMIZATION ALWAYS",
        ]
    if preservar_logica:
        # O topo nao tem saida: sem isto o Quartus remove TODA a logica (nada
        # e observavel) e reporta 1 ALM. Na raiz (|), PRESERVE_FANOUT_FREE_NODE
        # equivale ao atributo noprune em todo registrador -- opcao de
        # ferramenta, o RTL nao muda. Conferido em execucao real: a forma
        # global nao existe (Error 125091), wildcard e ignorado (Critical
        # Warning 136017) e `-to <entidade do topo>` nao pega; so a raiz.
        linhas.append('set_instance_assignment -name PRESERVE_FANOUT_FREE_NODE ON -to "|"')
    linhas += [f"set_global_assignment -name VHDL_FILE src/{n}" for n in copiadas]
    linhas.append(f"set_global_assignment -name SDC_FILE {sdc}")
    (pasta / "comum.tcl").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    ignorados: dict[str, list[str]] = {}
    for rev in revisoes:
        qsf = [
            f"# Revisao {rev.nome}: {rev.descricao}.",
            "set_global_assignment -name SOURCE_TCL_SCRIPT_FILE comum.tcl",
        ]
        for nome_g, valor in rev.generics.items():
            tcl = _valor_tcl(valor)
            if tcl is None:
                ignorados.setdefault(rev.nome, []).append(nome_g)
                qsf.append(f"# {nome_g} = \"\" fica no default do VHDL (Quartus recusa string vazia)")
            else:
                qsf.append(f"set_parameter -name {nome_g} {tcl}")
        (pasta / f"{rev.nome}.qsf").write_text("\n".join(qsf) + "\n", encoding="utf-8")

    (pasta / f"{nome}.qpf").write_text(
        'QUARTUS_VERSION = "25.1"\n\n# Revisions\n\n'
        + "".join(f'PROJECT_REVISION = "{r.nome}"\n' for r in revisoes),
        encoding="utf-8",
    )
    return Projeto(pasta=pasta, nome=nome, sdc=sdc, fontes=copiadas, generics_ignorados=ignorados,
                   preservar_logica=preservar_logica)


def _relativo(caminho: Path) -> str:
    try:
        return Path(caminho).resolve().relative_to(RAIZ_REPO).as_posix()
    except ValueError:
        return str(caminho)


# --------------------------------------------------------------------------
# parsers novos (os demais vem de analyze.py)
# --------------------------------------------------------------------------

_RE_INICIO_ETAPA = re.compile(r"^Info: Running Quartus Prime (.+?)\s*$")
_RE_FIM_ETAPA = re.compile(
    r"^(?:Info|Error)(?: \(\d+\))?: Quartus Prime (.+?) was (successful|unsuccessful)\."
    r" (\d+) errors?, (\d+) warnings?"
)
_RE_ERRO = re.compile(r"^(\s*)Error(?: \((\d+)\))?: (.*)$")
_RE_AVISO_CRITICO = re.compile(r"^(\s*)Critical Warning(?: \((\d+)\))?: (.*)$")
_RE_ARQUIVO_LINHA = re.compile(r"([\w.\-/\\]+\.vhdl?)\((\d+)\)", re.IGNORECASE)
_ETAPAS_DE_FORA = {"Shell", "Full Compilation"}

# Linhas "Error:" que sao so o eco do resumo de cada executavel, nao um erro
# do design. Ficariam repetidas em todo log de falha e esconderiam o erro de
# verdade (o 170012, o 10500...).
_RUIDO = tuple(re.compile(p) for p in (
    r"^Quartus Prime .+ was (?:un)?successful",
    r"^(?:Peak virtual memory|Processing (?:ended|started)|Elapsed time|Total CPU time)",
    r"^Flow compile .* was not successful",
    r"^ERROR: Error\(s\) found while running an executable",
    r"^Evaluation of Tcl script .* unsuccessful",
))


def parse_compile_log(texto: str, fontes: dict[str, str] | None = None) -> dict:
    """Etapas do `quartus_sh --flow compile`, o veredito da compilacao e os
    erros que importam, cada um com a etapa em que apareceu e, quando o
    Quartus cita, arquivo e linha -- traduzidos de volta para o caminho
    original da fonte (`fontes`: nome em src/ -> caminho no repositorio)."""
    fontes = fontes or {}
    por_nome = {Path(k).name.lower(): v for k, v in fontes.items()}
    etapas: list[dict] = []
    abertas: dict[str, dict] = {}
    atual: str | None = None
    erros: list[dict] = []
    avisos: list[dict] = []
    compila: bool | None = None

    for linha in texto.splitlines():
        m = _RE_INICIO_ETAPA.match(linha)
        if m:
            nome = m.group(1)
            if nome not in _ETAPAS_DE_FORA:
                etapa = {"etapa": nome, "status": "incompleta", "erros": None, "avisos": None}
                etapas.append(etapa)
                abertas[nome] = etapa
                atual = nome
            continue
        m = _RE_FIM_ETAPA.match(linha)
        if m:
            nome, resultado = m.group(1), m.group(2)
            if nome == "Full Compilation":
                compila = resultado == "successful"
            elif nome in abertas:
                abertas[nome].update(
                    status="ok" if resultado == "successful" else "falhou",
                    erros=int(m.group(3)), avisos=int(m.group(4)),
                )
                atual = None
            continue
        m = _RE_ERRO.match(linha)
        if m:
            msg = m.group(3).strip()
            if any(r.match(msg) for r in _RUIDO) or m.group(2) in ("293001", "23031"):
                continue
            erros.append(_mensagem(m, atual, por_nome))
            continue
        m = _RE_AVISO_CRITICO.match(linha)
        if m:
            avisos.append(_mensagem(m, atual, por_nome))

    falhou = next((e["etapa"] for e in etapas if e["status"] == "falhou"), None)
    if falhou is None and compila is not True:
        # Sem "Full Compilation was successful" e sem etapa reprovada: o
        # processo morreu no meio (tempo esgotado, falta de memoria, Ctrl+C).
        falhou = next((e["etapa"] for e in etapas if e["status"] == "incompleta"), None)
    return {
        "compila": bool(compila),
        "etapa_que_falhou": falhou,
        "etapas": etapas,
        "erros": erros,
        "avisos_criticos": avisos,
    }


def _mensagem(m: re.Match, etapa: str | None, por_nome: dict[str, str]) -> dict:
    # O Quartus completa a mensagem com "File: /workspace/src/x.vhd" -- o
    # caminho de dentro do container, que nao existe para quem le.
    msg = re.sub(r"/workspace/src/([\w.\-]+)",
                 lambda a: por_nome.get(a.group(1).lower(), a.group(0)), m.group(3).strip())
    item = {"id": m.group(2), "etapa": etapa, "mensagem": msg, "detalhe": bool(m.group(1))}
    a = _RE_ARQUIVO_LINHA.search(msg)
    if a:
        base = Path(a.group(1).replace("\\", "/")).name.lower()
        item["arquivo"] = por_nome.get(base, a.group(1))
        item["linha"] = int(a.group(2))
    return item


def classificar_falha(compilacao: dict, utilizacao_alm_pct: float | None) -> tuple[str | None, str | None]:
    """(motivo, dica) para uma compilacao reprovada. Os IDs vem dos logs reais
    de implemetation_tests/opus_5_RISCVIM/fpga: 170012 (nao cabe: falta LAB),
    188026/170143 (cabe, mas nao roteia)."""
    if compilacao["compila"]:
        return None, None
    etapa = compilacao["etapa_que_falhou"]
    ids = {e["id"] for e in compilacao["erros"]} | {a["id"] for a in compilacao["avisos_criticos"]}
    incompleta = compilacao.get("tempo_esgotado") or any(
        e["etapa"] == etapa and e["status"] == "incompleta" for e in compilacao["etapas"])
    if etapa is None or incompleta:
        return ("compilacao_incompleta",
                "O Quartus nao chegou ao fim" + (f" (parou durante {etapa})" if etapa else "")
                + ": tempo esgotado (--timeout-min), falta de memoria no Docker ou projeto "
                "invalido. Veja o compile.log e o analyze.log.")
    if etapa == ETAPA_SINTESE:
        return ("erro_de_sintese",
                "O VHDL nao passou pela analise e sintese do Quartus. Veja os erros "
                "(arquivo e linha): o Quartus e mais estrito que o GHDL em construcoes "
                "de sintese, entao uma CPU aprovada no rvverify ainda pode reprovar aqui.")
    if etapa == ETAPA_FITTER:
        if "170012" in ids or (utilizacao_alm_pct is not None and utilizacao_alm_pct > 100):
            return ("nao_cabe",
                    "O design pede mais recursos do que o device tem. Reduza a area "
                    "(uma memoria de leitura assincrona nao vira M10K e vira registradores "
                    "mais mux) ou teste num device maior com --device, sabendo que esse "
                    "numero nao vale para o alvo.")
        if "188026" in ids or "170143" in ids:
            return ("nao_roteia",
                    "Coube, mas o roteamento falhou. O proprio Quartus recomenda a "
                    "otimizacao agressiva de roteabilidade: rode de novo com "
                    "--roteamento-agressivo (opcao de ferramenta, o RTL nao muda).")
        return "falha_no_fitter", "O Fitter reprovou; veja os erros abaixo."
    return f"falha_em_{nome_quartus(etapa).lower()}", f"A etapa {etapa} reprovou; veja os erros abaixo."


def parse_tabela_recursos(texto: str) -> dict[str, dict[str, str]]:
    """Tabela "Fitter Resource Usage Summary" do <rev>.fit.rpt, linha a
    linha: {recurso: {"uso": ..., "percentual": ...}}. E dela que saem as
    LUTs (ALUTs) e os blocos M10K -- o fit.summary nao traz nenhum dos dois.
    O Quartus escreve a tabela mesmo quando o fit reprova, com o uso acima de
    100 %, que e exatamente o numero que explica a reprovacao."""
    linhas = texto.splitlines()
    inicio = next((i for i, l in enumerate(linhas) if l.startswith("; Fitter Resource Usage Summary")), None)
    if inicio is None:
        return {}
    tabela: dict[str, dict[str, str]] = {}
    comecou = False
    for linha in linhas[inicio + 1:]:
        if linha.startswith("+"):
            continue
        if not linha.startswith(";"):
            if comecou:
                break
            continue
        celulas = [c.strip() for c in linha.strip().strip(";").split(";")]
        if len(celulas) < 2 or celulas[0] in ("", "Resource"):
            comecou = comecou or celulas[0] == "Resource"
            continue
        comecou = True
        nome = re.sub(r"\s+", " ", re.sub(r"^--\s*", "", celulas[0]))
        tabela.setdefault(nome, {"uso": celulas[1], "percentual": celulas[2] if len(celulas) > 2 else ""})
    return tabela


def _uso(linha: dict[str, str] | None) -> dict | None:
    """'21,851 / 113,560' + '19 %' -> {usado, total, percentual, qualificador}."""
    if not linha:
        return None
    m = re.match(r"^([\d,]+)(?:\s*/\s*([\d,]+))?$", linha["uso"])
    if not m:
        return None
    out = {
        "usado": int(m.group(1).replace(",", "")),
        "total": int(m.group(2).replace(",", "")) if m.group(2) else None,
        "percentual": None,
        "qualificador": None,
    }
    p = re.match(r"^([<>]?)\s*([\d.]+)\s*%$", linha.get("percentual", ""))
    if p:
        out["percentual"] = float(p.group(2))
        out["qualificador"] = p.group(1) or None
    return out


def _int(linha: dict[str, str] | None) -> int | None:
    u = _uso(linha)
    return u["usado"] if u else None


_RE_TNS = re.compile(r"Type\s*:\s*(.+?)\n\s*Slack\s*:\s*(-?[\d.]+)\n\s*TNS\s*:\s*(-?[\d.]+)")


def pior_tns_setup(sta_summary: str) -> float | None:
    valores = [float(t) for tipo, _, t in _RE_TNS.findall(sta_summary) if "Setup" in tipo]
    return min(valores) if valores else None


def parse_caminho_critico(texto: str) -> dict | None:
    """Saida de `report_timing -setup -npaths 1 -detail path_only -stdout`
    (formato conferido em
    implemetation_tests/opus_5_RISCVIM/fpga/quartus_output_*/reports/critical_path.log)."""
    m = re.search(r"Path #1: Setup slack is (-?[\d.]+)(?: \((\w+)\))?", texto)
    if not m:
        return None

    def campo(rotulo: str) -> str | None:
        c = re.search(rf"{rotulo}\s*:\s*(.+?)\s*$", texto, re.MULTILINE)
        return c.group(1) if c else None

    def numero(rotulo: str) -> float | None:
        c = re.search(rf"{rotulo}\s*:\s*(-?[\d.]+)", texto)
        return float(c.group(1)) if c else None

    chegada = texto.split("Data Arrival Path:", 1)[-1].split("Data Required Path:", 1)[0]
    celulas = len(re.findall(r"^\s*Info \(332115\):\s+[\d.]+\s+-?[\d.]+\s+\w*\s+CELL\s", chegada, re.MULTILINE))
    return {
        "slack_ns": float(m.group(1)),
        "situacao": m.group(2),
        "de": campo("From Node"),
        "para": campo("To Node"),
        "clock_lancamento": campo("Launch Clock"),
        "clock_captura": campo("Latch Clock"),
        "chegada_ns": numero("Data Arrival Time"),
        "requerido_ns": numero("Data Required Time"),
        "celulas_no_caminho": celulas or None,
    }


def avaliar_restricao(compile_log: str) -> tuple[bool, bool, list[str]]:
    """(restrito, confiavel, motivos). FR-RV-38: sem a restricao de clock
    aplicada de verdade, o Fmax e marcado como nao confiavel -- inclusive
    quando o .sdc existe mas o `get_ports {clk}` nao casou com porta nenhuma
    (nome de clock errado no cpu.toml), que o Quartus so avisa."""
    motivos: list[str] = []
    restrito = True
    if analyze.NO_SDC_MARKER in compile_log:
        restrito = False
        motivos.append("o Quartus nao encontrou o .sdc")
    for m in re.finditer(r"^\s*Warning \((332049|332174)\): (.*)$", compile_log, re.MULTILINE):
        if m.group(1) == "332049" and "create_clock" in m.group(2):
            restrito = False
        motivos.append(f"Warning ({m.group(1)}): {m.group(2).strip()}")
    sem_restricao = re.findall(r"Warning \(332060\): (.*)$", compile_log, re.MULTILINE)
    motivos += [f"Warning (332060): {msg.strip()}" for msg in sem_restricao]
    # O Fitter e o TimeQuest leem o .sdc cada um: o mesmo aviso sai duas vezes.
    return restrito, restrito and not sem_restricao, list(dict.fromkeys(motivos))


# --------------------------------------------------------------------------
# Docker
# --------------------------------------------------------------------------

class Docker:
    """Roda a imagem do Quartus. Isolado numa classe para os testes trocarem
    por um falso, sem Docker nem Quartus."""

    def __init__(self, executavel: str = "docker"):
        self.executavel = executavel
        self.imagem: str | None = None

    def _cli(self, *args: str, timeout: float = 120) -> subprocess.CompletedProcess:
        return subprocess.run([self.executavel, *args], capture_output=True, text=True, timeout=timeout)

    def conferir_servidor(self) -> str:
        try:
            p = self._cli("version", "--format", "{{.Server.Version}}")
        except FileNotFoundError as exc:
            raise ErroDeAmbiente(f"comando `{self.executavel}` nao encontrado no PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise ErroDeAmbiente("o Docker nao respondeu em 120 s.") from exc
        if p.returncode != 0:
            detalhe = (p.stderr or p.stdout).strip().splitlines()
            raise ErroDeAmbiente(
                "o Docker nao esta rodando (abra o Docker Desktop ou inicie o daemon). "
                + (detalhe[-1] if detalhe else "")
            )
        return p.stdout.strip()

    def escolher_imagem(self, candidatas: tuple[str, ...]) -> str:
        for imagem in candidatas:
            if self._cli("image", "inspect", imagem).returncode == 0:
                self.imagem = imagem
                return imagem
        raise ErroDeAmbiente(
            "nenhuma imagem do Quartus encontrada (" + ", ".join(candidatas) + "). Puxe a "
            "publicada:\n  docker pull gabrielgalazzi/imagens_projeto_descomp:25.1\nou "
            "builde a local (ver docker/README.md):\n  docker build -t quartus-lite:25.1 docker/quartus-lite"
        )

    def rodar(self, pasta: Path, args: list[str], log: Path | None, *,
              entrypoint: str | None = None, timeout_s: float | None = None) -> int:
        nome = f"quartus-testing-{uuid.uuid4().hex[:12]}"
        cmd = [self.executavel, "run", "--rm", "--name", nome,
               "-v", f"{Path(pasta).resolve()}:/workspace", "-w", "/workspace"]
        if entrypoint:
            cmd += ["--entrypoint", entrypoint]
        cmd += [self.imagem, *args]
        if log is not None:
            log.parent.mkdir(parents=True, exist_ok=True)
        destino = open(log, "wb") if log is not None else subprocess.DEVNULL
        try:
            proc = subprocess.Popen(cmd, stdout=destino, stderr=subprocess.STDOUT)
            try:
                return proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                self._matar(nome)
                proc.wait()
                if log is not None:
                    destino.close()
                    with open(log, "a", encoding="utf-8") as f:
                        f.write(f"\n[quartus_testing] tempo esgotado apos {timeout_s:.0f} s; "
                                f"container {nome} encerrado.\n")
                return RC_TEMPO_ESGOTADO
            except KeyboardInterrupt:
                self._matar(nome)
                proc.wait()
                raise
        finally:
            if log is not None and not destino.closed:
                destino.close()

    def _matar(self, nome: str) -> None:
        try:
            self._cli("kill", nome, timeout=60)
        except (subprocess.TimeoutExpired, OSError):
            pass

    def devolver_dono(self, pasta: Path) -> None:
        """O Quartus roda como root no container; num Docker Engine nativo
        (sem o mapeamento do Docker Desktop) o que ele grava fica de root no
        host. Devolve a pasta ao usuario que rodou o script."""
        if os.name != "posix" or not hasattr(os, "getuid"):
            return
        self.rodar(pasta, ["-R", f"{os.getuid()}:{os.getgid()}", "/workspace"], None, entrypoint="chown")

    def remover(self, alvo: Path) -> None:
        """rmtree com o proprio container como plano B, para sobra de uma
        execucao interrompida antes do chown."""
        try:
            shutil.rmtree(alvo)
        except PermissionError:
            self.rodar(alvo.parent, ["-rf", f"/workspace/{alvo.name}"], None, entrypoint="rm")
            if alvo.exists():
                raise ErroDeAmbiente(f"nao consegui apagar {alvo}; apague a mao e rode de novo.")


# --------------------------------------------------------------------------
# execucao
# --------------------------------------------------------------------------

def _tcl_device(familia: str, device: str) -> str:
    return (
        "# Mesmo teste de docker/quartus-lite/quartus_smoketest/list_parts.tcl\n"
        "# (ADR-016): so a ferramenta sabe a string exata do device.\n"
        f"set parts [get_part_list -family {{{familia}}}]\n"
        'puts "QT_DEVICE_COUNT=[llength $parts]"\n'
        f"if {{[lsearch -exact $parts {{{device.upper()}}}] >= 0}} "
        '{ puts "QT_DEVICE_FOUND=1" } else { puts "QT_DEVICE_FOUND=0" }\n'
    )


def _tcl_caminho_critico(projeto: str, rev: str) -> str:
    return (
        "# Mesmo teste de implemetation_tests/opus_5_RISCVIM/fpga/report_critical_path.tcl\n"
        f"project_open {projeto} -revision {rev}\n"
        "create_timing_netlist\nread_sdc\nupdate_timing_netlist\n"
        "report_timing -setup -npaths 1 -detail path_only -panel_name {Critical} -stdout\n"
        "delete_timing_netlist\nproject_close\n"
    )


def _tcl_netlist(projeto: str, rev: str) -> str:
    return (
        "# Mesmo teste de docker/quartus-lite/quartus_smoketest/report_netlist.tcl\n"
        "# (FR-RV-40): a netlist RTL e acessivel sem GUI, via ::quartus::rtl.\n"
        f"project_open {projeto} -revision {rev}\n"
        "load_rtl_netlist\n"
        'puts "QT_RTL_CELLS=[llength [get_rtl_cells *]]"\n'
        "unload_rtl_netlist\nproject_close\n"
    )


def _ler(caminho: Path) -> str | None:
    return caminho.read_text(encoding="utf-8", errors="replace") if caminho.exists() else None


def _duracao(t0: float) -> float:
    return round(time.monotonic() - t0, 1)


def _checagem(id_: str, nome: str, req: str, status: str, detalhe: str = "") -> dict:
    return {"id": id_, "checagem": nome, "req": req, "status": status, "detalhe": detalhe}


def montar_recursos(fit_summary: str | None, fit_rpt: str | None, map_summary: str | None) -> dict | None:
    """Recursos da FPGA. Com fit: numeros do Fitter (alocacao real no
    device). Sem fit mas com sintese: so o que a sintese ja sabe, rotulado
    como tal -- ALM e LUT so existem depois do fit."""
    if fit_summary:
        fit = analyze.parse_fit_summary(fit_summary)
        t = parse_tabela_recursos(fit_rpt or "")
        alms = _uso(t.get("Logic utilization (ALMs needed / total ALMs on device)")) or {
            "usado": fit["logic_alms_used"], "total": fit["logic_alms_total"],
            "percentual": fit["logic_utilization_percent"],
            "qualificador": fit["logic_utilization_percent_qualifier"],
        }
        bits = _uso(t.get("Total block memory bits")) or {
            "usado": fit["block_memory_bits_used"], "total": fit["block_memory_bits_total"],
            "percentual": None, "qualificador": None,
        }
        entradas = {k.split()[0]: _int(t.get(k)) for k in (
            "7 input functions", "6 input functions", "5 input functions",
            "4 input functions", "<=3 input functions") if t.get(k)}
        recursos = {
            "fonte": "fitter",
            "device": fit["device"],
            "status_fit": fit["status"],
            "cabe": fit["fits"],
            "alms": alms,
            "alms_em_uso_no_placement": _uso(t.get("[A] ALMs used in final placement [=a+b+c+d]")),
            "labs": _uso(t.get("Total LABs: partially or completely used")),
            "luts": {
                "aluts_logica": _int(t.get("Combinational ALUT usage for logic")),
                "aluts_route_through": _int(t.get("Combinational ALUT usage for route-throughs")),
                "por_numero_de_entradas": entradas or None,
            },
            "registradores": _int(t.get("Dedicated logic registers")) or fit["registers"],
            "pinos": _uso(t.get("I/O pins")) or {"usado": fit["pins_used"], "total": fit["pins_total"],
                                                 "percentual": None, "qualificador": None},
            "memoria": {
                "bits_em_bloco": bits,
                "blocos_m10k": _uso(t.get("M10K blocks")),
                "bits_mlab": _int(t.get("Total MLAB memory bits")),
                "alms_como_memoria": _int(t.get("[d] ALMs used for memory (up to half of total ALMs)")),
            },
            "dsp": _uso(t.get("Total DSP Blocks")) or {"usado": fit["dsp_blocks_used"], "total": fit["dsp_blocks_total"],
                                                       "percentual": None, "qualificador": None},
            "plls": _uso(t.get("Fractional PLLs")) or {"usado": fit["plls_used"], "total": fit["plls_total"],
                                                       "percentual": None, "qualificador": None},
            "clocks_globais": _uso(t.get("Global clocks")),
            "dificuldade_de_empacotamento": (t.get("Difficulty packing design") or {}).get("uso"),
            "interconexao_media": (t.get("Average interconnect usage (total/H/V)") or {}).get("uso"),
            "interconexao_pico": (t.get("Peak interconnect usage (total/H/V)") or {}).get("uso"),
            "fan_out_maximo": _int(t.get("Maximum fan-out")),
            "tabela_do_fitter": t or None,
        }
        mem = recursos["memoria"]
        if (mem["bits_em_bloco"] or {}).get("usado") == 0 and not mem["bits_mlab"]:
            recursos["nota_memoria"] = (
                "Nenhum bit em M10K nem em MLAB: as memorias do design, se houver (banco "
                "de registradores, RAM de dados, ROM), viraram registradores e logica. "
                "M10K e sincrona; memoria de leitura assincrona nao e inferida nela."
            )
        return recursos
    kv = analyze.parse_kv_report(map_summary or "")
    # Sintese reprovada tambem grava map.summary, mas com "Failed" e todo
    # campo "N/A until Partition Merge": nao ha numero nenhum para mostrar.
    if kv.get("Analysis & Synthesis Status", "").startswith("Successful"):

        def inteiro(chave: str) -> int | None:
            v = kv.get(chave, "").replace(",", "")
            return int(v) if v.isdigit() else None

        return {
            "fonte": "sintese",
            "nota": "O Fitter nao rodou: so ha os numeros da sintese. ALMs, LUTs e "
                    "percentuais do device so existem depois do fit.",
            "registradores": inteiro("Total registers"),
            "pinos": {"usado": inteiro("Total pins"), "total": None, "percentual": None, "qualificador": None},
            "memoria": {"bits_em_bloco": {"usado": inteiro("Total block memory bits"), "total": None,
                                          "percentual": None, "qualificador": None}},
            "dsp": {"usado": inteiro("Total DSP Blocks"), "total": None, "percentual": None, "qualificador": None},
            "plls": {"usado": inteiro("Total PLLs"), "total": None, "percentual": None, "qualificador": None},
        }
    return None


def montar_potencia(pow_summary: str | None) -> dict | None:
    if not pow_summary:
        return None
    p = analyze.parse_pow_summary(pow_summary)
    return {
        "estimativa": True,  # FR-RV-39: nunca medicao
        "status": p["status"],
        "total_mw": p["total_mw"],
        "dinamica_nucleo_mw": p["core_dynamic_mw"],
        "estatica_nucleo_mw": p["core_static_mw"],
        "io_mw": p["io_mw"],
        "confianca": p["confidence"],
    }


def testar_revisao(docker: Docker, projeto: Projeto, rev: Revisao, cpu: CpuQuartus,
                   periodo_ns: float, timeout_s: float, avisar) -> dict:
    saida = projeto.pasta
    out = saida / f"quartus_output_{rev.nome}"
    reports = out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    resultado: dict[str, Any] = {
        "revisao": rev.nome,
        "descricao": rev.descricao,
        "generics": {k: v for k, v in rev.generics.items()},
        "generics_no_default_do_vhdl": projeto.generics_ignorados.get(rev.nome, []),
        "evidencias": _relativo(out),
    }
    checagens: list[dict] = []

    # 1. O wrapper `analyze` da propria imagem (TRV-8.7, FR-RV-41): compila,
    #    extrai fit/timing/Fmax/potencia e preserva o .sof.
    avisar(f"[{rev.nome}] compilando no Quartus (sintese, fit, timing, potencia) -- pode levar varios minutos")
    t0 = time.monotonic()
    rc = docker.rodar(saida, ["analyze", "--project", projeto.nome, "--revision", rev.nome,
                              "--workdir", "/workspace", "--output", f"/workspace/{out.name}"],
                      out / "analyze.log", timeout_s=timeout_s)
    resultado["duracao_compilacao_s"] = _duracao(t0)
    resultado["analyze_exit_code"] = rc

    compile_log = _ler(out / "compilation" / "compile.log") or ""
    compilacao = parse_compile_log(compile_log, projeto.fontes)
    if rc == RC_TEMPO_ESGOTADO:
        compilacao["compila"] = False
        compilacao["tempo_esgotado"] = True

    of = saida / "output_files"
    textos = {suf: _ler(of / f"{rev.nome}.{suf}") for suf in
              ("map.summary", "fit.summary", "sta.summary", "pow.summary", "fit.rpt")}
    for suf in ("map.summary", "fit.summary", "sta.summary", "pow.summary"):
        if textos[suf] is not None:
            shutil.copy2(of / f"{rev.nome}.{suf}", reports / f"{rev.nome}.{suf}")

    recursos = montar_recursos(textos["fit.summary"], textos["fit.rpt"], textos["map.summary"])
    pct_alm = ((recursos or {}).get("alms") or {}).get("percentual")
    motivo, dica = classificar_falha(compilacao, pct_alm)
    compilacao["motivo"] = motivo
    compilacao["dica"] = dica
    compilacao["log"] = _relativo(out / "compilation" / "compile.log")
    resultado["compilacao"] = compilacao
    resultado["recursos"] = recursos

    sintese_ok = any(e["etapa"] == ETAPA_SINTESE and e["status"] == "ok" for e in compilacao["etapas"])
    fitter_rodou = textos["fit.summary"] is not None

    checagens.append(_checagem(
        "compilacao", "Compilacao completa (--flow compile)", "TRV-8.3, FR-RV-41",
        "ok" if compilacao["compila"] else "falhou",
        "sintese, fit, assembler e timing passaram" if compilacao["compila"]
        else f"parou em: {compilacao['etapa_que_falhou'] or 'etapa desconhecida'} ({motivo})"))
    checagens.append(_checagem(
        "fit", "Fit e utilizacao de recursos", "FR-RV-37",
        ("ok" if recursos and recursos.get("cabe") else "falhou") if fitter_rodou else "pulado",
        _resumo_recursos(recursos) if fitter_rodou else "o Fitter nao rodou (a sintese reprovou)"))

    # Uma CPU sem registrador depois da sintese nao e uma CPU pequena: e uma
    # CPU que o Quartus apagou por nao ter nada observavel no topo. Todo
    # numero dai para frente descreveria um design vazio (NFR-RV-02).
    regs = (recursos or {}).get("registradores")
    resultado["logica_removida"] = bool(sintese_ok and regs == 0)
    if not sintese_ok or regs is None:
        status_logica, detalhe_logica = "pulado", "sem contagem de registradores"
    elif regs == 0:
        status_logica = "falhou"
        detalhe_logica = ("0 registradores: o Quartus removeu a logica (nada observavel no topo); "
                          "os numeros nao representam a CPU" + ("" if projeto.preservar_logica
                                                                else " -- rode com --preservar-logica sim"))
    else:
        status_logica = "ok"
        detalhe_logica = f"{_n(regs)} registradores" + (
            " (registradores sem fan-out preservados)" if projeto.preservar_logica else "")
    checagens.append(_checagem("logica", "Logica mantida pela sintese (o design nao virou vazio)",
                               "NFR-RV-02", status_logica, detalhe_logica))

    # 2. Frequencia: slack/TNS do sta.summary, Fmax do fmax.log do analyze,
    #    caminho critico por report_timing.
    if compilacao["compila"]:
        restrito, confiavel, motivos = avaliar_restricao(compile_log)
        sta = analyze.parse_sta_summary(textos["sta.summary"] or "")
        fmax = analyze.parse_fmax_log(_ler(out / "compilation" / "fmax.log") or "")
        alvo_mhz = round(1000.0 / periodo_ns, 3)
        fmax_ref = fmax["restricted_fmax_mhz"] or fmax["fmax_mhz"]
        frequencia = {
            "clock": cpu.clock,
            "periodo_alvo_ns": periodo_ns,
            "alvo_mhz": alvo_mhz,
            "restrito": restrito,
            "confiavel": confiavel,
            "motivos_nao_confiavel": motivos,
            "fmax_mhz": fmax["fmax_mhz"],
            "fmax_restrito_mhz": fmax["restricted_fmax_mhz"],
            "clock_do_fmax": fmax["clock"],
            "periodo_minimo_ns": round(1000.0 / fmax_ref, 3) if fmax_ref else None,
            "fmax_atende_alvo": (fmax_ref >= alvo_mhz) if fmax_ref else None,
            "slack_setup_pior_ns": sta.get("worst_setup_slack_ns"),
            "slack_hold_pior_ns": sta.get("worst_hold_slack_ns"),
            "tns_setup_pior_ns": pior_tns_setup(textos["sta.summary"] or ""),
            "fechamento_de_timing": sta.get("closure"),
            "caminho_critico": None,
        }
        avisar(f"[{rev.nome}] caminho critico (report_timing)")
        tcl = f"_qt_caminho_{rev.nome}.tcl"
        (saida / tcl).write_text(_tcl_caminho_critico(projeto.nome, rev.nome), encoding="utf-8")
        rc_cc = docker.rodar(saida, ["-t", tcl], reports / "critical_path.log",
                             entrypoint="quartus_sta", timeout_s=timeout_s)
        frequencia["caminho_critico"] = parse_caminho_critico(_ler(reports / "critical_path.log") or "")
        resultado["frequencia"] = frequencia

        checagens.append(_checagem(
            "restricao", "Restricao de clock aplicada pelo TimeQuest", "FR-RV-38, TRV-8.4",
            "ok" if confiavel else ("aviso" if restrito else "falhou"),
            f"create_clock {cpu.clock} @ {periodo_ns:g} ns" + ("" if confiavel else "; " + "; ".join(motivos[:3]))))
        checagens.append(_checagem(
            "slack", "Slack de setup/hold no pior corner", "FR-RV-38",
            "ok" if sta.get("worst_setup_slack_ns") is not None else "falhou",
            f"setup {sta.get('worst_setup_slack_ns')} ns, hold {sta.get('worst_hold_slack_ns')} ns, "
            f"fechamento {'sim' if sta.get('closure') else 'nao'}"))
        checagens.append(_checagem(
            "fmax", "Fmax (report_clock_fmax_summary)", "FR-RV-38",
            "ok" if fmax_ref else "falhou",
            f"{fmax_ref} MHz (alvo {alvo_mhz:g} MHz)" if fmax_ref else "o TimeQuest nao reportou Fmax"))
        cc = frequencia["caminho_critico"]
        checagens.append(_checagem(
            "caminho_critico", "Caminho critico (report_timing)", "FR-RV-38",
            "ok" if cc else "falhou",
            f"{cc['de']} -> {cc['para']}, slack {cc['slack_ns']} ns" if cc else f"report_timing saiu com {rc_cc}"))
    else:
        resultado["frequencia"] = None
        for id_, nome in (("restricao", "Restricao de clock aplicada pelo TimeQuest"),
                          ("slack", "Slack de setup/hold no pior corner"),
                          ("fmax", "Fmax (report_clock_fmax_summary)"),
                          ("caminho_critico", "Caminho critico (report_timing)")):
            checagens.append(_checagem(id_, nome, "FR-RV-38", "pulado", "so existe com a compilacao completa"))

    # 3. Potencia (quartus_pow, rodado pelo analyze).
    resultado["potencia"] = montar_potencia(textos["pow.summary"]) if compilacao["compila"] else None
    pot = resultado["potencia"]
    checagens.append(_checagem(
        "potencia", "Potencia estimada (quartus_pow)", "FR-RV-39, TRV-8.5",
        ("ok" if pot and pot["total_mw"] is not None else "falhou") if compilacao["compila"] else "pulado",
        (f"{pot['total_mw']} mW (estimativa, confianca: {pot['confianca']})" if pot and pot["total_mw"] is not None
         else "quartus_pow nao produziu pow.summary") if compilacao["compila"]
        else "so existe com a compilacao completa"))

    # 4. Netlist RTL sem GUI (FR-RV-40) -- basta a sintese.
    if sintese_ok:
        avisar(f"[{rev.nome}] netlist RTL (::quartus::rtl)")
        tcl = f"_qt_netlist_{rev.nome}.tcl"
        (saida / tcl).write_text(_tcl_netlist(projeto.nome, rev.nome), encoding="utf-8")
        rc_nl = docker.rodar(saida, ["-t", tcl], out / "netlist" / "rtl_netlist.log",
                             entrypoint="quartus_map", timeout_s=timeout_s)
        m = re.search(r"QT_RTL_CELLS=(\d+)", _ler(out / "netlist" / "rtl_netlist.log") or "")
        resultado["netlist_rtl"] = {"celulas_topo": int(m.group(1)) if m else None,
                                    "log": _relativo(out / "netlist" / "rtl_netlist.log")}
        checagens.append(_checagem(
            "netlist", "Netlist RTL acessivel sem GUI (::quartus::rtl)", "FR-RV-40, TRV-8.6",
            "ok" if m else "falhou",
            f"{m.group(1)} celula(s) RTL no topo" if m else f"quartus_map -t saiu com {rc_nl}"))
    else:
        resultado["netlist_rtl"] = None
        checagens.append(_checagem("netlist", "Netlist RTL acessivel sem GUI (::quartus::rtl)",
                                   "FR-RV-40, TRV-8.6", "pulado", "a sintese nao passou"))

    sof = out / "bitstream" / f"{rev.nome}.sof"
    resultado["bitstream"] = _relativo(sof) if sof.exists() else None
    checagens.append(_checagem(
        "bitstream", "Arquivo de gravacao .sof preservado", "FR-RV-41",
        "ok" if sof.exists() else ("falhou" if compilacao["compila"] else "pulado"),
        _relativo(sof) if sof.exists() else "sem compilacao completa nao ha .sof"))

    resultado["checagens"] = checagens
    return resultado


def _resumo_recursos(r: dict | None) -> str:
    if not r:
        return "sem dados"
    if r.get("fonte") == "sintese":
        return f"so sintese: {r.get('registradores')} registradores"
    a = r.get("alms") or {}
    pct = f"{a.get('qualificador') or ''}{a.get('percentual')} %" if a.get("percentual") is not None else "?"
    return f"{r.get('status_fit')}: {_n(a.get('usado'))} / {_n(a.get('total'))} ALMs ({pct})"


def _n(v: Any) -> str:
    return f"{v:,}".replace(",", ".") if isinstance(v, int) else ("-" if v is None else str(v))


def executar(args: argparse.Namespace, docker: Docker | None = None, avisar=None) -> tuple[int, dict | None]:
    avisar = avisar or (lambda msg: print(f"quartus_testing: {msg}", flush=True))
    docker = docker or Docker(args.docker)
    inicio = _dt.datetime.now().astimezone()

    cpu = carregar_cpu(Path(args.pasta))
    revisoes = revisoes_para(cpu, args.isa)
    device = args.device.upper()
    familia = args.familia or familia_do_device(device)
    if not familia:
        raise ErroDeEntrada(f"nao sei a familia do device {device}; passe --familia (ex.: \"Cyclone V\").")
    periodo_ns = float(args.periodo_ns) if args.periodo_ns is not None else cpu.periodo_ns
    if periodo_ns <= 0:
        raise ErroDeEntrada("--periodo-ns deve ser positivo.")
    saida = Path(args.saida) if args.saida else AQUI / "resultados" / nome_quartus(cpu.nome)
    saida = saida.resolve()
    timeout_s = args.timeout_min * 60 if args.timeout_min else None

    if args.preservar_logica == "sim":
        preservar, motivo_preservar = True, "pedido com --preservar-logica sim"
    elif args.preservar_logica == "nao":
        preservar, motivo_preservar = False, "desligado com --preservar-logica nao"
    elif cpu.top_tem_saida is False:
        preservar, motivo_preservar = True, (
            f"o topo `{cpu.top}` nao tem nenhuma porta de saida; sem isto o Quartus "
            "removeria toda a logica")
    else:
        preservar, motivo_preservar = False, (
            f"o topo `{cpu.top}` tem porta(s) de saida" if cpu.top_tem_saida
            else f"entidade `{cpu.top}` nao encontrada nas fontes; nada preservado")

    avisar(f"CPU {cpu.nome} ({_relativo(cpu.pasta)}), topo {cpu.top}, {len(cpu.fontes)} fonte(s); "
           f"alvo {device} @ {1000.0 / periodo_ns:g} MHz; revisao(oes): {', '.join(r.nome for r in revisoes)}")
    if preservar:
        avisar(f"preservando registradores sem fan-out (PRESERVE_FANOUT_FREE_NODE): {motivo_preservar}")

    versao_docker = docker.conferir_servidor()
    imagem = docker.escolher_imagem((args.imagem,) if args.imagem else IMAGENS_PADRAO)
    avisar(f"Docker {versao_docker}, imagem {imagem}")

    # Pasta de saida: so apaga o que esta ferramenta mesma criou.
    if saida.exists():
        if not (saida / MARCADOR_SAIDA).exists() and any(saida.iterdir()):
            raise ErroDeEntrada(f"{saida} ja existe e nao foi criada por esta ferramenta; escolha outra --saida.")
        docker.remover(saida)
    saida.mkdir(parents=True)
    (saida / MARCADOR_SAIDA).write_text("pasta gerada por quartus_testing/quartus_cpu_check.py\n", encoding="utf-8")

    relatorio: dict[str, Any] = {
        "ferramenta": "quartus_testing/quartus_cpu_check.py",
        "gerado_em": inicio.isoformat(timespec="seconds"),
        "cpu": {
            "nome": cpu.nome,
            "pasta": _relativo(cpu.pasta),
            "manifesto": _relativo(cpu.manifesto),
            "top": cpu.top,
            "vhdl": VHDL_STD[cpu.std],
            "fontes": [_relativo(f) for f in cpu.fontes],
        },
        "alvo": {
            "familia": familia,
            "device": device,
            "clock": cpu.clock,
            "periodo_ns": periodo_ns,
            "alvo_mhz": round(1000.0 / periodo_ns, 3),
            "periodo_do_cpu_toml": args.periodo_ns is None,
            "roteamento_agressivo": args.roteamento_agressivo,
        },
        "sintese": {
            "top_tem_saida": cpu.top_tem_saida,
            "preservar_logica": preservar,
            "motivo": motivo_preservar,
        },
        "ambiente": {"docker": versao_docker, "imagem": imagem},
        "checagens_do_ambiente": [],
        "revisoes": [],
        "saida": _relativo(saida),
    }
    try:
        # Checagem 1 do smoke test (TRV-8.2): a imagem responde.
        rc = docker.rodar(saida, ["--version"], saida / "_qt_versao.log", timeout_s=600)
        versao = re.search(r"Version (.+)", _ler(saida / "_qt_versao.log") or "")
        relatorio["ambiente"]["quartus"] = versao.group(1).strip() if versao else None
        relatorio["checagens_do_ambiente"].append(_checagem(
            "imagem", "Imagem do Quartus responde (quartus_sh --version)", "TRV-8.2, ADR-015",
            "ok" if rc == 0 and versao else "falhou",
            versao.group(1).strip() if versao else f"saiu com {rc}"))
        if not versao:
            log_versao = _ler(saida / "_qt_versao.log") or ""
            if "mounts denied" in log_versao or "not shared from the host" in log_versao:
                # Docker Desktop so compartilha o $HOME por default: /tmp e
                # outros discos ficam de fora, e o container nem sobe.
                raise ErroDeAmbiente(
                    f"o Docker nao consegue montar {saida} (fora das pastas compartilhadas do "
                    "Docker Desktop). Use uma --saida dentro do seu usuario ou adicione o "
                    "caminho em Docker Desktop > Settings > Resources > File sharing.")
            raise ErroDeAmbiente(f"a imagem {imagem} nao respondeu a --version; veja {saida / '_qt_versao.log'}.")
        avisar(f"Quartus {relatorio['ambiente']['quartus']}")

        # Checagem 2 (list_parts.tcl, ADR-016): o device existe na imagem.
        (saida / "_qt_device.tcl").write_text(_tcl_device(familia, device), encoding="utf-8")
        docker.rodar(saida, ["-t", "_qt_device.tcl"], saida / "_qt_device.log", timeout_s=600)
        achou = re.search(r"QT_DEVICE_FOUND=(\d)", _ler(saida / "_qt_device.log") or "")
        total = re.search(r"QT_DEVICE_COUNT=(\d+)", _ler(saida / "_qt_device.log") or "")
        ok_device = bool(achou and achou.group(1) == "1")
        relatorio["checagens_do_ambiente"].append(_checagem(
            "device", f"Device {device} instalado na imagem (get_part_list)", "ADR-016, FR-RV-42",
            "ok" if ok_device else "falhou",
            f"{total.group(1) if total else '?'} devices {familia} na imagem"))
        if not ok_device:
            raise ErroDeAmbiente(
                f"o device {device} ({familia}) nao esta instalado na imagem {imagem}; veja "
                f"{saida / '_qt_device.log'}. Familias extras entram por --build-arg DEVICE_SUPPORT (FR-RV-42).")

        projeto = gerar_projeto(cpu, saida, revisoes, device=device, familia=familia,
                                periodo_ns=periodo_ns, roteamento_agressivo=args.roteamento_agressivo,
                                preservar_logica=preservar)
        relatorio["projeto_quartus"] = {
            "qpf": f"{projeto.nome}.qpf",
            "sdc": projeto.sdc,
            "fontes_copiadas": projeto.fontes,
        }
        for rev in revisoes:
            relatorio["revisoes"].append(
                testar_revisao(docker, projeto, rev, cpu, periodo_ns, timeout_s, avisar))
    finally:
        docker.devolver_dono(saida)
        if not args.manter_projeto:
            for pesado in ("db", "incremental_db"):
                if (saida / pesado).exists():
                    shutil.rmtree(saida / pesado, ignore_errors=True)
        relatorio["duracao_total_s"] = round((_dt.datetime.now().astimezone() - inicio).total_seconds(), 1)
        compilam = [r["compilacao"]["compila"] for r in relatorio["revisoes"]]
        relatorio["veredito"] = (
            "COMPILA" if compilam and all(compilam)
            else "NAO_COMPILA" if compilam else "NAO_TESTADO"
        )
        (saida / "relatorio.json").write_text(json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8")
        (saida / "relatorio.md").write_text(relatorio_markdown(relatorio), encoding="utf-8")

    return (0 if relatorio["veredito"] == "COMPILA" else 1), relatorio


# --------------------------------------------------------------------------
# relatorios
# --------------------------------------------------------------------------

def _mhz(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f} MHz".replace(".", ",")


def _num(v: float | None, unidade: str = "", casas: int = 3) -> str:
    return "—" if v is None else f"{v:.{casas}f}{unidade}".replace(".", ",")


def _uso_md(u: dict | None) -> str:
    if not u or u.get("usado") is None:
        return "—"
    s = _n(u["usado"])
    if u.get("total") is not None:
        s += f" / {_n(u['total'])}"
    if u.get("percentual") is not None:
        s += f" ({u.get('qualificador') or ''}{u['percentual']:g} %)"
    return s


def _cel(texto: Any) -> str:
    """Celula de tabela Markdown: nome de no do Quartus tem `|`
    (`register_file:u|regs[3]`), que quebra a tabela mesmo dentro de crase."""
    return str(texto).replace("|", "\\|")


def _status_md(s: str) -> str:
    return {"ok": "✅ ok", "falhou": "❌ falhou", "pulado": "⏭️ pulado", "aviso": "⚠️ aviso"}.get(s, s)


def relatorio_markdown(r: dict) -> str:
    alvo, cpu, amb = r["alvo"], r["cpu"], r["ambiente"]
    l = [
        f"# Quartus — {cpu['nome']}",
        "",
        f"Gerado por `{r['ferramenta']}` em {r['gerado_em']}.",
        "",
        f"- **CPU:** `{cpu['pasta']}` (topo `{cpu['top']}`, {len(cpu['fontes'])} fonte(s), {cpu['vhdl']})",
        f"- **Alvo:** {alvo['familia']} `{alvo['device']}`, clock `{alvo['clock']}` em "
        f"{_num(alvo['periodo_ns'], ' ns', 3)} ({_mhz(alvo['alvo_mhz'])})"
        + ("" if alvo["periodo_do_cpu_toml"] else " — período passado por `--periodo-ns`")
        + (", roteamento agressivo" if alvo["roteamento_agressivo"] else ""),
        f"- **Ferramenta:** Quartus {amb.get('quartus') or '?'} na imagem `{amb['imagem']}`",
    ]
    sint = r.get("sintese") or {}
    if sint.get("preservar_logica"):
        l.append(f"- **Síntese:** registradores sem fan-out **preservados** "
                 f"(`PRESERVE_FANOUT_FREE_NODE` na raiz, equivalente a `noprune`) — {sint['motivo']}. "
                 "Opção de ferramenta, RTL intacto; a área tende a ficar um pouco acima do que um topo "
                 "com saídas reais daria, porque nada sem fan-out é podado.")
    l += [f"- **Veredito:** **{r['veredito'].replace('_', ' ')}**", ""]
    if r["revisoes"]:
        l += ["## Resumo", "",
              "| revisão | compila | Fmax | alvo | ALMs | LUTs (ALUTs) | registradores | memória em bloco | DSP | potência (estimada) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for rev in r["revisoes"]:
            c, f, rc, p = rev["compilacao"], rev["frequencia"] or {}, rev["recursos"] or {}, rev["potencia"] or {}
            luts = (rc.get("luts") or {}).get("aluts_logica")
            mem = (rc.get("memoria") or {}).get("bits_em_bloco")
            l.append(
                f"| `{rev['revisao']}` | {'sim' if c['compila'] else '**não** — ' + (c['motivo'] or '?')} "
                f"| {_mhz(f.get('fmax_restrito_mhz') or f.get('fmax_mhz'))}"
                f"{'' if not f or f.get('confiavel') else ' (não confiável)'} "
                f"| {_mhz(alvo['alvo_mhz'])}{'' if not f else (' ✅' if f.get('fmax_atende_alvo') else ' ❌')} "
                f"| {_uso_md(rc.get('alms'))} | {_n(luts)} | {_n(rc.get('registradores'))} "
                f"| {_uso_md(mem)} bits | {_uso_md(rc.get('dsp'))} "
                f"| {_num(p.get('total_mw'), ' mW', 2) if p else '—'} |")
        l.append("")

    if r["checagens_do_ambiente"]:
        l += ["## Ambiente", "", "| checagem | status | detalhe | req |", "|---|---|---|---|"]
        l += [f"| {c['checagem']} | {_status_md(c['status'])} | {_cel(c['detalhe'])} | {c['req']} |"
              for c in r["checagens_do_ambiente"]]
        l.append("")

    for rev in r["revisoes"]:
        l += _secao_revisao(rev, alvo)

    l += [
        "## Como ler",
        "",
        "- **Compila** = o `quartus_sh --flow compile` inteiro passou (síntese, fit, assembler, timing). "
        "Não caber no device é reprovação de compilação: sem fit não há timing nem potência.",
        "- **Fmax** vem do `report_clock_fmax_summary` (corner lento). O *restrito* já desconta "
        "limites de hardware (largura mínima de pulso) e é o que a placa de fato aguenta. "
        "**Fechamento de timing** = slack de setup e hold ≥ 0 no pior dos quatro corners.",
        "- **LUTs**: no Cyclone V a LUT é a ALUT (até 6 entradas; duas por ALM). *ALMs* é a unidade "
        "em que o device é cobrado; *LABs* agrupam 10 ALMs.",
        "- **Memória em bloco** = bits em M10K. Zero com muitos registradores quer dizer que a "
        "memória do design virou flip-flop e mux.",
        "- **Potência** é sempre **estimativa** do Power Analyzer, com toggle rate default — "
        "a confiança baixa é o rótulo do próprio Quartus (FR-RV-39). Potência real só medindo a placa.",
        "",
    ]
    return "\n".join(l)


def _secao_revisao(rev: dict, alvo: dict) -> list[str]:
    c = rev["compilacao"]
    generics = ", ".join(f"`{k} = {json.dumps(v)}`" for k, v in rev["generics"].items()) or "defaults do VHDL"
    l = [f"## Revisão `{rev['revisao']}`", "",
         f"{rev['descricao']}. Generics: {generics}. Evidências em `{rev['evidencias']}/`.", ""]
    if rev.get("logica_removida"):
        l += ["> ❌ **O Quartus removeu a lógica da CPU** (0 registradores depois da síntese): nada no "
              "topo é observável, então tudo foi podado. Frequência, recursos e potência abaixo "
              "descrevem um design vazio, **não a CPU**. Rode com `--preservar-logica sim`.", ""]
    l += ["### 1. Compila?", ""]
    if c["compila"]:
        l.append(f"**Sim.** Tempo de compilação: {_num(rev['duracao_compilacao_s'], ' s', 1)}.")
    else:
        l.append(f"**Não.** Parou em **{c['etapa_que_falhou'] or 'etapa desconhecida'}** — `{c['motivo']}`.")
        if c.get("tempo_esgotado"):
            l.append("O tempo limite (`--timeout-min`) estourou antes do fim.")
        if c["dica"]:
            l += ["", f"> {c['dica']}"]
    if c["etapas"]:
        l += ["", "| etapa | resultado | erros | avisos |", "|---|---|---|---|"]
        l += [f"| {e['etapa']} | {e['status']} | {_n(e['erros'])} | {_n(e['avisos'])} |" for e in c["etapas"]]
    principais = [e for e in c["erros"] if not e["detalhe"]] or c["erros"]
    if principais:
        l += ["", f"**Erros** ({len(c['erros'])} no total, log completo em `{c['log']}`):", ""]
        for e in principais[:20]:
            onde = f" — `{e['arquivo']}:{e['linha']}`" if e.get("arquivo") else ""
            l.append(f"- `Error ({e['id'] or '-'})` [{e['etapa'] or '?'}]{onde}: {e['mensagem'][:400]}")
        if len(principais) > 20:
            l.append(f"- … mais {len(principais) - 20} erro(s) no log.")
    # 169085 (pino sem localizacao) sai em toda CPU sem pinagem de placa; o
    # 332148 sai uma vez por corner. Agrupados, sobra o que muda a leitura.
    criticos: dict[tuple, int] = {}
    for a in c["avisos_criticos"]:
        if a["id"] != "169085":
            chave = (a["id"], a["etapa"], a["mensagem"])
            criticos[chave] = criticos.get(chave, 0) + 1
    if criticos:
        l += ["", "**Avisos críticos:**", ""]
        l += [f"- `Critical Warning ({i})` [{e or '?'}]: {m[:300]}" + (f" (×{n})" if n > 1 else "")
              for (i, e, m), n in list(criticos.items())[:10]]
    l.append("")

    f = rev["frequencia"]
    l += ["### 2. Frequência", ""]
    if not f:
        l += ["Sem compilação completa não há análise de timing.", ""]
    else:
        if not f["confiavel"]:
            l += ["> ⚠️ **Fmax não confiável** (FR-RV-38): " + "; ".join(f["motivos_nao_confiavel"][:5]), ""]
        cc = f["caminho_critico"] or {}
        l += [
            "| métrica | valor |", "|---|---|",
            f"| Fmax restrito | {_mhz(f['fmax_restrito_mhz'])} |",
            f"| Fmax | {_mhz(f['fmax_mhz'])} |",
            f"| período mínimo | {_num(f['periodo_minimo_ns'], ' ns')} |",
            f"| alvo (`.sdc`) | {_mhz(f['alvo_mhz'])} ({_num(f['periodo_alvo_ns'], ' ns')}) — "
            f"{'atende' if f['fmax_atende_alvo'] else 'não atende'} |",
            f"| pior slack de setup | {_num(f['slack_setup_pior_ns'], ' ns')} |",
            f"| pior slack de hold | {_num(f['slack_hold_pior_ns'], ' ns')} |",
            f"| pior TNS de setup | {_num(f['tns_setup_pior_ns'], ' ns')} |",
            f"| fechamento de timing | {'sim' if f['fechamento_de_timing'] else 'não'} |",
        ]
        if cc:
            l += [
                f"| caminho crítico: de | `{_cel(cc['de'])}` |",
                f"| caminho crítico: para | `{_cel(cc['para'])}` |",
                f"| caminho crítico: chegada / requerido | {_num(cc['chegada_ns'], ' ns')} / {_num(cc['requerido_ns'], ' ns')} |",
                f"| células no caminho | {_n(cc['celulas_no_caminho'])} |",
            ]
        l.append("")

    rc = rev["recursos"]
    l += ["### 3. Recursos da FPGA (memória, LUTs e o resto)", ""]
    if not rc:
        l += ["A síntese não terminou: não há contagem de recursos.", ""]
    elif rc["fonte"] == "sintese":
        l += [f"> {rc['nota']}", "", "| recurso | uso |", "|---|---|",
              f"| registradores | {_n(rc['registradores'])} |",
              f"| bits de memória em bloco | {_uso_md(rc['memoria']['bits_em_bloco'])} |",
              f"| DSP | {_uso_md(rc['dsp'])} |",
              f"| pinos | {_uso_md(rc['pinos'])} |", ""]
    else:
        luts, mem = rc["luts"], rc["memoria"]
        por_entrada = ", ".join(f"{k} ent.: {_n(v)}" for k, v in (luts["por_numero_de_entradas"] or {}).items())
        l += [
            f"Fit: **{rc['status_fit']}** no `{rc['device']}`"
            + ("" if rc["cabe"] else " — **o design não coube**") + ".", "",
            "| recurso | uso |", "|---|---|",
            f"| ALMs (lógica) | {_uso_md(rc['alms'])} |",
            f"| ALMs no placement final | {_uso_md(rc['alms_em_uso_no_placement'])} |",
            f"| LABs | {_uso_md(rc['labs'])} |",
            f"| LUTs: ALUTs de lógica | {_n(luts['aluts_logica'])}" + (f" ({por_entrada})" if por_entrada else "") + " |",
            f"| LUTs: ALUTs de route-through | {_n(luts['aluts_route_through'])} |",
            f"| registradores | {_n(rc['registradores'])} |",
            f"| memória: bits em bloco | {_uso_md(mem['bits_em_bloco'])} |",
            f"| memória: blocos M10K | {_uso_md(mem['blocos_m10k'])} |",
            f"| memória: bits em MLAB | {_n(mem['bits_mlab'])} |",
            f"| DSP | {_uso_md(rc['dsp'])} |",
            f"| PLLs | {_uso_md(rc['plls'])} |",
            f"| clocks globais | {_uso_md(rc['clocks_globais'])} |",
            f"| pinos de E/S | {_uso_md(rc['pinos'])} |",
            f"| interconexão (total/H/V): média | {rc['interconexao_media'] or '—'} |",
            f"| interconexão (total/H/V): pico | {rc['interconexao_pico'] or '—'} |",
            f"| fan-out máximo | {_n(rc['fan_out_maximo'])} |",
        ]
        if rc.get("nota_memoria"):
            l += ["", f"> {rc['nota_memoria']}"]
        l.append("")

    p = rev["potencia"]
    l += ["### 4. Potência (estimativa)", ""]
    if not p:
        l += ["Sem compilação completa não há análise de potência.", ""]
    else:
        l += ["| componente | mW |", "|---|---|",
              f"| **total** | **{_num(p['total_mw'], '', 2)}** |",
              f"| dinâmica do núcleo | {_num(p['dinamica_nucleo_mw'], '', 2)} |",
              f"| estática do núcleo | {_num(p['estatica_nucleo_mw'], '', 2)} |",
              f"| E/S | {_num(p['io_mw'], '', 2)} |",
              "", f"Confiança segundo o Quartus: *{p['confianca']}*. É estimativa, não medição.", ""]

    l += ["### Checagens", "", "| checagem | status | detalhe | req |", "|---|---|---|---|"]
    l += [f"| {k['checagem']} | {_status_md(k['status'])} | {_cel(k['detalhe'])} | {k['req']} |"
          for k in rev["checagens"]]
    l.append("")
    return l


def resumo_terminal(r: dict) -> str:
    l = [""]
    for c in r["checagens_do_ambiente"]:
        l.append(f"  {c['status']:>6}  {c['checagem']} — {c['detalhe']}")
    for rev in r["revisoes"]:
        c, f, rc, p = rev["compilacao"], rev["frequencia"], rev["recursos"], rev["potencia"]
        l += ["", f"== {rev['revisao']} ({rev['descricao']}) =="]
        if rev.get("logica_removida"):
            l.append("  ATENCAO     0 registradores: o Quartus removeu a logica (nada observavel no topo);"
                     " os numeros abaixo NAO representam a CPU -- use --preservar-logica sim")
        if c["compila"]:
            l.append(f"  compila     sim ({rev['duracao_compilacao_s']:g} s)")
        else:
            l.append(f"  compila     NAO -- {c['etapa_que_falhou'] or '?'}: {c['motivo']}")
            for e in ([e for e in c["erros"] if not e["detalhe"]] or c["erros"])[:5]:
                onde = f" [{e['arquivo']}:{e['linha']}]" if e.get("arquivo") else ""
                l.append(f"    Error ({e['id'] or '-'}){onde}: {e['mensagem'][:200]}")
            if c["dica"]:
                l.append(f"    dica: {c['dica']}")
        if f:
            fmax = f["fmax_restrito_mhz"] or f["fmax_mhz"]
            l.append(
                f"  frequencia  Fmax {fmax} MHz (alvo {f['alvo_mhz']:g} MHz: "
                f"{'atende' if f['fmax_atende_alvo'] else 'NAO atende'}), slack setup "
                f"{f['slack_setup_pior_ns']} ns, hold {f['slack_hold_pior_ns']} ns"
                + ("" if f["confiavel"] else "  [NAO CONFIAVEL]"))
            cc = f["caminho_critico"]
            if cc:
                l.append(f"              caminho critico: {cc['de']} -> {cc['para']}")
        else:
            l.append("  frequencia  -- (sem compilacao completa)")
        if rc and rc["fonte"] == "fitter":
            mem = rc["memoria"]
            l.append(
                f"  recursos    ALMs {_uso_md(rc['alms'])}, LUTs (ALUTs) {_n(rc['luts']['aluts_logica'])}, "
                f"registradores {_n(rc['registradores'])}")
            l.append(
                f"              memoria {_uso_md(mem['bits_em_bloco'])} bits (M10K {_uso_md(mem['blocos_m10k'])}), "
                f"DSP {_uso_md(rc['dsp'])}, PLLs {_uso_md(rc['plls'])}, pinos {_uso_md(rc['pinos'])}")
        elif rc:
            l.append(f"  recursos    so sintese: {_n(rc['registradores'])} registradores (sem fit)")
        else:
            l.append("  recursos    -- (a sintese nao terminou)")
        if p:
            l.append(
                f"  potencia    {p['total_mw']} mW ESTIMADOS (dinamica {p['dinamica_nucleo_mw']}, "
                f"estatica {p['estatica_nucleo_mw']}, E/S {p['io_mw']}); confianca: {p['confianca']}")
        else:
            l.append("  potencia    -- (sem compilacao completa)")
        falhas = [k["id"] for k in rev["checagens"] if k["status"] in ("falhou", "aviso")]
        puladas = [k["id"] for k in rev["checagens"] if k["status"] == "pulado"]
        l.append(f"  checagens   {sum(k['status'] == 'ok' for k in rev['checagens'])} ok"
                 + (f", falhou/aviso: {', '.join(falhas)}" if falhas else "")
                 + (f", puladas: {', '.join(puladas)}" if puladas else ""))
    l += ["", f"veredito: {r['veredito']}   relatorio: {r['saida']}/relatorio.md (e relatorio.json)"]
    return "\n".join(l)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parser_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="quartus_cpu_check.py",
        description="Compila uma CPU no Quartus (imagem Docker quartus-lite) e reporta se compila "
                    "(e o erro), frequencia, recursos da FPGA e potencia estimada.",
    )
    p.add_argument("pasta", help="pasta da CPU, com o cpu.toml (ex.: cpus/rv32i_pipeline)")
    p.add_argument("--saida", help="pasta de saida (default: quartus_testing/resultados/<nome>)")
    p.add_argument("--device", default=DEVICE_PADRAO, help=f"device alvo (default: {DEVICE_PADRAO})")
    p.add_argument("--familia", help="familia do device (default: deduzida, ex.: Cyclone V)")
    p.add_argument("--periodo-ns", type=float,
                   help="periodo do clock alvo em ns (default: [clock].period_ns do cpu.toml)")
    p.add_argument("--isa", choices=("padrao", "rv32i", "rv32im", "ambas"), default="padrao",
                   help="padrao: generics do cpu.toml; rv32i/rv32im: forca o rv32m_generic; "
                        "ambas: RV32I e depois RV32IM (default: padrao)")
    p.add_argument("--roteamento-agressivo", action="store_true",
                   help="liga FITTER_AGGRESSIVE_ROUTABILITY_OPTIMIZATION (o que o Quartus "
                        "recomenda quando o roteamento falha)")
    p.add_argument("--preservar-logica", choices=("auto", "sim", "nao"), default="auto",
                   help="mantem registradores sem fan-out (noprune na raiz). auto: so quando o "
                        "topo nao tem porta de saida, que sem isto vira um design vazio (default: auto)")
    p.add_argument("--imagem", help=f"imagem Docker (default: a primeira que existir entre {', '.join(IMAGENS_PADRAO)})")
    p.add_argument("--docker", default="docker", help="executavel do Docker (default: docker)")
    p.add_argument("--timeout-min", type=float, default=180,
                   help="tempo maximo de cada chamada ao Quartus, em minutos (default: 180; 0 = sem limite)")
    p.add_argument("--manter-projeto", action="store_true",
                   help="nao apaga db/ e incremental_db/ do Quartus no fim (centenas de MB)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser_cli().parse_args(argv)
    try:
        rc, relatorio = executar(args)
    except (ErroDeEntrada, ErroDeAmbiente) as exc:
        print(f"quartus_testing: erro: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nquartus_testing: interrompido.", file=sys.stderr)
        return 130
    print(resumo_terminal(relatorio))
    return rc


if __name__ == "__main__":
    sys.exit(main())
