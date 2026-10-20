# Módulo 2 — Primeiro classificador local

O módulo estabelece uma referência lexical reproduzível, usando as descrições oficiais dos temas e exemplos humanos de treinamento. Todo o cálculo usa a biblioteca padrão do Python. Não há chamada a modelo, chave de API, embeddings gerados por serviço ou reutilização de classificações de IA da primeira etapa.

**Registro de 20/10/2026:** configurações e separação descritas abaixo foram definidas antes de observar qualquer resultado do classificador nas referências reais. A seção de resultados registra a primeira execução; nenhuma receita foi alterada depois de observar suas métricas.

## Escopo e separação dos dados

O [protocolo v2](PROTOCOLO_AVALIACAO.md) reserva os 20 `teste_ids` da primeira partição externa para a avaliação final do módulo 4. Os 80 `treino_ids` dessa partição são o conjunto de desenvolvimento. Somente suas três partições internas são usadas neste módulo.

Essa restrição corrige um risco do plano inicial: examinar resultados internos de todas as cinco partições externas permitiria que as 100 referências influenciassem a construção do sistema. As partições do módulo 1 continuam preservadas; não houve escolha da reserva com base no desempenho.

O módulo 2 produz:

- Predições internas fora da amostra para as 80 referências, por configuração.
- Métricas exploratórias e diagnósticos de apoio, separando casos dentro e fora da taxonomia.
- Até cinco sugestões da configuração selecionada para cada uma das 559 questões sem rótulo, usando somente as 80 referências de desenvolvimento no ajuste.
- Configuração, evidências de integridade e produtos suficientes para reprodução local.

Não há predições para a reserva de 20, CSV final de publicação, confiança calibrada nem decisão automática de `fora`. As sugestões para as 559 questões são saídas intermediárias do classificador.

## Representação lexical

A limpeza e os campos preparados vêm do módulo 1. O classificador usa unigrama e bigrama de palavras. IDs, coorte, disciplina e assunto de origem não entram na representação. O ID é usado para rastreabilidade e para impedir que um exemplo forneça apoio humano à própria predição.

Os campos recebem os seguintes pesos fixos:

| Documento | Campos e pesos |
|---|---|
| Tema do catálogo | Título 3, caminho da árvore 1, descrição 1 |
| Questão de treinamento ou consulta | Enunciado 2, comando 2, alternativas 1 |

Para cada termo com contagem positiva `c`, o peso de frequência é `1 + log(c)`. Para um corpus de `n` documentos e frequência documental `df`, o peso inverso é `log((1 + n) / (1 + df)) + 1`. Os vetores são normalizados pela norma L2; sua comparação usa similaridade de cosseno. Termos ausentes do vocabulário de treinamento não fornecem evidência lexical.

O vocabulário e o IDF são ajustados no catálogo oficial e nos textos humanos de treinamento de cada partição. Textos de validação, da reserva e das 559 questões não entram nesse ajuste. Para as sugestões das 559, o ajuste usa catálogo mais as 80 referências de desenvolvimento.

As fórmulas seguem a convenção documentada em [TF–IDF no scikit-learn](https://scikit-learn.org/stable/modules/feature_extraction.html#tfidf-term-weighting), mas são implementadas localmente. A biblioteca não é uma dependência do projeto.

## Sinais e configurações fixadas

Somente temas ativos com nível maior que zero podem ser candidatos. Disciplinas da raiz não podem ser usadas como um tema genérico que aumente artificialmente o acerto por tolerância hierárquica. A posição na árvore descreve o tema; o classificador não recebe a disciplina verdadeira da questão.

São comparadas duas configurações, registradas em [experimento_lexical.json](../config/modulo2/experimento_lexical.json):

| Configuração | Similaridade com catálogo | Apoio humano | Leis e artigos |
|---|---:|---:|---:|
| Lexical | 0,70 | 0,30 | 0,00 |
| Lexical com leis | 0,60 | 0,30 | 0,10 |

O apoio humano considera até três exemplos de treino mais semelhantes, ponderados pelo quadrado da similaridade. O tema central recebe peso `1`; cada tema extra recebe peso `0,5`. Exemplos rotulados como fora da taxonomia fornecem um diagnóstico de apoio a `fora`, sem transferir um tema inexistente nem acionar uma decisão de fora. Uma referência em validação não pode participar desse apoio.

O sinal legal extrai leis e artigos por regras determinísticas sobre strings. Siglas e aliases são normalizados de forma documentada. O escore usa Jaccard entre conjuntos de instrumentos e pares de instrumento/artigo reconhecidos na questão e no tema. Um número de artigo sem instrumento identificado não pontua. A coincidência de uma citação é evidência auxiliar; sua presença não comprova qual assunto é cobrado. Citações não reconhecidas, contextos ambíguos e ausência de menção explícita limitam esse sinal.

O escore final é a soma ponderada dos três sinais, conforme a tabela. A configuração selecionada maximiza o acerto interno pelo critério de ramo; em empate, usa acerto exato e, persistindo o empate, um identificador estável da configuração. Essa regra foi fixada antes das métricas. Ela escolhe uma referência para estudo, sem impor uma meta de publicação de 95% neste módulo.

As ponderações são escolhas de engenharia fixadas para esta primeira comparação. O módulo 3 poderá propor alternativas usando os 80 exemplos de desenvolvimento, preservando o histórico e sem abrir a reserva final.

## Como interpretar os resultados

O critério principal segue o enunciado: o tema central sugerido pode coincidir com o central humano, um extra humano ou um ancestral ou descendente de um deles. Temas irmãos não são aceitos. Extras sugeridos não podem resgatar um primeiro candidato incorreto.

Também devem ser apresentados critérios mais restritos, como coincidência exata e parentesco imediato, para tornar visível o efeito da tolerância hierárquica. A presença de um tema aceitável entre os cinco candidatos é um diagnóstico de recuperação; não substitui o acerto da primeira sugestão.

As métricas internas são exploratórias. Embora cada sugestão de validação seja produzida sem treinar naquele exemplo, os resultados podem orientar mudanças no sistema. Eles não estimam de forma independente o desempenho da configuração escolhida.

Nenhum escore é denominado probabilidade ou `confianca`. A diferença entre os dois primeiros escores, a similaridade com um exemplo e a coincidência de leis são sinais para estudo posterior. A calibração e a política de publicação pertencem ao módulo 4.

Toda contagem deve indicar seu denominador. Questões humanas fora da taxonomia não têm um tema correto no catálogo; seu tratamento deve ser mostrado separadamente. Não se deve apresentar taxa de acerto somente nos casos dentro da taxonomia como resultado sobre todas as referências.

## Execução e reprodução

A partir da pasta `etapa-complementar`, o contrato de execução do módulo é:

```console
python -B -m classificacao_local experimentar --saida artefatos/lexical-v1
python -B -m classificacao_local verificar --saida artefatos/lexical-v1
```

O primeiro comando executa as duas configurações fixadas nas três validações internas das 80 referências, seleciona a configuração e gera suas sugestões para as 559 questões. O segundo verifica a reprodução dos produtos. Não é necessário criar `.env`.

O código fica no pacote `classificacao_local`, separado do pacote de preparação `classificacao_topicos`. A configuração fica em `config/modulo2/`. Isso preserva as fontes e os hashes do módulo 1.

| Produto | Conteúdo |
|---|---|
| `protocolo.json` | Separação efetivamente usada e restrições do experimento |
| `metricas_desenvolvimento.json` | Comparação interna e configuração selecionada |
| `predicoes_desenvolvimento.jsonl` | Predições fora da amostra nas 80 referências, para as duas configurações |
| `sugestoes_avaliacao.jsonl` | Até cinco sugestões da configuração selecionada para cada uma das 559 questões |
| `modelo_lexical.json` | Ajuste da configuração lexical com as 80 referências |
| `modelo_lexical_leis.json` | Ajuste da configuração lexical com leis com as 80 referências |
| `manifesto.json` | Hashes das entradas, configurações, código e produtos |

O manifesto identifica fontes, configuração, código e produtos por SHA-256. Os produtos determinísticos não dependem de caminhos absolutos ou horário de execução. Alterações de código ou configuração exigem uma nova saída; um diretório com conteúdo divergente é recusado. Execute apenas um processo por diretório de saída: o publicador não oferece exclusão mútua entre processos concorrentes.

## Resultado da primeira execução

O experimento gerou 160 predições de desenvolvimento: uma por referência e por receita, sempre fora do respectivo treino. O conjunto tem 74 referências dentro da taxonomia, seis fora e 55 temas centrais distintos. As 20 reservadas não receberam predições.

| Medida nas 80 referências | Lexical | Lexical com leis |
|---|---:|---:|
| Primeiro tema aceito pelo critério de ramo | 31/80 (38,75%) | 31/80 (38,75%) |
| Primeiro tema aceito por parentesco imediato | 31/80 (38,75%) | 31/80 (38,75%) |
| Primeiro tema igual ao central ou a um extra humano | 18/80 (22,50%) | 18/80 (22,50%) |
| Algum tema aceito entre os cinco candidatos | 57/80 (71,25%) | 54/80 (67,50%) |
| Primeiro tema aceito, somente nas referências dentro da taxonomia | 31/74 (41,89%) | 31/74 (41,89%) |

A receita `lexical` foi selecionada pelo desempate fixo do identificador: os dois critérios de acerto ficaram iguais. O resultado entre os cinco candidatos não participou dessa seleção. A receita com leis não melhorou o primeiro candidato nesta comparação e teve três acertos a menos no conjunto de cinco; isso não demonstra que citações sejam inúteis em outras configurações.

O desempenho ainda é insuficiente para sustentar publicação automática. O acerto do primeiro candidato é diferente da futura precisão entre publicadas, pois ainda não existe política de publicação. A presença de um tema aceitável entre cinco candidatos tampouco equivale à classificação correta: revela uma oportunidade de melhorar a ordenação. Os 23 casos sem tema aceitável entre os cinco incluem 17 dentro da taxonomia e seis fora; esses seis exigem tratamento próprio na política de decisão.

Nas 27 referências cujo tema central aparecia como central de um exemplo do respectivo treino, o primeiro candidato acertou 17 (62,96%). Nas 47 referências dentro da taxonomia sem esse apoio central, acertou 14 (29,79%). Essa separação é descritiva e pode refletir também diferenças de dificuldade; não é uma demonstração causal do ganho dos exemplos. Os seis casos fora permanecem no denominador geral, com zero acertos de tema, porque este módulo ainda não decide `fora`.

Por disciplina, a receita lexical obteve 1/8 em Criminologia, 5/10 em Legislação Especial, 15/32 em Penal e 10/24 em Processo Penal. Os denominadores pequenos impedem conclusões amplas sobre cada disciplina.

A curva diagnóstica usa os oito cortes de escore fixados antes da execução, sem selecionar um limiar de publicação. Na lexical, `score >= 0,25` reteve 17/80 referências e acertou 12/17; `score >= 0,35` reteve apenas uma e acertou essa uma. Esse único acerto não comprova precisão de 95%. Cortes a partir de `0,45` não retiveram nenhum caso, com taxas representadas por `null`, sem inventar precisão de conjunto vazio.

As [métricas completas](../artefatos/lexical-v1/metricas_desenvolvimento.json) mantêm ambas as receitas, seus denominadores, grupos e curvas. As [559 sugestões intermediárias](../artefatos/lexical-v1/sugestoes_avaliacao.jsonl) usam o modelo lexical ajustado nas 80 referências; elas não têm acerto mensurável sem seus rótulos. Nenhuma questão recebeu julgamento ou correção manual de uma IA.

## Validação técnica

Foram aprovados **87 testes**, executados em duas chamadas: a descoberta inicial cobriu 72 testes em 210,714 segundos; o novo arquivo de integração do experimento cobriu 15 testes sintéticos em 0,599 segundo. A primeira chamada inclui os 33 testes preservados do módulo 1, os 16 do extrator e os 23 do motor. Os comandos foram:

```console
python -B -m unittest discover -s tests -v
python -B -m unittest discover -s tests -p test_experimento.py -v
```

Uma próxima chamada ao primeiro comando descobre os 87 testes. Os controles cobrem isolamento da reserva, ausência de vocabulário de validação no ajuste, bloqueio de ressubstituição, denominadores, rejeição de partições e grupos inválidos, serialização JSON, determinismo e preservação de resultados divergentes. Uma revisão adicional sintética variou 40 vezes a ordem das entradas, a serialização e duas sementes de hash, sem diferença de resultado.

Os comandos `experimentar` e `verificar` concluíram com código zero. A verificação reconstruiu os sete arquivos com bytes idênticos em **83,159 segundos**, com conexões de rede e leitura de `.env` bloqueadas por um audit hook do Python. O tempo do primeiro comando não foi instrumentado. O [checkpoint do módulo 2](../artefatos/checkpoints/modulo2.json) registra resultados, ambiente e hashes.

Os artefatos também passaram em conferências estruturais: uma predição de desenvolvimento por referência e receita; vizinhos restritos ao treino correto; modelos finais ajustados somente nas 80 referências; 559 sugestões com IDs únicos; reserva sem predição; candidatos ativos com nível maior que zero; ausência de confiança calibrada e de decisão final. O código, a configuração e os artefatos determinísticos do módulo 1 permanecem idênticos ao commit anterior.

A reprodução byte a byte foi validada em **CPython 3.14.7, Windows AMD64**. Outras plataformas e versões ainda não foram testadas; pequenas diferenças numéricas entre ambientes podem exigir investigação antes de alegar equivalência. Os tempos observados não são uma estimativa de capacidade para 50 mil questões por semana; esse dimensionamento pertence à entrega final.

## Limites e próxima parada

Os 100 rótulos humanos cobrem somente questões antigas, e os 80 de desenvolvimento representam ainda menos exemplos por tema. Não há rótulos nas 300 questões recentes. Portanto, a generalização para esse grupo e o atendimento à meta de precisão de 95% continuam sem comprovação.

Descrições curtas, vocabulário distante entre questão e tema, negação, conflitos entre alternativas e identificação incompleta de citações são limitações esperadas da recuperação lexical. Elas orientam hipóteses para o módulo 3; não autorizam corrigir manualmente uma questão com julgamento de IA.

O módulo 2 está concluído, com execução local reproduzível, isolamento da reserva e medições internas registradas. Está pronto para revisão e commit pelo autor. O próximo passo é comparar melhorias no módulo 3, preservando a reserva final até que a receita completa de classificação, calibração e decisão esteja congelada.
