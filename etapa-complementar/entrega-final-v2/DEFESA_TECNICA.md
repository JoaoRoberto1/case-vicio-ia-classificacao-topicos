# Defesa técnica e roteiro de apresentação

Autor: **João Roberto de Oliveira Felix**.

Este roteiro usa os resultados da grade completa M8: **`sinais_large` foi selecionada, mas a publicação ficou desabilitada; 0 das 559 questões foram publicadas**. Confira os números no [relatório](relatorio.md), na [previsão](previsao.json) e nas [métricas M8](../artefatos/precisao-m8-v1/metricas.json). As tabelas anteriores descrevem outros experimentos. O roteiro explica o sistema e suas limitações; não substitui a leitura do código nem promete um resultado na contratação.

## Roteiro de cinco minutos

**0:00 a 0:45 - Problema e régua.** Uma questão publicada no tema errado prejudica o estudo do aluno. A métrica principal é a precisão entre publicadas, buscando a maior cobertura possível. O acerto de todas as sugestões e o acerto no top 5 são diagnósticos diferentes. As 100 referências não entram na avaliação oficial das 559 questões restantes.

**0:45 a 1:45 - Dados e representação.** A preparação limpa HTML, preserva IDs e verifica a árvore. Muitas descrições originais informavam apenas parentesco; por isso, o catálogo recebeu definições, termos e fontes versionados. Há ainda âncoras explícitas de leis e artigos, construídas sem olhar as classificações das questões. Enunciado, comando e alternativas fornecem evidências; assunto e disciplina de origem não são tratados como verdade.

**1:45 a 2:45 - Decisão própria.** Embeddings são preparados antecipadamente e salvos. Durante a classificação, há apenas código numérico local. A receita selecionada, `sinais_large`, aprende o ranking com os exemplos humanos de treino, combinando similaridades e seis sinais específicos. O escore ordena candidatos. Um ajuste separado estima a chance de aceitação pelo critério de ramo; a política define publicação ou revisão. A grade também avaliou RRF, cuja ordenação é fixa; nessa alternativa, os sinais informam confiança e política, sem alterar a fusão.

**2:45 a 3:45 - Como medi.** Cada predição avaliada é produzida fora do treino correspondente. A seleção da receita, da regra e o ajuste da confiança acontecem dentro dos blocos de treino, antes da avaliação externa. A grade e os critérios estão registrados. Contudo, as referências já orientaram rodadas anteriores: os resultados continuam exploratórios. As 20 referências inicialmente reservadas não são mais um teste novo independente.

**3:45 a 5:00 - Resultado, limites e produção.** A receita escolhida teve 53/80 acertos por ramo, um a menos que o M7; venceu pelo grupo interno elegível de 14/14. O procedimento externo aceitou somente quatro, todos corretos e vindos do RRF. Quatro não atingem o suporte mínimo de dez: a entrega publica 0/559, com precisão indefinida. Não atingimos a meta de precisão com cobertura. Mostre a reprodução sem rede ou encoder e encerre com o custo de revisão e a necessidade de nova avaliação humana temporal.

## Números da rodada final

| Recorte | Resultado | Interpretação |
|---|---|---|
| Receita selecionada, `sinais_large`, nas 80 | 53 por ramo, 39 exatos, 67 no top 5 | Acerto por ramo de 66,25%; não é precisão de publicação |
| Comparação pareada com M7 nas 80 | 0 melhoras e 1 piora por ramo | M7 tinha 54/80; não houve ganho global |
| Regra interna `confiança >= 0,90` | 14/14 corretas; cobertura interna 14/80 = 17,5% | Resultado usado na seleção, não confirmação independente |
| Procedimento externo nas 80 | 54 por ramo, 43 exatos, 66 no top 5 | Cada bloco pode escolher uma receita diferente |
| Aceites externos do procedimento | 4/4 corretos; cobertura 4/80 = 5% | Os quatro vieram de RRF no bloco 3; suporte abaixo de dez |
| Diagnóstico das 20 já conhecidas | 13 por ramo, 8 exatos, 17 no top 5 | Antes, M7 tinha 12/20 por ramo; não é teste novo independente |
| Entrega nas 559 sem referência | 0 publicadas; 559 para revisão | Cobertura 0%; precisão entre publicadas indefinida |

Os aceites externos não passaram diretamente para o CSV: o bloqueio da política final foi aplicado a todas as 659 linhas, incluindo as 100 referências. As sugestões e confianças permanecem disponíveis para revisão.

## Perguntas que preciso saber responder

### Qual é a diferença entre precisão, cobertura e confiança?

Precisão de publicação é `publicadas corretas / publicadas`. Cobertura é `publicadas / questões avaliadas`. Confiança é uma probabilidade estimada pelo sistema para uma sugestão. Não basta escrever 0,95 no CSV: é necessário verificar se as sugestões aceitas acertam na frequência prevista. Com zero publicadas, a precisão é indefinida; zero cobertura não comprova a meta.

### Por que não exigir confiança individual de 95% em todas as linhas?

O case exige 95% de precisão no conjunto publicado. Um limiar individual pode ser útil, mas não é a única política possível. A comparação inclui cortes de confiança, escore, margem e concordância dos sinais. Cada política é escolhida no treino e avaliada fora dele, com suporte mínimo e precisão do grupo explicitados. O suporte mínimo de dez é uma decisão de projeto, não uma certificação estatística.

### Por que escolher Large se M7 acertou mais questões?

A ordem de seleção foi fixada antes da rodada: maior cobertura entre políticas elegíveis, maior precisão e depois maior acerto global. O M7 acertou 54/80, mas nenhuma de suas regras passou pelos critérios internos. Duas combinações tiveram 14/14: `large_rrf20` com confiança mínima de 0,95 e `sinais_large` com mínima de 0,90. A segunda ganhou o desempate pelo acerto global, 53/80 contra 50/80 do RRF. Isso explica a escolha; não demonstra que Large seja superior ao M7 de forma geral.

### Se houve 14/14 e 4/4, por que não publicar?

São recortes diferentes. Os 14/14 de `sinais_large` foram usados para escolher a receita e a regra nas 80 referências. Na avaliação externa do procedimento, os blocos 1 e 2 escolheram M7 sem regra de publicação habilitada; só o bloco 3 escolheu RRF e aceitou quatro questões. Esses quatro acertos não são uma validação direta da receita final `sinais_large` nem reproduzem seus 14 aceites internos.

O procedimento externo teve apenas quatro aceites, abaixo do suporte mínimo de dez registrado no protocolo. Mesmo com 100% observado, o intervalo exploratório de Wilson é de 51,01% a 100%, sem cobrir adaptação histórica ou mudança de distribuição. A política foi desabilitada: 0/559 publicadas. Não posso apresentar 100% como precisão das 559, nem interpretar cobertura zero como meta atingida. Ampliar a publicação exige evidência nova, não reduzir o suporte depois de observar o resultado.

### A confiança calibrada ficou melhor?

O diagnóstico externo é misto: Brier de 0,207372 contra 0,220957 da constante ajustada no treino, mas ECE de 0,085172 contra 0,033977, em cinco faixas fixas. Menor é melhor nas duas métricas; portanto, Brier melhorou e ECE piorou. A log-loss foi 0,615813 contra 0,634058. Isso não autoriza afirmar calibração superior em todas as dimensões nem probabilidade individual certificada. São métricas do procedimento externo, não de um novo teste da receita final.

### Onde entrou IA e o que acontece durante a decisão?

O LLM ajudou a preparar descritores e referências do catálogo, sem julgar temas de questões avaliadas. O encoder gera vetores em uma etapa separada. Na decisão, há somente JSONs versionados e operações numéricas na biblioteca padrão do Python. A regressão de confiança e, nas receitas supervisionadas, o ranking treinado são componentes do classificador próprio; não são chamadas a um modelo de linguagem. No RRF, a ordenação é uma fórmula fixa. A reprodução bloqueia rede, leitura do `.env`, importação de encoders e acesso aos pesos.

### Como os 100 exemplos foram usados?

O desenvolvimento histórico usou 80 referências e reservou 20. Depois que os resultados das 20 ficaram conhecidos, elas perderam o papel de novo teste independente. A rodada final escolhe receita e política com as 80 e usa as 20 apenas para diagnóstico posterior. A confiança final usa previsões fora do treino das 80. Se a receita escolhida for supervisionada, o ranking é reajustado com as 100 para sugerir temas às 559 questões; esse reajuste não recebeu avaliação independente nova. Se for `large_rrf20`, não existe reajuste dos pesos da ordenação: os rótulos orientam seleção, confiança e avaliação, mas a fórmula RRF permanece fixa.

### A validação aninhada elimina todo o viés?

Não. Ela separa os rótulos externos dos ajustes e da seleção da grade atual. Não apaga decisões históricas influenciadas pelas mesmas referências. Além disso, o cross-fit interno da confiança compartilha conjuntos de treino dos rankers; serve à seleção interna. O teste externo do procedimento inteiro é a separação relevante nesta rodada. Uma avaliação recente, rotulada e ainda não consultada permanece necessária.

### Como a árvore entra no acerto e no ranking?

O critério aceita o tema central humano, um extra ou um ancestral/descendente de um deles; um irmão não conta. O classificador só considera temas ativos abaixo das raízes. A variante hierárquica pode recuar para o ancestral comum mais específico dos primeiros candidatos, com bloqueio de categorias genéricas definidas no código. São registrados o nível sugerido e os recuos para tornar visível uma eventual perda de especificidade.

### Por que há sinais de leis e artigos se o sistema não interpreta Direito?

Eles são pistas textuais reproduzíveis. O programa normaliza números e aliases e associa artigo a instrumento apenas quando a referência é inequívoca no segmento. Citar uma lei não prova que ela é o tema central, que está vigente naquele contexto ou que a alternativa está correta. Nas variantes `sinais_*`, esses atributos entram no ranking supervisionado. Em `large_rrf20`, informam confiança e política, mas não alteram a fusão RRF; o ranking M7 preservado também não passa a aprender esses novos sinais. Nenhum desses usos substitui validação humana.

### O modelo maior é automaticamente melhor?

Não. O E5-large INT8 foi comparado como alternativa de representação. O custo local, o tempo e as limitações da quantização foram registrados. A escolha depende das métricas da grade, não do tamanho do modelo ou de resultados em benchmarks externos. Mesmo que o modelo maior vença, isso não permite concluir que a versão FP32 teria o mesmo desempenho.

### Por que não automatizar a decisão `fora`?

Há apenas oito exemplos humanos fora da taxonomia. Baixa confiança pode significar uma representação ruim, uma convenção ambígua ou falta de exemplos, além de ausência real de tema. Por isso, a política encaminha casos incertos à revisão com uma sugestão. Não declara `fora` somente para retirar casos difíceis do recorte.

### Por que não preencher extras automaticamente?

Prever extras é uma segunda decisão que precisaria de avaliação própria. A versão entregue mantém esse campo vazio. Os extras humanos entram como destinos aceitos ao medir a sugestão principal, conforme a regra fornecida; isso não significa que o sistema tenha aprendido uma política multilabel validada.

### Como estimar o resultado das 559 sem seus rótulos?

A cobertura é contada exatamente no CSV, excluindo as 100 referências. Se houver publicação habilitada, a previsão de precisão extrapola a taxa do grupo aceito na avaliação externa, com intervalo e ressalvas. A média das confianças publicadas é um diagnóstico separado. Mudança de distribuição e adaptação histórica limitam essa extrapolação; nas receitas supervisionadas, há ainda o reajuste do ranking em 100 referências. A precisão observada das 559 permanece desconhecida.

### Como levar isso para 50 mil questões por semana?

Separaria preparação dos vetores, decisão numérica e revisão. A implementação das receitas Large também exige vetores Small: para questões novas, é preciso considerar os dois encoders. Cada execução retomada mede apenas o trabalho daquela execução, sem a geração anterior dos vetores reaproveitados. Não se deve dividir o tempo da última retomada pelos 1.030 registros e tratá-lo como custo integral.

Há uma evidência parcial separada: [intervalos de conclusão Large](../artefatos/embeddings-e5-large-m8/retomada-v1/tempo_questoes.json). Entre 65 conclusões consecutivas, 64 intervalos somaram 331,27124 segundos para 64 questões novas, com 67 janelas. O primeiro registro serve apenas de marco inicial; sua geração, a carga do encoder e o reaproveitamento de cache ficam fora da conta. Essa medição pertence à retomada que começou com 594 vetores prontos; a última execução começou com 851. As duas contagens não são o denominador dos 64 intervalos. Os intervalos incluem escrita e verificação entre conclusões. Extrapolar `331,27124 / 64 × 50.000 / 3.600` resulta em aproximadamente **71,89 horas Large**, além da estimativa Small de **4,35 horas**: cenário aritmético de **76,24 horas** de preparação nessa máquina, sem paralelismo.

Isso não é medição de 50 mil nem previsão garantida: o bloco de 64 questões recentes é contíguo, não aleatório, e os tempos vêm do sistema de arquivos em um computador compartilhado, sem relógio monotônico instrumentado. Comprimento dos textos, carga e custo fixo podem mudar. A aproximação Small também mistura questões e temas. O tempo total desde zero não foi medido. A decisão com vetores prontos tem seu próprio benchmark, separado da preparação. Para estimar custo financeiro, multiplicaria as horas de cada fase pela tarifa da máquina, acrescentando energia e revisão humana; não confundo ausência de API paga com custo total zero.

Para limitar RAM em produção, processaria questões em lotes e liberaria os caches de consultas entre eles. O código atual foi exercitado no recorte do case; não foi submetido a uma carga de 50 mil questões. O maior custo pode ser a revisão humana. Correções precisam registrar versão da árvore, tema central, extras ou `fora`, justificativa e revisor. Avaliaria candidatos semanalmente e só promoveria uma versão após um teste temporal separado, preservando a anterior para reversão.

## Demonstração sem interface gráfica

Na pasta `etapa-complementar`, execute:

```console
python -E -X utf8 -B -S scripts/entregar_precisao.py --verificar
```

O comando recompõe o experimento e compara os arquivos finais. Para demonstrar a execução em cópia sem credenciais, ambientes ou pesos:

```console
python -E -X utf8 -B -S scripts/verificar_precisao.py --evidencia tmp/defesa-m8.json
```

O destino da evidência deve ser novo; o verificador não sobrescreve registros. Abra o relatório e a previsão para explicar os números. Uma interface visual não é exigida no case e não melhora a precisão; o foco da demonstração é a decisão reproduzível e a interpretação correta dos resultados.

## Frases que devo evitar

- “Garantimos 95%”: uma taxa observada com poucos casos e referências reutilizadas não é garantia populacional.
- “As 20 são um teste independente”: elas já eram conhecidas nesta rodada.
- “O modelo confirmou o tema”: nenhum LLM julga as classificações avaliadas.
- “Cobertura zero significa 100% de precisão”: o denominador da precisão é zero.
- “O vetor é uma probabilidade”: similaridade e escore de ranking precisam de calibração.
- “Está pronto para produção”: reprodução local e estimativa de escala não substituem validação operacional e temporal.
