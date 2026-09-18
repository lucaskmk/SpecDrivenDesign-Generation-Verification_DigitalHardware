"""Formulário web da Fase 1 — REQ: FR-01, FR-02, FR-03

Renderiza o schema de schema.py (skip logic: campo booleano revela seus
children só quando marcado) e roda a validação cruzada (FR-03) antes de
liberar o botão de submissão. O parser que transforma a rubrica em
requisitos EARS (spec.json) é o T1.2, ainda não implementado — este módulo
só cobre o T1.1 (captura e validação da rubrica).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

# Bootstrap: quando este arquivo é executado diretamente (streamlit run,
# duplo clique no .bat), só o diretório dele entra no sys.path — o pacote
# spechdl (duas pastas acima) não fica importável sem isso.
_SRC_DIR = str(Path(__file__).resolve().parents[2])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from spechdl.ingestion.schema import SCHEMA, all_keys, validate_cross_fields  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "outputs"
RUBRICA_MD_PATH = OUTPUT_DIR / "rubrica.md"

# Seção "Hierarquia de memória" tem lógica dinâmica (nº de níveis de cache
# decide quantos grupos L1/L2/L3 aparecem) fora do schema declarativo —
# esses rótulos servem só pra exportar o markdown final de forma legível.
_MEMORY_DYNAMIC_LABELS = [
    ("l1_unificada", "L1 unificada?"),
    ("l1_tamanho_kb", "Tamanho de L1 (KB)"),
    ("l1_associatividade", "Associatividade de L1"),
    ("l1_latencia_hit", "Latência de hit de L1 (ciclos)"),
    ("l1i_tamanho_kb", "Tamanho de L1I (KB)"),
    ("l1i_associatividade", "Associatividade de L1I"),
    ("l1d_tamanho_kb", "Tamanho de L1D (KB)"),
    ("l1d_associatividade", "Associatividade de L1D"),
    ("l2_tamanho_kb", "Tamanho de L2 (KB)"),
    ("l2_associatividade", "Associatividade de L2"),
    ("l2_latencia_hit", "Latência de hit de L2 (ciclos)"),
    ("l3_tamanho_kb", "Tamanho de L3 (KB)"),
    ("l3_associatividade", "Associatividade de L3"),
    ("l3_latencia_hit", "Latência de hit de L3 (ciclos)"),
    ("hierarquia_inclusiva", "Hierarquia inclusiva?"),
]


def render_field(field: dict, answers: dict[str, Any]) -> Any:
    key = field["key"]
    ftype = field["type"]
    label = field["label"]
    help_text = field.get("help")

    if ftype == "bool":
        value = st.checkbox(label, value=field.get("default", False), help=help_text, key=key)
    elif ftype == "int":
        value = int(st.number_input(
            label,
            min_value=field.get("min", 0),
            max_value=field.get("max", 1_000_000),
            value=field.get("default", field.get("min", 0)),
            step=field.get("step", 1),
            help=help_text,
            key=key,
        ))
    elif ftype == "float":
        value = float(st.number_input(
            label,
            min_value=field.get("min", 0.0),
            max_value=field.get("max", 1000.0),
            value=field.get("default", 1.0),
            step=field.get("step", 0.1),
            help=help_text,
            key=key,
        ))
    elif ftype == "choice":
        options = field["options"]
        default = field.get("default", options[0])
        value = st.selectbox(label, options, index=options.index(default), help=help_text, key=key)
    elif ftype == "coded":
        options = field["options"]  # list[(code, label)]
        default = field.get("default", options[0][0])
        codes = [o[0] for o in options]
        labels = [o[1] for o in options]
        idx = st.selectbox(
            label, range(len(options)), index=codes.index(default),
            format_func=lambda i: labels[i], help=help_text, key=key,
        )
        value = codes[idx]
    else:
        raise ValueError(f"tipo de campo desconhecido: {ftype}")

    answers[key] = value

    # REQ: FR-01 (skip logic) — children só aparecem se o pai booleano
    # estiver marcado; senão ficam None (já inicializados em all_keys()).
    if ftype == "bool" and value and field.get("children"):
        for child in field["children"]:
            render_field(child, answers)

    return value


def render_memory_section(answers: dict[str, Any]) -> None:
    niveis = st.selectbox("Níveis de cache", [0, 1, 2, 3], index=1, key="niveis_cache")
    answers["niveis_cache"] = niveis

    if niveis >= 1:
        l1_unificada = st.checkbox(
            "L1 unificada?", value=True, key="l1_unificada",
            help="Se false, L1I e L1D separadas",
        )
        answers["l1_unificada"] = l1_unificada
        if l1_unificada:
            answers["l1_tamanho_kb"] = int(st.number_input("Tamanho de L1 (KB)", min_value=1, max_value=1024, value=32, key="l1_tamanho_kb"))
            answers["l1_associatividade"] = int(st.number_input("Associatividade de L1", min_value=1, max_value=64, value=4, key="l1_associatividade"))
            answers["l1_latencia_hit"] = int(st.number_input("Latência de hit de L1 (ciclos)", min_value=1, max_value=64, value=1, key="l1_latencia_hit"))
        else:
            answers["l1i_tamanho_kb"] = int(st.number_input("Tamanho de L1I (KB)", min_value=1, max_value=1024, value=32, key="l1i_tamanho_kb"))
            answers["l1i_associatividade"] = int(st.number_input("Associatividade de L1I", min_value=1, max_value=64, value=4, key="l1i_associatividade"))
            answers["l1d_tamanho_kb"] = int(st.number_input("Tamanho de L1D (KB)", min_value=1, max_value=1024, value=32, key="l1d_tamanho_kb"))
            answers["l1d_associatividade"] = int(st.number_input("Associatividade de L1D", min_value=1, max_value=64, value=4, key="l1d_associatividade"))
            answers["l1_latencia_hit"] = int(st.number_input("Latência de hit de L1 (ciclos)", min_value=1, max_value=64, value=1, key="l1_latencia_hit"))

    if niveis >= 2:
        answers["l2_tamanho_kb"] = int(st.number_input("Tamanho de L2 (KB)", min_value=1, max_value=32768, value=256, key="l2_tamanho_kb"))
        answers["l2_associatividade"] = int(st.number_input("Associatividade de L2", min_value=1, max_value=64, value=8, key="l2_associatividade"))
        answers["l2_latencia_hit"] = int(st.number_input("Latência de hit de L2 (ciclos)", min_value=1, max_value=200, value=10, key="l2_latencia_hit"))

    if niveis >= 3:
        answers["l3_tamanho_kb"] = int(st.number_input("Tamanho de L3 (KB)", min_value=1, max_value=262144, value=8192, key="l3_tamanho_kb"))
        answers["l3_associatividade"] = int(st.number_input("Associatividade de L3", min_value=1, max_value=64, value=16, key="l3_associatividade"))
        answers["l3_latencia_hit"] = int(st.number_input("Latência de hit de L3 (ciclos)", min_value=1, max_value=500, value=30, key="l3_latencia_hit"))

    if niveis >= 2:
        answers["hierarquia_inclusiva"] = st.checkbox("Hierarquia inclusiva?", key="hierarquia_inclusiva")


def render_form() -> None:
    st.set_page_config(page_title="SpecHDL Rubrica", page_icon="", layout="wide")
    st.title("SpecHDL —> Rubrica de especificação")
    st.caption(
        "Preencha as perguntas abaixo e envie. Essa é a única decisão que "
        "você precisa tomar. O resto do pipeline roda sozinho a partir daqui."
    )

    answers: dict[str, Any] = dict.fromkeys(all_keys())

    for i, section in enumerate(SCHEMA):
        with st.expander(section["section"], expanded=(i == 0)):
            if section["section"] == "Hierarquia de memória":
                render_memory_section(answers)
                for field in section["fields"]:
                    if field["key"] == "niveis_cache":
                        continue
                    render_field(field, answers)
            else:
                for field in section["fields"]:
                    render_field(field, answers)

    errors = validate_cross_fields(answers)
    for error in errors:
        st.error(error)

    if st.button("Submeter", disabled=bool(errors)):
        submit(answers)


def submit(answers: dict[str, Any]) -> None:
    # REQ: FR-02
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RUBRICA_MD_PATH.write_text(render_markdown(answers), encoding="utf-8")
    st.success(f"Rubrica salva em `{RUBRICA_MD_PATH}`.")
    st.info(
        "Isso cobre só o T1.1 (captura + validação da rubrica). O parser "
        "pra spec.json em EARS (T1.2) e as fases 2-6 (decomposição, "
        "geração de VHDL, verificação, PPA, relatório) ainda não foram "
        "implementadas — ver specs/tasks.md."
    )


def render_markdown(answers: dict[str, Any]) -> str:
    lines = ["# Rubrica preenchida", ""]
    for section in SCHEMA:
        lines.append(f"## {section['section']}")
        lines.append("")
        if section["section"] == "Hierarquia de memória":
            niveis = answers.get("niveis_cache")
            if niveis is not None:
                lines.append(f"- **Níveis de cache**: {niveis}")
            for key, label in _MEMORY_DYNAMIC_LABELS:
                value = answers.get(key)
                if value is not None:
                    lines.append(f"- **{label}**: {value}")
            fields = [f for f in section["fields"] if f["key"] != "niveis_cache"]
        else:
            fields = section["fields"]
        _emit_fields_md(fields, answers, lines)
        lines.append("")
    return "\n".join(lines) + "\n"


def _emit_fields_md(fields: list[dict], answers: dict[str, Any], lines: list[str], indent: int = 0) -> None:
    prefix = "  " * indent
    for field in fields:
        value = answers.get(field["key"])
        if value is None:
            continue
        lines.append(f"{prefix}- **{field['label']}**: {value}")
        if field.get("children"):
            _emit_fields_md(field["children"], answers, lines, indent + 1)


if __name__ == "__main__":
    render_form()
