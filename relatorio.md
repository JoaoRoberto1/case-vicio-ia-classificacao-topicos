# Classificar para publicar com critério

**Case Vício | João Roberto de Oliveira Felix | 16 de outubro de 2026**

**Entrega: 359 decisões, 77 publicações, 278 revisões e quatro questões fora do recorte.** A cobertura é 21,45%. A meta de precisão jurídica de 95% ainda não foi comprovada. A solução torna explícitos os motivos de retenção, preserva o histórico e permite reproduzir a entrega sem novas chamadas.

## 1. Raciocínio e escolhas

O erro mais caro é colocar a questão no tópico errado para o aluno. Comecei pela integridade dos textos e da árvore, separei o assunto central dos assuntos acessórios e tratei a possibilidade de recusar publicação como parte da solução. Os campos de origem foram preservados para diagnóstico, mas excluídos do prompt: não são rótulos confiáveis.

Usei o catálogo completo dos 375 nós ativos no primeiro classificador. Assim, a escolha inicial não depende de uma busca que poderia esconder o tema correto. Escolhi Gemini 3.5 Flash-Lite, com raciocínio MEDIUM, por funcionar no acesso gratuito disponível; não houve comparação que demonstrasse superioridade sobre outros modelos. A resposta estruturada registra central, extras, alternativas, evidência textual, confiança e necessidade de revisão.

| Hipótese / tentativa | Evidência e decisão |
| --- | --- |
| O contexto completo evita classificações pelo título isolado. | Limpeza de HTML e composição de enunciado, comando e alternativas; não reconstruí texto ausente nem corrigi OCR por adivinhação. |
| Pedir atenção explícita à ambiguidade ajuda a reter casos arriscados. | Nos mesmos 20 casos de desenvolvimento, o prompt v2 pediu dez revisões, contra três no v1. Ambos produziram 20 respostas válidas. Escolhi v2 pela triagem, sem alegar ganho de precisão. |
| Confiança alta basta para publicar. | Descartada como regra única: confiança não foi calibrada. A política também bloqueia candidatos concorrentes, raiz genérica, colisões entre ramos, excesso de extras e revisão solicitada. |
| Um segundo passe pode liberar casos retidos só por alternativas. | Nos 41 selecionados, houve 23 propostas; 20/23 coincidências estritas e uma divergência explícita. O critério previamente registrado falhou; nenhuma promoção foi adotada. |

## O que foi implementado

Python com biblioteca padrão: preparação, validação de IDs e evidências, API com pausas, recibos com checksum e retomada, política de decisão, exportação, revisão cega por IA e avaliação. A política v1 exige confiança autodeclarada de pelo menos 0,95, no máximo um extra e ausência dos bloqueios; foi registrada após o piloto, antes da inspeção dos novos resultados do lote. Não rebaixei o limiar para melhorar cobertura.

Revisões por agentes Codex apoiaram a auditoria e as exceções; não equivalem a especialistas jurídicos. Não implementei embeddings, treinamento supervisionado ou agentes autônomos na classificação de produção. São opções a testar após obter referência confiável.

Fontes: [política v1](config/politica_v1.json), [pilotos](docs/PILOTO_V1.md), [experimento controlado](docs/EXPERIMENTO_COBERTURA_V2.md). Os 20 casos do piloto são desenvolvimento, não amostra de validação independente.

<!-- pagina -->

# Os dados também precisam de decisões editoriais

## 2. Diagnóstico do recorte

A árvore tem 377 registros, dos quais 375 estão ativos, incluindo quatro raízes de disciplina. Não há IDs repetidos, ciclos ou pais ausentes. Isso confirma integridade estrutural, não separação clara entre os conceitos. Há 20 descrições vazias e 337 com prefixos de metadados de hierarquia; a maioria não fornece uma definição editorial que diferencie temas próximos.

Nos textos, 94 comandos já estavam vazios; após retirar marcação sem conteúdo, são 101. Há 18 assuntos de origem vazios e uma disciplina de origem vazia. A preparação sinalizou 148 questões, sem converter automaticamente os avisos em reprovação. Oito grupos de títulos se repetem em ramos distintos; o mapeamento de ambiguidades da política abrange 20 IDs, incluindo outras sobreposições potenciais.

| Problema concreto | Consequência e tratamento |
| --- | --- |
| Maria da Penha: 4704 / 6724; Drogas: 4708 / 6728; Ação Penal: 5063 / 5466. | O mesmo título não autoriza fundir IDs. Mantive os ramos e encaminhei colisões à revisão. Proponho ao editor definir escopo, exemplos e destino canônico quando houver duplicação real. |
| Q0239 tem comando genérico; Q0107 concentra informação no comando. | A unidade de classificação é o texto completo, incluindo alternativas. Enunciado curto, sozinho, não determina tema nem ausência de tema. |
| Q0099 contém marcação de Word; Q0078 tem degradação de OCR; Q0219 depende de contexto ausente. | Removi apenas marcação. Perda de conteúdo e ambiguidade entram na triagem; reparar o texto exige recuperar a fonte. |
| Q0180: Busca e Apreensão (5554) versus Prova Ilegal e Prova Ilícita (5594). | A auditoria questionou o foco central. Ter o outro tema como extra não corrige o central. A versão final retém a questão, sem afirmar qual rótulo está juridicamente certo. |
| Q0024 contrapõe nós irmãos de teorias criminológicas. | A diferença entre irmãos conta como erro na regra do case. O experimento mostrou necessidade de fronteiras editoriais claras, mesmo com referência de IA provisória. |

## Por que a cobertura é baixa

Na v1, das 277 revisões, 232 tinham temas alternativos, 218 confiança abaixo do limiar, 193 revisão solicitada, 60 ambiguidade mapeada e 32 excesso de extras; quatro vieram de correções de candidatos a `fora`. Os sinais se sobrepõem. Só 41 casos eram retidos exclusivamente por alternativas, sete apenas pela confiança e um apenas por ambiguidade. Reduzir somente o limiar não resolveria o gargalo principal.

Dos oito candidatos iniciais a `fora`, uma revisão separada por IA encontrou tema para quatro e os encaminhou a `revisar`; quatro permaneceram fora. Origem em outra disciplina não bastou para excluir. Essas intervenções estão registradas com antes/depois, evidências e limitações; não foram validadas por especialista.

Fontes: [diagnóstico estrutural](artefatos/preparacao/diagnostico.json), [ambiguidades](artefatos/revisao_taxonomia/ambiguidades.json), [cobertura v1](docs/COBERTURA_V1.md), [revisão de fora](artefatos/revisao_fora-v1/revisoes.json).

<!-- pagina -->

# Previsão com limites explícitos

## 3. Evidência, previsão e rastreabilidade

Congelei a v1 antes da comparação: três revisores por IA, em contextos separados e sem sugestões Gemini, cobriram os 78 publicados. A regra de amostrar até 80 restantes resultou em censo: cinco casos do desenvolvimento e 73 restantes. Houve **77/78 = 98,72% de concordância com a referência provisória**, uma divergência (Q0180) e nenhum inconclusivo. Isso não mede o possível erro compartilhado entre IAs. Os textos haviam sido vistos na exploração inicial; não há conjunto inteiramente intocado.

Q0009, Q0088 e Q0187 têm referências que aceitam dois temas. Tratá-las como não confirmadas produz 74/78 = 94,87%, uma sensibilidade posterior, não um intervalo estatístico. Em Q0179, uma busca exibiu incidentalmente trecho de gabarito de alternativas; o incidente foi registrado. Não houve acesso aos rótulos temáticos reservados do case.

Na v2, retive Q0180 por esse achado conhecido. As referências reutilizadas não tornam os 77 remanescentes uma validação independente, nem provam precisão de 100%. O segundo passe do 5C teve 22/23 concordâncias pela regra hierárquica, mas só 20/23 estritas e uma divergência: o lote inteiro de propostas foi rejeitado, sem escolher apenas os acertos após consultar a referência.

| Campo de previsao.txt | Como foi calculado |
| --- | --- |
| Precisão prevista: 94,81%. | Julgamento conservador: reserva de quatro possíveis erros, 73/77. As três referências múltiplas e o incidente motivam cautela, mas não são quatro erros observados, nem os únicos locais possíveis de erro. |
| Intervalo de precisão: 89,61% a 100%. | Cenários assumidos de zero a oito erros: 69/77 a 77/77. Dobrar a reserva é julgamento editorial, sem nível de confiança, calibração ou evidência de que oito seja teto. O resultado real pode ficar abaixo. |
| Cobertura: 21,45%; intervalo igual ao ponto. | Contagem conhecida: 77/359. Refere-se a este lote, não à próxima importação. |

Sem hipóteses sobre o erro da referência, os limites identificáveis da precisão jurídica seriam [0,1]. Por isso, a previsão acima é assumidamente subjetiva. Para cumprir 95% neste conjunto, podem existir no máximo três erros; quatro já deixam o resultado em 94,81%. Não ajustei o CSV para fazer a previsão parecer atingir a meta. Extras, decisões de revisão e exclusões não são avaliados pela concordância do central.

## Custo e tempo observados

Piloto v1, lote completo (já inclui piloto v2) e 5C somam 474 tentativas registradas e 13.079.922 tokens conhecidos; 40 tentativas não informam uso. O lote usa 404 tentativas; o 5C, 50. A conclusão das últimas 197 questões levou 87 min 32 s; o 5C, 21 min 48 s, com esperas. Esses tempos de execução não medem esforço humano total. As 20 horas foram planejamento, não apontamento de horas.

A API foi usada em projeto gratuito, sem ativar faturamento. Consumo Codex, verificações sintéticas e possível chamada interrompida sem recibo ficam fora desses totais; o modelo específico dos revisores Codex não foi registrado nos recibos. Não afirmo custo total zero. Código, prompts, recibos, intervenções e cálculos estão no repositório.

Fontes: [auditoria v1](docs/AUDITORIA_V1.md), [trilha v2](artefatos/decisoes-v2/manifesto_decisoes.json), [evidências documentais](artefatos/entrega-v2/evidencias.json), [previsão completa](previsao.txt).

<!-- pagina -->

# Publicar em escala exige validação

## 4. Proposta para 50 mil questões por semana

**Este desenho é proposto, não foi implementado nem homologado.** Até existir avaliação jurídica independente, operaria em sombra, com aprovação editorial antes da exposição ao aluno. A confiança autodeclarada e a concordância entre IAs não bastam para liberar publicação em escala.

- **Importar:** preservar original, limpar marcação, detectar duplicatas e conteúdo incompleto. Usar fila idempotente, limites por projeto, tentativas limitadas e fila de falhas. Versionar modelo, prompt, taxonomia e decisão para reversão.
- **Selecionar candidatos:** combinar busca lexical e embeddings, ancestrais e ramos repetidos. Validar recall@k antes de substituir o catálogo completo. Sem candidatos confiáveis, consultar o catálogo ou reter; nunca deduzir `fora` apenas da busca.
- **Decidir e revisar:** LLM estruturado, regras e abstenção. Testar classificador treinado após acumular rótulos adjudicados; calibrar limiares por ramo em dados separados. Não incluir segundo agente em todo item: o 5C não demonstrou ganho adotável.
- **Integrar à plataforma:** professor recebe texto, sugestão, alternativas e motivo; correções são auditáveis. Reporte do aluno entra em triagem por gravidade e alcance, pode suspender a associação e aciona busca por erros semelhantes; não altera rótulos automaticamente.

## Custo por questão e capacidade

Tarifas Standard consultadas em 16/10/2026 para Gemini 3.5 Flash-Lite: US$0,30/M tokens de entrada, US$0,03/M de entrada em cache e US$2,50/M de saída, incluindo raciocínio. Fórmula: **[(I - C) × 0,30 + C × 0,03 + S × 2,50] / (1 milhão × N)**; cache C já faz parte da entrada I e S inclui raciocínio.

| Cenário de API | US$/item | US$/50 mil | Hipótese e limite |
| --- | --- | --- | --- |
| Catálogo atual, com cache | 0,0057 | 283,44 | Consumo conhecido das 404 tentativas dividido por 359; cache informado. |
| Catálogo atual, sem desconto | 0,0127 | 634,27 | Mesmo consumo conhecido; entrada inteira à tarifa cheia. Não é teto de gasto. |
| Candidatos reduzidos | 0,0057 | 284,62 | Hipótese: 4 mil tokens de entrada, 1,5 mil de saída+raciocínio e 1,15 tentativas/item; sem cache. Ainda não medido. |

Os cenários não são faturas: excluem uso ausente, infraestrutura, embeddings, revisão e auditoria. A recuperação pode reduzir tokens e também o benefício do cache; a economia precisa ser medida. Na mistura atual, seriam **38.719 revisões/semana**. A dois minutos cada, cerca de 1.291 horas; a US$20/h hipotéticos, só revisão custa US$0,52 por questão importada. O gargalo é editorial. A cota gratuita informada de 500 chamadas/dia não suporta 50 mil/semana; seria necessário orçamento e cotas próprios.

## Qualidade contínua e critério de liberação

Congelar política e avaliar lote novo com especialistas cegos, adjudicação e amostra probabilística estratificada por ramo/origem. Estimar precisão dos publicados com pesos amostrais e limite inferior de 95% de confiança pelo menos igual a 95%; inconclusivos entram como não confirmados. Auditar extras e `fora` separadamente e medir perdas entre retidos. Monitorar semanalmente precisão × cobertura, fila/tempo de revisão, custo, falhas e reportes; separar amostra aleatória de casos prioritários. Mudança de modelo, taxonomia ou queda de qualidade exige nova validação e retenção do segmento afetado.

Fontes: [preços Google](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite), [limites por projeto](https://ai.google.dev/gemini-api/docs/rate-limits), [consumo e hipóteses reproduzíveis](artefatos/entrega-v2/evidencias.json).

<!-- pagina -->

# Memo ao professor

**Assunto: tornar os temas mais claros e proteger o estudo por tópico**

Professor(a), examinei 359 questões. A entrega propõe 77 para publicação, mantém 278 para revisão e deixa quatro fora do recorte por falta de tema adequado. Essa seleção ainda precisa de validação jurídica: a conferência disponível foi feita por ferramentas de IA, sem revisão de especialista. Publicar menos foi uma forma de preservar as dúvidas, não uma demonstração de que todas as publicadas estão certas.

## O que encontramos

Algumas questões misturam vários assuntos nas alternativas; outras têm texto incompleto ou marcas de uma importação antiga. Nesses casos, classificar só pela primeira frase induz erro. Há também temas com o mesmo nome em lugares diferentes da árvore, e muitas descrições apenas repetem onde o tema está, sem dizer o que ele abrange.

Um exemplo concreto é Q0180: a classificação sugeriu Busca e Apreensão, mas a conferência apontou Prova Ilegal e Prova Ilícita como possível foco principal. Mantive a questão em revisão. Ela mostra por que precisamos identificar o conhecimento central exigido, e não apenas o procedimento citado na narrativa.

## Mudanças que recomendo nos temas

- **Esclarecer os nomes repetidos.** Lei Maria da Penha aparece nos IDs 4704 e 6724; Drogas, em 4708 e 6728; Ação Penal, em 5063 e 5466. Precisamos definir se são duplicações ou recortes diferentes. Se forem equivalentes, escolher um destino principal e preservar o encaminhamento das associações antigas; se forem distintos, explicitar a diferença no nome e na descrição.
- **Escrever critérios curtos de inclusão e exclusão.** Para cada fronteira problemática, registrar o que pertence ao tema, o que vai para o tema vizinho e dois exemplos comentados. Começaria por prova versus busca e apreensão, teorias criminológicas próximas e os nomes repetidos.
- **Evitar depósitos genéricos de questões.** Um tema introdutório deve receber apenas o que cobra a introdução. Quando a questão cobra conteúdo específico, precisamos do destino correspondente; quando mistura focos sem predominância, a dúvida deve ficar visível para revisão.

## De que preciso do seu julgamento

Primeiro, decidir o escopo desses pares e a regra para escolher o assunto principal quando há várias alternativas sobre temas diferentes. Depois, revisar um conjunto novo, separado dos rótulos reservados deste case, incluindo publicadas, retidas e possíveis ausências de tema. Os casos duvidosos precisam de justificativa curta e, quando houver discordância entre revisores, de uma decisão editorial registrada.

Sugiro começar pelas fronteiras recorrentes e pelos casos com maior impacto no aluno. A conferência regular também deve incluir questões sorteadas: olhar apenas reclamações não mostra quantos erros passam despercebidos. Quando o aluno reportar um erro, o professor confirma a correção e verifica se o mesmo problema aparece em outras questões do tema.

**Resultado esperado:** temas que professores e ferramentas consigam distinguir da mesma forma, revisão concentrada nas dúvidas reais e publicação acompanhada de qualidade medida. As sugestões acima não alteraram a árvore fornecida neste case.
