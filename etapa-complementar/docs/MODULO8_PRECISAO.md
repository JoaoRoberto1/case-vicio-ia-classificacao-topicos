# Módulo 8 - Sinais específicos, confiança e comparação do E5-large

Estado: **pausado a pedido do usuário em 21/10/2026**. Comparação parcial concluída; preparação do E5-large interrompida com checkpoints locais preservados. A entrega final ainda depende da comparação completa e da reprodução. Consulte [retomada segura](RETOMADA_MODULO8.md) antes de continuar.

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

Os [sete produtos parciais](../artefatos/precisao-m8-small-v1/manifesto.json) não consultam os rótulos das 20 para escolha e não exportam as 559. O objetivo desse pacote é registrar a comparação small enquanto a representação maior é preparada.

## Preparação local do modelo maior

O E5-large é a variante INT8 publicada no repositório oficial, revisão `3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3`, licença MIT. O modelo ONNX tem 561.845.741 bytes; tokenizer e pesos têm SHA-256 fixados. As dependências opcionais e a configuração estão em [embeddings_large.json](../config/modulo8/embeddings_large.json).

O notebook possui Intel i7-7600U, AVX2, sem AVX512/VNNI, e cerca de 12 GB de RAM compartilhada com os aplicativos. O arquivo oficial quantizado tem AVX512/VNNI no nome, mas o ONNX Runtime o executa em AVX2. Essa combinação pode sofrer saturação U8S8; não se declara equivalência ao FP32 nem ganho de classificação sem medir.

O primeiro lote interrompeu por pressão de memória. Desativar a arena e o padrão de memória do ONNX reduziu a retenção, preservando byte a byte os dez vetores do piloto. O lote final usa batch 1 e duas threads; verifica disponibilidade de RAM e comprometimento. Checkpoints por registro, autenticados por entradas, configuração e implementação, permitem retomar. Nenhum aplicativo foi encerrado e a configuração do sistema não foi alterada.

A escolha dos dez registros do piloto depende somente do hash de tipo/ID. Os textos e rótulos não foram usados para escolhê-los. Dez vetores distintos e cossenos não constantes afastam colapso trivial no piloto; não demonstram qualidade temática ou ausência de saturação.

## Comandos de retomada

Na pasta `etapa-complementar`, a comparação parcial é reproduzida sem dependências de IA:

```console
python -E -X utf8 -B -S -m classificacao_precisao verificar --small
```

Somente a preparação exige o ambiente opcional e os pesos locais. **Antes de executar, resolver a divergência de procedência do protocolo registrada na [retomada segura](RETOMADA_MODULO8.md); o checkpoint preservado tem 594 registros, mas atualmente bloqueia a retomada por identidade divergente.** Não iniciar uma segunda preparação enquanto outra estiver em andamento:

```console
.venv/Scripts/python.exe -E -X utf8 -B -m classificacao_precisao.preparar_large preparar
```

Quando o cache completo estiver pronto, o comando de entrega refaz a grade completa e gera CSV/previsão. O verificador opera em cópia permitida; o benchmark mede somente a aplicação do modelo já ajustado:

```console
python -E -X utf8 -B -S scripts/entregar_precisao.py
python -E -X utf8 -B -S scripts/verificar_precisao.py
python -E -X utf8 -B -S scripts/medir_precisao.py --evidencia artefatos/checkpoints/benchmark_modulo8.json
```

Os destinos de evidência devem ser novos. Pesos, checkpoints transitórios e ambientes virtuais permanecem ignorados pelo Git. Os vetores numéricos e a procedência que sustentam a decisão integram o repositório.

## Verificações já concluídas

A suíte completa passou com 482 testes. Os testes novos cobrem sinais, integridade vetorial, calibração, exclusão de rótulos externos, exportação das 659 linhas, isolamento da reprodução e benchmark sem encoder. Essa verificação avalia software, não a precisão nas 559 questões sem rótulos disponíveis.

A comparação completa, o benchmark real, a reprodução isolada, o PDF final e o checkpoint de fechamento ainda precisam ser concluídos antes de tratar a pasta `entrega-final-v2` como entrega pronta.
