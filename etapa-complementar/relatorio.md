**João Roberto de Oliveira Felix**

# Classificação de tópicos da Vício

Etapa complementar | Relatório técnico | 21 de outubro de 2026

**Resultado:** o sistema é reproduzível e classifica sem chamar um modelo de linguagem. A receita congelada acertou 6 de 20 sugestões no teste reservado. Não sustentou publicação automática: as 559 questões da avaliação oficial seguem para revisão. A meta de precisão de 95% com cobertura não foi atingida.

## Sistema e decisões

O pipeline limpa o HTML e combina enunciado, comando e alternativas. Preserva a árvore, os IDs e os anexos por hashes. Disciplina e assunto de origem não são gabaritos nem atributos. Somente temas ativos abaixo da raiz concorrem; a avaliação compara IDs e parentesco com a folha-verdade humana, sem julgamento de questões por IA.

| Componente | Implementação e função |
|---|---|
| Representação lexical | TF-IDF de palavras e pares de palavras; enunciado e comando têm peso 2, alternativas 1; título do tema 3, caminho e descrição 1. Vocabulário e IDF usam apenas catálogo e textos de treino. |
| Preparação semântica | E5 multilingual small local, FP32, 384 dimensões; prefixos query/passage, janelas de 480 tokens e sobreposição de 32. Vetores normalizados e persistidos; nenhum modelo participa da decisão. |
| Ordenação | Fusão recíproca das posições lexical e semântica, pesos 0,5/0,5 e k=20. O escore é similaridade, não probabilidade. Os rótulos dos vizinhos não pontuam na receita vencedora. |
| Confiança e política | Três calibradores comparados no desenvolvimento. Só publicar com confiança e precisão observada mínimas de 0,95, suporte mínimo de 10 e tema elegível. Sem limiar sustentado, revisar. |

Para evitar tópicos genéricos como destino fácil, publicar exige folha ativa e exclui seis expressões genéricas fixadas antes do teste. Não há promoção a ancestrais. Não automatizei `fora` com apenas seis exemplos dessa classe no desenvolvimento; confiança baixa não prova ausência de tema. Extras previstos ficam vazios.

## Dados que limitam a classificação

São 659 questões e 377 temas: 375 ativos e quatro raízes. Há 337 descrições que apenas informam parentesco, 20 vazias e oito títulos repetidos em ramos diferentes. Isso oferece pouca definição operacional para distinguir temas próximos. A limpeza sinalizou 401 comandos vazios e 134 enunciados curtos; são avisos para considerar os demais campos, não prova de conteúdo inválido.

Fontes: [diagnóstico](artefatos/preparacao/diagnostico.json), [receita](artefatos/melhorias-v1/receita_congelada.json), [preparação e origem do codificador](docs/MODULO3_EXPERIMENTOS.md). Revisão E5: `614241f622f53c4eeff9890bdc4f31cfecc418b3`, licença MIT. Nenhuma decisão temática foi tomada à mão.

<!-- pagina -->

# Avaliação e calibração

As 100 referências humanas são do banco anterior: 92 dentro da árvore, oito fora, 61 temas centrais distintos e 39 questões com extras. Reservei 20 antes do primeiro experimento; usei 80 em três partições internas para comparar receitas. Cada sugestão de desenvolvimento foi produzida sem treinar naquela questão. A seleção entre receitas nessas mesmas 80 é exploratória.

## O que foi testado e descartado

| Receita nas 80 referências | Acerto por ramo | Tema aceitável no top5 |
|---|---:|---:|
| Catálogo lexical sem exemplos | 34/80 | 56/80 |
| Lexical com exemplos humanos | 31/80 | 57/80 |
| Lexical com exemplos e citações legais | 31/80 | 54/80 |
| Semântica isolada | 21/80 | 34/80 |
| **Híbrido de catálogo selecionado** | **37/80** | **54/80** |
| Híbrido com exemplos lexicais | 36/80 | 59/80 |
| Híbrido com exemplos semânticos | 37/80 | 54/80 |

A regra prévia priorizou acertos por ramo, depois exatos e prioridade fixa. O híbrido sem exemplos venceu; o empate com exemplos semânticos não justificou sua complexidade. As citações não melhoraram o lexical e a semântica sozinha piorou. O aumento do primeiro acerto veio com queda do top5 frente ao lexical com exemplos: não houve melhoria uniforme.

Comparei constante, logística do escore e logística de escore mais margem, com probabilidades fora do ajuste do calibrador. Os Brier foram 0,2495, 0,2580 e 0,2567. A constante venceu e, ajustada nas 80, devolve (37+0,5)/(80+1) = 46,30%: uma taxa global, sem discriminar risco individual. Nenhuma alternativa chegou a 0,95 nas probabilidades crossfit. Calibrador, código, política e procedimento final foram congelados antes de preparar os vinte vetores reservados.

## Teste reservado e previsão oficial

Na reserva: **6/20 acertos por ramo, 3/20 exatos e 12/20 no top5**; 0 publicadas e 20 revisões. O intervalo de Wilson de 95% para o acerto de todas as sugestões é 14,55%-51,90%; não é precisão de publicação. A confiança média de 46,30% superou os 30% de acerto observados. Os componentes não foram alterados após esse resultado.

A previsão oficial exclui as 100 referências: cobertura **0/559**, intervalo 0-0 e precisão entre publicadas **indefinida**. O zero em `previsao.txt` é apenas sentinela do formato numérico; o JSON preserva `null`. A faixa 0-1 indica ausência de informação, não um intervalo de confiança calculado. As 300 questões recentes não têm rótulos disponíveis.

Fontes: [experimentos](artefatos/melhorias-v1/metricas_desenvolvimento.json), [calibração](artefatos/calibracao-v1/metricas_desenvolvimento.json), [reserva](artefatos/reserva-v1/metricas_reserva.json), [previsão](artefatos/decisoes-v1/previsao.json). O critério de ramo aceita o tema humano ou relação ancestral; irmãos não contam. Extras humanos também entram na comparação.

<!-- pagina -->

# Operação e próximos experimentos

## Diagnóstico de erro e intervenção

Dos 14 erros reservados, nove caíram em outra disciplina, dois em outro ramo da mesma disciplina, um em tema irmão e dois tinham referência `fora`, considerando central e extras humanos. O acerto no top5 de 12/20 separa seis falhas de ordenação dos oito casos sem candidato aceito, incluindo os dois `fora`. Descrições pobres e títulos duplicados são hipóteses de contribuição, não causas jurídicas demonstradas para cada erro; precisam de critérios de inclusão e exclusão.

A próxima rodada deve comparar descrições enriquecidas e ordenação supervisionada, com versões próprias e correções humanas. Não ajustaria limiares para fazer a reserva atual parecer melhor: ela já foi utilizada. Uma nova avaliação deve incluir questões recentes rotuladas e permanecer separada do ajuste.

## Capacidade e custo para 50 mil por semana

As medidas locais são de CPython 3.14.7 no Windows e CPU na preparação. Não são benchmark de produção. A tabela é extrapolação linear, supondo textos e catálogo semelhantes, uma execução sequencial e ausência de paralelização; os tempos incluem custos fixos.

| Fase | Medida local | Extrapolação para 50 mil |
|---|---|---|
| Preparar vetores novos | 20 questões em 21,248 s | 14,76 h; amostra pequena, inclui carregamento do modelo |
| Reajustar e gerar decisões | 559 questões em 306,270 s | 7,61 h; inclui verificação e escrita |
| Revisão humana | Cenário de 2 min por questão | 1.666,7 h com a política atual de revisão integral |

O custo de API é zero; computador, energia e trabalho humano têm custo. No cenário acima, processamento local seria aproximadamente 22,37 horas-máquina por semana. O custo é `22,37 × custo da hora-máquina + 1.666,7 × custo da hora de revisão`. Por exemplo, **assumindo**, sem cotação, R$ 1/h de máquina e R$ 50/h de revisão: cerca de R$ 83,36 mil/semana, dominados pelo trabalho humano. Essa operação não é viável como automação no estado atual.

Proponho importar em lotes, preparar vetores fora da decisão e medir vazão e memória antes de dimensionar. Cada correção deve registrar texto, versão da árvore, tema central/extras ou `fora`, justificativa, revisor e versão do sistema. Novos exemplos e pares confundidos alimentam treino; discordâncias recebem adjudicação. A cada semana, avaliar uma versão candidata com novas correções, mantendo teste temporal separado. Promover somente após demonstrar a meta com suporte e cobertura; caso contrário, preservar a versão anterior. Essa rotina é proposta, não serviço já implantado.

## Reprodução e alcance da entrega

Na pasta `etapa-complementar`, `python -B -m classificacao_decisao regenerar` refaz a entrega a partir dos anexos preparados e artefatos versionados. `python -B -S scripts/verificar_entrega.py` confere a reprodução em cópia temporária sem dependências de IA. O README explica a origem dos artefatos e os tempos. Os caches dispensam pesos e API na decisão.

As 659 linhas preservam três origens: 80 sugestões fora da amostra com confiança crossfit, 20 do teste congelado e 559 do reajuste final nos textos das 100 referências. Esse reajuste muda o IDF, mantém calibrador e política das 80 e não recebeu outro teste independente. Classificações de IA da primeira entrega não foram reutilizadas.

Fontes: [diagnóstico de erros e contas de escala](artefatos/entrega-m5-v1/diagnostico.json), [checkpoint M3](artefatos/checkpoints/modulo3.json), [checkpoint M4](artefatos/checkpoints/modulo4.json) e [procedência do código](config/reuso_codigo.json).

<!-- pagina -->

# Memo para o professor

**Para:** equipe responsável pelos temas e pela revisão de questões  
**De:** João Roberto de Oliveira Felix  
**Assunto:** critérios dos temas e prioridade da revisão

## O que encontramos

O sistema ainda não está pronto para colocar questões automaticamente na área de estudo do aluno. No teste separado de vinte questões, a primeira sugestão ficou correta em seis; em doze havia um tema aceitável entre as cinco opções. Por isso, a entrega envia todas as questões à revisão. A sugestão pode ajudar a localizar candidatos, mas não deve substituir sua decisão.

A árvore tem títulos iguais em ramos diferentes e muitas descrições que apenas repetem onde o tema está na hierarquia. Esses registros não esclarecem quando usar cada opção. Um nome semelhante pode representar convenções distintas; não recomendamos juntar temas automaticamente.

## Mudanças recomendadas nos temas

Começar pelos títulos repetidos e pelos temas genéricos que concentram questões. Para cada um, registrar uma definição curta, o que entra, o que não entra e como se distingue dos temas próximos. Escolher exemplos e contraexemplos revisados pela equipe. A árvore deve indicar se o tema aceita questões diretamente ou apenas organiza subtemas.

Quando dois nomes representarem o mesmo destino de estudo, a equipe poderá definir um destino principal e um redirecionamento. Se representarem recortes diferentes, explicitar a fronteira. Qualquer mudança precisa de versão e de um mapa entre IDs anteriores e atuais, para preservar o histórico e permitir revisão das questões afetadas.

Também precisamos de uma regra comum para assunto central e assuntos adicionais. A folha-verdade traz 39 questões com extras. O sistema ainda não os prevê; na avaliação, os extras humanos também contam como destinos aceitos para a sugestão principal. Quando nenhuma opção servir, registre `fora` e a lacuna encontrada, sem forçar um tema genérico.

## Apoio necessário da equipe

Priorizar uma amostra das questões recentes, temas com poucos exemplos e casos em que os candidatos são muito próximos. Guardar um conjunto recente separado para testar a próxima versão; as questões já usadas para corrigir o sistema não devem comprovar sua qualidade. Em uma parte da amostra, dois revisores podem classificar de forma independente e resolver divergências antes de consolidar a referência.

Na revisão, registrar tema escolhido, alternativas aceitáveis, motivo da correção e eventual problema no texto ou na árvore. É útil separar erro de sugestão, informação ausente, ambiguidade da convenção e ausência de tema. Esses registros ajudam a decidir se devemos melhorar os dados, a árvore ou o classificador.

**Recomendação de operação:** manter revisão antes da publicação e realizar um piloto limitado à capacidade real da equipe. Só ampliar a publicação automática quando uma nova avaliação humana mostrar precisão de pelo menos 95%, com quantidade de casos e cobertura explicitadas. O resultado atual oferece uma base auditável para essa próxima rodada, mas ainda não reduz a fila de revisão.
