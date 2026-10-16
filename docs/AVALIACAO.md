# Protocolo de avaliação

Este protocolo orienta o desenvolvimento e a auditoria. Não existem rótulos oficiais disponíveis nem apoio de especialista jurídico para a revisão local. A auditoria da versão 1 foi concluída em 16/10/2026, por censo das 78 publicadas e com referência provisória de IA: 77 coincidências exatas e uma divergência. Os critérios registrados abaixo foram preservados; a execução e suas limitações estão documentadas ao final e em [AUDITORIA_V1.md](AUDITORIA_V1.md). Os requisitos oficiais estão no [enunciado](../case-ia-classificacao-de-topicos.pdf) e no [LEIA-ME](../LEIA-ME.md).

O experimento 5C também foi concluído em 16/10/2026. Nenhuma das 23 propostas foi adotada: houve 20/23 coincidências estritas e uma divergência explícita, sem satisfazer os critérios da [política v2](../config/politica_v2.json). A versão atual mantém 77 publicadas após reter Q0180 por achado conhecido. A avaliação usada para escolher essa versão é evidência de desenvolvimento, não validação independente posterior à escolha.

## Populações e métricas

- Todas as 359 questões precisam de uma decisão final.
- Cobertura observada do lote: quantidade de `publicar` dividida por 359.
- Precisão nas publicadas: proporção de temas centrais considerados corretos entre as publicadas, conforme a regra de avaliação adotada e explicitada.
- Uma revisão local é referência provisória, não o gabarito reservado pela organização. Registrar se o avaliador é o candidato, um especialista ou uma ferramenta de IA.
- Confiança autodeclarada e concordância de modelos são sinais; não demonstram isoladamente a meta de 95%.

## Desenvolvimento e auditoria

1. Selecionar um piloto variado, incluindo HTML excessivo, comando importante, alternativas essenciais, origem incorreta, possíveis lacunas e conflitos de ramo.
2. Usar o piloto para desenvolver a preparação, o prompt e as regras. Registrar as alterações e os erros que as motivaram.
3. Identificar todos os IDs usados nos ajustes. A leitura exploratória anterior abrangeu o conjunto; uma separação futura não será descrita como conjunto nunca visto.
4. Congelar hashes dos dados, prompt, configuração, respostas e política antes da auditoria.
5. Separar as publicadas em dois estratos: itens utilizados no desenvolvimento e demais itens. Revisar integralmente o estrato de desenvolvimento e selecionar uma amostra aleatória do segundo, com semente e lista de IDs registradas. A precisão geral deve ponderar os dois estratos por seus tamanhos; a revisão dos itens de desenvolvimento não será descrita como avaliação independente. Se houver estratificação adicional, definir os estratos antes de revisar e utilizar pesos apropriados.
6. Revisar também casos difíceis deliberadamente escolhidos para diagnóstico, separando essa análise da estimativa baseada em amostragem.
7. Se a auditoria provocar ajustes, registrar uma nova versão. Não reutilizar a mesma amostra para alegar uma avaliação independente da nova política.

A [política v1](../config/politica_v1.json) fixa o censo dos publicados dos vinte casos de desenvolvimento e uma amostra aleatória simples, sem reposição, de `min(80,N)` demais publicados, com semente `2026101401`. O tamanho foi fixado antes da seleção e da leitura dos resultados dessa auditoria. O pacote cego contém só ID e texto da questão; a referência deve ser registrada sem acesso ao tema sugerido, escore ou motivo do classificador. Uma amostra sem erros, isoladamente, não comprova precisão jurídica de 95% quando a referência também é IA.

O piloto inicial está em `artefatos/piloto/manifesto_piloto.json`: vinte questões, sendo dez deliberadas e dez complementares por diversidade estrutural. A semente é 20261014. O manifesto registra os motivos, os IDs restantes e os hashes dos prompts. O piloto do prompt de classificação v2 usa exatamente os mesmos IDs; os pilotos servem ao desenvolvimento, não à extrapolação direta de precisão.

## Registro da revisão

Para cada item, registrar ID, versão avaliada, tema proposto, tema ou temas aceitos pela revisão local, decisão, justificativa curta, origem da referência, responsável, data e dúvidas pendentes. Quando possível, revisar o conteúdo antes de consultar a sugestão automática, reduzindo a influência da resposta do modelo.

A auditoria deverá distinguir acerto, erro e julgamento inconclusivo. Não excluir inconclusivos silenciosamente do denominador: apresentar cenários e explicar o tratamento. Intervalos condicionados aos rótulos locais não incluem automaticamente o erro do revisor.

## Política operacional v1

- `publicar`: tema central sustentado pelo texto completo e risco compatível com a política escolhida a partir dos experimentos.
- `revisar`: há sugestão de tema ativo, mas a decisão requer avaliação adicional. O motivo deve explicar a dúvida concreta.
- `fora`: nenhum tema da árvore é adequado, após verificar alternativas de enquadramento. Origem externa ou baixa confiança não bastam.
- Temas inativos não podem aparecer como tema central ou extra.
- Uma falha técnica permanece pendência de processamento; não se transforma automaticamente em `fora` ou em classificação inventada.

A política usa `confianca_autodeclarada >= 0.95`, ausência de revisão solicitada e de temas concorrentes, tema central fora do nível zero e da lista de ambiguidades, e no máximo um extra. Essas condições são conjuntas. O limiar é operacional: 0,95 na saída do modelo não equivale a 95% de precisão observada. A preferência por um tema pai precisa ser semanticamente justificada; raízes genéricas não servem de atalho para ampliar a cobertura. A lista assinada de ambiguidades contém vinte IDs; não propaga automaticamente impedimento para pais ou filhos.

Uma sugestão `sem_tema` fica pendente até confirmação separada com justificativa e identificação do revisor. A indisponibilidade de uma resposta ou falha de validação não autoriza escolher um tema nem excluir a questão do escopo.

## Ambiguidades que precisam ser documentadas

| Ponto | Texto ou lacuna oficial | Tratamento nesta etapa |
| --- | --- | --- |
| Regra hierárquica | Aceita tema atribuído ou nó do mesmo ramo, descrito como pai ou filho; subtema irmão é erro | Na estimativa local, aceitar ID igual ou relação imediata pai/filho; registrar a interpretação conservadora, sem estendê-la a ancestrais distantes |
| Títulos iguais | Existem IDs em ramos diferentes | Manter IDs distintos; registrar conflitos |
| Nós de disciplina | Não há detalhamento completo de seu uso na avaliação | Não usar automaticamente raízes como solução de dúvida |
| Confiança em `fora` | O formato define chance de tema central correto, mas não há tema central em `fora` | Exportar 0 como sentinela de não aplicável, explicitamente documentada; não é probabilidade de a decisão `fora` estar correta |
| Extras | Não está detalhada sua participação na avaliação | Não tratar extras como correção de um tema central errado |
| Intervalo de cobertura | Cobertura final do lote é observável; o case também solicita intervalo | Usar a cobertura contada e intervalo degenerado `[c,c]`; não representa cobertura de futuras importações |

## Estimação e incerteza

Sejam `D` os publicados de desenvolvimento, revistos por censo, e `N` os demais publicados. Na amostra aleatória de tamanho `n`, sejam `k` os erros; no censo, `d`. A estimativa ponderada é `(D - d + N * (1 - k/n)) / (D + N)`. Não juntar as duas revisões como se todos os itens tivessem a mesma probabilidade de seleção.

O intervalo de 95% inverte as duas caudas inclusivas da distribuição hipergeométrica, respeitando amostragem sem reposição. Se `[K_L,K_U]` limita o total de erros no estrato restante, o intervalo de precisão é `[1-(d+K_U)/(D+N), 1-(d+K_L)/(D+N)]`. O cálculo usa combinatória e frações exatas; os testes incluem cobertura em populações pequenas e casos de censo. [Distribuição hipergeométrica — NIST](https://www.itl.nist.gov/div898/software/dataplot/refman2/ch8/hypcdf.pdf), [estimação em população finita](https://cran.r-project.org/web/packages/samplingbook/vignettes/Sprop-remarks.html).

O cenário principal conta julgamentos inconclusivos como não confirmados; o cenário otimista conta-os como acertos. Nenhum elimina inconclusivos do denominador. Ambos são condicionais à referência de IA e cobrem apenas incerteza amostral: erros compartilhados entre classificador e revisor podem permanecer invisíveis. O ponto e o intervalo não serão apresentados como precisão validada por especialista.

## Critérios para a autoavaliação final

`previsao.txt` somente será preenchido após definir a versão avaliada, a referência local, a amostra, o tratamento dos inconclusivos e o método dos intervalos. Estimativas devem permanecer distinguíveis de resultados oficiais. Não há garantia prévia de alcançar a meta.

## Execução da versão 1 em 16 de outubro de 2026

O [manifesto de auditoria](../artefatos/auditoria-v1/manifesto_auditoria.json) aplicou a regra registrada de censo do desenvolvimento e `min(80,N)` demais publicados. Como havia cinco publicados de desenvolvimento e 73 restantes, ambos os estratos foram censitados. A seleção abrangeu todos os 78 publicados, mantendo as 359 decisões congeladas: 78 `publicar`, 277 `revisar` e quatro `fora`.

Três agentes produziram referências para 26 questões cada, a partir das entradas cegas e da taxonomia, sem consultar sugestões Gemini. Os registros e fontes foram identificados por bloco e as referências foram [congeladas antes da comparação](../artefatos/revisao_auditoria-v1/manifesto_revisoes.json). São revisões por IA, não revisões de especialistas independentes. Esta etapa não realizou novas chamadas Gemini.

| Comparação do tema central | Desenvolvimento | Restante | Total |
| --- | ---: | ---: | ---: |
| ID exato entre os aceitos pela referência | 5 | 72 | 77 |
| Apenas pai ou filho imediato | 0 | 0 | 0 |
| Divergência | 0 | 1 | 1 |
| Inconclusivo | 0 | 0 | 0 |
| Total revisado | 5 | 73 | 78 |

A divergência é Q0180. O [relatório de avaliação](../artefatos/avaliacao-v1/relatorio_avaliacao.json) registra **77/78 = 98,7179% de concordância condicional à referência de IA**. Os cenários principal e otimista coincidem porque não há julgamentos inconclusivos. O campo técnico `precisao_condicional` tem esse alcance; não representa precisão jurídica validada.

O intervalo condicional é degenerado, `[77/78, 77/78]`, porque não existe incerteza de amostragem em um censo. Ele não mede o possível erro das referências, erros compartilhados entre as IAs ou desempenho em futuras importações. A cobertura observada da versão 1 permanece `78/359 = 21,7270%`, com intervalo `[78/359, 78/359]` relativo somente a este lote. O resultado não comprova a meta jurídica de 95%.

### Limitações e sensibilidade posterior

O [dossiê do bloco 01](../artefatos/revisao_auditoria-v1/fontes/bloco_01.json) registra exposição incidental, em Q0179, a um trecho de gabarito de alternativas retornado por uma busca. Esse gabarito não contém os rótulos temáticos reservados da organização, e o documento não foi aberto nem adotado como fonte. Ainda assim, não é possível excluir influência do trecho. A questão foi mantida no denominador, sem alterar seu julgamento por causa do incidente.

Três referências admitem mais de um tema central: Q0009, Q0088 e Q0187. O contrato prévio permite conjuntos de temas aceitáveis e as três contaram como coincidências exatas. Uma [análise exploratória posterior](../artefatos/analises/sensibilidade-referencia-v1.json) considera essas três referências como não confirmadas, preservando as 78 questões no denominador: o indicador passa a `74/78 = 94,87%`.

Essa sensibilidade não estava fixada antes da comparação, não substitui o resultado principal e não altera os arquivos de referência ou as decisões. Ela explicita quanto a conclusão depende da aceitação dos julgamentos de IA. Nenhum dos dois números equivale à avaliação jurídica reservada pela organização.

## Experimento 5C concluído em 16 de outubro de 2026

O [diagnóstico da cobertura](COBERTURA_V1.md) identificou 41 questões com temas alternativos como único sinal de revisão. O [pré-registro do 5C](../artefatos/experimento-cobertura-v2/preregistro.json) fixou a seleção, a intervenção e os critérios antes da análise específica desta etapa. O segundo passe fez 50 chamadas Gemini e terminou com 37 sugestões tecnicamente válidas e quatro falhas com tentativas esgotadas: Q0086, Q0119, Q0194 e Q0322. Essas falhas mantiveram a decisão original de revisão e não viraram `fora`.

Foram [congeladas 23 propostas](../artefatos/experimento-cobertura-v2/propostas/manifesto_propostas.json) antes de consultar as referências cegas dos 41 selecionados. Cada proposta exigia segundo passe aprovado pela política base e igualdade do tema central e do conjunto de extras entre os passes. Os rótulos e a confiança a exportar continuavam sendo os originais; concordância não foi usada como recalibração.

A regra de adoção exigia um lote não vazio, coincidência estrita de pelo menos 95% e zero divergências explícitas pela regra hierárquica v1. Coincidência estrita exige referência provisória, presença de tema e somente o central original como tema aceitável. Inconclusivos, referências com vários temas aceitáveis e parentesco imediato permanecem no denominador e não contam como coincidências estritas. A decisão era adotar todas as propostas ou nenhuma, sem filtrar individualmente os discordantes depois da comparação.

| Indicador nas 23 propostas congeladas | Resultado |
| --- | ---: |
| Coincidência estrita | 20/23 = 86,9565% |
| Mesmo ID entre os aceitos pela regra v1 | 21 |
| Apenas pai ou filho imediato | 1 |
| Divergência explícita pela regra v1 | 1, em Q0024 |
| Concordância pela regra hierárquica v1 | 22/23 = 95,6522% |
| Propostas adotadas | 0 |

O [resultado](../artefatos/decisoes-v2/relatorio_experimento.json) é negativo para a intervenção: o indicador estrito ficou abaixo do limiar e a divergência em Q0024 também bloqueou a adoção. Q0024, Q0130 e Q0293 não foram confirmadas pelo critério estrito. As 23 propostas continuam no denominador, inclusive após a rejeição integral do lote. O valor secundário de 95,65% não substitui os critérios registrados.

Q0180 foi tratada separadamente por achado já conhecido da auditoria v1: passou de `publicar` para `revisar`, mantendo central, extras e confiança. A [versão 2](../artefatos/decisoes-v2/manifesto_decisoes.json) contém **77 `publicar`, 278 `revisar` e quatro `fora`**, com cobertura observada de **77/359 = 21,4485%**. A retirada não representa novo acerto validado. O resultado histórico de 77/78 da auditoria v1 permanece associado à sua população original; não é convertido em uma estimativa independente para a v2.

As referências são provisórias de IA, sem especialista jurídico. O censo não mede o erro dessas referências nem permite extrapolar para futuras importações. Além disso, a própria avaliação foi usada para escolher a versão; ela constitui desenvolvimento e não comprova a meta jurídica de 95%. Método, procedência e limites estão em [Experimento controlado de cobertura](EXPERIMENTO_COBERTURA_V2.md).

### Reprodução offline e ponto de parada

Com os prompts reconstruídos e os recibos, propostas e referências congelados disponíveis, reproduza os cálculos em pastas novas:

```powershell
python -B -m classificacao_topicos.experimento_cobertura propor --raiz . --saida artefatos/reproducao-5c/propostas
python -B -m classificacao_topicos.experimento_cobertura concluir --raiz . --saida artefatos/reproducao-5c/decisoes
```

Os comandos não chamam API nem leem `.env`; conferem os hashes e recusam saídas divergentes. `--saida` controla o destino da reprodução, e `concluir` continua usando as propostas e referências congeladas nos caminhos originais. A reconstrução do lote do segundo passe está no [README](../README.md#experimento-5c-e-decisões-v2-sem-api).

A suíte final executou 270 testes, com 269 aprovados e um pulado por privilégio de symlink no Windows, em 116,632 s. O módulo 5C está pronto para revisão e commit. O próximo módulo produzirá `previsao.txt`, relatório de até cinco páginas e memo, incluindo a proposta para 50 mil questões por semana e distinguindo estimativas, resultados históricos e evidência de desenvolvimento.
