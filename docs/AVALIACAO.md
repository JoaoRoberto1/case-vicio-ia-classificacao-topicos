# Protocolo de avaliação

Este protocolo orienta o desenvolvimento e a auditoria. Não existem rótulos oficiais disponíveis nem apoio de especialista jurídico para a revisão local. Os dois pilotos já têm comparações com referências provisórias de IA; a precisão das publicadas ainda não foi estimada. Os requisitos oficiais estão no [enunciado](../case-ia-classificacao-de-topicos.pdf) e no [LEIA-ME](../LEIA-ME.md).

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

O piloto inicial está em `artefatos/piloto/manifesto_piloto.json`: vinte questões, sendo dez deliberadas e dez complementares por diversidade estrutural. A semente é 20261014. O manifesto registra os motivos, os IDs restantes e os hashes dos prompts. A v2 usa exatamente os mesmos IDs; os pilotos servem ao desenvolvimento, não à extrapolação direta de precisão.

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
