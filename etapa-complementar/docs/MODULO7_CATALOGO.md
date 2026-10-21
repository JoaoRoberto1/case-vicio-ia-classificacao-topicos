# Módulo 7 Catálogo enriquecido e classificação seletiva

O enriquecimento do catálogo melhorou o acerto por ramo de **37/80 para 54/80** no desenvolvimento (46,25% para 67,5%). No diagnóstico das 20 referências já conhecidas, o resultado passou de **6/20 para 12/20**. A melhoria não atingiu a meta de publicação com precisão de 95%: nenhuma política da grade reuniu suporte mínimo e precisão suficientes. A cobertura continua em zero, com precisão entre publicadas indefinida.

O pacote é um experimento separado. CSV, previsão, PDF, calibração e demais artefatos congelados dos módulos 1 a 6 mantêm seus bytes. As sugestões novas estão em [catalogo-m7-v1](../artefatos/catalogo-m7-v1/manifesto.json); não substituem automaticamente a entrega M5.

## O que mudou

Os 371 temas ativos não raiz receberam descrições conceituais, termos associados e fontes por registro. As descrições originais frequentemente continham contagens e caminhos, com pouca informação temática. O novo catálogo preserva títulos, IDs, status e árvore; substitui somente a representação descritiva usada pelo experimento.

O LLM participou exclusivamente da preparação do catálogo, a partir da taxonomia e de fontes oficiais ou acadêmicas. Não recebeu questões com rótulos ou sugestões para escolher, votar ou validar classificações. Não foram usados rótulos da primeira entrega nem do concorrente. A [procedência](../config/modulo7/preparacao_catalogo.json) registra instrução, limitações e identificação disponível da ferramenta. Os quatro arquivos por disciplina conservam as fontes e as ambiguidades. Não houve revisão jurídica humana; recortes desconhecidos como “Parte 1/2” não receberam limites inventados.

Os vetores dos 371 temas foram preparados novamente com o mesmo E5-small local, com revisão e hashes fixados no M3. Os vetores das 659 questões foram reutilizados. Durante a classificação, o programa usa somente a biblioteca padrão do Python e os caches numéricos versionados; não executa encoder nem chama API.

Foram comparadas seis receitas:

| Receita | Acerto por ramo em 80 | Acerto exato | Top 5 por ramo |
| --- | ---: | ---: | ---: |
| Referência anterior M3 | 37 | 24 | 54 |
| Catálogo enriquecido lexical | 51 | 34 | 66 |
| Catálogo enriquecido semântico | 47 | 34 | 64 |
| Combinação RRF k=5 | 54 | 39 | 66 |
| Combinação RRF k=20 | 54 | 38 | 67 |
| Ranking aprendido | 54 | 41 | 66 |
| Ranking aprendido com recuo hierárquico | **54** | **42** | 66 |

TF-IDF é ajustado somente no catálogo, sem usar textos de avaliação no vocabulário ou IDF. O ranking aprendido combina oito sinais numéricos: similaridades lexical e semânticas, posições dos candidatos, concordância entre sinais e nível do tema. Uma perda logística por pares aprende coeficientes a partir dos temas centrais e extras humanos de treino, com peso igual por questão, regularização e número de passos fixos. Seu escore não é probabilidade.

A variante hierárquica pode escolher o ancestral comum mais específico dos três primeiros candidatos quando ele é ativo, não raiz e não possui título genérico excluído. Fez 13 recuos nas 80 questões: as sugestões de nível 1 passaram de 25 para 38. O acerto por ramo permaneceu em 54 e o exato cresceu de 41 para 42; o ganho principal sobre o M3, portanto, já existia sem esses recuos. A granularidade está registrada para que a melhora não seja confundida com publicação indiscriminada em categorias amplas.

## Como a seleção foi avaliada

A [grade](../config/modulo7/protocolo.json) foi fixada antes da primeira medição M7, com SHA-256 `77448049ed4c668ed550735530df81e4cfaa584d2121181d81415e2bd30c0ea1`. A implementação recusa outro conteúdo. Esse registro local não apaga o conhecimento acumulado nas rodadas anteriores.

1. As seis receitas produziram previsões fora do treino nas três partições das 80 referências. O ajuste do ranker recebe somente rótulos de treino. Identidade ou texto repetido entre treino e consulta é recusado.
2. Em cada treino externo, três partições internas escolhem conjuntamente receita e regra de abstenção. São comparados cortes de escore e margem nos quantis 50%, 65%, 80% e 90%, além da concordância dos primeiros candidatos lexical e semântico. A regra precisa de pelo menos dez casos e 95% de acerto por ramo na seleção interna; entre regras viáveis, vence a maior cobertura. Sem regra viável, o acerto global serve apenas para escolher sugestões para revisão.
3. A regra escolhida dentro do treino é aplicada à validação externa sem consultar seus rótulos. Esse procedimento teve **53/80 acertos por ramo (66,25%)**, 37 exatos e 68 no top 5. Nenhum dos três treinos internos encontrou regra de publicação viável, portanto não houve publicações externas.
4. Somente depois da seleção, a receita global escolhida foi aplicada às 20 referências já conhecidas. Foram **12/20 acertos por ramo, 11 exatos e 17 no top 5**. Em comparação pareada, sete questões melhoraram e uma piorou por ramo. Esse é um diagnóstico exploratório, não um novo teste independente.
5. A receita escolhida foi reajustada nas 100 referências humanas e gerou 559 sugestões experimentais. Elas continuam destinadas à revisão. Não há rótulos oficiais disponíveis para medir seu acerto.

Nas 80, a comparação pareada da receita escolhida com o M3 teve 22 melhorias e cinco regressões por ramo, ganho líquido de 17. No acerto exato, foram 25 melhorias e sete regressões, ganho líquido de 18.

As 80 referências já foram reutilizadas em desenvolvimento, e as outras 20 já eram conhecidas. A validação aninhada limita o otimismo da seleção desta grade; não torna todo o histórico independente. As métricas não garantem desempenho em questões recentes nem no lote de 559.

## Por que a cobertura ainda é zero

A auditoria confirmou que a versão M4 seleciona um calibrador constante de 46,30% e exige probabilidade individual de pelo menos 95%. A precisão conjunta de 95% exigida pelo case não equivale a essa restrição individual. Exigir somente folhas também era uma decisão da implementação, não uma exigência explícita do enunciado.

O M7 testa a precisão do grupo aceito diretamente e permite o recuo hierárquico descrito acima. Mesmo assim, entre os cortes pré-definidos com suporte de pelo menos dez casos, o melhor resultado de desenvolvimento foi **15/17 = 88,24%**. Esse resultado foi selecionado olhando os rótulos de desenvolvimento e já é otimista; não sustenta anunciar 95% nas questões sem rótulo.

O suporte mínimo de dez é uma escolha de projeto, não uma certificação estatística. A política também exigiria pelo menos dez publicações e 95% observados na validação externa aninhada antes de habilitar uma candidata. O campo de probabilidade condicional descreve o grupo aceito na seleção, quando existente; não é calibração individual de cada questão. Nesta execução nenhuma política foi habilitada, e a precisão entre publicadas permanece `null`, não zero.

## Reprodução e checkpoint

Na pasta `etapa-complementar`, a reprodução das decisões usa somente Python e os arquivos versionados:

```console
python -E -X utf8 -B -S -m classificacao_catalogo verificar
python -E -X utf8 -B -S scripts/verificar_catalogo.py
```

O segundo comando cria uma cópia por lista permitida, sem `.env`, ambiente virtual ou pesos; bloqueia rede e encoder e confere os onze produtos byte a byte. Não refaz embeddings nem constitui um novo teste estatístico. A evidência da execução fica no [registro de reprodução](../artefatos/checkpoints/reproducao_modulo7.json).

Para preparar novamente os embeddings, é necessário o ambiente de preparação e os pesos locais fixados no M3. Esse comando é separado da decisão:

```console
.venv/Scripts/python.exe -X utf8 -B -m classificacao_catalogo preparar
```

Os 66 testes novos cobrem integridade do catálogo, imutabilidade da taxonomia, normalização e aprendizado numérico, seleção sem acesso ao rótulo, bloqueio de ressubstituição, hierarquia e isolamento dos cortes. A reprodução verifica o fluxo completo nos dados reais sem exibir casos para adjudicação por LLM. Os testes verificam software; as métricas acima medem o classificador.

O [checkpoint M7](../artefatos/checkpoints/modulo7.json) registra os hashes, as métricas e a preservação dos módulos anteriores. Este é um ponto de parada e commit. O próximo experimento deve priorizar uma representação semântica mais forte ou sinais específicos extraídos por regras, com comparação limitada e pré-definida. Aumentar a cobertura só será uma melhora se a precisão do grupo publicado também puder ser sustentada.
