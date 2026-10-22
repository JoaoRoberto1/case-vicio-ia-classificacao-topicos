# Módulo 8 - Sinais específicos, confiança e comparação do E5-large

Estado em 22/10/2026: **preparação e comparação completa concluídas; política final desabilitada por suporte externo insuficiente**. A receita selecionada foi `sinais_large`; o CSV contém 659 sugestões para revisão, com zero publicações entre as 559 questões de avaliação. A meta de precisão de 95% para publicação não foi demonstrada. Benchmark, reprodução isolada e fechamento documental têm evidências próprias. Consulte o [registro de retomada](RETOMADA_MODULO8.md).

## Protocolo e separação da decisão

A grade está fixada em [protocolo.json](../config/modulo8/protocolo.json), SHA-256 `4ac9d655cf825b98bfc5b2151466e618637fd7d906deeaf0de6e3cd5730ba115`, antes da primeira métrica M8. São seis receitas: M7 preservado, sinais com E5-small, a variante small hierárquica, fusão RRF com E5-large, sinais com large e a variante large hierárquica.

Os módulos 1 a 7 mantêm seus arquivos e hashes. A grade não foi ampliada depois do resultado parcial. O LLM preparou dados do catálogo e código; não escolheu, votou ou validou temas de questões avaliadas. As classificações anteriores de IA e as do concorrente não foram usadas como rótulos.

O programa de decisão usa biblioteca padrão do Python e vetores em JSON. A preparação do encoder é um comando separado; a reprodução bloqueia rede, `.env`, pesos e importação de bibliotecas de modelos.

## Sinais e catálogo

Os seis atributos acrescentados ao ranking M7 são: sobreposição de instrumentos normativos no corpo, pares artigo/instrumento, cobertura de termos distintivos no corpo, cobertura nas alternativas, cobertura do título no corpo e evidência de norma única. Termos e IDF vêm somente do catálogo. Campos de origem e gabaritos são ignorados.

As [âncoras normativas](../config/modulo8/ancoras_normativas.json) têm 88 registros para 87 temas, com fontes oficiais e notas. Foram elaboradas a partir da taxonomia e legislação, sem consultar questões ou rótulos. O conjunto final oferece instrumentos para 94 dos 371 temas e pares artigo/instrumento para 53. Há 3.453 unidades lexicais distintas. Recortes Parte 1/2 não receberam fronteiras inventadas; referências ambíguas não viram evidência positiva.

O ranking aprendido mantém a perda por pares, normalização apenas no treino, regularização e parâmetros do M7; as variantes novas têm 14 atributos. A representação large substitui o cosseno semântico enriquecido e os atributos de posição/interação derivados dele. O cosseno do catálogo original small permanece nas variantes aprendidas. Na fusão RRF, a ordenação depende apenas das posições lexical e large, com pesos iguais e k=20.

## Confiança e política

A confiança estima acerto pelo critério de ramo usando nove atributos: escore, margem, cossenos lexical/semântico, concordância dos primeiros candidatos, evidência específica, acordo estrutural dos cinco primeiros e margens lexical/semântica. A logística usa normalização do treino, regularização L2=1 sobre soma das perdas, duas pseudo-observações de peso 0,5 no centro e otimização de Newton. Escore de ranking e taxa empírica do grupo não são apresentados como probabilidades individuais.

A seleção compara 18 regras por receita: nove cortes/concordâncias do M7, seis cortes fixos de confiança e três conjunções de evidências. Uma candidata exige pelo menos dez casos e 95% de precisão observada. Entre candidatas elegíveis, vence a maior cobertura, seguida pelos desempates registrados. Sem candidata, escolhe-se a melhor sugestão global para revisão.

Em cada bloco externo das 80 referências, somente seus exemplos de treino chegam à seleção interna e ao ajuste da confiança. A regra e o calibrador são aplicados ao bloco externo antes de medir seu resultado. Publicação final ainda exige pelo menos dez publicações externas e 95% de precisão externa observada. Esse critério não certifica precisão populacional.

O cross-fit interno da confiança utiliza predições OOF cujos rankers compartilham conjuntos de treino. Ele serve à seleção interna; não é um teste independente. O bloco externo completo fica fora dos ajustes desta grade. A reutilização histórica das 80 referências continua sendo uma limitação, e as outras 20 já eram conhecidas. Não existe novo holdout independente.

## Resultado parcial com E5-small

| Receita | Acerto por ramo | Exato | Top 5 |
|---|---:|---:|---:|
| M7 preservado | 54/80 | 42/80 | 66/80 |
| Small + sinais | 53/80 | 38/80 | 66/80 |
| Small + sinais + hierarquia | 54/80 | 38/80 | 66/80 |

O M7 foi reproduzido exatamente, incluindo escores e candidatos. Os novos sinais não o superaram nessa comparação. A seleção aninhada parcial acertou 54/80 e não publicou nenhuma questão.

A confiança externa teve Brier 0,189694, contra 0,225916 da constante ajustada dentro de cada treino externo. A melhoria nessa perda não equivale a atingir a meta de publicação. O melhor grupo exploratório com suporte de pelo menos dez teve 16 acertos em 17 casos (94,12%), no corte de confiança de 0,90 do M7. Nenhuma regra atingiu 95% com o suporte exigido.

Os [sete arquivos parciais](../artefatos/precisao-m8-small-v1/manifesto.json) não consultam os rótulos das 20 para escolha e não exportam as 559. Esse pacote histórico registra a comparação small realizada antes da conclusão da representação maior.

Esses produtos correspondem à fonte original do commit `043b14e4e67ed2d8ee894c5d0a1eac25ac337687`. A fonte de `classificacao_precisao/experimento.py` foi preservada em [precisao-m8-small-fontes-v1](../artefatos/precisao-m8-small-fontes-v1/registro.json), com SHA-256 `5c29dcdb149a5a07e38acb6c1004b947d0b2b2e437b5f40d34c5491322c03a5f`.

Na execução completa, o diagnóstico das 20 referências conhecidas exigiu corrigir a leitura de um arquivo histórico M7: sua extensão é `.jsonl`, mas o produtor gravou um array JSON indentado. A correção adapta somente esse parser, depois da seleção. Não muda receitas, protocolo, calibração, escolha ou política de publicação. Os manifestos e resultados parciais foram preservados; a fonte corrigida possui sua própria assinatura.

## Resultado da comparação completa

A execução completa durou 822,052 segundos e gerou [12 arquivos do experimento](../artefatos/precisao-m8-v1/manifesto.json), incluindo o manifesto que assina 11 produtos. A exportação gerou `publicacao.csv`, `previsao.txt` e `previsao.json`. Esse tempo inclui comparação e ajuste; não é o benchmark de aplicar o classificador já ajustado.

Os resultados OOF de cada receita nas 80 referências de desenvolvimento são:

| Receita | Acerto por ramo | Exato | Top 5 |
|---|---:|---:|---:|
| M7 preservado | 54/80 | 42/80 | 66/80 |
| Small + sinais | 53/80 | 38/80 | 66/80 |
| Small + sinais + hierarquia | 54/80 | 38/80 | 66/80 |
| Large + RRF, k=20 | 50/80 | 35/80 | 68/80 |
| Large + sinais | 53/80 | 39/80 | 67/80 |
| Large + sinais + hierarquia | 54/80 | 38/80 | 67/80 |

Duas regras internas tiveram 14 acertos em 14 casos: `large_rrf20` com confiança ≥ 0,95 e `sinais_large` com confiança ≥ 0,90. Empataram em cobertura e precisão internas; `sinais_large` venceu pelo desempate de acerto global, 53/80 contra 50/80. O M7 acertou 54/80, mas não tinha regra de publicação elegível. Essa seleção segue a prioridade previamente fixada de cobertura com precisão e suporte mínimos; não indica melhora de acerto global sobre o M7.

Na avaliação externa aninhada, o **procedimento de seleção** acertou 54/80 por ramo, 43/80 exatos e 66/80 no top 5. As escolhas variaram: os blocos 1 e 2 usaram `baseline_m7`, sem publicação; o bloco 3 usou `large_rrf20`, que produziu as quatro candidatas externas. Portanto, **54/80 e 4/4 não são uma validação externa direta da receita final `sinais_large`**.

As candidatas externas cobriram 4/80 = 5%, com quatro acertos e Wilson de 95% entre 51,01% e 100%. O grupo tem menos que os dez casos exigidos pelo protocolo; a política final foi desabilitada. O intervalo é descritivo e não elimina a reutilização histórica das referências. Os 14/14 internos não substituem esse suporte externo.

A confiança externa teve Brier 0,207372, contra 0,220957 da constante ajustada por treino externo. O ECE foi 0,085172, contra 0,033977 da constante: houve melhora de Brier, mas não de ECE. Nenhuma dessas métricas comprova precisão populacional de 95%.

Nas [20 referências já conhecidas](../artefatos/precisao-m8-v1/diagnostico_reserva_conhecida.json), `sinais_large` obteve 13/20 por ramo, 8/20 exatos e 17/20 no top 5. Esse diagnóstico foi executado depois da seleção; não é um novo teste independente. As 559 sugestões finais usam ranking reajustado com as 100 referências, sem novo teste independente desse reajuste.

O [CSV final](../entrega-final-v2/publicacao.csv) contém 659 linhas, todas com decisão `revisar`: 80 sugestões externas, 20 do diagnóstico conhecido e 559 do ajuste com 100 referências. O bloqueio final também se aplica às quatro candidatas externas, por isso elas não aparecem como publicações no CSV. Nas 559 questões, a cobertura final é **0/559 = 0%**, e a precisão entre publicadas é **indefinida**, registrada como `null` na [previsão JSON](../entrega-final-v2/previsao.json). O zero no campo numérico correspondente do TXT é uma sentinela de ausência de previsão, não uma precisão medida. Não há rótulos disponíveis para medir acerto nessas 559 questões.

## Preparação local do modelo maior

O E5-large é a variante INT8 publicada no repositório oficial, revisão `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3`, licença MIT. O modelo ONNX tem 561.845.741 bytes; tokenizer e pesos têm SHA-256 fixados. As dependências opcionais e a configuração estão em [embeddings_large.json](../config/modulo8/embeddings_large.json).

O notebook possui Intel i7-7600U, AVX2, sem AVX512/VNNI, e cerca de 12 GB de RAM compartilhada com os aplicativos. O arquivo oficial quantizado tem AVX512/VNNI no nome, mas o ONNX Runtime o executa em AVX2. Essa combinação pode sofrer saturação U8S8; não se declara equivalência ao FP32 nem ganho de classificação sem medir.

O primeiro lote interrompeu por pressão de memória. Desativar a arena e o padrão de memória do ONNX reduziu a retenção, preservando byte a byte os dez vetores do piloto. O lote final usa batch 1 e duas threads; verifica disponibilidade de RAM e comprometimento. Checkpoints por registro, autenticados por entradas, configuração e implementação, permitem retomar. Nenhum aplicativo foi encerrado e a configuração do sistema não foi alterada.

A escolha dos dez registros do piloto depende somente do hash de tipo/ID. Os textos e rótulos não foram usados para escolhê-los. Dez vetores distintos e cossenos não constantes afastam colapso trivial no piloto; não demonstram qualidade temática ou ausência de saturação.

O snapshot em `piloto/fontes/` foi capturado depois da alteração de preparação e não corresponde às fontes registradas no manifesto do primeiro piloto. Esse piloto não é apresentado como reprodução integralmente recuperável. Seus manifestos foram preservados, e `piloto_memoria/` registra a implementação e a configuração usadas no cache completo. A [nota de procedência](../artefatos/embeddings-e5-large-m8/PROCEDENCIA_PILOTOS.md) detalha a limitação.

Na pausa de 21/10, havia 594 vetores autenticados. A [migração de 22/10](../artefatos/embeddings-e5-large-m8/migracao-protocolo-v1/manifesto.json) corrigiu exclusivamente a referência do protocolo no índice: esse arquivo integra a procedência, mas não participa da construção dos textos, tokenização, inferência ou agregação. Entradas, configuração e demais fontes permaneceram idênticas. Os índices anterior e posterior foram preservados; hash, texto, dimensão, finitude, norma L2, tokens e janelas dos 594 registros foram conferidos.

A primeira retomada gerou 257 registros e parou pela guarda de memória com 851 registros salvos, durante execução concorrente da suíte de testes na fase de temas. Após a suíte encerrar, a segunda retomada reutilizou os 851 e gerou os 179 temas restantes. A [auditoria final](../artefatos/embeddings-e5-large-m8/retomada-v2/conclusao.json) confirmou os 1.030 vetores de 1.024 dimensões, 1.053 janelas, nenhum truncamento e preservação dos índices de 594 e 851 registros. SHA-256 do cache: `ccc440ce7edb031a03bdd16b235aa394d02be3505907e527f5cdaef1399dd74c`.

O [tempo da última execução](../artefatos/embeddings-e5-large-m8/execucao.json), **161,044 segundos**, cobre a leitura/verificação de 851 registros e a geração de 179 temas. Não representa o custo integral dos 1.030 registros. As execuções interrompidas não possuem duração completa recuperada.

A [medição parcial das questões](../artefatos/embeddings-e5-large-m8/retomada-v1/tempo_questoes.json) contém 65 timestamps que delimitam **64 intervalos, 67 janelas e 331,27124 segundos**. O primeiro registro apenas delimita o início; sua geração fica fora do denominador. O bloco terminou antes da suíte e da interrupção, exclui temas, carga do modelo e os 594 registros reutilizados. É uma amostra contígua em host compartilhado, medida por timestamps de arquivos; não certifica representatividade de uma carga de 50 mil questões.

## Tempo da aplicação offline

O [benchmark M8](../artefatos/checkpoints/benchmark_modulo8.json) aplicou o modelo já ajustado às 559 questões e reproduziu exatamente as predições salvas. A medição separa carga, aplicação e duração total da execução:

| Componente | Segundos |
|---|---:|
| Carga | 23,471 |
| Aplicação das 559 decisões | 330,730 |
| Execução total, incluindo verificações | 358,880 |

A extrapolação linear da aplicação para 50 mil questões é **8,2173 horas**, no mesmo hardware e sob hipótese de carga comparável. É uma estimativa somente da decisão com vetores prontos; não inclui geração de embeddings Small/Large, ajuste do ranking, seleção, revisão humana ou operação completa. O catálogo, a distribuição dos textos e a concorrência do host podem mudar o tempo observado. Os 822,052 segundos da comparação completa e os 161,044 segundos da última retomada do encoder medem operações distintas e não devem ser usados como tempo de inferência dessas 559 questões.

## Comandos de retomada

Para conferir os hashes do pacote parcial, use um checkout separado do commit `043b14e4e67ed2d8ee894c5d0a1eac25ac337687`. Na pasta `etapa-complementar` desse checkout, execute sem dependências de IA:

```console
python -E -X utf8 -B -S -m classificacao_precisao verificar --small
```

A fonte atual tem outra assinatura por causa da correção do parser; a reprodução do manifesto parcial exige a versão histórica. A cópia arquivada permite auditar a diferença sem substituir arquivos do checkout atual.

A preparação está concluída; não é preciso executar o encoder novamente para classificar ou reproduzir a decisão. O comando abaixo documenta a etapa opcional que exige ambiente e pesos locais:

```console
.venv/Scripts/python.exe -E -X utf8 -B -m classificacao_precisao.preparar_large preparar
```

Com o cache completo disponível, o comando de entrega refaz a grade e gera CSV/previsão; essa geração já foi concluída. O benchmark mede a aplicação do modelo ajustado e o verificador reproduz os produtos em cópia permitida:

```console
python -E -X utf8 -B -S scripts/entregar_precisao.py
python -E -X utf8 -B -S scripts/medir_precisao.py --evidencia tmp/benchmark-m8-conferencia.json
python -E -X utf8 -B -S scripts/verificar_precisao.py --evidencia tmp/verificacao-m8-conferencia.json
```

Os destinos de evidência devem ser novos; se os exemplos em `tmp/` já existirem, escolher outros nomes. As evidências oficiais em `artefatos/checkpoints/` não devem ser sobrescritas. O comando de entrega aceita produtos existentes quando seus bytes são idênticos. Pesos, checkpoints transitórios e ambientes virtuais permanecem ignorados pelo Git. Os vetores numéricos e a procedência que sustentam a decisão integram o repositório.

## Verificações já concluídas

A [suíte final](../artefatos/checkpoints/testes_modulo8.json) passou com **496 testes em 329,929 segundos** (333,585 segundos de parede), código de saída zero e fontes preservadas. Antes da correção do parser histórico, a suíte tinha 493 testes; os 17 testes direcionados da correção também passaram. As verificações cobrem sinais, integridade vetorial, calibração, exclusão de rótulos externos, exportação das 659 linhas, isolamento da reprodução, migração de procedência, medição de intervalos e benchmark sem encoder. Elas avaliam software, não a precisão nas 559 questões sem rótulos disponíveis.

A preparação, a comparação completa e a exportação foram concluídas. O resultado e o escopo da validação são registrados no [benchmark M8](../artefatos/checkpoints/benchmark_modulo8.json), na [reprodução M8](../artefatos/checkpoints/reproducao_modulo8.json) e no [checkpoint M8](../artefatos/checkpoints/modulo8.json). Esses registros permitem conferir as evidências da entrega e suas limitações, sem interpretar testes de software como certificação de precisão temática.
