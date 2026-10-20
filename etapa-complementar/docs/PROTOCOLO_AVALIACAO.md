# Protocolo de avaliação do classificador

Este protocolo separa a construção do classificador da medição de sua qualidade. O objetivo é estimar a precisão das publicações e sua cobertura usando exclusivamente as referências humanas fornecidas, sem transformar similaridade ou concordância entre IAs em evidência de acerto.

**Protocolo v2, registrado no início do módulo 2 em 20/10/2026, antes da primeira predição ou métrica de classificação.** A primeira partição externa fornece uma reserva final de 20 referências. Somente as 80 referências restantes podem orientar o desenvolvimento dos módulos 2 e 3 e o ajuste da política no módulo 4. O calibrador e os limiares de publicação ainda serão implementados e congelados antes de abrir a reserva.

O [protocolo estrutural v1](../config/protocolo_avaliacao.json), suas cinco partições externas e seus produtos do módulo 1 permanecem preservados. A mudança é de uso das partições: a comparação interativa de resultados internos de todas as cinco partições exporia as 100 referências durante a engenharia e impediria apresentar depois esses mesmos exemplos como avaliação independente. A reserva foi escolhida pelo índice fixo `1`, sem observar desempenho e sem buscar uma separação mais favorável. O [registro do módulo 2](MODULO2_CLASSIFICADOR.md) descreve a primeira comparação permitida.

A regra de uso está registrada separadamente em [protocolo_desenvolvimento.json](../config/modulo2/protocolo_desenvolvimento.json). A configuração estrutural e os hashes da preparação do módulo 1 não são reescritos para acomodar esta revisão.

## Fontes e população avaliada

São 659 questões e 377 temas, dos quais 375 ativos. A folha-verdade fornece 100 referências humanas: 92 dentro da taxonomia, 8 fora, 61 temas centrais distintos e 39 questões com pelo menos um tema extra.

As 100 referências estão entre as 359 questões do banco anterior. A avaliação oficial usa as 559 restantes: 259 antigas e 300 recentes. Os resultados nas referências humanas não medem diretamente a qualidade nas recentes; qualquer extrapolação deve declarar essa limitação.

As colunas de disciplina e assunto de origem podem estar erradas. Elas não são gabarito. Os rótulos e julgamentos de IA do projeto anterior não entram em treinamento, calibração, seleção ou avaliação.

## Preparação permitida e rastreabilidade

Limpeza, extração de citações e organização da árvore devem ser reproduzíveis. Modelos podem gerar artefatos de preparação, inclusive embeddings e descrições enriquecidas, com origem, versão, instruções e parâmetros registrados. Não podem escolher temas, votar, julgar nem validar classificações.

As transformações e embeddings em cache não podem incorporar o tema verdadeiro de uma questão de avaliação. Exemplos ou termos propostos durante a preparação não podem virar rótulos artificiais de questões avaliadas.

A execução que gera as decisões será local, sem chamadas a modelos de linguagem. O manifesto registra SHA-256 das fontes, configurações, código de preparação e produtos, sem caminhos absolutos ou horários variáveis. Mudanças exigem nova configuração e novo diretório de saída; resultados anteriores são preservados.

## Grupos e partições

A configuração estrutural fica em `config/protocolo_avaliacao.json`, com semente `20261020`, cinco partições externas e três internas por treino externo. Esses arquivos são a origem das partições, não uma autorização para abrir todos os testes durante o desenvolvimento.

Questões duplicadas ou muito semelhantes pertencem ao mesmo grupo. O agrupamento combina igualdade do texto normalizado com Jaccard de sequências de cinco termos, limiar `0.85`, para textos com pelo menos 12 termos. Grupos conectados permanecem juntos, mesmo quando a ligação é transitiva.

O agrupamento usa texto, sem consultar rótulos. As partições e seu diagnóstico ficam em `particoes.json` e `diagnostico.json`. Devem ser conferidos ausência de sobreposição entre treino e avaliação, suporte por disciplina e distribuição de casos fora da taxonomia. Poucos exemplos por tema impedem prometer equilíbrio por tema.

Não se admite obter o tema de uma questão de validação por meio de um exemplo duplicado mantido no treino. A geração dos grupos usa texto; a estratificação usa disciplina da referência humana e condição de fora da taxonomia exclusivamente para balancear as partições, nunca como atributo de classificação.

Na preparação de 20/10/2026, o detector produziu 659 grupos unitários: não encontrou duplicatas segundo a normalização e o limiar definidos. Isso não exclui semelhanças abaixo do limiar. As cinco partições externas têm 80 exemplos de treino e 20 de teste cada, com três partições internas. Os oito casos fora da taxonomia ficaram distribuídos em 2, 1, 1, 2 e 2 nos testes externos. Nenhuma previsão de tema foi produzida nessa etapa.

## Desenvolvimento em 80 referências e reserva final de 20

A separação é obtida do elemento com `indice == 1` em `folds`, no [arquivo de partições do módulo 1](../artefatos/preparacao/particoes.json):

| Conjunto | Origem | Uso permitido |
|---|---|---|
| Desenvolvimento, 80 referências | `treino_ids` da primeira partição externa | Engenharia, comparação interna, calibração e escolha de limiares |
| Três validações internas | `internas` dessa mesma partição | Medições fora da amostra de treinamento, restritas às 80 referências |
| Reserva final, 20 referências | `teste_ids` da primeira partição externa | Uma avaliação da receita completa e congelada, no módulo 4 |
| Avaliação oficial, 559 questões | `avaliacao_ids` | Sugestões do módulo 2 e decisões finais; não há rótulos disponíveis |

Em cada validação interna, o classificador recebe apenas os textos e os rótulos dos respectivos `treino_ids`. Os rótulos de `validacao_ids` são usados pelo avaliador depois de produzir as sugestões. Cada uma das 80 referências recebe uma predição interna fora da amostra por configuração. A mesma referência nunca pode fornecer apoio humano para sua própria predição de validação.

As três validações internas orientam a escolha de representações e parâmetros. Uma vez que seus resultados influenciam o desenvolvimento, suas métricas são **exploratórias**, mesmo quando cada predição foi feita sem treinar no próprio exemplo. Recalibrar ou repetir as partições não torna esses 80 exemplos independentes da engenharia.

O módulo 2 não produz predições nem métricas para os 20 exemplos da reserva. Também não executa as outras quatro partições externas. Os rótulos já integram os anexos públicos e foram usados na preparação e estratificação do módulo 1; portanto, a reserva é uma restrição do procedimento, não um segredo nem uma garantia de cegamento humano.

No módulo 4, a ordem obrigatória será:

1. Desenvolver e escolher a receita, o calibrador, o limiar e a regra de `fora` usando somente as 80 referências e suas validações internas.
2. Congelar código, configuração, métricas, método de incerteza e procedimento de reajuste antes de gerar qualquer predição da reserva.
3. Ajustar a receita nos 80 exemplos de desenvolvimento e predizer os 20 reservados uma única vez.
4. Abrir os rótulos da reserva para calcular as métricas, incluindo contagens e denominadores.
5. Registrar o resultado mesmo se for ruim. Uma alteração motivada por essa avaliação torna qualquer reavaliação dos mesmos 20 exemplos exploratória.

As cinco partições do módulo 1 poderão sustentar posteriormente uma análise ampliada em 100 referências, desde que identificada como **exploratória**: 80 delas já terão orientado a engenharia. Essa análise não substitui nem aumenta o tamanho da reserva final.

Vocabulários aprendidos, estatísticas de termos, seleção de atributos e quaisquer ajustes supervisionados devem respeitar essa separação. A árvore oficial e transformações fixas independentes dos rótulos podem ser compartilhadas. No módulo 2, o vocabulário e o IDF usam o catálogo oficial e os textos de treino de cada ajuste; textos de validação, da reserva e das 559 questões não entram nesse ajuste. Um eventual uso futuro de todo o corpus sem rótulos deve ser declarado como preparação transdutiva; não comprova generalização para concursos futuros.

IDs servem somente para joins, integridade e exclusão de exemplos; não são atributos. Coorte, disciplina e assunto de origem também não entram no classificador. A descrição de um tema não pode incorporar uma resposta específica obtida ao examinar um rótulo reservado.

## Famílias e calibração previstas

O orçamento inicial limita a comparação a três famílias: busca lexical; busca lexical com sinais de leis e artigos; recuperação híbrida com embeddings em cache. A similaridade com exemplos humanos pode compor um sinal adicional, sempre restrito aos exemplos de treinamento.

O módulo 2 fixa duas configurações lexicais em [experimento_lexical.json](../config/modulo2/experimento_lexical.json) antes de sua primeira medição interna. Ele compara escores, sem calibrar probabilidades, publicar questões ou decidir `fora`. O uso de descrições oficiais e sinais de leis/artigos não envolve classificação jurídica feita por LLM.

Antes de consultar qualquer resultado da reserva final, serão fixados em configuração:

- Representações, sinais, candidatos e grades de parâmetros de cada família, com seu histórico de mudanças durante o desenvolvimento.
- Procedimento de calibração com previsões internas fora da amostra, sem calibrar sobre previsões do próprio treinamento.
- Conjunto de limiares, restrição de precisão, suporte mínimo e regra de desempate da seleção.
- Procedimento de reajuste final e tratamento de partições sem suporte suficiente.

Normalização de siglas e identificação de leis ou artigos são transformações de strings, documentadas e determinísticas. Não constituem validação jurídica nem autorização para mapear manualmente uma questão a um tema. O sistema deve manter separada a evidência textual de sua interpretação pelo classificador.

O escore de recuperação não é uma probabilidade. A coluna `confianca` deverá representar uma estimativa calibrada da chance de o tema central estar certo, com desempenho de calibração e limitações apresentados. Nenhum limiar será escolhido diretamente nas previsões externas.

## Acerto e política de decisão

O critério principal segue o case: o tema central previsto pode coincidir com o central humano, com um extra humano ou com um ancestral ou descendente de um deles. Irmãos de um tema não contam como acerto. Extras previstos não resgatam um tema central errado.

Além do critério oficial, reportaremos acerto exato e acerto com parentesco imediato para mostrar a sensibilidade à tolerância hierárquica. A implementação deve distinguir ancestralidade de simples compartilhamento de pai.

A política de publicação excluirá disciplinas de nível zero e controlará temas excessivamente genéricos. Esses critérios serão definidos pela estrutura e descrição da taxonomia antes da avaliação externa. A tolerância hierárquica não justifica enviar toda questão a um ancestral genérico.

Somente temas ativos podem ser sugeridos. `Publicar` exige confiança e suporte conforme a política; `revisar` mantém uma sugestão de tema para o especialista. `Fora` exige evidência de ausência de tema adequado e terá avaliação própria. Confiança baixa, isoladamente, não significa estar fora da taxonomia.

## Métricas e incerteza

Na reserva final, registrar contagens de acertos, erros e publicações; precisão entre publicadas; cobertura; desempenho por disciplina quando houver suporte; comportamento dos casos fora presentes nessa reserva; e curva de precisão versus cobertura, sem usá-la para escolher outro limiar. Os oito casos fora estão distribuídos entre desenvolvimento e reserva, não são oito testes finais independentes. Avaliar também o erro e a confiabilidade das probabilidades, evitando conclusões por faixas com poucos exemplos.

No módulo 2, a taxa de acerto do primeiro candidato nas referências internas não é precisão de publicações: ainda não existe política de publicação. Similaridade, margem entre candidatos, presença do tema correto entre cinco sugestões e apoio de exemplos humanos são diagnósticos. Não devem aparecer como confiança calibrada ou comprovação de atendimento à meta.

A estimativa de precisão deve trazer denominador, intervalo e hipóteses do método escolhido antes da avaliação final. Dependência entre questões semelhantes e entre treinamentos das partições internas precisa ser considerada ou explicitada. Mesmo um acerto em todos os 20 exemplos reservados não demonstra precisão mínima de 95% com um limite inferior de confiança de 95%; o subconjunto publicado pode ser ainda menor.

Na entrega final, a cobertura das 559 questões é uma contagem conhecida: número de publicações nessas questões dividido por 559. Ela não recebe um intervalo estatístico inventado; o formato exigido será preenchido com o mesmo valor nos dois extremos, com explicação. A precisão permanece desconhecida até o gabarito oficial e terá previsão, suporte e incerteza próprios.

Separar o comportamento das 259 questões antigas e das 300 recentes ajuda a descrever a mudança de dados, mas sem rótulos recentes não há medição de precisão nesse segundo grupo. Intervalos baseados nas referências antigas não eliminam essa limitação.

## Receita final e registro dos experimentos

Após avaliar a receita congelada, o treinamento final pode usar as 100 referências humanas, mantendo a configuração e o procedimento de reajuste documentados antes da abertura da reserva. Isso incorpora mais dados, mas produz um ajuste diferente daquele medido nos 20 exemplos; o desempenho do ajuste final nas 559 questões permanece desconhecido. O CSV conterá 659 decisões, mas as 100 referências serão excluídas de todas as previsões sobre a avaliação oficial.

Cada experimento deve registrar configuração, hashes, partições, tempo, previsões, métricas, alterações e justificativas. Resultados negativos também serão preservados. O relatório distinguirá dados observados, estimativas, decisões de engenharia e questões ainda sem evidência.

A distinção entre seleção e avaliação segue a discussão de [validação cruzada aninhada na documentação do scikit-learn](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html). O projeto usa implementação própria e a biblioteca padrão; a referência metodológica não adiciona uma dependência.
