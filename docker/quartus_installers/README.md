# Cache dos instaladores do Quartus (não versionado)

Esta pasta existe só para receber, localmente, os arquivos que o
`docker/Quartus_Dockerfile` copia pra dentro da imagem. Nada aqui é
versionado (ver `.gitignore`) — são binários de gigabytes, sob licença da
Altera, e cada máquina que builda a imagem baixa os seus.

## Por que isso não é automático

O CDN de download da Altera (`download.altera.com/akdlm/...`) fica atrás de
mitigação de bot da Akamai e de um aceite de licença na própria página de
download. As duas coisas exigem uma sessão de navegador de verdade — um
`curl`/`wget` sem essa sessão recebe HTTP 403, mesmo com User-Agent e
Referer de navegador (conferido em 2026-09-18, ver `specs/decisions.md`,
ADR-015). Isso vale igual dentro de um `RUN curl` do `docker build`: não é
uma questão de quem builda, a barreira é a mesma. Por isso o Dockerfile não
tenta baixar nada — ele espera os arquivos já aqui.

## Passo a passo

1. Abra num navegador de verdade e aceite a licença:
   https://www.altera.com/downloads/fpga-development-tools/quartus-prime-lite-edition-design-software-version-25-1-linux
2. Baixe:
   - `QuartusLiteSetup-25.1std.0.1129-linux.run` (instalador base, ~2 GB)
   - `cyclonev-25.1std.0.1129.qdz` (suporte ao device Cyclone V — o alvo
     deste projeto, `5CEBA4F23C7`; é o único `DEVICE_SUPPORT` default)
   - qualquer outro `<familia>-25.1std.0.1129.qdz` só se for habilitar
     outra família no build (`cycloneiv`, `cyclone10lp`, `max10`, `max` —
     ver o cabeçalho de `docker/Quartus_Dockerfile` pro nome exato de
     arquivo esperado por família; só `cyclonev` foi conferido contra uma
     resposta real do servidor)
3. Coloque os arquivos aqui, sem renomear.
4. Builde a partir da raiz do repositório:
   ```
   docker build -f docker/Quartus_Dockerfile -t quartus-lite:25.1 docker
   ```

Se a versão 25.1std.0.1129 mudar (Intel/Altera lança uma build nova), passe
`--build-arg QUARTUS_VERSION=<nova versão>` no build e baixe os arquivos
correspondentes com esse mesmo sufixo de versão.

## Verificação de integridade (opcional)

Não há checksum oficial publicado pela Altera pra conferir automaticamente
— por isso o Dockerfile não trava o build em nenhum hash. Se você quiser
detectar corrupção entre downloads futuros, gere o seu próprio arquivo
`SHA256SUMS` nesta pasta (`sha256sum *.run *.qdz > SHA256SUMS`) depois do
primeiro download confiável: o Dockerfile confere contra ele automaticamente
se o arquivo existir.
