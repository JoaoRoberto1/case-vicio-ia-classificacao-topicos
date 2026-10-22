# Módulo 9 — revisão da política de publicação

João Roberto de Oliveira Felix

Experimento exploratório. O CSV desta pasta é uma simulação candidata, não substitui a entrega oficial.

Política interna: **confianca_p90**; 14/14 acertos internos. Ranking fixo `sinais_large`; nenhum tema foi escolhido ou validado por LLM.

Procedimento externo: **9/9**, precisão 100,00%, cobertura 11,25% nas 80 referências. Wilson de 95%: 70,09% a 100,00%.

Aplicação candidata: **60/559 = 10,73%**. Precisão nas 559 desconhecida.

Passou pelo critério operacional de estabilidade: **não**.

- Publicações não se repetiram nos três blocos externos.

## Estabilidade externa

| Bloco | Acertos/aceitos | Cobertura | Precisão |
|---|---:|---:|---:|
| 1 | 6/6 | 22,22% | 100,00% |
| 2 | 3/3 | 11,11% | 100,00% |
| 3 | 0/0 | 0,00% | indefinida |

## Seis filtros: diagnóstico, sem nova seleção

| Filtro | Acertos/aceitos externos | Precisão externa | Cobertura externa | Aceitos nas 559 |
|---|---:|---:|---:|---:|
| confianca_p80 | 21/23 | 91,30% | 28,75% | 137 |
| confianca_p80_concordancia | 17/19 | 89,47% | 23,75% | 112 |
| confianca_p90 | 14/14 | 100,00% | 17,50% | 60 |
| confianca_p90_concordancia | 12/12 | 100,00% | 15,00% | 49 |
| confianca_p95 | 9/9 | 100,00% | 11,25% | 30 |
| confianca_p95_concordancia | 7/7 | 100,00% | 8,75% | 23 |

Diagnóstico nas 20 referências já conhecidas: 2/3 entre aceitas. Esse resultado foi calculado após a seleção e não é teste independente.

## Interpretação

O mínimo global de 10 foi removido deste experimento. A escolha entre seis filtros ocorre apenas nas previsões internas. Cada calibrador externo foi ajustado com rankings reconstituídos exclusivamente no treino daquele bloco. A confiança OOF global nunca é utilizada como confiança externa.

A concordância exige o mesmo tema em sinais_small, large_rrf20 e sinais_large. Os algoritmos são correlacionados: concordar não equivale a validar. O filtro não altera o tema escolhido pela receita âncora.

A estabilidade exige publicação nos três blocos e precisão observada ≥95% em cada um e no agregado. É uma escolha operacional, não garantia estatística; até 1/1 em cada bloco passaria. Wilson é descritivo, não corrige reutilização histórica/seleção adaptativa e não certifica as 559 questões.

As curvas não são usadas para trocar retrospectivamente a política escolhida. As 100 referências já foram consultadas em rodadas anteriores, e as 300 questões recentes não têm rótulos humanos disponíveis. O experimento não cria um novo teste independente. Não ampliar a grade para procurar um resultado favorável.

Reprodução: `python -E -X utf8 -B -S scripts/revisar_politica.py --verificar` na pasta `etapa-complementar`. O manifesto registra as fontes, o código e os produtos usados.
