#!/usr/bin/env python3
"""Diagnóstico de falha e orientação para quem entregou a CPU.

REQ: FR-RV-28 (diagnóstico estruturado de cada caso reprovado), FR-RV-27
(títulos dos requisitos no resumo), NFR-RV-02 (nada aqui muda o veredito).

O veredito vem sempre da simulação. Este módulo só **descreve** uma falha que
o GHDL já produziu, a partir do `report.json` gravado pelo testbench
(`tb_generic.py`) e do log do caso:

- o tipo da falha (valor divergente, travamento, caminho de observação
  inexistente, compilação, simulação abortada, programa grande demais);
- cada divergência de RAM com endereço, entrada, esperado e obtido;
- a instrução que a CPU parece estar executando no lugar da pedida, quando
  TODOS os valores obtidos coincidem com ela segundo o modelo de referência;
- uma orientação sobre o bloco de hardware a revisar.

A orientação é rotulada como sugestão: ela aponta onde costuma estar o
defeito que produz aquele sintoma, e não afirma onde ele está.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from ._ferramentas import ref

MASK32 = 0xFFFFFFFF

I_OPS = ["add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu"]
M_OPS = ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"]

# funct3 de cada instrução R-type: M e base com o mesmo funct3 só se
# distinguem pelo funct7, e é daí que vem a confusão mais comum.
FUNCT3 = {
    "add": 0, "sub": 0, "sll": 1, "slt": 2, "sltu": 3,
    "xor": 4, "srl": 5, "sra": 5, "or": 6, "and": 7,
    "mul": 0, "mulh": 1, "mulhsu": 2, "mulhu": 3,
    "div": 4, "divu": 5, "rem": 6, "remu": 7,
}

TITULOS_REQUISITO = {
    "FR-RV-04": "Semântica RV32I: registradores, aritmética de 32 bits e load/store",
    "FR-RV-05": "Memórias e mapa de endereços",
    "FR-RV-11": "Baseline RV32I verificada antes da extensão",
    "FR-RV-12": "Unidade M integrada ao caminho de dados",
    "FR-RV-13": "As oito instruções da extensão M",
    "FR-RV-14": "Casos especiais da divisão",
    "FR-RV-21": "Execução, parada e detecção de travamento",
    "FR-RV-22": "Valores de borda e dependência entre instruções",
    "FR-RV-23": "Esperado derivado do modelo de referência",
    "FR-RV-24": "Métricas de eficiência",
    "FR-RV-25": "Área por síntese",
    "FR-RV-32": "Comparação de eficiência RV32I × RV32IM",
    "FR-RV-33": "Área por síntese a partir do manifesto",
}

TITULOS_TIPO = {
    "valor": "Valor errado na RAM",
    "travamento": "A CPU não terminou o programa",
    "observacao": "Caminho do cpu.toml não existe no design",
    "compilacao": "O GHDL não compilou as fontes",
    "simulacao": "O GHDL abortou a simulação",
    "rom_pequena": "O programa não cabe na ROM declarada",
    "manifesto": "O manifesto não permite esta verificação",
    "interno": "Erro interno do validador",
}

DICA_POR_CASO = {
    "add": "Confira a soma na ULA: 32 bits em complemento de dois, com o "
           "vai-um do bit 31 descartado (sem saturação).",
    "sub": "Confira a subtração rs1 − rs2 e a ordem dos operandos. SUB e ADD "
           "têm o mesmo funct3 (000); o bit 30 da instrução (funct7 = 0100000) "
           "é o que seleciona SUB.",
    "and": "Confira a operação bit a bit e o funct3 decodificado (AND = 111).",
    "or": "Confira a operação bit a bit e o funct3 decodificado (OR = 110).",
    "xor": "Confira a operação bit a bit e o funct3 decodificado (XOR = 100).",
    "sll": "Deslocamento lógico à esquerda: só os 5 bits baixos de rs2 contam "
           "(shamt = rs2[4:0]); valores como 0xFFFFFFFF deslocam 31 posições.",
    "srl": "Deslocamento lógico à direita: entra zero pela esquerda, e só "
           "rs2[4:0] conta.",
    "sra": "Deslocamento aritmético: o bit de sinal é replicado pela esquerda "
           "(shift_right sobre signed). SRA e SRL têm o mesmo funct3 (101) e se "
           "distinguem pelo funct7 (0100000).",
    "slt": "Comparação COM sinal: 0x80000000 é o menor valor e 0x7FFFFFFF o "
           "maior. Compare como signed, e o resultado é 0 ou 1.",
    "sltu": "Comparação SEM sinal: 0xFFFFFFFF é o maior valor. Compare como "
            "unsigned, e o resultado é 0 ou 1.",
    "x0_imutavel": "x0 lê sempre zero e descarta escrita: bloqueie a escrita "
                   "quando rd = 0 ou force a leitura de x0 para zero.",
    "load_store_larguras": "Confira a extensão de sinal de LB e LH (replicam o "
                           "bit 7 e o bit 15), a extensão com zeros de LBU e "
                           "LHU, e quantos bytes SB, SH e SW escrevem.",
    "branches": "Confira a condição de cada branch (BLT/BGE com sinal, "
                "BLTU/BGEU sem sinal), o alvo PC + imediato de 13 bits e que o "
                "branch não tomado segue para PC + 4.",
    "jal_jalr_lui_auipc": "JAL grava PC + 4 em rd e salta para PC + imediato; "
                          "JALR salta para rs1 + imediato com o bit 0 zerado; "
                          "LUI carrega imediato << 12 e AUIPC soma isso ao PC.",
    "laco_com_dependencia": "Laço com dependência entre instruções seguidas. "
                            "Num pipeline, confira o forwarding e o flush do "
                            "branch; num monociclo, o caminho do branch e a "
                            "escrita no banco de registradores.",
    "mul": "MUL devolve os 32 bits BAIXOS do produto; o sinal dos operandos não "
           "muda essa parte.",
    "mulh": "MULH devolve os 32 bits ALTOS do produto de 64 bits, com sinal × "
            "com sinal.",
    "mulhsu": "MULHSU: rs1 COM sinal × rs2 SEM sinal, 32 bits altos. O erro "
              "comum é tratar os dois operandos como com sinal.",
    "mulhu": "MULHU: 32 bits altos do produto sem sinal × sem sinal.",
    "div": "DIV trunca em direção a zero. Divisão por zero dá −1 "
           "(0xFFFFFFFF), e (−2³¹) / (−1) dá −2³¹.",
    "divu": "DIVU opera sem sinal. Divisão por zero dá 0xFFFFFFFF.",
    "rem": "REM tem o sinal do DIVIDENDO. Divisão por zero devolve o dividendo, "
           "e (−2³¹) rem (−1) dá 0.",
    "remu": "REMU opera sem sinal. Divisão por zero devolve o dividendo.",
    "divisao_por_zero": "RISC-V não gera trap na divisão por zero: DIV e DIVU "
                        "dão 0xFFFFFFFF, REM e REMU devolvem o dividendo, e a "
                        "CPU continua executando a instrução seguinte.",
    "overflow_da_divisao": "(−2³¹) / (−1) não cabe em 32 bits: DIV deve dar "
                           "0x80000000 e REM deve dar 0, sem trap.",
    "misto_rv32i_rv32m": "Instruções M no meio de laços e load/store: confira "
                         "que o resultado da unidade M chega ao banco de "
                         "registradores (mux de saída do estágio de execução) "
                         "e, num pipeline, que o forwarding também vale para "
                         "esse resultado.",
}

DICA_POR_TIPO = {
    "travamento": "A CPU não chegou ao auto-laço de parada (`halt: j halt`). "
                  "Causas comuns: salto ou branch com alvo errado, PC que não "
                  "avança, ou [halt] mal declarado no cpu.toml — num pipeline "
                  "com busca especulativa use commit_pc, não fetch_pc "
                  "(ADR-008).",
    "observacao": "Os caminhos do cpu.toml seguem os nomes das INSTÂNCIAS "
                  "(rótulos do port map) e dos sinais, separados por ponto — "
                  "não os nomes das entidades. A mensagem lista o que existe "
                  "naquele escopo.",
    "compilacao": "Corrija a linha indicada. Se o erro for de declaração não "
                  "encontrada, confira a ordem de [design].sources: pacotes "
                  "vêm antes de quem os usa.",
    "simulacao": "O GHDL parou durante a execução. 'index out of bounds' "
                 "costuma ser guarda de faixa e índice de array em expressões "
                 "separadas — veja a restrição 3 em entregas/README.md.",
    "rom_pequena": "Aumente [program].size_words no cpu.toml e repasse o valor "
                   "ao generic de tamanho da ROM.",
    "manifesto": "Declare no cpu.toml o caminho que falta, ou aceite que essa "
                 "verificação fica fora do alcance do validador.",
    "interno": "A falha é do validador, não da CPU. Rode pela linha de comando "
               "com --workdir para guardar os arquivos e reporte o erro.",
}

# pseudo-operações testadas junto das instruções reais
_PSEUDO = {
    "rs1": lambda a, b: a & MASK32,
    "rs2": lambda a, b: b & MASK32,
    "zero": lambda a, b: 0,
}


def hexw(value: int) -> str:
    return f"0x{value & MASK32:08x}"


def com_sinal(value: int) -> int:
    v = value & MASK32
    return v - (1 << 32) if v & 0x80000000 else v


def _aplicar(op: str) -> Callable[[int, int], int]:
    if op in _PSEUDO:
        return _PSEUDO[op]
    if op in M_OPS:
        return lambda a, b: ref.apply_m(op, a, b)
    return lambda a, b: ref.apply_i(op, a, b)


def detectar_confusao(esperada: str, pares: list[tuple[int, int]],
                      obtidos: list[int]) -> str | None:
    """Instrução cujo resultado coincide com TODOS os valores obtidos.

    Só responde quando a coincidência é total: um único par divergente
    descarta o candidato. Devolve None se nenhuma instrução explica o que a
    CPU produziu -- nesse caso não há o que sugerir.
    """
    if not pares or len(pares) != len(obtidos):
        return None
    # "tudo zero" primeiro, porque é o sintoma mais literal; depois as
    # instruções base antes das M, porque o caso clássico é M executar como base
    candidatos = (["zero"] + [op for op in I_OPS + M_OPS if op != esperada]
                  + ["rs1", "rs2"])
    for op in candidatos:
        f = _aplicar(op)
        if all(f(a, b) == (g & MASK32) for (a, b), g in zip(pares, obtidos)):
            return op
    return None


def dica_confusao(esperada: str, confundida: str, n_pares: int) -> str:
    """Texto que explica o sintoma de uma instrução executando no lugar de outra."""
    E, C = esperada.upper(), confundida.upper()
    if confundida == "zero":
        return (f"Todos os {n_pares} resultados de {E} saíram zero: a instrução "
                f"não chegou a escrever o resultado. Confira se ela é "
                f"reconhecida como válida"
                + (" (funct7 = 0000001 e o generic da extensão M ligado)"
                   if esperada in M_OPS else "")
                + " e se o resultado chega ao banco de registradores.")
    if confundida in ("rs1", "rs2"):
        qual = "primeiro" if confundida == "rs1" else "segundo"
        return (f"Os {n_pares} resultados de {E} são iguais ao {qual} operando: a "
                f"operação não está sendo aplicada. Confira a seleção da "
                f"operação e o mux que leva o resultado ao banco.")
    if esperada in M_OPS and confundida in I_OPS \
            and FUNCT3.get(esperada) == FUNCT3.get(confundida):
        return (f"Os {n_pares} resultados de {E} coincidem com {C}, que tem o "
                f"mesmo funct3. O decodificador não está olhando o funct7 = "
                f"0000001, que é o que identifica a extensão M.")
    if {esperada, confundida} in ({"sra", "srl"}, {"add", "sub"}):
        return (f"Os {n_pares} resultados de {E} coincidem com {C}. As duas têm o "
                f"mesmo funct3 e diferem só pelo bit 30 da instrução "
                f"(funct7 = 0100000): confira esse bit no decodificador"
                + (" e o deslocamento com sinal." if esperada == "sra" else "."))
    return (f"Os {n_pares} resultados de {E} coincidem com o que {C} produziria: "
            f"a CPU parece executar {C} no lugar de {E}. Confira opcode, "
            f"funct3 e funct7 no decodificador e a seleção da operação.")


# --------------------------------------------------------------------------
# diagnóstico
# --------------------------------------------------------------------------

_ERRO_LOG_RE = re.compile(r"(ghdl:error|error:|bound check|out of bounds|"
                          r"assertion (error|failure))", re.IGNORECASE)


def _linhas_de_erro(log_texto: str, limite: int = 8) -> list[str]:
    out = []
    for linha in log_texto.splitlines():
        s = linha.strip()
        if not s or "numeric_std" in s or "metavalue" in s:
            continue
        if _ERRO_LOG_RE.search(s):
            out.append(s[:300])
            if len(out) >= limite:
                break
    return out


def _primeira_linha(texto: str, limite: int = 220) -> str:
    linha = (texto or "").strip().splitlines()[0] if (texto or "").strip() else ""
    return linha if len(linha) <= limite else linha[: limite - 1] + "…"


def diagnosticar(*, nome: str, relatorio: dict | None,
                 excecao: BaseException | None = None,
                 log_texto: str = "",
                 rotulos: dict[int, str] | None = None,
                 pares: list[tuple[int, int]] | None = None,
                 enderecos_pares: list[int] | None = None,
                 erros_compilacao: list[dict] | None = None,
                 tipo_forcado: str | None = None,
                 mensagem_forcada: str = "",
                 limite: int = 16) -> dict[str, Any]:
    """Monta o diagnóstico de um caso reprovado (FR-RV-28)."""
    rotulos = rotulos or {}
    rel = relatorio or {}
    erro = rel.get("erro") or {}
    falhas = rel.get("falhas") or []

    if tipo_forcado:
        tipo = tipo_forcado
    elif erros_compilacao is not None:
        tipo = "compilacao"
    elif erro.get("tipo"):
        tipo = erro["tipo"]
    elif falhas:
        tipo = "valor"
    elif relatorio is None and _linhas_de_erro(log_texto):
        tipo = "simulacao"
    else:
        tipo = "interno"

    diag: dict[str, Any] = {
        "tipo": tipo,
        "titulo": TITULOS_TIPO.get(tipo, tipo),
        "resumo": "",
        "divergencias": [],
        "total_divergencias": 0,
        "confusao": None,
        "dica": "",
        "mensagem": "",
        "erros_ghdl": [],
        "dados": erro.get("dados") or {},
    }

    if tipo == "valor":
        divs = []
        for f in falhas:
            if f.get("tipo") == "ram":
                addr = int(f["endereco"])
                divs.append({
                    "onde": f"RAM[{hexw(addr)}]",
                    "endereco": hexw(addr),
                    "entrada": rotulos.get(addr, ""),
                    "esperado": hexw(f["esperado"]),
                    "esperado_dec": com_sinal(f["esperado"]),
                    "obtido": hexw(f["obtido"]),
                    "obtido_dec": com_sinal(f["obtido"]),
                })
            elif f.get("tipo") == "registrador":
                divs.append({
                    "onde": f"x{f['indice']}",
                    "endereco": "",
                    "entrada": "",
                    "esperado": hexw(f["esperado"]),
                    "esperado_dec": com_sinal(f["esperado"]),
                    "obtido": hexw(f["obtido"]),
                    "obtido_dec": com_sinal(f["obtido"]),
                })
            else:
                divs.append({"onde": f.get("tipo", "?"), "endereco": "",
                             "entrada": f.get("mensagem", ""), "esperado": "",
                             "esperado_dec": None, "obtido": "",
                             "obtido_dec": None})
        diag["total_divergencias"] = len(divs)
        diag["divergencias"] = divs[:limite]

        dump = rel.get("ram_dump") or {}
        if pares and enderecos_pares and dump:
            try:
                obtidos = [int(dump[hex(a)]) for a in enderecos_pares]
            except (KeyError, TypeError, ValueError):
                obtidos = []
            if len(obtidos) == len(pares):
                diag["confusao"] = detectar_confusao(nome, pares, obtidos)

        n = len(divs)
        plural = "posição" if n == 1 else "posições"
        diag["resumo"] = f"{n} {plural} com valor diferente do esperado"
        if diag["confusao"] and diag["confusao"] not in _PSEUDO:
            diag["resumo"] += f" — parece {diag['confusao'].upper()}"
        dicas = []
        if diag["confusao"]:
            dicas.append(dica_confusao(nome, diag["confusao"], len(pares or [])))
        if nome in DICA_POR_CASO:
            dicas.append(DICA_POR_CASO[nome])
        diag["dica"] = " ".join(dicas)

    elif tipo == "travamento":
        dados = diag["dados"]
        maxc = dados.get("max_ciclos")
        diag["resumo"] = (f"não terminou em {maxc} ciclos" if maxc
                          else "não terminou dentro do teto de ciclos")
        diag["mensagem"] = erro.get("mensagem", "")
        extra = ""
        quentes = dados.get("pcs_mais_visitados") or []
        paradas = set(dados.get("enderecos_de_parada") or [])
        if quentes and quentes[0][0] not in paradas:
            extra = (f" O PC mais visitado foi {hexw(quentes[0][0])} "
                     f"({quentes[0][1]} ciclos), fora do endereço de parada: "
                     f"a execução ficou presa ali.")
        elif not dados.get("pc_observavel", True):
            extra = (" Declare [observe].pc_fetch no cpu.toml para o "
                     "diagnóstico mostrar onde a CPU parou.")
        diag["dica"] = DICA_POR_TIPO["travamento"] + extra
        if nome in DICA_POR_CASO:
            diag["dica"] += " " + DICA_POR_CASO[nome]

    elif tipo == "compilacao":
        erros = erros_compilacao or []
        diag["erros_ghdl"] = erros
        if erros:
            e0 = erros[0]
            diag["resumo"] = f"{e0['arquivo']}:{e0['linha']}: {e0['mensagem']}"
        else:
            diag["resumo"] = _primeira_linha(mensagem_forcada) or "falha na compilação"
        diag["mensagem"] = mensagem_forcada
        diag["dica"] = DICA_POR_TIPO["compilacao"]

    elif tipo == "simulacao":
        linhas = _linhas_de_erro(log_texto)
        diag["mensagem"] = "\n".join(linhas) or str(excecao or "")
        diag["resumo"] = _primeira_linha(linhas[0] if linhas else str(excecao or ""))
        diag["dica"] = DICA_POR_TIPO["simulacao"]

    else:
        msg = mensagem_forcada or erro.get("mensagem") or (
            f"{type(excecao).__name__}: {excecao}" if excecao else "")
        diag["mensagem"] = msg
        diag["resumo"] = _primeira_linha(msg) or diag["titulo"]
        diag["dica"] = DICA_POR_TIPO.get(tipo, "")

    return diag


def resumo_em_texto(diag: dict, *, max_divergencias: int = 3) -> list[str]:
    """Linhas legíveis do diagnóstico, para a linha de comando."""
    linhas = [f"{diag['titulo']}: {diag['resumo']}"]
    for d in diag.get("divergencias", [])[:max_divergencias]:
        entrada = f" {d['entrada']}" if d.get("entrada") else ""
        if d.get("esperado"):
            linhas.append(f"  {d['onde']}{entrada}: esperado {d['esperado']} "
                          f"({d['esperado_dec']}), obtido {d['obtido']} "
                          f"({d['obtido_dec']})")
        else:
            linhas.append(f"  {d['onde']}{entrada}")
    resto = diag.get("total_divergencias", 0) - max_divergencias
    if resto > 0:
        linhas.append(f"  ... e mais {resto}")
    for e in diag.get("erros_ghdl", [])[:3]:
        linhas.append(f"  {e['arquivo']}:{e['linha']}:{e['coluna']}: {e['mensagem']}")
    if diag.get("dica"):
        linhas.append(f"  sugestão: {diag['dica']}")
    return linhas
