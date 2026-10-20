# Módulo 4 — Calibração e decisões

**Pré-registro de 20/10/2026, antes da primeira medição do módulo 4.** Este documento fixa o procedimento de calibração, a política de decisão, a avaliação reservada e o reajuste final. A seção de resultados foi acrescentada depois das medições, preservando as decisões abaixo.

**Módulo 4 concluído:** 81 novos testes aprovados, quinze produtos reconstruídos com bytes idênticos e os dois arquivos oficiais da raiz conferidos. O calibrador constante venceu a comparação de desenvolvimento; nenhum limiar atingiu os critérios de publicação. A política congelada encaminha todas as questões à revisão. Na reserva, o primeiro tema acertou 6/20 referências por ramo. O procedimento não demonstrou a meta de precisão nem produziu cobertura de automação. A avaliação e suas limitações estão detalhadas no fechamento.

O módulo transforma as sugestões do classificador em probabilidades estimadas de acerto e decisões de `publicar`, `revisar` ou `fora`. A meta do case é precisão de pelo menos 95% nas publicações, com a maior cobertura possível dentro dessa restrição. O procedimento pode terminar sem publicações se o desenvolvimento não sustentar nenhum dos limiares fixados; esse resultado não autoriza reduzir a exigência ou inventar precisão.

A configuração está em [protocolo.json](../config/modulo4/protocolo.json). Valem a separação 80/20/559 do [protocolo de avaliação](PROTOCOLO_AVALIACAO.md) e a receita `hibrido_catalogo` congelada no [módulo 3](MODULO3_EXPERIMENTOS.md). Não serão comparados novos classificadores, pesos de recuperação, codificadores ou regras jurídicas neste módulo.

## Ponto de partida e alvo da probabilidade

O classificador selecionado combinou os rankings lexical e semântico do catálogo e acertou 37/80 referências por ramo e 24/80 pelo critério exato no desenvolvimento. Com escore RRF de pelo menos `0,95`, reteve 23 exemplos e acertou 17. Esses resultados anteriores motivam calibrar a saída; o escore não é uma probabilidade.

A variável-alvo da calibração é `acerto_ramo`: o primeiro tema sugerido é aceito pelo critério oficial de central, extra humano ou ancestral/descendente de um deles. Os critérios exato e de parentesco imediato continuam registrados separadamente. Não serão escolhidos como novos alvos após observar o desempenho M4. Uma referência humana `fora` tem alvo zero para o tema sugerido pelo classificador.

A coluna `confianca` representa a estimativa de probabilidade desse acerto por ramo. Não é probabilidade de decisão `fora`, de acerto exato, de algum candidato do top5 estar correto ou de consenso entre modelos. A calibração será medida; chamar uma transformação de calibrador não demonstra, por si só, que suas probabilidades são confiáveis.

## Dados permitidos e validação da calibração

O desenvolvimento usa exclusivamente as 80 predições fora da amostra da receita vencedora do M3. Os únicos atributos candidatos do calibrador são o escore do primeiro tema e a margem para o segundo tema. IDs servem a joins e partições; disciplina, origem, coorte, tema verdadeiro, texto jurídico e resultados de IA anteriores não entram como atributos.

As três partições internas existentes também separam o ajuste e a avaliação do calibrador. Em cada partição:

1. Ajustar o calibrador nas predições OOF das outras 53 ou 54 referências, com os respectivos indicadores humanos de acerto.
2. Calcular médias, escalas e limites de domínio somente nesse treino do calibrador.
3. Gerar probabilidades para as 27 ou 26 referências da validação, sem usar seus indicadores de acerto no ajuste.
4. Comparar essas probabilidades com os indicadores humanos somente no avaliador.

Cada uma das 80 referências recebe uma probabilidade crossfit por calibrador. Não se mede qualidade usando probabilidades do calibrador ajustado sobre os próprios indicadores de acerto. Depois da seleção, o calibrador escolhido é ajustado nas 80 predições OOF para a reserva e as 559 questões sem rótulo.

Essa validação continua **exploratória**. As mesmas 80 referências já orientaram a escolha do classificador M3 e agora orientam a escolha do calibrador e da política. Os ajustes lexicais das partições compartilham textos e produzem observações dependentes. No `hibrido_catalogo`, os rótulos dos vizinhos não participam do escore nem da margem, mas isso não transforma o conjunto reutilizado em um teste independente. A reserva de 20 referências terá essa função restrita.

## Grade de calibradores e ajuste numérico

Serão comparadas somente três receitas, com a prioridade abaixo:

| Prioridade | Receita | Atributos |
|---|---|---|
| 0 | `constante` | Nenhum |
| 1 | `logistica_score` | Escore do primeiro tema |
| 2 | `logistica_score_margem` | Escore e margem para o segundo tema |

A transformação logística usa `p = sigmoid(b + β · z)`, com atributos padronizados pela média e pelo desvio populacional do treino recebido. Atributo constante recebe escala 1. A penalidade L2 tem `λ = 1`, aplicada aos coeficientes padronizados; o intercepto não recebe L2. Esse valor não será ajustado a partir dos resultados.

O objetivo soma a perda logística dos exemplos, `λ/2 × soma(β²)` e duas pseudo-observações no centro padronizado: um acerto e um erro, cada um com peso `0,5`. A penalidade acompanha a **soma** das perdas, não sua média. Na receita constante, a solução é:

```text
p = (acertos + 0,5) / (n + 1)
```

Essa expressão coincide com a média posterior binomial sob Beta(`0,5`, `0,5`). Não se afirma que a mesma construção seja o prior de Jeffreys de uma regressão multivariada. Caso o treino tenha somente acertos ou somente erros, será usada essa constante suavizada, com coeficientes zero.

O ajuste logístico usa Newton com busca de passo de Armijo e no máximo 100 iterações. A convergência exige simultaneamente máximo absoluto do gradiente de até `1e-8` e decremento de Newton `gᵀ H⁻¹ g` de até `1e-12`. Falhas de convergência devem interromper a execução, sem salvar silenciosamente um ajuste incompleto. Um passo pequeno, isoladamente, não comprova convergência. Parâmetros, escalas, pseudocontagens e diagnóstico de convergência serão persistidos.

Esse critério numérico foi corrigido nos testes sintéticos, antes de qualquer medição M4: o limite inicial de gradiente `1e-10` travava por arredondamento em uma fixture colinear com gradiente de aproximadamente `3,4e-10`. A função-objetivo, a regularização e a grade permaneceram as mesmas; a correção exige também o decremento de Newton, sem usar resultados reais para escolher parâmetros.

A escolha será lexicográfica: menor Brier crossfit, menor logloss crossfit, menor prioridade e, por fim, nome da receita. As três alternativas permanecerão registradas, inclusive resultados negativos. Uma constante que vença a comparação será mantida; não se forçará uma probabilidade variável apenas para produzir publicações.

A abordagem se apoia na distinção entre escores e probabilidades e na necessidade de ajustar a transformação fora da amostra de treinamento. [Niculescu-Mizil e Caruana](https://icml.cc/Conferences/2005/proceedings/papers/079_GoodProbabilities_NiculescuMizilCaruana.pdf) comparam sigmoid e isotônica e mostram maior risco de sobreajuste da isotônica quando há poucos dados. Isso orienta a grade pequena deste projeto, sem demonstrar que a sigmoid seja correta para o RRF.

[Lin, Lin e Weng](https://www.csie.ntu.edu.tw/~htlin/paper/doc/plattprob.pdf) discutem estabilidade numérica no ajuste da sigmoid. O uso aqui de dois atributos possíveis, L2 e pseudo-observações no centro é uma decisão de engenharia do projeto; não será apresentado como implementação literal de Platt.

## Política de publicação e revisão

A seleção do limiar usará somente as 80 probabilidades crossfit do calibrador selecionado. A grade fixa é `0,95`, `0,975` e `0,99`. Para cada limiar, reter somente referências que atendam simultaneamente a:

- Tema sugerido elegível segundo as regras estruturais e de título abaixo.
- Presença de evidência numérica segundo o indicador do classificador M3.
- Atributos usados pelo calibrador dentro do domínio observado no respectivo treino.
- Confiança maior ou igual ao limiar.

Uma alternativa de publicação exige pelo menos **dez** referências retidas e precisão empírica por ramo de pelo menos **95%** nesse subconjunto. Entre alternativas que cumpram ambas as condições, escolher a maior quantidade publicada; em empate, o menor limiar.

O suporte mínimo de dez é uma restrição de engenharia para impedir decisões apoiadas em poucos exemplos. Não demonstra precisão populacional de 95%. A meta do case não exige que o limite inferior de um intervalo estatístico alcance 95%; por isso, essa condição adicional não será imposta. As contagens e o intervalo serão mostrados para explicitar a incerteza.

Se nenhum limiar atender aos critérios, a política ficará com publicação automática desabilitada e limiar nulo. A grade, o suporte e a precisão mínima não serão relaxados depois desse resultado. Questões que não puderem ser publicadas irão para revisão, com o primeiro tema sugerido e o motivo técnico da abstenção.

### Especificidade dos temas

Um tema pode ser publicado somente se estiver ativo, tiver nível pelo menos 1 e não possuir descendente ativo. A verificação percorre a ancestralidade completa, inclusive quando existe um intermediário inativo. O sistema não promove sugestões a ancestrais para aproveitar a tolerância hierárquica do critério de acerto.

Também serão excluídos títulos que contenham uma das seis expressões fixadas: `aspectos gerais`, `considerações gerais`, `disposições gerais`, `introdução`, `noções gerais` e `princípios gerais`. A comparação normaliza caixa, acentos, pontuação e espaços, respeitando limites de palavras.

Esses filtros são conservadores e independentes de julgamentos jurídicos de questões. Podem encaminhar temas adequados à revisão, e não garantem que toda folha restante seja suficientemente específica. Nenhuma expressão será acrescentada para corrigir um erro observado na reserva.

### Domínio da calibração

Para cada atributo usado pelo calibrador, registrar o mínimo e o máximo observados no treino. Publicar exige que o valor consultado permaneça no intervalo fechado correspondente. No crossfit, os limites vêm das outras 53 ou 54 referências; na reserva e na avaliação oficial, vêm das 80 predições OOF usadas pelo calibrador final.

A constante não usa atributos e, portanto, não tem restrição numérica de domínio por escore ou margem. Nas receitas logísticas, um valor fora da faixa pode receber probabilidade para diagnóstico, mas sua decisão será revisão. Essa regra evita publicar por extrapolação nesses atributos; ela não detecta toda mudança de distribuição nem comprova validade semântica.

### Casos fora da taxonomia e extras

O desenvolvimento contém somente seis referências `fora`. Não será ajustado um detector automático de ausência de tema adequado com esse suporte. `fora_automatico` permanece falso; confiança baixa, ausência de evidência ou título genérico levam à revisão.

A avaliação registrará quantos casos humanos `fora` existem, quantas chamadas `fora` o sistema fez, acertos, precisão e recall. Com zero chamadas, a precisão de `fora` será indefinida; o recall será zero quando houver referências dessa classe. A quantidade de casos dentro da taxonomia não será usada para apresentar uma acurácia enganosa de detecção de `fora`.

Os extras previstos permanecerão vazios. Nenhum tema adicional será incluído sem um procedimento próprio avaliado. Extras humanos continuam participando exclusivamente do critério oficial de acerto do primeiro tema.

## Congelamento antes da reserva

A ordem de execução é obrigatória:

1. Produzir o calibrador final ajustado nas 80 referências, a política, as métricas de desenvolvimento e as predições calibradas OOF.
2. Congelar esses quatro produtos, o código M4, suas configurações e as fontes M3 por SHA-256. Registrar também os conjuntos 80/20/559 e o procedimento de reajuste final.
3. Conferir o selo do congelamento antes de preparar ou inferir qualquer uma das 20 questões reservadas.
4. Estender o cache, em outro diretório, acrescentando somente os vinte vetores faltantes com o mesmo codificador e os mesmos parâmetros M3.
5. Aplicar o classificador e o calibrador ajustados nos 80 exemplos e congelados às vinte questões; somente depois comparar com os rótulos humanos.
6. Registrar o resultado mesmo que seja desfavorável. Não alterar classificador, calibrador, filtros ou limiar em resposta a essa avaliação.

A extensão reutiliza os 639 vetores de questões e os 371 vetores de temas do M3 sem alterar seus conteúdos. O novo cache deverá conter 659 questões e os mesmos 371 temas. O codificador recebe somente os vinte textos faltantes, sem rótulos, candidatos, probabilidades ou decisões. A troca do vínculo do classificador para o cache completo não altera seus parâmetros nem refaz seu treino.

Preparar embeddings é uma operação explícita, separada da classificação. Ler o cache não pode carregar o codificador, baixar pesos ou iniciar rede como fallback. As decisões e a reprodução a partir dos vetores persistidos usam operações numéricas locais.

Haverá uma avaliação estatística reservada da receita congelada. A reprodução técnica determinística desses mesmos produtos não constitui um novo teste independente nem autoriza procurar parâmetros melhores. Qualquer mudança metodológica motivada pela reserva tornaria sua reavaliação exploratória e precisaria ser identificada como tal.

## Métricas, intervalos e previsão

Serão registrados Brier, logloss e um diagnóstico de confiabilidade em cinco faixas fixas: `[0; 0,2)`, `[0,2; 0,4)`, `[0,4; 0,6)`, `[0,6; 0,8)` e `[0,8; 1]`. Cada faixa terá suporte, confiança média e taxa observada de acerto. O ECE dessas faixas é diagnóstico, não critério de seleção nem prova de boa calibração. Faixas vazias terão medidas indefinidas, sem zeros artificiais.

A logloss limita as probabilidades a `[1e-15; 1 - 1e-15]` apenas no cálculo da perda para evitar logaritmos indefinidos. Isso não transforma os valores extremos em evidência de certeza.

As proporções observadas terão intervalo **bilateral de Wilson de 95%**, fixado antes da reserva. A fórmula e suas limitações estão descritas no [NIST](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm). O método considera observações Bernoulli e não incorpora a busca anterior de receitas, dependência entre questões, mudança de distribuição ou incerteza do reajuste final. No desenvolvimento, os intervalos serão descritivos. Na reserva, o tamanho máximo de vinte referências e o possível subconjunto ainda menor de publicadas limitam sua força.

Contagens serão apresentadas com seus denominadores: acertos, erros, publicações, cobertura e casos fora. A taxa de acerto de todas as sugestões não será chamada de precisão de publicação. Quando não houver publicações, a precisão e seu intervalo observado serão `null` nos registros JSON; não haverá uma precisão de 0% ou 100% para o conjunto vazio.

A previsão oficial considera somente as **559** questões sem referência humana:

- `cobertura_prevista`: número efetivo de publicações dividido por 559.
- `cobertura_intervalo`: o mesmo valor nos dois extremos, pois essa cobertura é uma contagem conhecida.
- `precisao_prevista`: média das probabilidades calibradas entre as publicadas, caso existam.
- `precisao_intervalo`: intervalo de Wilson das publicadas da reserva como referência transportada, caso exista esse suporte; na ausência dele, domínio não informativo `[0; 1]`.

A média das probabilidades nas 559 questões e o intervalo observado na reserva têm origens distintas. O intervalo transportado não é um IC calculado para essa média nem incorpora o reajuste com 100 referências. Seu uso exige supor que a política e a confiabilidade se mantenham entre a amostra antiga reservada e as questões avaliadas. As 300 recentes não têm rótulos conhecidos, portanto essa hipótese não é comprovada. O relatório separará a estimativa do modelo da evidência reservada e explicitará essas limitações.

Se não houver publicações nas 559 questões, a precisão prevista será matematicamente indefinida. Para respeitar o formato numérico de `previsao.txt`, o campo receberá `0.00` **exclusivamente como sentinela**, acompanhado de explicação explícita após os quatro campos. O intervalo `0.00-1.00` será descrito como domínio sem informação, não como intervalo estimado. O registro estruturado preservará `null`, e o resumo não apresentará a sentinela como “precisão de 0%”.

## Reajuste final e procedência das 659 linhas

Depois do teste reservado, o classificador será reajustado com as 100 referências, mantendo os parâmetros M3. O calibrador continuará sendo o ajuste nas 80 predições OOF, e a política permanecerá congelada. Não serão usados os vinte resultados reservados para recalibrar probabilidades ou selecionar outro limiar.

No `hibrido_catalogo`, os rótulos dos exemplos não contribuem para o escore de candidatos; os textos de treino participam do vocabulário e do IDF lexical. Por isso, reajustar com 100 referências altera a representação lexical e pode alterar rankings e escores, sem constituir aprendizado adicional dos vinte rótulos na pontuação híbrida. Esse ajuste final não recebe outro teste independente; o controle de domínio não elimina essa diferença.

O `publicacao.csv` terá 659 IDs únicos, mas suas linhas terão três procedências registradas em artefato de auditoria:

| Linhas | Tema sugerido | Confiança e decisão |
|---|---|---|
| 80 referências de desenvolvimento | Predição OOF da vencedora M3 | Probabilidade crossfit M4 e política selecionada |
| 20 referências reservadas | Predição do classificador ajustado nas 80 referências e congelado | Calibrador ajustado nas 80 referências e política congelados |
| 559 questões avaliadas oficialmente | Predição do reajuste com 100 referências | Calibrador ajustado nas 80 referências e política congelados |

Essa composição evita apresentar a inferência de uma referência pelo seu próprio ajuste como desempenho. As probabilidades das oitenta linhas também são crossfit, não saídas do calibrador final sobre suas próprias observações de ajuste. A procedência será documentada fora do CSV para preservar o esquema oficial. As cem referências não entrarão na previsão de precisão ou na cobertura oficial.

## Artefatos e critério de fechamento

O módulo usa diretórios novos; código, configurações e produtos assinados dos módulos 1, 2 e 3 permanecem preservados.

| Local | Conteúdo e função |
|---|---|
| `classificacao_decisao/` | Calibração, política, extensão explícita do cache e execução M4 |
| `config/modulo4/` | Protocolo fixado antes das medições e fontes |
| `artefatos/calibracao-v1/` | `calibrador.json`, `politica.json`, `metricas_desenvolvimento.json`, `predicoes_calibradas.jsonl` e registro de congelamento |
| `artefatos/embeddings-e5-m4-v1/` | Cache estendido e manifesto, preservando os vetores M3 |
| `artefatos/reserva-v1/` | Predições e avaliação única da receita congelada nas vinte referências |
| `artefatos/decisoes-v1/` | Ajuste final, decisões, previsão, procedência das linhas e manifestos |
| `publicacao.csv` e `previsao.txt` | Arquivos oficiais na raiz de `etapa-complementar/` |

O fechamento exige testes das fórmulas e limites numéricos, isolamento de partições, ausência de reserva no desenvolvimento, verificação do congelamento antes da extensão, aplicação da política, esquema das 659 linhas e reprodução determinística. A classificação e a conferência dos produtos devem funcionar sem rede, chave de API, leitura de `.env`, acesso aos pesos ou importação das dependências do codificador.

A própria CLI instala um mecanismo de auditoria antes de executar a operação. Todos os comandos bloqueiam conexão de rede, resolução de nomes e abertura de `.env` ou `.env.*`. Exceto `preparar-reserva`, também bloqueiam a abertura de pesos em `.cache-modelos` e a importação de `numpy`, `onnxruntime`, `tokenizers`, `torch`, `transformers`, `sentence_transformers` e `huggingface_hub`. A chamada direta das funções da biblioteca não instala esse mecanismo global; os bloqueios fazem parte dos comandos.

## Resultados de desenvolvimento e política congelada

As [métricas de desenvolvimento](../artefatos/calibracao-v1/metricas_desenvolvimento.json) preservam as três receitas, com 80 probabilidades crossfit para cada uma:

| Calibrador | Brier | Logloss | ECE em cinco faixas | Maior probabilidade crossfit |
|---|---:|---:|---:|---:|
| **`constante`** | **0,249488** | **0,692128** | **0,000341** | **0,481818** |
| `logistica_score` | 0,257978 | 0,722224 | 0,064797 | 0,731667 |
| `logistica_score_margem` | 0,256684 | 0,722345 | 0,053194 | 0,802162 |

A constante venceu pelo menor Brier, conforme a ordem fixada. O escore bruto tratado como probabilidade teve Brier de 0,415861 e logloss de 2,400793, diagnóstico que reforça sua inadequação como confiança. A melhora dessas perdas ao usar uma constante não significa que o sistema tenha aprendido a separar as questões fáceis das difíceis.

O ECE quase zero da constante no desenvolvimento é especialmente limitado: suas probabilidades ficam próximas da frequência global de acertos e caem na mesma faixa de avaliação. Isso permite boa concordância agregada sem discriminar o risco de cada questão. A receita selecionada não oferece uma ordenação individual de confiança; esse resultado é uma limitação central da automação.

Nenhuma das três opções chegou a probabilidade crossfit de `0,95`. Na receita selecionada, todos os três limiares retiveram zero exemplos, com precisão e intervalo indefinidos. A publicação foi desabilitada antes da reserva, sem reduzir o suporte mínimo, os limiares ou a exigência de precisão.

O filtro estrutural considerou 316 dos 377 nós elegíveis: excluiu quatro disciplinas, dois inativos, 51 temas com descendentes ativos e quatro títulos genéricos adicionais. A cobertura zero não foi causada apenas por esses filtros: a confiança selecionada já é insuficiente em todos os exemplos.

O ajuste final do calibrador nas 80 predições OOF produziu:

```text
confianca = (37 + 0,5) / (80 + 1) = 0,462962962962963
```

Esse valor foi o mesmo para as vinte questões reservadas e para as 559 avaliadas oficialmente. As oitenta linhas de desenvolvimento preservam as probabilidades crossfit, que variam entre 0,453704 e 0,481818 conforme o treino de cada partição.

A calibração terminou em 1,946 segundo; sua reprodução conferiu seis produtos idênticos em 1,377 segundo. O [congelamento](../artefatos/calibracao-v1/congelamento.json) foi produzido antes da extensão do cache e da inferência reservada, com SHA-256:

```text
c40b3b66cac5bfb1ae7b741c2abdbb5a022eef04e039789bd9a45789e5142b40
```

## Preparação adicional e avaliação reservada

Depois do congelamento, o codificador preparou somente os vinte textos faltantes. Foram processados 3.885 tokens de conteúdo em 21 janelas; uma questão precisou de mais de uma janela, sem truncamento registrado. A preparação adicional levou 21,248 segundos. O cache completo reutiliza os 639 vetores de questões e os 371 vetores de temas do M3, acrescentando os vinte reservados.

As [métricas da reserva](../artefatos/reserva-v1/metricas_reserva.json) foram obtidas em 11,474 segundos, com a política intacta:

| Medida nas vinte referências | Resultado |
|---|---:|
| Primeiro tema correto por ramo | 6/20 — 30,00% |
| Primeiro tema correto com parentesco imediato | 6/20 — 30,00% |
| Primeiro tema correto pelo critério exato | 3/20 — 15,00% |
| Tema aceitável entre cinco candidatos | 12/20 — 60,00% |
| Publicadas / revisar / fora | 0 / 20 / 0 |
| Brier | 0,236557 |
| Logloss | 0,666214 |
| ECE em cinco faixas | 0,162963 |

O Wilson de 95% para a taxa de acerto por ramo de todas as sugestões foi de aproximadamente **14,55% a 51,90%**. Esse intervalo não mede precisão entre publicadas: não houve publicações, logo essa precisão e seu intervalo permanecem indefinidos.

A confiança constante foi de aproximadamente 46,30%, enquanto a frequência de acertos reservada foi de 30%. A diferença agregada de 16,30 pontos percentuais mostra por que o ECE baixo no desenvolvimento não deve ser apresentado como comprovação de confiabilidade em dados novos. O teste é pequeno e o resultado não autoriza reajustar a receita congelada.

Havia dois casos humanos `fora`. O sistema não fez chamadas `fora`, portanto seu recall foi 0/2 e sua precisão nessa decisão foi indefinida. Ambos foram para revisão. Nas referências dentro da taxonomia, os acertos por ramo foram 0/2 em Criminologia, 0/2 em Legislação Especial, 3/8 em Penal e 3/6 em Processo Penal. Esses suportes não sustentam conclusões por disciplina nem novas regras específicas.

## Geração da entrega e cobertura observada

A geração real terminou com código de saída zero em **306,270 segundos**. Foram produzidos o [CSV de 659 linhas](../publicacao.csv), o [arquivo de previsão](../previsao.txt), o modelo final e os registros de procedência. Todas as 659 decisões são `revisar`; não houve publicações nem decisões `fora`.

O [registro estruturado da previsão](../artefatos/decisoes-v1/previsao.json) confirma a separação:

| Conjunto | Linhas | Publicar | Revisar | Fora |
|---|---:|---:|---:|---:|
| Referências de desenvolvimento com probabilidades crossfit | 80 | 0 | 80 | 0 |
| Referências reservadas, preservando o teste congelado | 20 | 0 | 20 | 0 |
| Questões antigas sem referência humana | 259 | 0 | 259 | 0 |
| Questões recentes sem referência humana | 300 | 0 | 300 | 0 |
| **Total** | **659** | **0** | **659** | **0** |

A cobertura oficial é **0/559 = 0%**. As cem referências humanas foram excluídas desse denominador. A precisão entre publicadas permanece indefinida, registrada como `null` no JSON. Em `previsao.txt`, o zero da primeira linha é a sentinela explicada no próprio arquivo; o domínio `[0; 1]` não é um intervalo de confiança estimado.

A entrega técnica demonstra execução e abstenção reproduzíveis, mas **não resolve a meta de automação do case**: nenhuma questão foi liberada para o aluno. A política conservou os critérios fixados, em vez de apresentar confiança alta sem suporte. Esse resultado negativo permanece parte da avaliação do sistema, sem trocar a grade após observar o desenvolvimento ou a reserva.

## Comandos e verificações

Os comandos são executados na pasta `etapa-complementar/`. Para conferir todos os produtos M4 e os dois arquivos oficiais a partir dos caches versionados:

```powershell
python -B -m classificacao_decisao verificar
```

Para regenerar os dois arquivos oficiais a partir do congelamento, da avaliação reservada e dos artefatos preservados:

```powershell
python -B -m classificacao_decisao regenerar
```

A sequência de preparação e avaliação está separada para manter o congelamento anterior à reserva:

```powershell
python -B -m classificacao_decisao calibrar
python -B -m classificacao_decisao verificar-calibracao
.venv/Scripts/python.exe -B -m classificacao_decisao preparar-reserva
python -B -m classificacao_decisao avaliar-reserva
python -B -m classificacao_decisao regenerar
python -B -m classificacao_decisao verificar
```

`preparar-reserva` exige o ambiente e os pesos locais registrados no módulo 3 quando precisa gerar os vinte vetores. Não baixa pesos implicitamente. Na reprodução usando o cache completo já versionado, essa preparação com modelo não é necessária.

Foram aprovados **81 novos testes M4**, em duas chamadas: 79 em 21,657 segundos e dois testes adicionais dos bloqueios em 4,922 segundos. O conjunto inclui calibração, filtros, domínio, isolamento dos conjuntos, congelamento antes do cache, inferência reservada antes da leitura dos rótulos de avaliação, reaproveitamento das probabilidades crossfit, reajuste somente com referências e predição somente das questões sem rótulo.

As fixtures sintéticas conferem também a reprodução de quinze produtos e duas entregas na raiz, preservação de arquivos não relacionados e recusa de saídas divergentes. Os dois testes adicionais executam em processos separados: um confirma que o próprio comando `verificar` instala os bloqueios; o outro confere que a preparação permite os pesos e o codificador, mantendo bloqueados rede e credenciais. Não houve consulta individual de questões ou julgamento jurídico por LLM nesses testes.

A reprodução integral dos produtos reais terminou com código de saída zero em **268,722 segundos**, com os bloqueios da própria CLI ativos. Foram reconstruídos quinze produtos com bytes idênticos: seis de calibração e congelamento, três da reserva e seis da entrega. Os dois arquivos oficiais da raiz também coincidiram com as versões reproduzidas.

O [checkpoint do módulo 4](../artefatos/checkpoints/modulo4.json) reúne ambiente, comandos, tempos, testes, auditoria estrutural e SHA-256 de dezenove arquivos: os quinze produtos, os dois arquivos do cache completo e as duas cópias oficiais da raiz. A reprodução foi conferida em CPython 3.14.7, Windows AMD64, usando os vetores persistidos; isso não demonstra reprodução numérica em qualquer hardware nem capacidade de produção.

O módulo termina em um ponto de revisão e commit pelo autor, sem commit ou push automático. O resultado científico permanece negativo para a automação: a receita não sustentou publicação automática, e cobertura zero não equivale ao atendimento da meta de precisão. O módulo 5 organizará a entrega e a defesa com essa limitação explícita. Como a reserva já foi utilizada, melhorias orientadas por esse resultado serão desenvolvimento exploratório e exigirão outras referências para nova avaliação independente.
