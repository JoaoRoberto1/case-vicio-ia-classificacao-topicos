# Case Vício — Classificação de tópicos

**João Roberto de Oliveira Felix** · Etapa complementar · 22 de outubro de 2026

A entrega atual é o **módulo 8**, com as 659 questões e as 100 referências humanas fornecidas pela equipe. Os arquivos finais ficam em [etapa-complementar/entrega-final-v2](etapa-complementar/entrega-final-v2/README.md).

- [Classificações — publicacao.csv](etapa-complementar/entrega-final-v2/publicacao.csv)
- [Autoavaliação — previsao.txt](etapa-complementar/entrega-final-v2/previsao.txt) e [memória dos cálculos](etapa-complementar/entrega-final-v2/previsao.json)
- [Relatório PDF de quatro páginas, incluindo memo](etapa-complementar/entrega-final-v2/relatorio.pdf) e [versão em Markdown](etapa-complementar/entrega-final-v2/relatorio.md)
- [Defesa técnica e roteiro de cinco minutos](etapa-complementar/entrega-final-v2/DEFESA_TECNICA.md)

## Resultado e limite principal

**A meta de publicação com precisão de pelo menos 95% não está sustentada pelos dados disponíveis.** A política final encaminha as 659 questões à revisão, com tema sugerido e confiança estimada. Nas 559 questões fora da folha-verdade, a cobertura é 0%; sem publicações, a precisão é indefinida.

| Medida | Resultado | Interpretação |
|---|---:|---|
| Receita escolhida: E5-large + sinais | 53/80 por ramo (66,25%) | Desenvolvimento; 39 exatos e 67 no top 5. |
| M7 preservado na mesma comparação | 54/80 por ramo (67,50%) | O modelo maior não elevou o acerto global. |
| Procedimento de seleção aninhada | 54/80 por ramo (67,50%) | Avalia seleção, confiança e política fora do ajuste de cada bloco. |
| Grupo aceito na seleção interna | 14/14 | Motivou a escolha de `sinais_large`; não é teste independente. |
| Publicações candidatas externas | 4/4, em 80 questões | Suporte abaixo do mínimo de 10; Wilson exploratório de 51,01% a 100%. |
| Diagnóstico nas 20 já conhecidas | 13/20 por ramo (65%) | Não orientou a escolha nesta rodada; não é um novo teste independente. |
| Publicação final nas 559 | 0/559 | As 559 seguem para revisão; precisão observada desconhecida. |

A seleção prioriza cobertura elegível, seguida pelos desempates registrados. `sinais_large` e RRF tiveram regras internas com 14/14; `sinais_large` venceu o desempate pelo acerto global de 53/80 contra 50/80 do RRF. O M7 acertou 54/80, mas não teve regra elegível. Os quatro casos externos vieram de `large_rrf20` no terceiro bloco; os dois primeiros blocos não publicaram. Esses 4/4 avaliam o procedimento completo, não comprovam diretamente a receita final. O suporte mínimo foi fixado antes dos resultados e não foi reduzido depois deles.

As 80 referências de desenvolvimento já participaram de módulos anteriores, e as 20 inicialmente reservadas já eram conhecidas. Os resultados são **exploratórios**. A validação aninhada separa os ajustes desta grade, mas não elimina a adaptação histórica. Os acertos por ramo aceitam central, extra ou ancestral/descendente; temas irmãos contam como erro.

## Executar sem API ou modelo de linguagem

Requer **Python 3.11+**. Na raiz do repositório:

```console
cd etapa-complementar
python -E -X utf8 -B -S scripts/entregar_precisao.py
```

Esse comando recompõe a comparação e regenera o CSV e as previsões usando os anexos preparados e os artefatos versionados. Não instala dependências, não lê chave e não executa encoder. A execução completa observada levou **822,052 segundos (aproximadamente 13 min 42 s)** neste notebook Windows, em ambiente compartilhado; outros computadores podem diferir.

Aplicar apenas o modelo já ajustado às 559 questões levou **330,730 s**, além de **23,471 s** para carga e verificação inicial. O [benchmark](etapa-complementar/artefatos/checkpoints/benchmark_modulo8.json) confirmou todas as predições idênticas. Preparação dos vetores e revisão humana têm custos separados no relatório.

Para reproduzir em uma cópia temporária permitida e comparar todos os produtos:

```console
python -E -X utf8 -B -S scripts/verificar_precisao.py --evidencia tmp/verificacao-m8-01.json
```

Use um nome novo para cada evidência. A rotina bloqueia rede, credenciais, encoders e acesso a pesos. Recebe os caches já preparados e reutiliza o Python instalado; não é uma VM. Para testar o software:

```console
python -E -X utf8 -B -S -m unittest discover -s tests -q
```

O [guia da entrega](etapa-complementar/entrega-final-v2/README.md) explica benchmark, preparação opcional dos embeddings e geração do PDF. O [checkpoint de fechamento](etapa-complementar/artefatos/checkpoints/modulo8.json) reúne as evidências finais; a [reprodução](etapa-complementar/artefatos/checkpoints/reproducao_modulo8.json) registra seu escopo e os hashes.

**Verificações concluídas:** 496 testes aprovados em 329,929 s; reprodução em cópia permitida de 206 arquivos, em 533,096 s, reconstruindo os 12 produtos do experimento e os três arquivos de entrega com bytes idênticos. As fontes originais foram preservadas. O PDF foi regenerado e comparado byte a byte; suas quatro páginas foram renderizadas e inspecionadas visualmente. Essas verificações comprovam consistência do software e dos arquivos, não precisão temática nas questões sem rótulos.

## Sistema e procedência

O LLM participou apenas da preparação do catálogo e da implementação. Os encoders prepararam vetores antecipadamente. Nenhum modelo de linguagem escolhe, vota ou valida o tema das questões avaliadas. Durante a decisão, o classificador próprio usa operações numéricas e a biblioteca padrão do Python.

A receita escolhida combina ranking supervisionado por pares, similaridades lexical e semântica, sinais de normas/artigos/termos e uma regressão de confiança separada. O ranking final usa as 100 referências humanas; a confiança usa previsões fora do treino das 80. Esse reajuste final não recebeu um novo teste independente. Extras e a decisão `fora` não são automatizados.

| Fonte | Onde consultar |
|---|---|
| Regras e formato oficiais | [README do case](etapa-complementar/README-do-case.md), [PDF](<etapa-complementar/case-ia-classificacao-de-topicos (2).pdf>) e [anexos](etapa-complementar/anexos/LEIA-ME.md) |
| Grade, critérios e limites | [Protocolo M8](etapa-complementar/config/modulo8/protocolo.json) e [registro técnico](etapa-complementar/docs/MODULO8_PRECISAO.md) |
| Catálogo e referências normativas | [Preparação M7](etapa-complementar/config/modulo7/preparacao_catalogo.json) e [âncoras M8](etapa-complementar/config/modulo8/ancoras_normativas.json) |
| E5-large INT8 local | [Configuração](etapa-complementar/config/modulo8/embeddings_large.json), [manifesto dos vetores](etapa-complementar/artefatos/embeddings-e5-large-m8/manifesto.json) e [limites dos pilotos](etapa-complementar/artefatos/embeddings-e5-large-m8/PROCEDENCIA_PILOTOS.md) |
| Resultados reproduzíveis | [Métricas](etapa-complementar/artefatos/precisao-m8-v1/metricas.json), [manifesto](etapa-complementar/artefatos/precisao-m8-v1/manifesto.json) e [benchmark da decisão](etapa-complementar/artefatos/checkpoints/benchmark_modulo8.json) |

Pesos de modelos, ambientes virtuais, credenciais e arquivos temporários ficam fora do Git. Vetores numéricos, regras, modelos ajustados e sua procedência integram a entrega. Não há interface gráfica obrigatória: a demonstração está no roteiro de defesa e nos comandos reproduzíveis.

## Versões anteriores

Os arquivos `publicacao.csv`, `previsao.txt` e `relatorio.pdf` na raiz pertencem à primeira entrega, com 359 questões. Os arquivos de mesmo nome diretamente em `etapa-complementar` pertencem ao M5. Foram preservados para rastreabilidade e não são a entrega atual. O [README histórico](README_HISTORICO.md) mantém a documentação anterior; o [registro de retomada](etapa-complementar/docs/RETOMADA_MODULO8.md) explica a conclusão do M8.
