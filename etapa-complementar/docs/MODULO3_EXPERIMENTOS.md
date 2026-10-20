# Módulo 3 — Experimentos de melhoria

**Pré-registro de 20/10/2026, antes da primeira medição do módulo 3.** A grade, a preparação dos embeddings e a regra de seleção abaixo foram definidas antes de observar os resultados. O fechamento acrescenta as medições obtidas, preservando essas decisões.

**Módulo 3 concluído:** implementação, preparação do cache, 50 novos testes, comparação das sete receitas e reprodução integral conferidos. A receita `hibrido_catalogo` foi selecionada com 37/80 acertos por ramo e 24/80 pelo critério exato. Os sete produtos reconstruídos coincidiram byte a byte com os arquivos preservados. A comparação é exploratória, nas mesmas 80 referências do desenvolvimento; as 20 reservadas continuam fora do treinamento, da vetorização e da inferência.

O objetivo é medir se representações semânticas melhoram a recuperação e a ordenação dos temas, e separar esse efeito do apoio de exemplos humanos. O módulo termina com uma receita selecionada e artefatos locais verificáveis. Calibração, limiares, decisões de publicação e avaliação da reserva pertencem ao módulo 4.

## Evidência que motivou a comparação

O [módulo 2](MODULO2_CLASSIFICADOR.md) produziu 31 acertos em 80 referências pelo critério de ramo e 18 pelo critério exato. O primeiro candidato acertou menos que o conjunto de cinco candidatos: o tema aceitável apareceu no top5 de 57/80 referências na receita lexical. Isso permite investigar separadamente a presença de candidatos pertinentes e sua ordenação.

Entre as referências dentro da taxonomia, o módulo 2 acertou 17/27 quando o tema central humano já aparecia no treino e 14/47 quando ele não aparecia. A comparação inclui catálogo sem exemplos para medir a dependência desse apoio. Os seis casos `fora` do desenvolvimento continuam incluídos nas métricas gerais, mas este módulo não decide `fora` automaticamente.

Essas métricas agregadas motivaram a grade abaixo. Não houve revisão jurídica de questões individuais por um modelo de linguagem. O desempenho M3 não havia sido observado no pré-registro; os resultados positivos e negativos agora estão apresentados na seção de fechamento.

## Separação dos dados e preservação dos módulos anteriores

Vale o [protocolo de avaliação](PROTOCOLO_AVALIACAO.md): usar os 80 `treino_ids` da primeira partição externa e suas três validações internas. Cada receita produziu uma predição fora da amostra para cada uma dessas 80 referências. Os rótulos usados pelo classificador em cada ajuste se limitam ao treino interno; o avaliador compara as predições com as referências de validação depois da inferência.

As 20 referências de `teste_ids` não foram vetorizadas, usadas como vizinhas, inferidas ou avaliadas neste módulo. A preparação dos embeddings recebeu somente os textos das 80 referências de desenvolvimento, das 559 questões sem rótulo e dos temas ativos de nível maior que zero. Ela não recebe rótulos de questões nem resultados de classificadores.

O codificador semântico permanece fixo, sem ajuste com o corpus do case. O cache pode ser compartilhado entre as validações internas porque a transformação de cada texto independe dos rótulos e dos demais textos. Já o vocabulário e o IDF lexical continuam ajustados por partição, usando catálogo e textos do respectivo treino. O acesso ao cache completo não autoriza incluir questões de validação entre os vizinhos de treinamento.

IDs servem a joins, rastreabilidade e bloqueio de ressubstituição. Disciplina, assunto de origem, coorte e classificações de IA da primeira etapa não são atributos nem referências de avaliação.

O código novo fica em `classificacao_experimentos/`, e as configurações, em `config/modulo3/`. Os pacotes, configurações e produtos dos módulos 1 e 2 permanecem preservados. O experimento novo não reescreve os resultados anteriores.

## Grade de sete receitas

A ordem abaixo define a prioridade fixa de desempate. `L` representa a similaridade lexical entre questão e tema, `S` o cosseno dos embeddings, `E_L` o apoio dos exemplos lexicais do módulo 2 e `E_S` o apoio dos exemplos semânticos. `J` é o sinal de citações do módulo 2. `H` é a fusão por posições definida na seção seguinte.

| Prioridade | Receita | Escore dos candidatos |
|---|---|---|
| 0 | `lexical_catalogo` | `L` |
| 1 | `lexical_m2` | `0,70 L + 0,30 E_L` |
| 2 | `lexical_leis_m2` | `0,60 L + 0,30 E_L + 0,10 J` |
| 3 | `semantico_catalogo` | `S`, sem exemplos |
| 4 | `hibrido_catalogo` | `H`, sem exemplos |
| 5 | `hibrido_exemplos_lexicais` | `0,70 H + 0,30 E_L` |
| 6 | `hibrido_exemplos_semanticos` | `0,70 H + 0,30 E_S` |

Os pesos e a prioridade foram definidos antes da primeira medição M3. Não houve busca adicional de pesos, normalizações, quantidade de vizinhos ou tamanho de segmentos com base nesses resultados.

As receitas lexicais mantêm a implementação e os campos do módulo 2. As três primeiras usam pesos de catálogo, exemplos e leis de `1/0/0`, `0,7/0,3/0` e `0,6/0,3/0`, respectivamente. O texto lexical continua ponderando enunciado e comando por 2, alternativas por 1, título por 3, caminho e descrição por 1.

Todas as receitas consideram apenas temas ativos com nível maior que zero. Não há promoção automática a um ancestral genérico para explorar a tolerância hierárquica. Empates entre candidatos recebem ordenação estável pelo ID do tema.

### Fusão por posições

A distribuição dos cossenos semânticos difere da distribuição do TF-IDF. Por isso, as receitas híbridas combinam posições no ranking, sem somar diretamente esses dois tipos de cosseno. Para posições iniciadas em 1, a contribuição de um ranking será:

```text
r(rank) = (k + 1) / (k + rank), com k = 20
H(tema) = 0,5 × r(rank_lexical) + 0,5 × r(rank_semantico)
```

A normalização deixa a contribuição da primeira posição igual a 1 e fixa a escala usada na combinação com exemplos. O fator `k + 1` não muda a ordenação do catálogo híbrido isolado, mas afeta sua contribuição relativa quando combinado com apoio humano; por isso ele também faz parte da configuração congelada.

O método se inspira na fusão recíproca de posições de [Cormack, Clarke e Büttcher](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf). O artigo usa `k = 60`; `k = 20`, os pesos e a normalização deste projeto são decisões de engenharia prévias à medição M3. Não são parâmetros validados pelo artigo para este case. Não serão comparadas múltiplas normalizações.

### Apoio de exemplos humanos

O apoio lexical `E_L` mantém a regra do módulo 2. O apoio semântico `E_S` usa os três vizinhos de treino com maior similaridade positiva entre embeddings de questões. Ambos normalizam o quadrado das similaridades pela soma dos quadrados dos vizinhos selecionados. O tema central humano recebe peso 1 e cada extra recebe peso 0,5, respeitando o limite de apoio 1 por candidato. Exemplos `fora` participam do denominador e do sinal separado `apoio_fora`; não fornecem tema.

As questões de treino e de consulta usam o mesmo prefixo semântico `query: `; temas do catálogo usam `passage: `. Não se calcula apoio de vizinhos por consulta a um modelo: depois da preparação, ele é uma operação numérica sobre os vetores em cache.

A normalização dos vizinhos pode produzir apoio elevado mesmo quando todas as similaridades são fracas. Devem permanecer disponíveis os componentes do escore, a margem, as similaridades dos vizinhos e o apoio `fora`. Esses sinais são diagnósticos para a futura política do módulo 4; apoio alto não equivale a probabilidade alta de acerto.

## Preparação semântica fixada

Foi usado o modelo `intfloat/multilingual-e5-small`, revisão `614241f622f53c4eeff9890bdc4f31cfecc418b3`, em FP32, executado localmente. O [cartão oficial dessa revisão](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md) documenta embeddings de 384 dimensões, prefixos de consulta e passagem, média dos tokens com máscara de atenção e normalização L2. Também alerta para o limite de 512 tokens e para cossenos frequentemente elevados; esses valores não representam confiança de classificação.

O procedimento pré-registrado e executado foi:

1. Montar o texto da questão com enunciado, comando e valores das alternativas em ordem estável. Montar o texto do tema com título, caminho e descrição. Cada campo aparece uma vez na representação semântica, sem a repetição usada nos pesos lexicais.
2. Usar `query: ` para questões e `passage: ` para temas, inclusive em português.
3. Dividir o conteúdo em segmentos de até 480 tokens, com sobreposição de 32 tokens. Repetir o prefixo em cada segmento e respeitar o limite de 512 tokens, incluindo prefixo e tokens especiais. Registrar quantidade de tokens e segmentos para auditoria.
4. Executar o codificador FP32 local e calcular a média dos estados dos tokens cuja máscara de atenção é válida, seguida de normalização L2 de cada segmento.
5. Calcular a média dos vetores dos segmentos, normalizar novamente em L2 e arredondar cada coordenada para oito casas decimais ao persistir o vetor.

A segmentação e a agregação de segmentos são escolhas deste projeto, não uma promessa do modelo de preservar integralmente o significado de textos longos. O arredondamento fixa a representação persistida; não garante que a regeneração do codificador em qualquer hardware produza bytes idênticos.

Não houve finetuning, geração de temas, enriquecimento de descrições por LLM, votação ou validação jurídica por IA. O modelo somente transforma texto em vetor antes da decisão. A classificação usa os vetores persistidos e código local.

As dependências apenas para preparação são `onnxruntime==1.31.0`, `tokenizers==0.23.3` e `numpy==2.5.4`, em ambiente `.venv` separado. A classificação e a verificação a partir do cache usam a biblioteca padrão do Python. O download dos arquivos públicos do modelo requer rede na preparação inicial; não há API de inferência nem custo de API. Tempo e armazenamento locais estão registrados no fechamento, sem tratá-los como recursos gratuitos ou ilimitados.

## Cache e rastreabilidade

O cache fica em `artefatos/embeddings-e5-v1/`. Seu [manifesto](../artefatos/embeddings-e5-v1/manifesto.json) registra modelo, revisão, arquivos de origem e respectivos hashes, dimensão, precisão numérica, parâmetros de tokenização e segmentação, prefixos, agregação, arredondamento e contexto de preparação.

Cada vetor deve estar vinculado ao hash do texto efetivamente processado e à configuração usada. A validação deve conferir IDs esperados, ausência dos 20 reservados, cobertura, dimensão, valores finitos e integridade dos arquivos. Cache ausente, incompleto, incompatível ou adulterado deve causar erro; não pode disparar silenciosamente uma chamada de preparação ou de rede.

O [manifesto do experimento](../artefatos/melhorias-v1/manifesto.json) relaciona fontes oficiais, preparação M1, implementação e configuração M3, cache e produtos. A reprodução da classificação a partir do cache persistido é verificada separadamente da regeneração dos embeddings a partir do modelo.

## Medição, seleção e artefatos

As sete receitas foram executadas nas mesmas três partições internas. Foram produzidas 560 predições de desenvolvimento: uma por questão e receita, sem ressubstituição. A avaliação compara IDs e relações da árvore por código, usando exclusivamente a folha-verdade humana.

A seleção seguiu a ordem pré-registrada:

1. Maior número de acertos do primeiro candidato pelo critério de ramo.
2. Maior número de acertos pelo critério exato.
3. Menor prioridade na tabela de receitas.

As métricas registram os mesmos critérios de ramo, parentesco imediato e exato do M2, além de top5, denominadores e suporte dos subconjuntos. Os grupos dentro/fora, tema central visto/não visto no treino e disciplina ajudam a descrever limitações; não alteram o critério de seleção. A comparação com M2 apresenta contagens e a diferença observada, sem confundir uma diferença exploratória com melhoria comprovada em dados novos.

A receita vencedora foi ajustada nas 80 referências, persistida em JSON e usada para gerar 559 sugestões intermediárias. As demais receitas e seus resultados de desenvolvimento, inclusive negativos, ficam registrados. Não há CSV final, confiança calibrada ou decisão automática de publicação neste módulo.

Comandos disponíveis, executados na pasta `etapa-complementar/`, após a preparação do cache:

```powershell
python -B -m classificacao_experimentos experimentar --saida artefatos/melhorias-v1
python -B -m classificacao_experimentos verificar --saida artefatos/melhorias-v1
```

Para gerar o cache a partir dos textos em um diretório novo, no ambiente de preparação registrado:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --only-binary=:all: -r requirements-preparacao.lock.txt
python -B -m classificacao_experimentos baixar-modelo
.venv/Scripts/python.exe -B -m classificacao_experimentos preparar-embeddings --saida tmp/embeddings-regerados
```

O arquivo `requirements-preparacao.lock.txt` fixa também as dependências transitivas observadas. A etapa de download verifica tamanho e SHA-256 dos dois arquivos públicos. Os pesos ficam em `.cache-modelos/`, ignorada pelo Git; o ambiente `.venv/` também não é versionado. O cache versionado permite executar a classificação sem instalar essas bibliotecas ou baixar os pesos.

O comando de preparação reutiliza um cache existente somente se seus arquivos e a procedência corresponderem ao registro. Resultados divergentes não podem sobrescrever silenciosamente um experimento existente; uma mudança exige nova configuração e outro diretório de saída. Execute somente um processo por diretório de saída.

## Validação e limites para o módulo 4

Foram aprovados 50 novos testes: 13 da preparação, 17 do motor, 15 do experimento e 5 do cache. Eles cobrem separação de treino e validação, exclusão da reserva, uso de rótulos e extras, seleção e empates, cálculo da fusão, persistência do modelo e recusa de cache inconsistente. Os testes sintéticos incluem execução em processo limpo com rede e imports de dependências do codificador bloqueados.

A auditoria estrutural dos produtos reais conferiu 560 predições fora da amostra, 559 sugestões com IDs únicos, ausência dos 20 reservados, 5.595 candidatos válidos, 3.117 referências a vizinhos pertencentes ao treino correspondente e 36 assinaturas. Esses controles demonstram integridade e respeito ao protocolo; não acrescentam uma validação jurídica das classificações.

A preparação real terminou em 316,514 segundos e o experimento em 274,690 segundos. A reprodução integral dos produtos reais terminou com código de saída zero em 353,387 segundos; os sete arquivos coincidiram byte a byte. Um mecanismo de auditoria do Python bloqueou rede, leitura de `.env`, acesso aos pesos e imports das dependências do codificador durante essa conferência. As evidências de execução estão reunidas no [checkpoint do módulo 3](../artefatos/checkpoints/modulo3.json).

O resultado selecionado continua sendo uma estimativa exploratória: as 80 referências orientam a engenharia e a escolha da receita. A reserva final de 20 deve permanecer fechada até o congelamento do classificador, calibrador, política e procedimento de reajuste do módulo 4. Ela é pequena, e mesmo 20 acertos em 20 não demonstram precisão mínima de 95% com um limite inferior de confiança de 95%.

Similaridade semântica, posição na fusão e concordância entre vizinhos não são probabilidades calibradas. Os seis exemplos `fora` do desenvolvimento também oferecem pouco suporte para uma regra independente de exclusão. As 300 questões recentes não têm referência humana disponível, portanto uma melhora nas referências antigas não mede diretamente a precisão nesse grupo.

## Resultados e ponto de retomada

Os números abaixo vêm das [métricas agregadas do experimento](../artefatos/melhorias-v1/metricas_desenvolvimento.json). Todos usam as mesmas 80 referências, incluindo os seis casos `fora`. O critério de parentesco imediato produziu as mesmas contagens do critério de ramo nesta comparação.

| Receita | Acertos por ramo | Taxa por ramo | Acertos exatos | Tema aceitável no top5 |
|---|---:|---:|---:|---:|
| `lexical_catalogo` | 34/80 | 42,50% | 18/80 | 56/80 |
| `lexical_m2` | 31/80 | 38,75% | 18/80 | 57/80 |
| `lexical_leis_m2` | 31/80 | 38,75% | 18/80 | 54/80 |
| `semantico_catalogo` | 21/80 | 26,25% | 16/80 | 34/80 |
| **`hibrido_catalogo`** | **37/80** | **46,25%** | **24/80** | **54/80** |
| `hibrido_exemplos_lexicais` | 36/80 | 45,00% | 24/80 | 59/80 |
| `hibrido_exemplos_semanticos` | 37/80 | 46,25% | 24/80 | 54/80 |

A receita `hibrido_catalogo` empatou com `hibrido_exemplos_semanticos` em acertos por ramo e exatos, vencendo pela prioridade previamente fixada. O apoio de exemplos semânticos não melhorou essas métricas agregadas. A vencedora combina rankings do catálogo e não usa rótulos de vizinhos no escore; as referências humanas continuam essenciais à comparação e seleção, e os textos de treino continuam participando do IDF lexical.

O ganho observado sobre a referência lexical M2 foi de seis acertos em 80, ou 7,50 pontos percentuais, tanto por ramo quanto pelo critério exato. Parte da diferença já aparece ao retirar o apoio dos exemplos: o catálogo lexical isolado chega a 34/80. A vencedora supera essa ablação em três acertos por ramo. Esses resultados não isolam uma garantia geral de ganho por embeddings; o semântico isolado teve o pior resultado, com 21/80.

A melhora do primeiro candidato também não implica melhora do top5. A vencedora passou de 57/80 da referência M2 para 54/80 no top5. O híbrido com exemplos lexicais atingiu o maior top5, 59/80, mas acertou um caso a menos no primeiro candidato. O critério de seleção permaneceu o primeiro candidato, sem ser alterado para favorecer outra receita depois da medição.

| Subconjunto dentro da taxonomia | Referência lexical M2 | Híbrido de catálogo selecionado |
|---|---:|---:|
| Central humano visto no treino interno | 17/27 | 11/27 |
| Central humano não visto no treino interno | 14/47 | 26/47 |

A comparação mostra ganhos e perdas entre os subconjuntos: o total melhora porque o aumento entre temas centrais não vistos supera a redução entre os vistos. A presença de um tema no treino é um diagnóstico calculado pelo avaliador; não autoriza consultar o rótulo verdadeiro para decidir qual receita usar em uma questão nova.

Dentro da taxonomia, a vencedora acertou 37/74 (50,00%). Os seis casos `fora` não recebem acerto de tema, permanecendo no denominador geral. A distribuição por disciplina foi 5/8 em Criminologia, 3/10 em Direito Penal — Legislação Especial, 15/32 em Penal e 14/24 em Processo Penal. Esses grupos têm suporte pequeno e não justificam calibradores ou limiares separados por disciplina.

Na curva diagnóstica, escore igual ou superior a `0,95` reteve 23 referências, das quais 17 corretas por ramo (73,91%). Portanto, `0,95` de escore RRF não significa 95% de chance de acerto. A curva não estabelece uma política de publicação; a meta de precisão não foi demonstrada neste módulo.

### Preparação, custo e produtos observados

O cache contém 639 questões (80 de desenvolvimento e 559 sem rótulo) e 371 temas elegíveis: 1.010 registros com vetores de 384 dimensões. Foram processadas 1.032 janelas; 21 registros precisaram de mais de uma janela, sem truncamento de conteúdo registrado. Os 20 reservados não têm vetores nesse cache.

O arquivo `vetores.json` ocupa 8.085.275 bytes. Os arquivos de preparação baixados somam 487.351.240 bytes: 470.268.510 de `modelo.onnx` e 17.082.730 de `tokenizer.json`. Esses arquivos permanecem ignorados pelo Git; o download pode ser refeito a partir das origens e dos hashes fixados. O modelo é disponibilizado sob licença MIT.

Não houve chamada de API de inferência nem cobrança por API. O ambiente registrado é CPython 3.14.7, Windows AMD64, com execução do codificador em CPU, quatro threads e lotes de oito janelas. Os tempos de preparação e experimento refletem essa execução local, não uma medição de capacidade de produção.

Foram preservadas as 560 predições de desenvolvimento, as métricas de todas as receitas, 559 sugestões da vencedora, seu modelo em JSON e a [receita congelada para o módulo 4](../artefatos/melhorias-v1/receita_congelada.json), além do protocolo e manifesto. As referências lexicais M2 foram conferidas automaticamente contra suas predições anteriores, incluindo tema, escore, margem, critérios de acerto e ranking.

A próxima etapa é o módulo 4: calibrar a receita selecionada, definir suporte mínimo e política de publicação, revisão e `fora` usando somente o desenvolvimento. O classificador foi congelado para essa etapa; calibrador e política ainda não estão congelados. A reserva permanece fechada até esse procedimento completo ser definido.
