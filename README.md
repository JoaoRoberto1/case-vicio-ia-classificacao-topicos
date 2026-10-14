# Case Vício — Classificação de tópicos

## Visão geral

Solução em desenvolvimento para o processo seletivo de IA da Vício (Método VDE), voltada à classificação de questões de concursos jurídicos por tópico.

## Objetivo

Classificar as 359 questões fornecidas usando a árvore de temas de Penal, Processo Penal, Direito Penal - Legislação Especial e Criminologia. Cada questão receberá uma das seguintes decisões:

- **`publicar`**: vai diretamente ao aluno no tema escolhido.
- **`revisar`**: vai ao especialista com uma sugestão de tema.
- **`fora`**: nenhum tema da árvore serve; a questão sai do recorte até que um tema seja criado.

A **meta é atingir pelo menos 95% de precisão nas questões publicadas**, buscando a maior cobertura possível (fração do total de questões publicada). Essa é uma meta do case, ainda não um resultado alcançado ou validado.

## Materiais fornecidos

| Arquivo | Descrição |
| --- | --- |
| [case-ia-classificacao-de-topicos.pdf](case-ia-classificacao-de-topicos.pdf) | Enunciado oficial: contexto, critérios de avaliação, regras e entregas exigidas. |
| [LEIA-ME.md](LEIA-ME.md) | Documento original do organizador, com o dicionário dos campos e os formatos de entrega. |
| [questoes.jsonl](questoes.jsonl) | As 359 questões, com enunciado em HTML, comando, alternativas e campos de origem. |
| [temas.csv](temas.csv) | Árvore com 377 registros de disciplinas, temas e subtemas, incluindo descrições e status. |
| [entrega_modelo.csv](entrega_modelo.csv) | Exemplo de formato da futura entrega `publicacao.csv`. As duas linhas são fictícias e não representam classificações reais. |

Os requisitos são definidos pelo PDF oficial e pelo `LEIA-ME.md`. O arquivo `entrega_modelo.csv` não é a entrega final; `publicacao.csv` ainda será produzido.

## Regras importantes

- Todas as 359 questões precisam receber uma decisão.
- Temas inativos não podem ser utilizados.
- `disciplina_origem` e `assunto_origem` podem estar errados e não constituem um gabarito.
- Os rótulos dos especialistas foram reservados pela organização para avaliação e não foram disponibilizados.
- Dúvida entre temas não é, por si só, motivo para usar `fora`; essa decisão indica que nenhum tema da árvore serve.
- Conforme o `LEIA-ME.md`, `tema_central_id` é obrigatório em `publicar` e em `revisar` e fica vazio em `fora`. O campo `motivo` é obrigatório em `revisar` e em `fora`.

## Estado atual

O repositório está em organização inicial. A implementação do classificador, a avaliação e as entregas finais ainda estão pendentes.

## Como executar

As instruções de execução e reprodução, incluindo os passos para gerar `publicacao.csv`, serão adicionadas junto com a implementação.

## Entregas previstas

Todas as entregas abaixo estão **pendentes**:

- **`publicacao.csv`**: uma linha com a decisão para cada uma das 359 questões, seguindo o formato definido no `LEIA-ME.md`.
- **`previsao.txt`**: previsão de precisão nas publicadas e de cobertura, cada uma com seu intervalo e uma explicação da metodologia, antes de conhecer o resultado da avaliação da organização.
- **Relatório de até 5 páginas, em PDF ou Markdown**: raciocínio, hipóteses e experimentos; diagnóstico dos dados e temas; proposta de produção; e memo para o professor, especialista em Direito. A proposta de produção deverá abordar 50 mil questões por semana e novas importações, técnicas de IA, custo por questão, medição contínua da qualidade e integração com importação, revisão e reportes dos alunos.
- **Código, prompts, regras de decisão e instruções de reprodução**: documentação do processo completo de classificação e estimativa de precisão, incluindo as chamadas a modelos que forem utilizadas.

O enunciado solicita um memo de uma página, cobrindo achados, mudanças recomendadas nos temas e apoio necessário do especialista. Como proposta de organização da entrega, será reservada uma das cinco páginas do relatório para esse memo.

## Rastreabilidade

Serão registrados os experimentos, as decisões manuais e seus motivos, os modelos utilizados, o custo aproximado, o tempo gasto e as limitações. Esses registros acompanharão a implementação e a avaliação, distinguindo propostas, procedimentos executados e resultados observados.
