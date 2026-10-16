# Ponto de retomada do case

**Módulo 4 concluído em 16/10/2026: 359 de 359 sugestões tecnicamente válidas, sem pendências.** O usuário autorizou concluir de uma vez as 197 questões restantes, substituindo as pausas a cada vinte chamadas. A execução terminou e a integridade do lote foi conferida. Este é o ponto de parada para revisão e commit; o módulo 5A e a auditoria não foram iniciados.

## Estado salvo

| Parte | Estado |
| --- | --- |
| Módulo 1: dados e árvore | Concluído: 359 questões preparadas, 377 temas validados, 375 ativos |
| Módulo 2: protocolo | Definido: política v1, referências por IA, censo do desenvolvimento e amostra de até 80 demais publicados |
| Módulo 3: integração e pilotos | Concluído: dois pilotos de vinte casos, prompt v2 selecionado |
| Módulo 4: lote completo | Concluído: 359 sugestões tecnicamente válidas, zero falhas atuais e zero IDs sem recibo |
| Módulo 5A: decisões | Funções e testes offline prontos; integração CLI, aplicação da política e confirmação de `fora` pendentes |
| Módulo 5B: avaliação | Pendente; executar após congelar as decisões |
| Módulo 6: relatório e memo | Pendente |
| Módulo 7: entrega final e reprodução | Pendente; o lote concluído ainda não é a entrega final |

O lote está em `artefatos/execucoes/lote-v2-35-flash-lite/`: 358 recibos originais com sucesso e a recuperação offline anterior de Q0005, totalizando 359 sugestões válidas. Os vinte sucessos do piloto v2 estão incluídos, pois foram reutilizados sem novas chamadas. Q0005 conserva o recibo original com status histórico de erro e quatro tentativas; `Q0005.revalidacao.json` fornece a sugestão efetiva após validar a origem. Validade técnica não representa decisão de publicação nem precisão jurídica medida.

O [checkpoint final](../artefatos/checkpoints/conclusao_modulo4_2026-10-16.json) registra os 359 IDs, hashes dos recibos e da revalidação, consumo, falhas e verificações. O [registro da execução contínua](../artefatos/experimentos/conclusao-lote-v2-2026-10-16.json) preserva as 29 invocações, seus horários e resumos. Seu estado `concluido_aguardando_verificacao_final` é o encerramento original do executor; a conferência posterior consta no checkpoint final. O [resumo do experimento](../artefatos/experimentos/lote-v2-35-flash-lite.json) aponta para esse checkpoint.

## Conclusão das 197 questões restantes

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

## Verificações da conclusão

- `python -B -m unittest discover -s tests -q`: 213 testes, 212 aprovados e um pulado por falta de privilégio do Windows para criar link simbólico real; a proteção também tem teste simulado aprovado. Duração: 46,556 s. A suíte foi executada nesta retomada; não foi repetida após alterações apenas de dados e documentação.
- Os 359 recibos tiveram identidade do experimento, checksum e histórico conferidos. As 359 sugestões efetivas passaram pelo esquema, IDs ativos e correspondência de evidência. A revalidação de Q0005 teve origem e seleção cronológica conferidas novamente.
- Os 162 recibos anteriores e o derivado de Q0005 permaneceram byte a byte idênticos. As 197 questões novas conservam suas tentativas, erros e metadados de uso.
- Fontes originais, manifestos, código, testes, modelo, prompt, política e regras de validação permaneceram iguais.
- A preparação e os prompts já haviam sido reconstruídos offline em pasta temporária com hashes idênticos. Os hashes foram reconferidos no encerramento; a pendência de fins de linha no Git está descrita abaixo.
- `.env` e `contexto_local/` continuam ignorados. A conferência final inclui busca de credencial Google nos arquivos versionáveis, links locais da documentação e `git diff --check`.
- Nenhum commit, push, aplicação da política, auditoria ou exportação final foi realizado nesta continuação.

## Ajuste de reprodução a incluir neste commit

O `temas.csv` local usa CRLF e coincide exatamente com o hash do manifesto (`9c6e98a6cd568816671c0fa14e2449b152cee10e20cb1327b3b097c1c5ce4cbc`). O blob no HEAD usa LF (`260c1826a6604a64ce26be0883ddc63e2ba768f1e55dcf88f323db42be36325c`). O texto é idêntico; apenas os fins de linha diferem. Essa pendência continua presente apesar da mensagem do commit anterior. Ela não afeta a execução local, mas precisa ser corrigida para reproduzir os hashes em outro checkout.

O comando `git add --renormalize -- temas.csv`, com o atributo atual `-text`, prepara no índice os bytes exatos da fonte local. Foi comprovado em índice e armazenamento de objetos temporários, fora do repositório. A fonte e o índice real permaneceram intactos; o comando deve ser executado pelo usuário junto ao commit abaixo. Depois, `git ls-files --eol temas.csv` deve mostrar `i/crlf w/crlf attr/-text`. A comparação ignorando fins de linha não deve mostrar mudança textual.

## Commit deste módulo

Este commit reúne 197 novos recibos, o registro contínuo, o checkpoint final, o resumo do experimento e a documentação. Os commits anteriores não precisam ser refeitos.

Comandos sugeridos, a partir da raiz:

```powershell
git status --short
git add --renormalize -- temas.csv
git ls-files --eol temas.csv
git diff --cached --ignore-space-at-eol -- temas.csv
git add README.md docs/RETOMADA.md docs/PLANO_EXECUCAO.md artefatos/checkpoints/conclusao_modulo4_2026-10-16.json artefatos/experimentos/conclusao-lote-v2-2026-10-16.json artefatos/experimentos/lote-v2-35-flash-lite.json artefatos/execucoes/lote-v2-35-flash-lite
git diff --cached --stat
git diff --cached --name-only
git commit -m "data: conclui lote de classificacao v2"
```

Os arquivos grandes `artefatos/piloto/entradas.jsonl`, `artefatos/piloto-v2/entradas.jsonl` e `artefatos/lote-v2/entradas.jsonl` continuam locais e ignorados: repetem o catálogo e são regeneráveis. Não usar `git add -f` para incluir `.env`, contexto privado ou prompts expandidos.

## Retomada e reprodução

Na mesma pasta, ler este registro e conferir `git status --short`. O módulo 4 está completo: não é necessário executar novas chamadas de classificação. As cotas informadas pelo usuário para o modelo eram 15 RPM, 250 mil TPM e 500 RPD; uma futura etapa com API precisa considerar o uso do dia. Nenhum gasto ou ativação de faturamento foi autorizado.

Em outro checkout, corrigir primeiro os bytes de `temas.csv` no commit conforme acima. Os prompts expandidos não estarão no Git; reconstruí-los antes de executar ou validar recibos:

```powershell
python -B -m classificacao_topicos preparar
python -B -m classificacao_topicos preparar-piloto
python -B -m classificacao_topicos preparar-piloto --saida artefatos/piloto-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -B -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
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

1. **5A — decisões:** integrar à CLI as funções existentes de decisões, auditoria e avaliação, preservando os testes e contratos; aplicar `config/politica_v1.json`; confirmar separadamente as propostas de `fora`; gerar as 359 linhas de `publicacao.csv` e congelar as decisões. Parar para revisão e commit antes de revisar a amostra.
2. **5B — avaliação:** preparar o pacote cego com censo dos publicados entre os vinte casos de desenvolvimento e amostra sem reposição de `min(80,N)` demais publicados, semente `2026101401`. Produzir referências de IA sem acesso às respostas Gemini e calcular os cenários conservador e otimista, condicionados à referência.
3. **6 — relatório:** preencher `previsao.txt` e produzir relatório de até cinco páginas, incluindo memo de uma página e proposta para 50 mil questões por semana.
4. **7 — entrega:** verificar arquivos finais e reprodução em checkout limpo. Publicação do repositório e envio dos materiais dependem de instrução do usuário.

## Decisões que devem ser preservadas

O usuário não tem apoio jurídico disponível e não há gabarito oficial. A referência futura será identificada como produzida por IA. Concordância entre IAs não comprova precisão jurídica. O limiar 0,95 é operacional e a confiança é autodeclarada, não calibrada. A política foi registrada antes de inspecionar as novas classificações; não ajustá-la sobre a amostra e depois chamar essa avaliação de independente.

Na avaliação local, igualdade de ID ou relação imediata pai/filho é aceita; irmãos e ancestrais distantes permanecem distintos. Essa interpretação conservadora do case está documentada. A confiança de `fora` será zero como sentinela de não aplicável; o intervalo da cobertura observada será degenerado. As convenções estão em [AVALIACAO.md](AVALIACAO.md).

Para retomar: **“Leia docs/RETOMADA.md e continue somente o módulo 5A; pare ao concluir para eu revisar e commitar.”**
