# Ponto de retomada do case

**Módulo 5A concluído em 16/10/2026: 359 decisões congeladas, sem pendências de exportação.** São 78 `publicar`, 277 `revisar` e quatro `fora`, com cobertura observada de 21,73%. Este é o ponto de parada para revisão e commit do usuário antes da avaliação real do módulo 5B. A meta de 95% de precisão ainda não foi verificada.

## Estado salvo

| Parte | Estado |
| --- | --- |
| Módulo 1: dados e árvore | Concluído: 359 questões preparadas, 377 temas validados, 375 ativos |
| Módulo 2: protocolo | Definido: política v1, referências por IA, censo do desenvolvimento e amostra de até 80 demais publicados |
| Módulo 3: integração e pilotos | Concluído: dois pilotos de vinte casos, prompt v2 selecionado |
| Módulo 4: lote completo | Concluído e commitado: 359 sugestões tecnicamente válidas |
| Módulo 5A: decisões | Concluído: CLI integrada, oito revisões registradas, CSV e trilha congelados; aguarda commit |
| Módulo 5B: avaliação | Pendente; preparar pacote cego e avaliar as publicadas |
| Módulo 6: relatório e memo | Pendente |
| Módulo 7: entrega final e reprodução | Pendente; verificar checkout limpo e pacote completo |

## Conclusão do módulo 5A

A base desta etapa foi o commit `d22435a54c59021f3eeea5dd698aad10d8e32d29`. O [CSV da raiz](../publicacao.csv) é cópia byte a byte do [CSV congelado](../artefatos/decisoes-v1/publicacao.csv). O [manifesto de decisões](../artefatos/decisoes-v1/manifesto_decisoes.json) registra contagens e hashes; a [trilha](../artefatos/decisoes-v1/trilha_decisoes.jsonl) preserva sugestões originais, aplicação da política e intervenções. O arquivo de pendências está vazio.

A política v1 foi aplicada sem alteração de limiar, modelo, prompt de classificação ou validadores das respostas. A aplicação inicial produziu 78 propostas de publicação, 273 de revisão e oito candidatos a `fora`. Os oito receberam uma leitura separada por IA, sem acesso inicial às respostas Gemini, seguida de adjudicação registrada com os resultados originais. Essa revisão não é validação por especialista nem auditoria das publicadas.

| Resultado da revisão de `fora` | Questões |
| --- | --- |
| Ausência de tema confirmada | Q0039, Q0113, Q0142, Q0168 |
| Tema encontrado; encaminhamento para `revisar` | Q0154 → 5135; Q0261 → 5136; Q0298 → 5222; Q0358 → 5133 |

As justificativas, evidências, dúvidas de escopo, fontes oficiais e o antes/depois estão em [revisoes.json](../artefatos/revisao_fora-v1/revisoes.json). A entrada reproduzível do exportador é [confirmacoes_fora.jsonl](../artefatos/revisao_fora-v1/confirmacoes_fora.jsonl). As quatro correções sempre exigem revisão; nenhuma foi promovida a `publicar`. As 78 publicações permaneceram iguais às propostas pela política.

O exportador recusa substituir uma saída completa por decisões diferentes. Reexecutar com entradas idênticas valida e reutiliza os mesmos arquivos, sem regravá-los; uma mudança posterior exige outra pasta/versionamento. A CLI inclui `preparar-decisoes`, `preparar-auditoria` e `avaliar-auditoria`; as duas últimas foram exercitadas apenas com dados sintéticos nos testes. Nenhuma amostra ou referência real da auditoria foi produzida nesta etapa.

O [checkpoint 5A](../artefatos/checkpoints/modulo5a_2026-10-16.json) reúne a base Git, os hashes, as verificações e os limites. Consulte [DECISOES_V1.md](DECISOES_V1.md) para os contratos e a reprodução.

### Verificações do módulo 5A

- Suíte completa: `python -B -m unittest discover -s tests -q`, com 233 testes, 232 aprovados e um pulado por falta de privilégio do Windows para criar link simbólico real; a proteção também tem teste simulado aprovado. Duração: 71,644 s.
- CSV com cabeçalho oficial, 359 IDs únicos na ordem preparada, temas ativos, extras válidos e motivos exigidos. As oito revisões estão coerentes com a trilha.
- Os 359 recibos originais e a revalidação de Q0005 permanecem idênticos ao checkpoint do módulo 4. As fontes locais, o prompt v2 e a política v1 foram preservados.
- Exportação repetida sem alterar bytes ou datas de modificação; reprodução em pasta temporária com os mesmos quatro produtos; cópia da raiz idêntica ao CSV congelado.
- Nenhuma chamada Gemini nesta etapa. As consultas às fontes públicas e a revisão por IA no Codex não têm consumo de tokens medido pelos recibos Gemini; não tratá-lo como zero.
- Conferência final dos hashes, links locais, arquivos versionáveis e `git diff --check`. `.env`, `contexto_local/` e os prompts expandidos continuam ignorados.

## Histórico preservado do módulo 4

O lote está em `artefatos/execucoes/lote-v2-35-flash-lite/`: 358 recibos originais com sucesso e a recuperação offline anterior de Q0005, totalizando 359 sugestões válidas. Os vinte sucessos do piloto v2 estão incluídos, pois foram reutilizados sem novas chamadas. Q0005 conserva o recibo original com status histórico de erro e quatro tentativas; `Q0005.revalidacao.json` fornece a sugestão efetiva após validar a origem. Validade técnica não representa decisão de publicação nem precisão jurídica medida.

O [checkpoint final](../artefatos/checkpoints/conclusao_modulo4_2026-10-16.json) registra os 359 IDs, hashes dos recibos e da revalidação, consumo, falhas e verificações. O [registro da execução contínua](../artefatos/experimentos/conclusao-lote-v2-2026-10-16.json) preserva as 29 invocações, seus horários e resumos. Seu estado `concluido_aguardando_verificacao_final` é o encerramento original do executor; a conferência posterior consta no checkpoint final. O [resumo do experimento](../artefatos/experimentos/lote-v2-35-flash-lite.json) aponta para esse checkpoint.

### Conclusão das 197 questões restantes

A continuação partiu do commit `6b86acdf4a09c868c92a3fd6c8a8ba380e1da6c3`, com 162 sugestões válidas e repositório limpo. Foram 227 novas chamadas: 197 sucessos, vinte falhas HTTP 503 e dez respostas rejeitadas pela validação local. Todas as falhas foram recuperadas em novas tentativas e permanecem nos históricos. As invocações internas fizeram até vinte chamadas cada, avançando automaticamente e aguardando após indisponibilidade transitória. O limite de proteção da continuação era 450 chamadas; ele não foi atingido.

As dez rejeições locais ocorreram em Q0171, Q0197, Q0208, Q0209, Q0215, Q0254, Q0322, Q0324, Q0339 e Q0345. Sete repetiram IDs entre extras e alternativas; três alteraram ou juntaram trechos da evidência. Todas passaram na segunda tentativa. Os validadores, o modelo, o prompt e a política permaneceram iguais; nenhum tema foi escolhido manualmente para contornar uma falha.

A execução durou 87 min 31,91 s de relógio, das 10:16:03 às 11:43:35 de 16/10, horário de São Paulo. A soma da duração das chamadas foi 2.355,46 s; o restante inclui intervalos, esperas e processamento local. Esse tempo observado não mede o esforço humano total das vinte horas estimadas para o projeto.

| Consumo registrado | Esta continuação | Lote acumulado |
| --- | ---: | ---: |
| Tentativas reais, incluindo erros | 227 | 404 |
| Tokens totais informados | 6.257.155 | 11.350.512 |
| Tentativas com uso informado | 207 | 376 |
| Tentativas sem metadados de uso | 20 | 28 |

Uso ausente é desconhecido, não zero. O total do lote já inclui as 21 tentativas do piloto v2 reutilizado; não somá-las novamente. Somando as vinte tentativas do piloto v1, são 424 tentativas únicas registradas nos experimentos de classificação. Houve 247 chamadas registradas desse modelo em 16/10, das quais vinte pertencem ao bloco anterior e 227 a esta continuação. Isso é contagem local dos recibos, não consulta de saldo ao provedor. A interrupção de 14/10 pode ter ocorrido após uma chamada ainda sem recibo; eventual uso não registrado permanece desconhecido.

A última invocação terminou com código zero. O executor encerrou, nenhum processo desse lote ficou em execução e não há lock residual. Os checkpoints anteriores, incluindo a [base de 162 válidas](../artefatos/checkpoints/bloco_2026-10-16_01.json), permanecem preservados; o histórico dos blocos está em [PLANO_EXECUCAO.md](PLANO_EXECUCAO.md).

### Verificações da conclusão do módulo 4

- `python -B -m unittest discover -s tests -q`: 213 testes, 212 aprovados e um pulado por falta de privilégio do Windows para criar link simbólico real; a proteção também tem teste simulado aprovado. Duração: 46,556 s. A suíte foi executada nesta retomada; não foi repetida após alterações apenas de dados e documentação.
- Os 359 recibos tiveram identidade do experimento, checksum e histórico conferidos. As 359 sugestões efetivas passaram pelo esquema, IDs ativos e correspondência de evidência. A revalidação de Q0005 teve origem e seleção cronológica conferidas novamente.
- Os 162 recibos anteriores e o derivado de Q0005 permaneceram byte a byte idênticos. As 197 questões novas conservam suas tentativas, erros e metadados de uso.
- Fontes originais, manifestos, código, testes, modelo, prompt, política e regras de validação permaneceram iguais.
- A preparação e os prompts já haviam sido reconstruídos offline em pasta temporária com hashes idênticos. Os hashes foram reconferidos no encerramento; a pendência de fins de linha no Git está descrita abaixo.
- `.env` e `contexto_local/` continuam ignorados. A conferência final inclui busca de credencial Google nos arquivos versionáveis, links locais da documentação e `git diff --check`.
- Nenhum commit, push, aplicação da política, auditoria ou exportação final foi realizado nesta continuação.

## Ajuste de reprodução a incluir neste commit

O `temas.csv` local usa CRLF e coincide exatamente com o hash do manifesto (`9c6e98a6cd568816671c0fa14e2449b152cee10e20cb1327b3b097c1c5ce4cbc`). O blob no HEAD anterior usa LF (`260c1826a6604a64ce26be0883ddc63e2ba768f1e55dcf88f323db42be36325c`). O texto é idêntico; apenas os fins de linha diferem. No módulo 5A, essa pendência foi corrigida no índice real do Git e ainda precisa entrar no commit.

Foi executado `git add --renormalize -- temas.csv`, com o atributo atual `-text`. A fonte local não foi editada; o índice agora contém seus bytes exatos. `git ls-files --eol temas.csv` mostra `i/crlf w/crlf attr/-text`, e a comparação ignorando fins de linha não mostra mudança textual. Os checkpoints históricos registram corretamente a pendência existente quando foram criados e permanecem intactos. O atributo `-text` também foi acrescentado para `publicacao.csv`, para preservar seu hash em outros checkouts.

A regra de whitespace de `temas.csv` reconhece o CRLF preservado como fim de linha, mantendo a checagem de espaços finais. Assim, `git diff --cached --check` não confunde a restauração dos bytes originais com espaços excedentes.

## Commit deste módulo

Este commit reúne o módulo 5A: exportação e integração CLI, testes, oito revisões, decisões congeladas, CSV da raiz, checkpoint e documentação. `temas.csv` já está preparado no índice. O assistente não fez commit ou push; os demais arquivos devem ser revisados e adicionados pelo usuário.

Comandos sugeridos, a partir da raiz:

```powershell
git status --short
git ls-files --eol temas.csv
git diff --cached --ignore-space-at-eol -- temas.csv
git add .gitattributes README.md docs/RETOMADA.md docs/PLANO_EXECUCAO.md docs/DECISOES_V1.md
git add classificacao_topicos/__main__.py classificacao_topicos/decisoes.py tests/test_cli.py tests/test_cli_decisoes.py tests/test_decisoes.py
git add prompts/revisao_fora_v1.txt artefatos/revisao_fora-v1 artefatos/decisoes-v1 artefatos/checkpoints/modulo5a_2026-10-16.json publicacao.csv
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git commit -m "feat: congela decisoes e integra avaliacao"
```

Os arquivos grandes `artefatos/piloto/entradas.jsonl`, `artefatos/piloto-v2/entradas.jsonl` e `artefatos/lote-v2/entradas.jsonl` continuam locais e ignorados: repetem o catálogo e são regeneráveis. Não usar `git add -f` para incluir `.env`, contexto privado ou prompts expandidos.

## Retomada e reprodução

Na mesma pasta, ler este registro e conferir `git status --short`. O módulo 4 está completo: não é necessário executar novas chamadas de classificação. As cotas informadas pelo usuário para o modelo eram 15 RPM, 250 mil TPM e 500 RPD; uma futura etapa com API precisa considerar o uso do dia. Nenhum gasto ou ativação de faturamento foi autorizado.

Em outro checkout, usar o commit que inclua os bytes corretos de `temas.csv`, conforme acima. Os prompts expandidos não estarão no Git; reconstruí-los antes de validar recibos ou decisões:

```powershell
python -B -m classificacao_topicos preparar
python -B -m classificacao_topicos preparar-piloto
python -B -m classificacao_topicos preparar-piloto --saida artefatos/piloto-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -B -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -B -m classificacao_topicos preparar-decisoes --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --politica config/politica_v1.json --confirmacoes-fora artefatos/revisao_fora-v1/confirmacoes_fora.jsonl --saida artefatos/decisoes-v1
python -B -m unittest discover -s tests -q
```

Esses comandos são offline. A chave deve ser configurada localmente conforme [CONFIGURACAO_API.md](CONFIGURACAO_API.md) quando necessária. Não repetir `verificar-api` se a integração já estiver funcionando: cada teste sintético é uma chamada real.

### Recuperação técnica de Q0005

A primeira resposta salva passa integralmente na validação atual, que tolera apenas caixa e espaços. A recuperação anterior foi registrada em `Q0005.revalidacao.json`; o recibo original, suas quatro tentativas e seus 122.031 tokens permanecem intactos. Não houve chamada de API, escolha manual de tema ou relaxamento adicional nesta continuação.

```powershell
python -B -m classificacao_topicos revalidar-recibo --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --id Q0005
```

O comando é offline e idempotente quando o derivado existente é válido. O executor e o módulo de decisões validam o derivado antes de usar a sugestão; o histórico original é a fonte exclusiva do consumo. Um derivado adulterado ou incompatível interrompe o processamento. Não editar o status do recibo original.

Ao conferir o lote por scripts, selecionar recibos por `Q[0-9]{4}\.json`, pois `Q*.json` inclui também o derivado. Separar status original e status efetivo. A função `carregar_revalidacao` verifica a origem e a seleção antes de `status_efetivo` ou `sugestao_efetiva`.

## Próximos módulos

1. **5B — avaliação:** preparar o pacote cego com censo dos publicados entre os vinte casos de desenvolvimento e amostra sem reposição de `min(80,N)` demais publicados, semente `2026101401`. Como há apenas 78 publicados no total, essa regra levará a revisar todos eles, preservando a distinção entre desenvolvimento e restante. Produzir referências provisórias de IA e calcular os cenários conservador e otimista, condicionados à referência.
2. **6 — relatório:** preencher `previsao.txt` e produzir relatório de até cinco páginas, incluindo memo de uma página e proposta para 50 mil questões por semana.
3. **7 — entrega:** verificar arquivos finais e reprodução em checkout limpo. Publicação do repositório e envio dos materiais dependem de instrução do usuário.

## Decisões que devem ser preservadas

O usuário não tem apoio jurídico disponível e não há gabarito oficial. A referência futura será identificada como produzida por IA. Concordância entre IAs não comprova precisão jurídica. O limiar 0,95 é operacional e a confiança é autodeclarada, não calibrada. A política foi registrada antes de inspecionar as novas classificações; não ajustá-la sobre a amostra e depois chamar essa avaliação de independente.

Na avaliação local, igualdade de ID ou relação imediata pai/filho é aceita; irmãos e ancestrais distantes permanecem distintos. Essa interpretação conservadora do case está documentada. A confiança das quatro sugestões corrigidas vem do revisor; a de `fora` é zero como sentinela de não aplicável. O intervalo da cobertura observada será degenerado. As convenções estão em [AVALIACAO.md](AVALIACAO.md).

Para retomar: **“Leia docs/RETOMADA.md e continue somente o módulo 5B; pare ao concluir para eu revisar e commitar.”**
