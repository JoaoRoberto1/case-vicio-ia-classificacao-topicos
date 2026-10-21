# Defesa técnica e roteiro de apresentação

Autor: **João Roberto de Oliveira Felix**.

Use os números do [relatório final](relatorio.md) e da [previsão](previsao.json). As tabelas das versões anteriores descrevem outros experimentos. Este roteiro explica o sistema e suas limitações; não substitui a leitura do código nem promete um resultado na contratação.

## Roteiro de cinco minutos

**0:00 a 0:45 - Problema e régua.** Uma questão publicada no tema errado prejudica o estudo do aluno. A métrica principal é a precisão entre publicadas, buscando a maior cobertura possível. O acerto de todas as sugestões e o acerto no top 5 são diagnósticos diferentes. As 100 referências não entram na avaliação oficial das 559 questões restantes.

**0:45 a 1:45 - Dados e representação.** A preparação limpa HTML, preserva IDs e verifica a árvore. Muitas descrições originais informavam apenas parentesco; por isso, o catálogo recebeu definições, termos e fontes versionados. Há ainda âncoras explícitas de leis e artigos, construídas sem olhar as classificações das questões. Enunciado, comando e alternativas fornecem evidências; assunto e disciplina de origem não são tratados como verdade.

**1:45 a 2:45 - Decisão própria.** Embeddings são preparados antecipadamente e salvos. Durante a classificação, o programa combina similaridade lexical, vetores e sinais específicos com código numérico local. O ranking supervisionado aprende com os exemplos humanos de treino. O escore ordena candidatos; um segundo ajuste estima a chance de a sugestão ser aceita pelo critério de ramo. A política escolhe o que publicar e o que encaminhar à revisão.

**2:45 a 3:45 - Como medi.** Cada predição avaliada é produzida fora do treino correspondente. A seleção da receita, da regra e o ajuste da confiança acontecem dentro dos blocos de treino, antes da avaliação externa. A grade e os critérios estão registrados. Contudo, as referências já orientaram rodadas anteriores: os resultados continuam exploratórios. As 20 referências inicialmente reservadas não são mais um teste novo independente.

**3:45 a 5:00 - Resultado, limites e produção.** Apresente o resultado final de ramo, a precisão do grupo publicado e a cobertura, com seus denominadores. Explique o que a comparação com o modelo maior mudou ou deixou de mudar. Mostre a reprodução sem rede ou encoder. Termine com o gargalo observado, o custo de revisão e a próxima avaliação temporal necessária para promover uma versão em produção.

## Perguntas que preciso saber responder

### Qual é a diferença entre precisão, cobertura e confiança?

Precisão de publicação é `publicadas corretas / publicadas`. Cobertura é `publicadas / questões avaliadas`. Confiança é uma probabilidade estimada pelo sistema para uma sugestão. Não basta escrever 0,95 no CSV: é necessário verificar se as sugestões aceitas acertam na frequência prevista. Com zero publicadas, a precisão é indefinida; zero cobertura não comprova a meta.

### Por que não exigir confiança individual de 95% em todas as linhas?

O case exige 95% de precisão no conjunto publicado. Um limiar individual pode ser útil, mas não é a única política possível. A comparação inclui cortes de confiança, escore, margem e concordância dos sinais. Cada política é escolhida no treino e avaliada fora dele, com suporte mínimo e precisão do grupo explicitados. O suporte mínimo de dez é uma decisão de projeto, não uma certificação estatística.

### Onde entrou IA e o que acontece durante a decisão?

O LLM ajudou a preparar descritores e referências do catálogo, sem julgar temas de questões avaliadas. O encoder gera vetores em uma etapa separada. Na decisão, há somente JSONs versionados e operações numéricas na biblioteca padrão do Python. A regressão e o ranking treinado são componentes do classificador próprio; não são chamadas a um modelo de linguagem. A reprodução bloqueia rede, leitura do `.env`, importação de encoders e acesso aos pesos.

### Como os 100 exemplos foram usados?

O desenvolvimento histórico usou 80 referências e reservou 20. Depois que os resultados das 20 ficaram conhecidos, elas perderam o papel de novo teste independente. A rodada final escolhe receita e política com as 80, usa as 20 apenas para diagnóstico posterior e reajusta o ranking com as 100 para sugerir temas às 559 questões. A confiança final usa previsões fora do treino das 80. Esse reajuste não recebeu uma avaliação independente nova.

### A validação aninhada elimina todo o viés?

Não. Ela separa os rótulos externos dos ajustes e da seleção da grade atual. Não apaga decisões históricas influenciadas pelas mesmas referências. Além disso, o cross-fit interno da confiança compartilha conjuntos de treino dos rankers; serve à seleção interna. O teste externo do procedimento inteiro é a separação relevante nesta rodada. Uma avaliação recente, rotulada e ainda não consultada permanece necessária.

### Como a árvore entra no acerto e no ranking?

O critério aceita o tema central humano, um extra ou um ancestral/descendente de um deles; um irmão não conta. O classificador só considera temas ativos abaixo das raízes. A variante hierárquica pode recuar para o ancestral comum mais específico dos primeiros candidatos, com bloqueio de categorias genéricas definidas no código. São registrados o nível sugerido e os recuos para tornar visível uma eventual perda de especificidade.

### Por que há sinais de leis e artigos se o sistema não interpreta Direito?

Eles são pistas textuais reproduzíveis. O programa normaliza números e aliases e associa artigo a instrumento apenas quando a referência é inequívoca no segmento. Citar uma lei não prova que ela é o tema central, que está vigente naquele contexto ou que a alternativa está correta. Os sinais entram no ranking; não substituem o conjunto das evidências nem uma validação humana.

### O modelo maior é automaticamente melhor?

Não. O E5-large INT8 foi comparado como alternativa de representação. O custo local, o tempo e as limitações da quantização foram registrados. A escolha depende das métricas da grade, não do tamanho do modelo ou de resultados em benchmarks externos. Mesmo que o modelo maior vença, isso não permite concluir que a versão FP32 teria o mesmo desempenho.

### Por que não automatizar a decisão `fora`?

Há apenas oito exemplos humanos fora da taxonomia. Baixa confiança pode significar uma representação ruim, uma convenção ambígua ou falta de exemplos, além de ausência real de tema. Por isso, a política encaminha casos incertos à revisão com uma sugestão. Não declara `fora` somente para retirar casos difíceis do recorte.

### Por que não preencher extras automaticamente?

Prever extras é uma segunda decisão que precisaria de avaliação própria. A versão entregue mantém esse campo vazio. Os extras humanos entram como destinos aceitos ao medir a sugestão principal, conforme a regra fornecida; isso não significa que o sistema tenha aprendido uma política multilabel validada.

### Como estimar o resultado das 559 sem seus rótulos?

A cobertura é contada exatamente no CSV, excluindo as 100 referências. Se houver publicação habilitada, a previsão de precisão extrapola a taxa do grupo aceito na avaliação externa, com intervalo e ressalvas. A média das confianças publicadas é um diagnóstico separado. Mudança de distribuição, adaptação histórica e reajuste em 100 referências limitam essa extrapolação. A precisão observada das 559 permanece desconhecida.

### Como levar isso para 50 mil questões por semana?

Separaria preparação dos vetores, decisão numérica e revisão. Os benchmarks locais e a projeção linear são explicitados no relatório; não equivalem a um teste de carga de 50 mil. O maior custo pode ser a revisão humana. Correções precisam registrar versão da árvore, tema central, extras ou `fora`, justificativa e revisor. Avaliaria candidatos semanalmente e só promoveria uma versão após um teste temporal separado, preservando a anterior para reversão.

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
