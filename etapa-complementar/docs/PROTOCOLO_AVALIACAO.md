# Protocolo de avaliação do classificador

Este protocolo separa a construção do classificador da medição de sua qualidade. O objetivo é estimar a precisão das publicações e sua cobertura usando exclusivamente as referências humanas fornecidas, sem transformar similaridade ou concordância entre IAs em evidência de acerto.

**Estado atual:** preparação e protocolo estrutural concluídos no módulo 1. Classificadores, grades de parâmetros, calibrador e limiares ainda não estão implementados. Esses componentes serão versionados antes da primeira medição externa.

## Fontes e população avaliada

São 659 questões e 377 temas, dos quais 375 ativos. A folha-verdade fornece 100 referências humanas: 92 dentro da taxonomia, 8 fora, 61 temas centrais distintos e 39 questões com pelo menos um tema extra.

As 100 referências estão entre as 359 questões do banco anterior. A avaliação oficial usa as 559 restantes: 259 antigas e 300 recentes. Os resultados nas referências humanas não medem diretamente a qualidade nas recentes; qualquer extrapolação deve declarar essa limitação.

As colunas de disciplina e assunto de origem podem estar erradas. Elas não são gabarito. Os rótulos e julgamentos de IA do projeto anterior não entram em treinamento, calibração, seleção ou avaliação.

## Preparação permitida e rastreabilidade

Limpeza, extração de citações e organização da árvore devem ser reproduzíveis. Modelos podem gerar artefatos de preparação, inclusive embeddings e descrições enriquecidas, com origem, versão, instruções e parâmetros registrados. Não podem escolher temas, votar, julgar nem validar classificações.

As transformações e embeddings em cache não podem incorporar o tema verdadeiro de uma questão de avaliação. Exemplos ou termos propostos durante a preparação não podem virar rótulos artificiais de questões avaliadas.

A execução que gera as decisões será local, sem chamadas a modelos de linguagem. O manifesto registra SHA-256 das fontes, configurações, código de preparação e produtos, sem caminhos absolutos ou horários variáveis. Mudanças exigem nova configuração e novo diretório de saída; resultados anteriores são preservados.

## Grupos e partições

A configuração fica em `config/protocolo_avaliacao.json`, com semente `20261020`, cinco partições externas e três internas.

Questões duplicadas ou muito semelhantes pertencem ao mesmo grupo. O agrupamento combina igualdade do texto normalizado com Jaccard de sequências de cinco termos, limiar `0.85`, para textos com pelo menos 12 termos. Grupos conectados permanecem juntos, mesmo quando a ligação é transitiva.

O agrupamento usa texto, sem consultar rótulos. As partições e seu diagnóstico ficam em `particoes.json` e `diagnostico.json`. Devem ser conferidos ausência de sobreposição entre treino e avaliação, suporte por disciplina e distribuição de casos fora da taxonomia. Poucos exemplos por tema impedem prometer equilíbrio por tema.

Cada questão rotulada será avaliada uma única vez na camada externa, quando seu grupo estiver excluído do treinamento. Não se admite obter seu tema de um exemplo duplicado mantido no treino.

Na preparação de 20/10/2026, o detector produziu 659 grupos unitários: não encontrou duplicatas segundo a normalização e o limiar definidos. Isso não exclui semelhanças abaixo do limiar. As cinco partições externas têm 80 exemplos de treino e 20 de teste cada, com três partições internas. Os oito casos fora da taxonomia ficaram distribuídos em 2, 1, 1, 2 e 2 nos testes externos. Nenhuma previsão de tema foi produzida nessa etapa.

## Ajuste interno e avaliação externa

Para cada partição externa:

1. Reserve os grupos externos e seus rótulos para a avaliação.
2. Use somente os grupos restantes nas três partições internas para ajustar parâmetros, calibrar probabilidades, selecionar a família e o limiar de publicação.
3. Reajuste a receita selecionada nos dados externos de treinamento, conforme o procedimento de calibração previamente fixado.
4. Gere e registre previsões para a partição externa sem usar seus rótulos na decisão.
5. Abra os rótulos externos apenas para calcular as métricas.

Vocabulários aprendidos, estatísticas de termos, seleção de atributos e quaisquer ajustes supervisionados devem respeitar essa separação. A árvore oficial e transformações fixas independentes dos rótulos podem ser compartilhadas. Um eventual uso de todo o corpus sem rótulos deve ser declarado como preparação transdutiva; não comprova generalização para concursos futuros.

As previsões externas concatenadas avaliam a **receita de seleção interna**. Não se pode escolher a melhor família olhando esse conjunto e usar a mesma medição como estimativa imparcial da família escolhida.

Se a inspeção externa orientar nova regra, atributo, grade ou calibrador, a revisão será registrada como exploratória. Repetir partições não cria novas referências humanas nem restaura independência.

## Famílias e calibração previstas

O orçamento inicial limita a comparação a três famílias: busca lexical; busca lexical com sinais de leis e artigos; recuperação híbrida com embeddings em cache. A similaridade com exemplos humanos pode compor um sinal adicional, sempre restrito aos exemplos de treinamento.

Antes de consultar qualquer resultado externo, serão fixados em configuração:

- Representações, sinais, candidatos e grades de parâmetros de cada família.
- Procedimento de calibração com previsões internas fora da amostra, sem calibrar sobre previsões do próprio treinamento.
- Conjunto de limiares, restrição de precisão, suporte mínimo e regra de desempate da seleção.
- Procedimento de reajuste final e tratamento de partições sem suporte suficiente.

O escore de recuperação não é uma probabilidade. A coluna `confianca` deverá representar uma estimativa calibrada da chance de o tema central estar certo, com desempenho de calibração e limitações apresentados. Nenhum limiar será escolhido diretamente nas previsões externas.

## Acerto e política de decisão

O critério principal segue o case: o tema central previsto pode coincidir com o central humano, com um extra humano ou com um ancestral ou descendente de um deles. Irmãos de um tema não contam como acerto. Extras previstos não resgatam um tema central errado.

Além do critério oficial, reportaremos acerto exato e acerto com parentesco imediato para mostrar a sensibilidade à tolerância hierárquica. A implementação deve distinguir ancestralidade de simples compartilhamento de pai.

A política de publicação excluirá disciplinas de nível zero e controlará temas excessivamente genéricos. Esses critérios serão definidos pela estrutura e descrição da taxonomia antes da avaliação externa. A tolerância hierárquica não justifica enviar toda questão a um ancestral genérico.

Somente temas ativos podem ser sugeridos. `Publicar` exige confiança e suporte conforme a política; `revisar` mantém uma sugestão de tema para o especialista. `Fora` exige evidência de ausência de tema adequado e terá avaliação própria. Confiança baixa, isoladamente, não significa estar fora da taxonomia.

## Métricas e incerteza

Nas previsões externas, registrar contagens de acertos, erros e publicações; precisão entre publicadas; cobertura; desempenho por disciplina; comportamento dos oito casos fora; e curva de precisão versus cobertura. Avaliar também o erro e a confiabilidade das probabilidades, evitando conclusões por faixas com poucos exemplos.

A estimativa de precisão deve trazer denominador, intervalo e hipóteses do método escolhido antes da avaliação externa. Dependência entre questões semelhantes e entre treinamentos das partições precisa ser considerada ou explicitada. Uma amostra pequena, mesmo sem erros observados, não garante precisão mínima de 95%.

Na entrega final, a cobertura das 559 questões é uma contagem conhecida: número de publicações nessas questões dividido por 559. Ela não recebe um intervalo estatístico inventado; o formato exigido será preenchido com o mesmo valor nos dois extremos, com explicação. A precisão permanece desconhecida até o gabarito oficial e terá previsão, suporte e incerteza próprios.

Separar o comportamento das 259 questões antigas e das 300 recentes ajuda a descrever a mudança de dados, mas sem rótulos recentes não há medição de precisão nesse segundo grupo. Intervalos baseados nas referências antigas não eliminam essa limitação.

## Receita final e registro dos experimentos

Após avaliar a receita, o treinamento final pode usar as 100 referências humanas, mantendo a configuração e a regra de seleção documentadas. O CSV conterá 659 decisões, mas as 100 referências serão excluídas de todas as previsões sobre a avaliação oficial.

Cada experimento deve registrar configuração, hashes, partições, tempo, previsões, métricas, alterações e justificativas. Resultados negativos também serão preservados. O relatório distinguirá dados observados, estimativas, decisões de engenharia e questões ainda sem evidência.
