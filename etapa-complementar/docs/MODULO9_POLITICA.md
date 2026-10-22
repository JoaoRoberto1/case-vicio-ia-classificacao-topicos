# Módulo 9 - Revisão da política de publicação

Estado em 22/10/2026: **experimento concluído; candidata não passou pelo critério operacional de estabilidade**. O procedimento externo aceitou nove casos e acertou os nove, com cobertura de 11,25% nas 80 referências, mas não publicou no terceiro bloco. A regra final candidata aceitaria 60/559 questões, ou 10,73%, com precisão desconhecida nesse lote. A [entrega M8](../entrega-final-v2/README.md) permanece preservada; sua cobertura oficial continua em zero.

## Problema e escopo

O M8 manteve a publicação desabilitada porque o procedimento externo aceitou quatro casos, todos corretos e concentrados em uma partição, abaixo do mínimo global de dez. Esse mínimo era uma escolha de implementação, não uma exigência do case nem uma certificação estatística de precisão. O M9 questiona essa escolha sem transformar os quatro acertos em prova de qualidade futura.

O objetivo é medir o que acontece ao selecionar filtros sem esse mínimo e exigir repetição do resultado entre os três blocos externos. O ranking principal, a representação dos textos, o encoder, os rótulos humanos e a logística de confiança do M8 permanecem os mesmos. O módulo não cria novos temas, não corrige classificações manualmente e não amplia a grade após observar os resultados.

Antes do registro M9, já eram conhecidos os resultados M1–M8, os 14/14 internos da regra M8 e o diagnóstico de retirar apenas sua trava: o corte de confiança de 0,90 aceitaria 60/559 questões sem rótulos; nas 20 referências conhecidas, aceitaria três com dois acertos. Essas observações motivaram o experimento e estão explicitadas no protocolo. O M9 não é apresentado como confirmação independente dessas hipóteses.

## Protocolo e filtros

O [protocolo M9](../config/modulo9/protocolo.json) foi registrado em **22/10/2026 às 17:08:17 UTC**, antes das novas métricas M9. Seu SHA-256 é `f686c64cce60d1c100d318946f1d0e23659557cfbb3b6e233d76c0c0596162cf`; a implementação recusa alterações nesse conteúdo.

Todas as sugestões usam a receita fixa `sinais_large`. A grade contém exatamente seis regras:

| Corte de confiança | Sem exigir concordância | Exigindo concordância exata |
|---|---|---|
| 0,80 | `confianca_p80` | `confianca_p80_concordancia` |
| 0,90 | `confianca_p90` | `confianca_p90_concordancia` |
| 0,95 | `confianca_p95` | `confianca_p95_concordancia` |

A concordância exige que `sinais_small`, `large_rrf20` e `sinais_large` sugiram exatamente o mesmo ID de tema. Dois votos em três ou uma relação de parentesco na taxonomia não bastam. São algoritmos numéricos locais sobre vetores já preparados; nenhum LLM escolhe, vota ou valida temas. Como esses algoritmos compartilham dados e sinais, sua concordância não é evidência independente de acerto.

Os cortes se aplicam à confiança estimada por questão. Já a condição de 95% na seleção se aplica à precisão observada do conjunto aceito. São quantidades distintas: um corte de 0,90 pode formar um grupo com precisão diferente de 90%.

## Seleção e separação dos dados

As coortes permanecem disjuntas: 80 referências de desenvolvimento, 20 referências historicamente conhecidas e 559 questões sem rótulos humanos disponíveis para avaliação.

1. Os rankings fora do treino das três receitas, produzidos pelo M8 nas 80 referências, são autenticados e reutilizados. A receita que fornece o tema permanece `sinais_large`.
2. Para cada um dos três blocos externos, o programa reconstitui três partições internas usando apenas o treino daquele bloco. O ajuste dos rankers internos não recebe os rótulos do bloco externo.
3. A seleção compara os seis filtros usando `confianca_oof` interna. Uma regra é elegível se aceitar pelo menos um caso e alcançar precisão observada de pelo menos 95%. Não há mínimo de dez.
4. Entre as regras elegíveis, a ordem é: maior número de aceitos, maior precisão, maior suporte mínimo entre partições internas, filtro sem exigência de concordância e maior corte. Partições sem publicação contam como suporte zero. Se nenhuma regra for elegível, o procedimento se abstém.
5. O calibrador externo é ajustado somente nas previsões internas reconstituídas. Sua nova `confianca` é aplicada ao ranking do bloco externo junto da regra já escolhida. A `confianca_oof` global não é usada como confiança externa.
6. A política candidata final é selecionada nas 80 previsões de desenvolvimento. As 20 referências conhecidas entram somente no diagnóstico posterior, e as 559 somente na aplicação e na contagem de cobertura. Esses resultados não retornam à seleção.

A confiança usa a mesma logística M8 de nove atributos, com normalização no treino, L2=1 e pseudocontagens. Não foram testados novos calibradores neste módulo. O segundo estágio OOF interno compartilha conjuntos de treino dos rankers e serve à seleção; não é um teste independente. A separação externa completa protege o ajuste da rodada atual, mas não apaga a reutilização histórica das referências.

## Critério de estabilidade

O procedimento recebe o indicador de aprovação experimental somente quando:

- existe publicação em cada um dos três blocos externos;
- a precisão observada é de pelo menos 95% em cada bloco com publicações;
- a precisão observada agregada também é de pelo menos 95%.

Essa é uma escolha operacional de repetibilidade, não uma garantia estatística. **Um acerto em um aceito em cada bloco, totalizando 3/3, já satisfaria o critério.** Por isso, contagens e intervalos de Wilson acompanham a avaliação; a aprovação experimental não autoriza declarar precisão populacional de 95% comprovada.

Os seis filtros também são medidos separadamente sobre as mesmas previsões externas. Essas curvas são diagnósticas: não se escolhe retrospectivamente uma alternativa que pareça melhor depois de o procedimento selecionado internamente falhar. O resultado externo descreve o procedimento de seleção de filtros; não valida diretamente apenas a regra única escolhida para a aplicação final.

## Resultados

Os [resultados registrados](../artefatos/politica-m9-v1/metricas.json) selecionaram `confianca_p90`, sem exigência de concordância. Na seleção interna global, essa regra teve **14/14 acertos**, com 17,50% de cobertura nas 80 referências. Esse resultado serve à escolha e não substitui a avaliação externa do procedimento.

O procedimento externo de seleção de filtros teve **9/9 acertos**, cobertura de **9/80 = 11,25%** e intervalo de Wilson de 95% entre **70,09% e 100%**:

| Bloco externo | Regra escolhida no treino interno | Acertos/aceitos internos dessa regra | Acertos/aceitos externos | Cobertura externa |
|---|---|---:|---:|---:|
| 1, com 27 referências | Confiança ≥ 0,90 | 8/8 | 6/6 | 22,22% |
| 2, com 27 referências | Confiança ≥ 0,95 | 5/5 | 3/3 | 11,11% |
| 3, com 26 referências | Abstenção: nenhuma regra elegível | Não se aplica | 0/0 | 0% |

No treino do terceiro bloco, a melhor precisão entre as seis regras foi **12/13 = 92,31%**, no corte de 0,80 com concordância. Como nenhuma regra interna atingiu 95%, o procedimento se absteve antes de consultar o resultado externo daquele bloco. O 0/0 externo tem precisão indefinida; não representa erros de classificação observados.

A única razão para reprovar o critério operacional de estabilidade foi a ausência de publicação no terceiro bloco. O agregado e os dois blocos que publicaram tiveram 100% de acerto observado. Exigir publicação nos três continua sendo uma escolha de projeto; a falha desse critério não demonstra que cobertura zero seja a solução ótima.

Na comparação histórica, o procedimento M8 tinha aceitado **4/80 = 5%**, com quatro acertos. O M9 aceitou **9/80 = 11,25%**, com nove acertos. Os procedimentos diferem: o M8 selecionava também a receita; o M9 fixa `sinais_large` e altera a seleção de filtros. A comparação não isola o efeito de remover o mínimo de dez nem demonstra melhoria do ranking.

### Curvas fixas: diagnóstico separado da seleção

Os seis filtros foram aplicados também às confianças externas calculadas com treinos internos reconstituídos. Essas medições não alteraram a política escolhida nem o resultado da avaliação do procedimento:

| Filtro fixo | Acertos/aceitos externos | Precisão externa observada | Cobertura externa em 80 | Aceitos nas 559 | Cobertura nas 559 |
|---|---:|---:|---:|---:|---:|
| Confiança ≥ 0,80 | 21/23 | 91,30% | 28,75% | 137 | 24,51% |
| Confiança ≥ 0,80 e concordância | 17/19 | 89,47% | 23,75% | 112 | 20,04% |
| Confiança ≥ 0,90 | 14/14 | 100% | 17,50% | 60 | 10,73% |
| Confiança ≥ 0,90 e concordância | 12/12 | 100% | 15,00% | 49 | 8,77% |
| Confiança ≥ 0,95 | 9/9 | 100% | 11,25% | 30 | 5,37% |
| Confiança ≥ 0,95 e concordância | 7/7 | 100% | 8,75% | 23 | 4,11% |

O filtro fixo de 0,90 teve **6/6, 4/4 e 4/4** nos três blocos, com Wilson agregado entre **78,47% e 100%**. Trata-se de uma medição externa da regra fixa nesta rodada, distinta dos 14/14 da seleção interna M8, apesar da mesma contagem. Também não é o resultado externo de 9/9 do procedimento adaptativo M9: esse procedimento escolheu outro corte no segundo bloco e abstenção no terceiro. Trocar o resultado principal por essa curva após observar os números violaria a separação registrada entre seleção e diagnóstico.

A concordância não produziu ganho demonstrado nesta grade. No corte de 0,80, reduziu a cobertura e a precisão observada; nos cortes de 0,90 e 0,95, removeu aceitos sem reduzir a contagem de erros, que já era zero nessas medições externas. Algoritmos concordarem não tornou o grupo automaticamente mais preciso.

### Aplicação candidata e referências conhecidas

A política final selecionada nas 80 referências, confiança ≥ 0,90 sem concordância, aceitaria **60/559 = 10,73%** das questões sem rótulos. A precisão dessas 60 é desconhecida e permanece `null` nos resultados; os 100% externos não são copiados como estimativa comprovada desse lote.

Nas 20 referências já conhecidas, a mesma política aceitou três e acertou duas: **2/3 = 66,67%**, cobertura de 15% e Wilson entre **20,77% e 93,85%**. A amostra é pequena e historicamente reutilizada, mas registra um erro aceito pelo filtro. O diagnóstico não foi usado para escolher outro corte nem permite afirmar que as 60 questões teriam precisamente a mesma taxa de acerto.

O [CSV candidato](../artefatos/politica-m9-v1/publicacao_candidata.csv) contém 659 linhas: **72 com `publicar` e 587 com `revisar`**. As 72 se dividem em nove decisões externas de desenvolvimento, três no diagnóstico conhecido e 60 no lote sem rótulos. Portanto, 72/659 não é o denominador utilizado para anunciar cobertura no lote de avaliação. Esse CSV é uma simulação separada; não foi promovido à entrega oficial.

### Interpretação da rodada

O experimento identificou grupos com acerto observado alto e mostrou que a abstenção anterior não equivale a incapacidade de produzir classificações corretas. Ao mesmo tempo, a escolha de filtros não se repetiu nos três treinos, o intervalo de incerteza continua amplo e há um erro entre os três aceitos no diagnóstico conhecido. A evidência não sustenta anunciar 95% de precisão nas 60 questões candidatas.

O M9 não demonstra que manter cobertura zero seja a melhor decisão possível. Demonstra o que a regra alternativa fez, onde a seleção ficou instável e qual é a cobertura disponível se a candidata for aplicada. A entrega oficial foi preservada conforme o protocolo congelado; não se alterou a regra de promoção depois de observar seu resultado. O objetivo de publicação com precisão sustentada continua em aberto.

A execução inicial levou **202,369 segundos**; a verificação posterior com preparação autenticada levou **0,764 segundo** e reproduziu os produtos. A reconstrução completa, incluindo os rankings internos e a concordância nas duas coortes finais, passou em **174,812 segundos**, com todos os produtos idênticos byte a byte. Os **45 testes do módulo** também passaram. Esses tempos incluem etapas distintas e não constituem benchmark de inferência por questão. A auditoria de hashes conferiu os cinco produtos da preparação, os oito produtos do experimento e suas fontes, incluindo a cadeia M8, sem alterações detectadas. O [checkpoint M9](../artefatos/checkpoints/modulo9.json) registra os arquivos e o estado para retomada.

## Artefatos e preservação da entrega

A preparação fica em `artefatos/politica-m9-preparacao-v1/`: previsões internas dos três blocos, concordância para as coortes de 20 e 559, fontes, hashes dos checkpoints e manifesto. A retomada exige fontes idênticas e pares completos de produto/hash; arquivos órfãos ou modificados são recusados.

O [experimento](../artefatos/politica-m9-v1/manifesto.json) grava em `artefatos/politica-m9-v1/`:

- `metricas.json`: seleção interna, avaliação externa, estabilidade, seis curvas, diagnóstico das 20 e cobertura das 559;
- `politica_candidata.json` e `calibracao_e_selecoes.json`: regra final, calibrador e escolhas de cada bloco;
- `predicoes_externas.jsonl`, `predicoes_20.jsonl` e `sugestoes_559.jsonl`: previsões das três coortes;
- `publicacao_candidata.csv`: simulação com as 659 linhas e contrato de colunas validado;
- `ANALISE.md` e `manifesto.json`: interpretação dos resultados e assinaturas das fontes e produtos.

O CSV candidato existe para inspeção mesmo se o critério de estabilidade falhar. Nas 80 referências, registra decisões externas do procedimento; nas 20 e nas 559, aplica a política final selecionada nas 80. **Não é uma substituição automática da entrega oficial.** O script não altera `entrega-final-v2/` nem os produtos históricos M1–M8.

As 559 sugestões reutilizam o ranking `sinais_large` ajustado com as 100 referências e a confiança ajustada nas 80 previsões OOF. A concordância complementar usa `sinais_small` ajustado com as mesmas 100 referências e RRF com parâmetros fixos. A cobertura nessa coorte é mensurável; a precisão continua desconhecida.

## Execução e reprodução

Na pasta `etapa-complementar`, execute com Python e os artefatos locais já preparados:

```console
python -E -X utf8 -B -S scripts/revisar_politica.py
```

Na primeira execução, o comando reconstitui rankings internos e calcula a concordância que falta, salvando checkpoints por bloco ou coorte. Se a preparação autenticada já estiver completa, ela é reutilizada. O comando recusa sobrescrever artefatos existentes com conteúdo divergente.

Para reproduzir seleção, calibração, métricas e CSV usando a preparação autenticada:

```console
python -E -X utf8 -B -S scripts/revisar_politica.py --verificar
```

Essa verificação compara os produtos byte a byte e é mais rápida porque não reexecuta os rankings da preparação. Para reconstituir também esses rankings e comparar toda a preparação antes de verificar os produtos:

```console
python -E -X utf8 -B -S scripts/revisar_politica.py --reconstruir --verificar
```

`--reconstruir` sem `--verificar` também força a recomposição, mantendo a recusa a substituir conteúdo divergente. Nenhum desses comandos gera embeddings: rede, credenciais, pesos e bibliotecas de encoder são bloqueados durante a execução. Não há chamada de API ou dependência de um serviço pago.

## Limites da conclusão

As 100 referências já foram consultadas no histórico do projeto. As 300 questões recentes não possuem rótulos humanos disponíveis, e não há novo teste independente nem revisão jurídica adicional. Wilson descreve a incerteza amostral nominal do grupo observado; não corrige a seleção adaptativa histórica nem comprova precisão nas 559 questões.

Remover um mínimo arbitrário pode aumentar cobertura, mas não cria evidência de acerto. Este módulo deve ser avaliado pelos erros e pelo suporte observado, pela consistência entre blocos e pela transparência sobre essas limitações. Se o procedimento falhar, a conclusão é registrada sem ampliar a grade em busca de um resultado favorável.
