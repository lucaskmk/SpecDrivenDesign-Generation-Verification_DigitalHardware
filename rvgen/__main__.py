#!/usr/bin/env python3
"""Gerador de CPUs RISC-V por agente -- ponto de entrada.

REQ: FR-RV-43 a FR-RV-50.

    python -m rvgen preparar              confere Ollama, modelo e executor;
                                          oferece instalar/baixar o que faltar
    python -m rvgen preparar --verificar  so confere, nao muda nada
    python -m rvgen preparar --sim        responde "sim" a toda confirmacao
    python -m rvgen tipos                 lista os tipos de CPU que da para gerar
    python -m rvgen gerar entregas/<nome> --tipo monociclo --isa rv32im
                                          gera, valida e corrige ate o veredito
    python -m rvgen gerar ... --provedor openrouter
                                          o mesmo, com um modelo externo
    python -m rvgen gerar ia_mono ...     so um nome: grava em experimentos/ia_mono
    python -m rvgen comparar              experimentos lado a lado (FR-RV-51)

Codigo de saida: 0 quando tudo esta pronto (preparar) ou a CPU atingiu o
objetivo (gerar), 1 com pendencia ou CPU reprovada, 2 com erro de uso, de
configuracao ou de ambiente.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import comparar as cmp
from . import contrato as ct
from . import executor as ex
from . import ollama as ol
from .agente import Agente, ErroGeracao, ErroIntegridade
from .config import REPO_ROOT, ErroConfig, ler_config
from .llm import ClienteOllama, ClienteOpenAI, ErroLLM

VERDE = "\033[32m"
VERMELHO = "\033[31m"
AMARELO = "\033[33m"
CINZA = "\033[90m"
FIM = "\033[0m"


class Tela:
    """Uma linha por item, no estilo do relatorio do rvverify."""

    def __init__(self, cor: bool) -> None:
        self.cor = cor

    def _c(self, texto: str, tom: str) -> str:
        return f"{tom}{texto}{FIM}" if self.cor else texto

    def ok(self, texto: str) -> None:
        print(f"  {self._c('ok   ', VERDE)}  {texto}", flush=True)

    def falta(self, texto: str, resolver: str | None = None) -> None:
        print(f"  {self._c('FALTA', VERMELHO)}  {texto}", flush=True)
        if resolver:
            print(f"         {self._c('resolver: ' + resolver, CINZA)}", flush=True)

    def info(self, texto: str) -> None:
        print(f"  {self._c('info ', AMARELO)}  {texto}", flush=True)


def _tamanho(n: int) -> str:
    """Bytes na unidade que faz sentido: uma camada de 400 bytes nao e 0.00 GB."""
    if n >= 1e9:
        return f"{n / 1e9:.2f} GB"
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    return f"{max(n, 1) / 1e3:.1f} KB"


def _progresso_download(interativo: bool):
    """Uma linha por etapa do download; no terminal, reescrita no lugar.

    O Ollama anuncia cada camada (`pulling <digest>`) antes de mandar o
    progresso dela, com o MESMO status: por isso a linha so muda quando o
    status muda, e cada camada ocupa uma linha so.
    """
    ultimo: dict = {"status": None, "decil": None}

    def mostrar(status: str, feito: int | None, total: int | None) -> None:
        numeros, decil = "", None
        if feito is not None and total:
            pct = int(100 * feito / total)
            decil = pct // 10
            numeros = f"{pct:3d}%  ({_tamanho(feito)} de {_tamanho(total)})"
        novo = status != ultimo["status"]
        texto = f"         {status[:28]:<28} {numeros}"
        if interativo:
            if novo and ultimo["status"] is not None:
                print()
            print(f"\r{texto:<78}", end="", flush=True)
        elif novo or decil != ultimo["decil"]:
            print(texto.rstrip(), flush=True)
        ultimo["status"], ultimo["decil"] = status, decil
    return mostrar


def _interativo() -> bool:
    """Ha alguem no terminal para responder uma confirmacao?"""
    return sys.stdin is not None and sys.stdin.isatty()


def cmd_preparar(args: argparse.Namespace) -> int:
    try:
        cfg = ler_config()
    except ErroConfig as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    interativo = _interativo()
    tela = Tela(cor=not args.sem_cor and sys.stdout.isatty())

    def confirmar(pergunta: str) -> bool:
        """FR-RV-44: nada e instalado nem baixado sem um sim explicito."""
        if args.verificar:
            return False
        if args.sim:
            return True
        if not interativo:
            tela.info("sem terminal interativo e sem --sim: nada sera instalado")
            return False
        resposta = input(f"         {pergunta} [s/N] ").strip().lower()
        return resposta in ("s", "sim", "y", "yes")

    modo = "so verificacao, nada sera alterado" if args.verificar else \
        "pergunta antes de instalar ou baixar"
    print(f"rvgen preparar -- o que o gerador precisa para rodar local ({modo})\n")
    pendencias = 0

    # -- 1. Ollama: servidor, executavel, instalacao ----------------------
    candidatos = ol.hosts_candidatos()
    servidor = ol.localizar_servidor(candidatos)
    binario = ol.localizar_binario()
    if servidor is None and binario is None:
        plano = ol.plano_de_instalacao()
        tela.falta("Ollama nao esta instalado", plano.manual or plano.descricao)
        if plano.manual is None and confirmar(f"Instalar o Ollama agora ({plano.descricao})?"):
            try:
                codigo = ol.executar_plano(plano)
            except ol.ErroOllama as e:
                codigo = 1
                tela.falta(f"a instalacao falhou: {e}")
            binario = ol.localizar_binario()
            if codigo == 0 and binario:
                tela.ok(f"Ollama instalado em {binario}")
                servidor = ol.localizar_servidor(candidatos)
            else:
                tela.falta(f"o instalador terminou com codigo {codigo} e o "
                           f"executavel nao foi encontrado", ol.URL_DOWNLOAD)
                pendencias += 1
        else:
            pendencias += 1
    elif binario is not None:
        tela.ok(f"Ollama instalado em {binario}")

    if servidor is None and binario is not None:
        # o `ollama serve` escuta em OLLAMA_HOST, se definido -- o primeiro candidato
        base_local = candidatos[0]
        if args.verificar:
            tela.falta("o servidor Ollama nao responde",
                       f'"{binario}" serve   (ou abra o app do Ollama)')
            pendencias += 1
        else:
            log = Path(tempfile.gettempdir()) / "rvgen-ollama-serve.log"
            tela.info(f"iniciando `ollama serve` em segundo plano (log: {log})")
            v = ol.iniciar_servidor(binario, log, base=base_local)
            if v:
                servidor = (base_local, v)
            else:
                tela.falta("o servidor nao respondeu em 30 s", f"veja o log {log}")
                pendencias += 1
    if servidor is not None:
        base, versao = servidor
        tela.ok(f"servidor Ollama {versao} em {base}")

    # -- 2. modelo ---------------------------------------------------------
    try:
        modelo, origem = ol.resolver_modelo(args.modelo, args.perfil, cfg.modelo)
    except ol.ErroOllama as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    if servidor is None:
        tela.falta(f"modelo {modelo} ({origem}): nao verificado, sem servidor Ollama")
        pendencias += 1
    else:
        base = servidor[0]
        try:
            instalados = ol.modelos_instalados(base)
        except ol.ErroOllama as e:
            instalados = []
            tela.falta(str(e))
        if ol.tem_modelo(instalados, modelo):
            tela.ok(f"modelo {modelo} ({origem})")
        else:
            tamanho = ol.tamanho_remoto(modelo)
            txt = f"{tamanho / 1e9:.2f} GB" if tamanho else "tamanho desconhecido"
            tela.falta(f"modelo {modelo} nao esta baixado ({origem})",
                       f"python -m rvgen preparar --modelo {modelo}   ({txt})")
            if confirmar(f"Baixar {modelo} agora ({txt}, de registry.ollama.ai)?"):
                try:
                    ol.baixar_modelo(base, modelo, _progresso_download(interativo))
                    if interativo:
                        print()
                    tela.ok(f"modelo {modelo} baixado")
                except ol.ErroOllama as e:
                    print()
                    tela.falta(str(e))
                    pendencias += 1
            else:
                pendencias += 1

    # -- 3. onde o rvverify roda ------------------------------------------
    pref = args.executor or cfg.executor
    checagens = []
    if pref in ("auto", "local"):
        checagens.append(("local", ex.checar_local()))
    if pref in ("auto", "docker"):
        checagens.append(("docker", ex.checar_docker(cfg.imagem_docker)))
    prontos = [(n, d) for n, d in checagens if d.pronto]
    if prontos:
        nome, d = prontos[0]
        tela.ok(f"executor do rvverify: {nome} -- {d.detalhe}")
    else:
        for nome, d in checagens:
            tela.falta(f"executor {nome} do rvverify: {d.detalhe}", d.como_resolver)
        pendencias += 1

    # -- 4. provedor externo (so informacao) ------------------------------
    if cfg.openrouter_key:
        tela.info(f"OPENROUTER_API_KEY definida: --provedor openrouter disponivel "
                  f"(modelo padrao {cfg.modelo_externo})")
    else:
        tela.info("OPENROUTER_API_KEY nao definida: so necessaria com --provedor openrouter")

    print()
    if pendencias:
        print(f"{pendencias} pendencia(s). Resolva as linhas FALTA acima e rode de novo.")
        return 1
    print("Tudo pronto. Proximo passo:\n"
          "  python -m rvgen gerar entregas/<nome> --tipo monociclo --isa rv32im")
    return 0


def cmd_tipos(args: argparse.Namespace) -> int:
    print("Tipos de CPU que o gerador pede e o rvverify sabe julgar:\n")
    for t in ct.TIPOS.values():
        print(f"  {t.nome:<11} {t.descricao}")
        print(f"  {'':<11} parada: {t.halt['mode']}; blocos padrao: "
              f"{', '.join(b.name for b in t.blocos)}")
    print(f"\nISAs: {', '.join(ct.ISAS)}. Outra extensao exige primeiro estender "
          f"o validador (spec, modelo de referencia, montador e casos).")
    return 0


class Relator:
    """Linhas do agente, mais um contador vivo enquanto o modelo responde."""

    def __init__(self, interativo: bool) -> None:
        self.interativo = interativo
        self._contador = False

    def progresso(self, caracteres: int) -> None:
        if self.interativo:
            print(f"\r           {caracteres} caracteres recebidos", end="", flush=True)
            self._contador = True

    def linha(self, texto: str) -> None:
        if self._contador:
            print("\r" + " " * 48 + "\r", end="")
            self._contador = False
        print(texto, flush=True)


def resolver_pasta(texto: str) -> Path:
    """ADR-019: so um nome, sem diretorio, vira `experimentos/<nome>`."""
    p = Path(texto)
    if not p.is_absolute() and len(p.parts) == 1:
        p = cmp.PASTA_PADRAO / p
    return p.resolve()


def cmd_comparar(args: argparse.Namespace) -> int:
    alvos = [Path(a) for a in args.pastas] or [cmp.PASTA_PADRAO]
    sessoes = cmp.sessoes(alvos, todas=args.todas)
    if not sessoes:
        onde = ", ".join(str(a) for a in alvos)
        print(f"Nenhuma sessao com resultado em {onde}. Gere uma CPU com "
              f"`python -m rvgen gerar <nome> --tipo ... --isa ...`.", file=sys.stderr)
        return 1
    # so vai a rede buscar preco se houver algum experimento com modelo externo
    externos = any(cmp.provedor_de(s) != "ollama" for s in sessoes)
    precos = None if (args.sem_rede or not externos) else cmp.precos_openrouter()
    linhas = [cmp.linha_de(s, precos) for s in sessoes]
    precos_ok = precos is not None or not externos
    print(cmp.tabela_texto(linhas, precos_ok), end="")
    if args.markdown:
        destino = Path(args.markdown)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(cmp.tabela_markdown(linhas, precos_ok), encoding="utf-8")
        print(f"\ntabela em Markdown: {destino}")
    return 0


def cmd_gerar(args: argparse.Namespace) -> int:
    def erro(texto: str) -> int:
        print(f"ERRO: {texto}", file=sys.stderr)
        return 2

    try:
        cfg = ler_config()
        tipo = ct.validar(args.tipo, args.isa)       # antes de qualquer modelo
    except (ErroConfig, ct.ErroContrato) as e:
        return erro(str(e))
    pasta = resolver_pasta(args.pasta)
    try:
        pasta.relative_to(REPO_ROOT)
    except ValueError:
        return erro(f"{pasta} esta fora do repositorio; use entregas/<nome>.")
    if args.exemplo and not any(Path(args.exemplo).glob("src/*.vhd")):
        return erro(f"--exemplo {args.exemplo}: nenhum src/*.vhd ali.")
    descricao = args.descricao
    if args.descricao_arquivo:
        try:
            descricao = Path(args.descricao_arquivo).read_text(encoding="utf-8-sig")
        except OSError as e:
            return erro(f"--descricao-arquivo {args.descricao_arquivo}: {e}")
    if descricao is not None and not descricao.strip():
        return erro("a descricao esta vazia.")
    try:
        executor = ex.escolher_executor(args.executor or cfg.executor, cfg.imagem_docker)
    except ex.ErroExecutor as e:
        return erro(f"{e}\nRode `python -m rvgen preparar` para ver o que falta.")

    relator = Relator(sys.stdout.isatty())
    provedor = args.provedor or cfg.provedor
    if provedor == "ollama":
        servidor = ol.localizar_servidor(ol.hosts_candidatos())
        if servidor is None:
            return erro("nenhum servidor Ollama respondeu. Rode `python -m rvgen preparar`.")
        try:
            modelo, origem = ol.resolver_modelo(args.modelo, args.perfil, cfg.modelo)
            instalados = ol.modelos_instalados(servidor[0])
        except ol.ErroOllama as e:
            return erro(str(e))
        if not ol.tem_modelo(instalados, modelo):
            return erro(f"o modelo {modelo} ({origem}) nao esta baixado. Rode "
                        f"`python -m rvgen preparar --modelo {modelo}`.")
        cliente = ClienteOllama(servidor[0], modelo, num_ctx=cfg.num_ctx,
                                temperatura=cfg.temperatura, timeout=cfg.timeout_s,
                                ao_progredir=relator.progresso)
        onde = f"ollama {modelo} ({origem}) em {servidor[0]}, num_ctx {cfg.num_ctx}"
    else:
        if not cfg.openrouter_key:
            return erro("OPENROUTER_API_KEY nao definida (.env ou ambiente).")
        modelo = args.modelo or cfg.modelo_externo
        cliente = ClienteOpenAI(cfg.openrouter_url, cfg.openrouter_key, modelo,
                                temperatura=cfg.temperatura, timeout=cfg.timeout_s)
        onde = f"openrouter {modelo}"

    rel_pasta = pasta.relative_to(REPO_ROOT).as_posix()
    print(f"rvgen gerar -> {rel_pasta}  ({tipo.nome}, {args.isa})")
    print(f"  modelo  : {onde}")
    print(f"  executor: {executor.nome}; ate {args.iteracoes} iteracoes de correcao"
          + (f"; exemplo: {args.exemplo}" if args.exemplo else ""))
    if descricao:
        print(f"  descricao: {len(descricao.strip())} caracteres, orienta o modelo abaixo "
              f"do contrato; NAO verificada pelo rvverify (vai para descricao.md)")
    agente = Agente(cliente=cliente, executor=executor, pasta=pasta, tipo=tipo,
                    isa=args.isa, iteracoes=args.iteracoes,
                    exemplo=Path(args.exemplo) if args.exemplo else None,
                    descricao=descricao, forcar=args.forcar, relatar=relator.linha)
    try:
        r = agente.gerar()
    except ErroIntegridade as e:
        print(f"\nVEREDITO RECUSADO: {e}", file=sys.stderr)
        return 1
    except (ErroGeracao, ErroLLM, ex.ErroExecutor) as e:
        # a pasta da sessao so existe se a geracao chegou a comecar
        onde = f"\n(sessao em {agente.sessao})" if agente.sessao.exists() else ""
        return erro(f"{e}{onde}")

    selo = "OBJETIVO ATINGIDO" if r.objetivo_atingido else "OBJETIVO NAO ATINGIDO"
    print(f"\n{'=' * 66}")
    print(f"{rel_pasta}   {r.veredito.upper()}   ({selo})")
    print("=" * 66)
    print(f"  placar final   : {r.placar.texto()}")
    print(f"  iteracoes      : {r.iteracoes} de correcao, {r.chamadas} chamadas ao modelo")
    print(f"  tokens         : {r.tokens_entrada} de entrada, {r.tokens_saida} de saida")
    print(f"  tempo          : {r.segundos / 60:.1f} min")
    print(f"  sessao         : {r.sessao.relative_to(REPO_ROOT).as_posix()}")
    print(f"  relatorio JSON : {r.relatorio.relative_to(REPO_ROOT).as_posix()}")
    print(f"  validar de novo: python -m rvverify {rel_pasta}")
    return 0 if r.objetivo_atingido else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m rvgen",
        description="Gera CPUs RISC-V com um agente de IA local (Ollama) ou "
                    "externo (OpenRouter) e as valida com o rvverify.",
    )
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("preparar", help="confere e prepara Ollama, modelo e executor")
    p.add_argument("--verificar", action="store_true",
                   help="so confere; nao instala, nao baixa, nao inicia nada")
    p.add_argument("--sim", action="store_true",
                   help="responde sim a toda confirmacao (para scripts)")
    p.add_argument("--modelo", help="modelo do Ollama (padrao: perfil pela VRAM)")
    p.add_argument("--perfil", choices=["auto", *ol.PERFIS], default=None,
                   help="perfil de modelo local (padrao: auto)")
    p.add_argument("--executor", choices=["auto", "local", "docker"], default=None,
                   help="onde rodar o rvverify (padrao: auto)")
    p.add_argument("--sem-cor", action="store_true", help="saida sem cor ANSI")
    p.set_defaults(func=cmd_preparar)

    t = sub.add_parser("tipos", help="lista os tipos de CPU e as ISAs aceitas")
    t.set_defaults(func=cmd_tipos)

    g = sub.add_parser("gerar", help="gera uma CPU, valida no rvverify e corrige")
    g.add_argument("pasta", help="nome do experimento (grava em experimentos/<nome>) "
                                 "ou uma pasta dentro do repositorio")
    g.add_argument("--tipo", required=True, choices=list(ct.TIPOS))
    g.add_argument("--isa", required=True,
                   help=f"ISA da CPU; o rvverify julga {', '.join(ct.ISAS)}")
    g.add_argument("--provedor", choices=["ollama", "openrouter"], default=None,
                   help="ollama (local, padrao) ou openrouter (externo)")
    g.add_argument("--modelo", help="modelo (padrao: perfil pela VRAM ou SPECHDL_LLM_MODEL)")
    g.add_argument("--perfil", choices=["auto", *ol.PERFIS], default=None,
                   help="perfil de modelo local")
    g.add_argument("--iteracoes", type=int, default=12,
                   help="maximo de correcoes antes do veredito (padrao: 12)")
    g.add_argument("--executor", choices=["auto", "local", "docker"], default=None,
                   help="onde rodar o rvverify (padrao: auto)")
    g.add_argument("--exemplo", metavar="DIR",
                   help="CPU de referencia cujo src/*.vhd entra no prompt "
                        "(ex.: cpus/rv32i_monociclo); fica registrado na sessao")
    g.add_argument("--forcar", action="store_true",
                   help="sobrescreve os arquivos gerados numa pasta que ja existe")
    d = g.add_mutually_exclusive_group()
    d.add_argument("--descricao", metavar="TEXTO",
                   help="descricao da CPU em texto livre; orienta o modelo abaixo do "
                        "contrato e NAO e verificada pelo rvverify (FR-RV-52)")
    d.add_argument("--descricao-arquivo", metavar="ARQUIVO",
                   help="o mesmo, lido de um arquivo de texto (UTF-8)")
    g.set_defaults(func=cmd_gerar)

    c = sub.add_parser("comparar", help="experimentos lado a lado: veredito, custo, tokens")
    c.add_argument("pastas", nargs="*",
                   help="experimentos ou pastas de experimentos (padrao: experimentos/)")
    c.add_argument("--todas", action="store_true",
                   help="todas as sessoes de cada experimento, nao so a mais recente")
    c.add_argument("--markdown", metavar="ARQUIVO",
                   help="grava a mesma tabela em Markdown (ex.: experimentos/COMPARACAO.md)")
    c.add_argument("--sem-rede", action="store_true",
                   help="nao busca precos no OpenRouter; custo externo sai como ?")
    c.set_defaults(func=cmd_comparar)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
