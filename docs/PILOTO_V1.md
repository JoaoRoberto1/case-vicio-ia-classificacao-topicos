# Primeiro piloto: classificação com catálogo completo

Este documento registra os dois pilotos e a escolha da versão para o lote completo.

## Pergunta do experimento

Uma chamada com a questão completa e todos os temas ativos consegue sugerir um tema central e reconhecer ambiguidades suficientes para orientar uma política de publicação? O piloto avalia essa hipótese em vinte casos de desenvolvimento. Não mede a precisão das futuras publicadas.

## Configuração e justificativa

- Questões: dez casos deliberados e dez complementares por diversidade estrutural, registrados em `artefatos/piloto/manifesto_piloto.json`.
- Prompt: `prompts/classificacao_v1.txt`, com todos os 375 temas ativos, seus IDs e caminhos. Descrições substantivas são preservadas; contagens históricas são omitidas.
- Campos da questão: enunciado, comando e alternativas normalizados. Origem excluída como hipótese inicial para reduzir influência de classificações anteriores potencialmente incorretas.
- Catálogo completo: evita introduzir nesta primeira versão uma busca de candidatos que poderia excluir o tema correto. O custo em tokens é medido para comparação posterior com alternativas mais econômicas.
- Modelo executado: `gemini-3.5-flash-lite`, raciocínio `MEDIUM`, resposta JSON estruturada, validação local de IDs ativos e evidência literal.
- Saídas: sugestões, sem converter confiança autodeclarada em probabilidade calibrada ou decisão de publicação.
- Intervalo no lote: trinta segundos entre novas chamadas, além do tempo de resposta. Interrupção na primeira falha técnica.

## Integração real em 14/10/2026

O usuário confirmou o nível gratuito do projeto e guardou a chave no `.env` local. A chave não foi exposta nem incluída nos artefatos. O arquivo foi preservado; modelos alternativos foram selecionados pela variável `GEMINI_MODEL` apenas no processo de execução.

As primeiras chamadas sintéticas identificaram uma divergência entre o tutorial e o contrato efetivo do endpoint: `responseFormat.text.mimeType` exige o enum `APPLICATION_JSON`. A rejeição HTTP 400 foi corrigida conforme a [referência REST](https://ai.google.dev/api/generate-content?hl=en#TextResponseFormat). O cliente passou a preservar diagnóstico HTTP sanitizado e duração, mantendo headers e credenciais fora dos registros.

Após a correção, `gemini-3.8-flash` retornou HTTP 503 em três tentativas espaçadas. Uma tentativa com `gemini-3.6-flash` também retornou 503. A chamada sintética com `gemini-3.5-flash-lite` funcionou: 18 tokens de entrada, nove de saída e 27 no total. Todos os recibos sintéticos estão em `artefatos/execucoes/verificacoes_api.jsonl`; tentativas sem informação de tokens não são contabilizadas como consumo zero.

O uso do Flash-Lite neste experimento decorre de disponibilidade observada, não de superioridade temática demonstrada. Sua ficha declara suporte a saída estruturada e a tabela de preços inclui nível gratuito. A qualidade será examinada nos casos do piloto. [Ficha do modelo](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [preços](https://ai.google.dev/gemini-api/docs/pricing).

## Cotas informadas pelo usuário

| Modelo | Requisições/minuto | Tokens/minuto | Requisições/dia |
| --- | ---: | ---: | ---: |
| Gemini 3.8 Flash | 60 | 100.000 | 100 |
| Gemini 3.5 Flash-Lite | 15 | 250.000 | 500 |

Esses limites foram informados a partir do painel do projeto em 14/10/2026, não obtidos automaticamente pelo código. Estão sujeitos às condições do provedor. O projeto gratuito não exige ativação de faturamento para as chamadas planejadas.

## Referência provisória e limites

As vinte questões receberam propostas temáticas de agentes de IA que leram os textos e a taxonomia sem consultar respostas do classificador. Elas estão em `artefatos/revisao_piloto/proposta_deliberados.jsonl` e `proposta_complementares.jsonl`, com justificativa e limitações por item.

Essa revisão é referência de desenvolvimento produzida por IA. Não constitui gabarito oficial, julgamento de especialista ou auditoria independente da qualidade jurídica. A redação das propostas ocorreu em paralelo às chamadas, com separação de acesso às respostas, e não será apresentada como pré-registro anterior a toda a execução.

Há onze propostas provisórias e nove julgamentos inconclusivos. Quando a referência é inconclusiva, coincidir com seu ID sugerido não transforma o caso em acerto demonstrado. Concordância entre modelos também pode refletir erros compartilhados. A análise deve manter diferenças entre IDs do mesmo ramo visíveis e não assumir equivalência irrestrita na regra oficial.

## Reprodução no PowerShell

Depois de preparar dados e piloto e configurar a chave local:

```powershell
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
python -m classificacao_topicos executar-piloto --saida artefatos/execucoes/piloto-v1-35-flash-lite --limite 20 --intervalo-segundos 30
```

A variável definida acima vale para a sessão do terminal e tem precedência sobre o `.env`. Recibos válidos são reutilizados; o comando não repete itens já concluídos. Para repetir o experimento com novas chamadas, use outra pasta de saída e verifique as cotas disponíveis.

O registro `artefatos/experimentos/piloto-v1-35-flash-lite.json` acompanha os hashes dos arquivos relevantes e as condições da execução. Os recibos preservam o modelo efetivamente retornado, consumo, duração e histórico de tentativas.

## Resultados e comparação com a v2

| Indicador | V1 | V2 |
| --- | ---: | ---: |
| Sugestões tecnicamente válidas | 20/20 | 20/20 |
| Chamadas, incluindo tentativas rejeitadas | 20 | 21 |
| Sugestões que pedem revisão | 3 | 10 |
| Sugestões sem tema | 1 | 1 |
| Coincidência exata com referência provisória | 10 | 9 |
| Diferença de ancestralidade no mesmo ramo | 1 | 2 |
| Divergência com referência provisória definida | 0 | 0 |
| Referência inconclusiva | 9 | 9 |
| Tokens de entrada | 569.480 | 605.456 |
| Tokens de resposta | 3.455 | 3.993 |
| Tokens de raciocínio | 22.435 | 21.988 |
| Tokens totais informados | 595.370 | 631.437 |
| Soma das durações das chamadas, sem pausas | 96,86 s | 101,93 s |

Os indicadores de correspondência incluem a proposta sem tema; são comparação de desenvolvimento entre IAs, não uma taxa de acerto jurídico. Os valores de tokens vêm dos recibos, incluindo falhas com consumo informado.

O prompt v2 tornou explícita a revisão de contexto ausente, OCR degradado, mistura sem tema dominante e colisões entre ramos. Passou a sinalizar Q0078 e Q0219 e a expor melhor duplicidades, como Q0036. Mantém todos os temas ativos no catálogo e os mesmos vinte casos; não adiciona exemplos com respostas do piloto. Foi escolhido pela melhor sinalização desses problemas conhecidos, sem afirmar superioridade de precisão demonstrada.

Durante a execução, uma evidência de Q0179 foi rejeitada por diferença de maiúscula/minúscula e a nova tentativa foi salva com o histórico. No início do lote completo, Q0005 também mostrou variação de caixa e espaços. A validação foi ajustada para tolerar somente essas diferenças de apresentação. Palavras, acentos, pontuação e OCR não são corrigidos nem comparados aproximadamente; paráfrases continuam inválidas. Os recibos originais e o consumo das tentativas foram preservados.

Em 15/10, a investigação de Q0005 confirmou que sua primeira tentativa passa integralmente no validador corrigido. As três posteriores não passam; uma delas também repete um ID entre papéis. A primeira resposta foi recuperada por revalidação offline, registrada em arquivo derivado ligado por hashes ao recibo original. As quatro chamadas e seus 122.031 tokens permanecem na contabilidade; não houve quinta chamada para essa recuperação. A seleção foi cronológica e técnica, sem comparação de qualidade temática entre as tentativas. Isso resolve a pendência de processamento, não constitui confirmação jurídica do tema.

As análises reproduzíveis estão em `artefatos/analises/piloto-v1-35-flash-lite/` e `artefatos/analises/piloto-v2-35-flash-lite/`. Exemplo:

```powershell
python -m classificacao_topicos analisar-piloto --piloto artefatos/piloto-v2 --execucao artefatos/execucoes/piloto-v2-35-flash-lite --saida artefatos/analises/piloto-v2-35-flash-lite
```

O lote completo reutiliza os vinte recibos válidos da v2 com os mesmos hashes de prompt, modelo e preparação. A cópia não constitui nova chamada e não deve duplicar o consumo na soma do projeto.
