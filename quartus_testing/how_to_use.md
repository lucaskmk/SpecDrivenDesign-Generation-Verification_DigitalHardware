# Como testar uma CPU no Quartus

Um comando compila a sua CPU no Quartus Prime Lite (dentro do Docker) e
responde quatro perguntas:

1. **Compila?** Se não compila, mostra o erro, com arquivo e linha.
2. **Frequência:** Fmax, se atinge o clock alvo e o caminho crítico.
3. **Uso da FPGA:** ALMs, LUTs, registradores, memória, DSP, pinos.
4. **Potência:** estimada pelo Quartus.

Não muda nada na sua CPU nem no veredito do `rvverify`. Detalhes de como
foi feito estão em
[`quartus_testing_report_implementation.md`](quartus_testing_report_implementation.md).

## 1. Antes de começar

Você precisa de quatro coisas:

| o quê | como conferir | se faltar |
|---|---|---|
| **O repositório clonado** | — | o script precisa ficar em `quartus_testing/`, dentro do repo: copiado sozinho, ele não roda |
| **Python 3.11 ou mais novo** | `python --version` | instale um Python novo; o 3.10 não serve |
| **Docker aberto e rodando** | `docker info` responde sem erro | abra o Docker Desktop (o script **não** abre o Docker sozinho) |
| **A imagem do Quartus** (~8 GB, uma vez só) | `docker images` mostra `gabrielgalazzi/imagens_projeto_descomp:25.1` ou `quartus-lite:25.1` | `docker pull gabrielgalazzi/imagens_projeto_descomp:25.1` |

E a **pasta da sua CPU** precisa ter um `cpu.toml`. Para o Quartus, só duas
tabelas importam:

```toml
[design]
name    = "fulano"                       # vira o nome da pasta de resultados
top     = "cpu"                          # entidade de topo
std     = "08"
sources = ["src/alu.vhd", "src/cpu.vhd"] # na ORDEM de análise (pacotes primeiro)

[clock]
signal    = "clk"                        # nome da porta de clock do topo
period_ns = 10                           # 10 ns = alvo de 100 MHz
```

Se a sua CPU já passa no `rvverify`, o `cpu.toml` dela já serve.

## 2. Rodar

Da raiz do repositório:

```bash
python quartus_testing/quartus_cpu_check.py entregas/fulano
```

Funciona com qualquer pasta, dentro ou fora do repo: `cpus/rv32i_pipeline`,
`../entregas/corsi_v4` etc. Leva de **30 s** (design pequeno) a **alguns
minutos** por compilação; uma CPU RV32IM em pipeline levou ~5 min.

Opções úteis:

| quero… | acrescente |
|---|---|
| testar como RV32I **e** como RV32IM (precisa de `rv32m_generic` no `cpu.toml`) | `--isa ambas` |
| outro clock alvo (ex.: 50 MHz) | `--periodo-ns 20` |
| outro FPGA | `--device 5CEFA9F23C7` |
| tentar de novo quando o Quartus diz que **não roteou** | `--roteamento-agressivo` |
| salvar os resultados em outro lugar | `--saida minha/pasta` |
| ver todas as opções | `--help` |

## 3. O que aparece no terminal

Primeiro, uma linha por etapa enquanto roda. No fim, o resumo. Este é o de
uma execução real:

```text
== padrao (generics do cpu.toml e defaults do VHDL) ==
  compila     sim (130.5 s)
  frequencia  Fmax 70.72 MHz (alvo 100 MHz: NAO atende), slack setup -4.14 ns, hold 0.322 ns
              caminho critico: register_file:u_register_file|registers[28][22] -> register_file:u_register_file|registers[30][2]
  recursos    ALMs 1.454 / 18.480 (8 %), LUTs (ALUTs) 1.849, registradores 1.023
              memoria 0 / 3.153.920 (0 %) bits (M10K 0 / 308 (0 %)), DSP 0 / 66 (0 %), PLLs 0 / 4 (0 %), pinos 165 / 224 (74 %)
  potencia    301.44 mW ESTIMADOS (dinamica 83.8, estatica 194.22, E/S 23.42); confianca: Low: user provided insufficient toggle rate data
  checagens   10 ok

veredito: COMPILA   relatorio: quartus_testing/resultados/corsi_v4/relatorio.md (e relatorio.json)
```

Quando **não compila**, o resumo mostra o erro e uma dica. Exemplo real, com
o caminho encurtado:

```text
  compila     NAO -- Analysis & Synthesis: erro_de_sintese
    Error (10482) [.../src/mono_alu.vhd:47]: VHDL error at mono_alu.vhd(47): object "sinal_que_nao_existe" is used but not declared
    dica: O VHDL nao passou pela analise e sintese do Quartus. Veja os erros (arquivo e linha): ...
```

O **exit code** também diz o resultado, o que é útil em script: `0` compila,
`1` não compila, `2` problema antes de compilar (Docker, imagem, `cpu.toml`).

## 4. Onde fica cada coisa

Tudo vai para **`quartus_testing/resultados/<name do cpu.toml>/`**. A pasta
fica fora do Git e é recriada a cada execução da mesma CPU.

```text
quartus_testing/resultados/fulano/
├── relatorio.md               ← COMECE AQUI: o relatório completo, legível
├── relatorio.json             ← os mesmos dados, para outro programa ler
├── quartus_output_padrao/     ← evidência de uma revisão (com --isa ambas: _rv32i e _rv32im)
│   ├── compilation/
│   │   ├── compile.log        ← log inteiro do Quartus (o erro de verdade está aqui)
│   │   ├── fmax.log           ← saída do cálculo de Fmax
│   │   └── power.log          ← saída do Power Analyzer
│   ├── reports/
│   │   ├── *.fit.summary      ← uso de recursos, direto do Quartus
│   │   ├── *.sta.summary      ← slack de timing por corner
│   │   ├── *.pow.summary      ← potência
│   │   ├── critical_path.log  ← o caminho crítico, célula por célula
│   │   └── summary.json       ← resumo no formato do wrapper analyze
│   ├── netlist/               ← dados de síntese (*.map.rpt, rtl_netlist.log)
│   └── bitstream/*.sof        ← arquivo para gravar na placa (só se compilou)
├── output_files/              ← todos os relatórios brutos do Quartus (*.fit.rpt, *.sta.rpt…)
├── src/                       ← cópia das suas fontes que foi compilada
└── *.qpf, *.qsf, comum.tcl, *.sdc   ← o projeto Quartus gerado do cpu.toml
```

Para abrir o projeto na GUI do Quartus depois, rode com `--manter-projeto`.
Sem isso, o banco de dados do Quartus (`db/`, centenas de MB) é apagado no
fim.

## 5. Como ler o `relatorio.md`

Ele tem um **resumo** no topo, com uma linha por revisão. Depois vem uma
seção por revisão:

- **1. Compila?** Diz *sim* ou *não*, a etapa em que parou e o motivo:
  - `erro_de_sintese`: erro no VHDL. O Quartus é mais estrito que o GHDL, então
    uma CPU aprovada no `rvverify` ainda pode reprovar aqui.
  - `nao_cabe`: precisa de mais recursos do que o FPGA tem. O relatório mostra
    quanto passou (ex.: 128 % dos ALMs).
  - `nao_roteia`: coube, mas o roteamento falhou. Tente
    `--roteamento-agressivo`.
  - `compilacao_incompleta`: o Quartus não terminou (tempo limite ou memória
    do Docker).
- **2. Frequência.** *Fmax* é a frequência máxima. *Atende* compara com o
  `period_ns` do `cpu.toml`. *Slack* negativo = não fecha timing no alvo.
  O *caminho crítico* é onde está o atraso.
- **3. Recursos da FPGA.** No Cyclone V, LUT = **ALUT**; o FPGA é "cobrado" em
  **ALMs**. *Memória em bloco* = bits em M10K. Zero aqui com muitos
  registradores quer dizer que as memórias viraram flip-flops.
- **4. Potência.** É sempre **estimativa**, não medição. A confiança baixa é o
  próprio Quartus avisando que não tem dados de atividade real.
- **Checagens.** Uma tabela `ok` / `falhou` / `aviso` / `pulado`. *Pulado* só
  quer dizer que a etapa anterior não deixou nada para checar, por exemplo
  sem fit não há timing.

## 6. Avisos que você pode ver

- **"registradores sem fan-out preservados"**: o topo da sua CPU não tem
  nenhuma porta de saída (só `clk`/`rst`, como as CPUs de referência). Sem
  ajuda, o Quartus apagaria a CPU inteira, porque nada é observável. O script
  liga sozinho uma opção que mantém a lógica. O VHDL não muda, e a área sai um
  pouco maior do que seria com saídas reais.
- **"O Quartus removeu a lógica da CPU" / 0 registradores**: aconteceu mesmo
  assim. Os números **não** representam a CPU. Rode de novo com
  `--preservar-logica sim`.
- **"Fmax não confiável"**: o `[clock].signal` do `cpu.toml` não é o nome de
  uma porta do topo, e o Quartus ignorou a restrição de clock. Corrija o nome.

## 7. Problemas comuns

| mensagem | o que fazer |
|---|---|
| `o Docker nao esta rodando` | abra o Docker Desktop e espere ele subir |
| `nenhuma imagem do Quartus encontrada` | `docker pull gabrielgalazzi/imagens_projeto_descomp:25.1` |
| `precisa de Python 3.11+` | rode com um Python mais novo (ex.: `python3.12 quartus_testing/...`) |
| `o Docker nao consegue montar ...` | a pasta de saída está fora do que o Docker Desktop compartilha: use uma `--saida` dentro da sua pasta de usuário |
| `nao tem cpu.toml` / `falta [clock]` / `fonte(s) que nao existem` | arrume o `cpu.toml` (seção 1) |
| `ImportError: nao encontrei o wrapper analyze` | o script foi copiado para fora do repositório; rode-o de `quartus_testing/` |
| `ja existe e nao foi criada por esta ferramenta` | a `--saida` aponta para uma pasta com outras coisas; escolha uma pasta nova |
| duas CPUs sobrescrevendo os resultados uma da outra | elas têm o mesmo `name` no `cpu.toml`: mude o nome ou use `--saida` |
