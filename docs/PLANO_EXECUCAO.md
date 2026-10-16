# Plano de execução do case

O trabalho está organizado em sete módulos, com 18 horas estimadas de esforço e duas horas de reserva. O objetivo é maximizar a cobertura com precisão de pelo menos 95% nas publicadas, sustentando a previsão com evidências. Essa meta ainda não foi validada.

| Módulo | Esforço previsto | Entrega e critério de conclusão | Estado |
| --- | --- | --- | --- |
| 1. Dados e árvore | 2 h | Preparação reproduzível das 359 questões e dos 377 registros, originais preservados, verificações de conteúdo e hierarquia | Concluído |
| 2. Protocolo de avaliação | 1,5 h | Piloto, critérios de revisão, cálculo de métricas e registro das ambiguidades | Definido e aplicado na v1; a regra de até 80 restantes resultou em censo dos 78 publicados |
| 3. Primeira versão e piloto | 3 h | Classificador simples, respostas estruturadas e análise de erros do piloto | Dois pilotos reais concluídos; v2 selecionada |
| 4. Execução completa | 1,5 h | Resultados persistidos para as 359 questões, sem perdas e com retomada | Concluído e commitado: 359 válidas, zero pendências técnicas |
| 5. Auditoria, decisão e cobertura | 5 h | Revisões registradas, decisões congeladas, avaliação e experimento controlado de cobertura | 5A, 5B e 5C concluídos e commitados; experimento negativo, v2 com 77 publicados |
| 6. Relatório e produção | 3 h | Previsão, até cinco páginas com diagnóstico, raciocínio, proposta para 50 mil questões por semana e memo | Concluído; pronto para revisão e commit |
| 7. Reprodução e entrega | 2 h | Arquivos finais verificados, README executável e preparação para defesa | Pendente |

O esforço previsto não representa tempo já gasto. O submódulo 5C faz parte das cinco horas previstas para o módulo 5; não acrescenta uma estimativa de tempo executado. Limites de API e achados da avaliação podem exigir ajustes. A conclusão de um módulo depende de seus artefatos e verificações.

## Pontos de parada e commits

O estado completo da pausa está em [RETOMADA.md](RETOMADA.md). O módulo 4 terminou com 359 sugestões válidas e foi commitado. O módulo 5A congelou 78 decisões `publicar`, 277 `revisar` e quatro `fora`; o 5B registrou 77/78 coincidências no censo dos publicados, frente à referência provisória de IA. O 5C terminou sem adotar nenhuma das 23 propostas: os critérios registrados de coincidência estrita e ausência de divergências não foram satisfeitos. A versão 2 contém 77 `publicar`, 278 `revisar` e quatro `fora`, após reter separadamente Q0180 por achado conhecido. A v1 permanece preservada. O ponto de parada atual é a revisão e o commit do módulo 6, com previsão e relatório completos, antes de iniciar a conferência final.

| Etapa de retomada | Tamanho do bloco | Ponto de parada | Commit sugerido |
| --- | --- | --- | --- |
| Base atual dos módulos 1 a 3 | Código, documentação e evidências já salvos | Suíte offline aprovada, originais íntegros, nenhum processo de API ativo | `feat: prepara dados e conclui pilotos de classificacao` |
| Módulo 4, blocos anteriores | Até 20 novas chamadas por continuação, incluindo retomadas | Histórico preservado nos checkpoints anteriores | `data: registra progresso do lote de classificacao` |
| Módulo 4 concluído | Continuação final de 197 questões, com invocações internas de até 20 chamadas | 359 sugestões tecnicamente válidas, incluindo Q0005 revalidada; zero pendências | `data: conclui lote de classificacao v2` |
| Módulo 5A concluído | CLI, política e revisão separada dos oito candidatos fora | CSV com 359 decisões e trilha congelados; pronto para commit antes da avaliação | `feat: congela decisoes e integra avaliacao` |
| Módulo 5B concluído | Censo de 78 publicados e diagnóstico das 277 revisões | Referências congeladas, concordância condicional e limitações registradas; pronto para commit | `eval: conclui auditoria e diagnostica cobertura` |
| Módulo 5C concluído | Segundo passe nos 41 casos, 23 propostas congeladas e avaliação por referência de IA | Resultado negativo, nenhuma promoção; v2 com Q0180 em revisão e v1 preservada; pronto para revisão e commit | `eval: registra experimento de desambiguacao e decisoes v2` |
| Módulo 6 concluído | `previsao.txt`, relatório PDF/Markdown de cinco páginas, memo e cálculos | Texto, números e layout revisados, com proposta para 50 mil questões por semana | `docs: adiciona previsao relatorio e proposta de producao` |
| Módulo 7 | Reprodução em checkout limpo | Entrega final verificada | `chore: valida entrega reproduzivel` |

Os commits são sugestões para o usuário; nenhum foi criado pelo assistente. A avaliação real da versão 1 já tem artefatos próprios. Sua conclusão não representa validação por especialista nem autorização para alterar retroativamente política, decisões ou referências congeladas.

## Próxima etapa

O [módulo 6](ENTREGA_DOCUMENTAL.md) está concluído e aguarda revisão e commit do usuário. A previsão subjetiva é 94,8052%, com cenários de 89,6104% a 100%, e cobertura conhecida de 21,4485%. O relatório de cinco páginas inclui o memo na última e distingue implementação, evidência observada e proposta de produção.

O CSV foi preservado. A retirada anterior de Q0180 é tratamento de achado conhecido, não um novo acerto validado. O uso da avaliação para escolher a versão impede descrevê-la como validação independente posterior à escolha. A faixa da previsão não é intervalo estatístico ou limite garantido; não há comprovação da meta jurídica de 95%.

O módulo 7 fará a reprodução completa em novo checkout e a conferência das entregas. Os cálculos offline do 5C já podem ser repetidos em pastas novas com os comandos `propor` e `concluir`, conforme o [README](../README.md#experimento-5c-e-decisões-v2-sem-api), sem novas chamadas ou mudanças nos artefatos congelados.

## Decisões iniciais

- Usar Python com biblioteca padrão na preparação e nos testes, sem instalação de dependências nesta etapa.
- Manter os materiais fornecidos na raiz, sem edição. Dados derivados ficam em `artefatos/`.
- Registrar hashes das fontes e produtos; a preparação deve gerar arquivos idênticos para entradas idênticas.
- Preservar enunciado, comando e alternativas separadamente, além de compor um texto completo.
- Manter temas inativos na árvore de diagnóstico e impedir seu uso como candidatos de classificação.
- Manter IDs distintos para títulos repetidos; não fundir ramos.
- Começar com uma chamada estruturada e uma política explícita; acrescentar etapas somente após analisar erros.
- Usar o plano gratuito do provedor somente após verificar o projeto e as cotas disponíveis. Nenhum gasto foi autorizado.

## Acompanhamento

A cada módulo, registrar entrega, comando de reprodução, verificações, tempo observado, limitações e próximo passo. Na classificação, acompanhar IDs processados, saídas válidas, decisões, cobertura, revisões, estimativa de precisão, uso de tokens e falhas.

O histórico de experimentos deve distinguir versão automática e intervenções manuais. Alterações manuais exigem ID, antes, depois, motivo, responsável e data.

### Primeiro bloco do módulo 4 concluído em 15 de outubro de 2026

- Retomada autorizada pelo usuário; execução limitada a vinte novas chamadas, sem iniciar outro bloco.
- Dezenove novos sucessos, Q0038 a Q0056. Q0005 voltou a apresentar evidência inválida e mantém quatro tentativas no histórico.
- Estado acumulado: 72 sucessos, uma resposta rejeitada e 286 questões sem recibo; 287 pendências no total.
- As vinte chamadas registraram 603.109 tokens totais e 178,88 segundos somados de duração de API, sem contar pausas e verificações locais.
- Modelo, prompt e política preservados. Os 53 recibos de sucesso anteriores permaneceram idênticos, e todos os recibos presentes foram validados.
- Suíte offline: 193 testes, 192 aprovados e um pulado por limitação de privilégio do Windows. Execução encerrada sem lock residual.
- Registro: `artefatos/checkpoints/bloco_2026-10-15_01.json`. Nenhuma decisão final, estimativa de precisão, alteração manual de tema ou commit realizado nesta etapa.

### Segundo bloco do módulo 4 concluído em 15 de outubro de 2026

- Recuperação offline de Q0005: a primeira tentativa salva passa na validação atual e foi registrada em um arquivo derivado, sem nova chamada, alteração manual do tema ou mudança das regras de evidência. O recibo original e suas quatro tentativas permanecem intactos.
- Vinte novas chamadas no total, com dezessete sucessos: Q0057, Q0058 e Q0060 a Q0074. Três falhas HTTP 503 em Q0058 e Q0063 interromperam invocações; as retomadas respeitaram o saldo do bloco e concluíram ambas as questões.
- Estado acumulado: 90 sugestões tecnicamente válidas, sendo 89 sucessos nos recibos originais e uma revalidação. Restam 269 questões sem recibo; nenhuma falha atual pendente entre as processadas.
- Consumo conhecido do bloco: 511.736 tokens em dezessete respostas; as três falhas não informaram uso. Duração somada das chamadas: 145,75 segundos, sem contar pausas, esperas e verificações locais.
- Os 73 recibos anteriores permaneceram byte a byte idênticos. Modelo, prompt e política preservados. A implementação de revalidação verifica hashes, histórico e seleção cronológica; o executor e as decisões usam a sugestão recuperada sem duplicar consumo.
- Suíte offline: 213 testes, 212 aprovados e um pulado por limitação de privilégio do Windows. Última invocação encerrada com código zero, sem processo de API ativo ou lock residual.
- Registro: `artefatos/checkpoints/bloco_2026-10-15_02.json`. Bloco pronto para revisão e commit do usuário; avaliação temática e entregas finais permanecem pendentes.

### Terceiro bloco do módulo 4 concluído em 15 de outubro de 2026

- Retomada autorizada pelo usuário após o commit `e0f320b`; vinte chamadas em uma única invocação, sem iniciar outro bloco.
- Dezenove novos sucessos entre Q0075 a Q0077 e Q0079 a Q0095. Q0083 foi rejeitada porque sua evidência uniu trechos separados com reticências inexistentes no enunciado. O JSON e os IDs passaram; a validação de evidência rejeitou corretamente a resposta.
- Estado acumulado: 109 sugestões tecnicamente válidas, sendo 108 sucessos nos recibos originais e a revalidação anterior de Q0005. Restam Q0083 e 249 questões sem recibo, totalizando 250 pendências.
- Consumo do bloco: 600.100 tokens informados nas vinte respostas, incluindo a rejeitada. Nenhuma falha de API neste bloco. As três falhas HTTP 503 sem metadados do bloco anterior continuam identificadas no consumo acumulado.
- Os 90 recibos anteriores e o derivado de Q0005 permaneceram byte a byte idênticos. Código, modelo, prompt, política e regras de evidência preservados.
- Suíte offline: 213 testes, 212 aprovados e um pulado por limitação de privilégio do Windows. A CLI retornou 1 por Q0083 pendente; execução encerrada sem processo de API ativo ou lock residual.
- Registro: `artefatos/checkpoints/bloco_2026-10-15_03.json`. Pronto para revisão e commit; a próxima execução tentará novamente Q0083 dentro do limite do próximo bloco.

### Quarto bloco do módulo 4 concluído em 15 de outubro de 2026

- Retomada autorizada pelo usuário após o commit `2a09668`; vinte chamadas em uma única invocação, sem iniciar outro bloco.
- Dezoito sucessos: Q0083 aceita na segunda tentativa e dezessete novos IDs válidos. Foram processados Q0096 a Q0098, Q0100 a Q0106 e Q0108 a Q0116; Q0099 e Q0107 já estavam no piloto.
- Q0103 foi rejeitada por evidência que concatena trechos com `[...]`, ausente no enunciado. Q0104 repetiu o ID `5477` em extras e alternativas, violando a exclusividade entre papéis. São falhas das respostas perante o contrato vigente; os validadores permaneceram iguais.
- Estado acumulado: 127 sugestões tecnicamente válidas, sendo 126 sucessos nos recibos originais e a revalidação anterior de Q0005. Restam Q0103, Q0104 e 230 questões sem recibo, totalizando 232 pendências.
- Consumo do bloco: 604.352 tokens informados nas vinte respostas, incluindo a segunda tentativa de Q0083 e as duas rejeitadas. Nenhuma falha de API neste bloco; o consumo ausente nas três falhas HTTP 503 anteriores permanece identificado.
- Dos 110 recibos anteriores, 109 permaneceram byte a byte idênticos. Q0083 mantém integralmente o objeto da primeira tentativa no histórico, inclusive checksum e consumo. O derivado de Q0005, código, modelo, prompt e política permanecem iguais.
- Suíte offline: 213 testes, 212 aprovados e um pulado por limitação de privilégio do Windows. A CLI retornou 1 por Q0103 e Q0104 pendentes; execução encerrada sem processo de API ativo ou lock residual.
- Registro: `artefatos/checkpoints/bloco_2026-10-15_04.json`. Pronto para revisão e commit; a próxima execução tentará novamente Q0103 e Q0104 dentro do limite do próximo bloco.

### Quinto bloco do módulo 4 concluído em 15 de outubro de 2026

- Retomada autorizada pelo usuário após o commit `d902476`; vinte chamadas em uma única invocação, sem iniciar outro bloco.
- Vinte sucessos: Q0103 e Q0104 aceitas na segunda tentativa e dezoito novos IDs, Q0117 a Q0134. Nenhuma falha de API ou validação local neste bloco.
- Estado acumulado: 147 sugestões tecnicamente válidas, sendo 146 sucessos nos recibos originais e a revalidação anterior de Q0005. Restam 212 questões sem recibo; nenhuma falha técnica atual pendente entre as processadas.
- Consumo do bloco: 606.116 tokens informados nas vinte respostas, incluindo as segundas tentativas de Q0103 e Q0104. O consumo ausente nas três falhas HTTP 503 anteriores permanece identificado.
- Dos 129 recibos anteriores, 127 permaneceram byte a byte idênticos. Q0103 e Q0104 mantêm integralmente os objetos das primeiras tentativas no histórico, inclusive checksum e consumo. O derivado de Q0005, código, modelo, prompt, política e validadores permanecem iguais.
- Suíte offline: 213 testes, 212 aprovados e um pulado por limitação de privilégio do Windows. CLI encerrada com código zero, sem processo de API ativo ou lock residual.
- Registro: `artefatos/checkpoints/bloco_2026-10-15_05.json`. Pronto para revisão e commit; a próxima execução avançará aos IDs sem recibo, começando em Q0135.

### Primeiro bloco do módulo 4 concluído em 16 de outubro de 2026

- Retomada autorizada pelo usuário após o commit `b5b2cb2`; vinte chamadas no total, incluindo as retomadas após indisponibilidade do provedor.
- Quinze sucessos: Q0135, Q0136, Q0138 a Q0141 e Q0143 a Q0151. Q0137 e Q0142 já estavam no piloto. Cinco falhas HTTP 503 ocorreram em Q0135 (duas), Q0145, Q0149 e Q0151; todas foram superadas nas retomadas e permanecem no histórico.
- As seis invocações fizeram 1, 1, 9, 5, 3 e 1 chamadas, respeitando o saldo do limite agregado de vinte. Nenhuma falha local de validação neste bloco.
- Estado acumulado: 162 sugestões tecnicamente válidas, sendo 161 sucessos nos recibos originais e a revalidação anterior de Q0005. Restam 197 questões sem recibo; nenhuma falha técnica atual pendente entre as processadas.
- Consumo do bloco: 451.328 tokens conhecidos nas quinze respostas válidas. As cinco falhas não informaram uso; somadas às três anteriores, são oito tentativas com consumo desconhecido. O lote acumula 177 tentativas e 5.093.357 tokens informados.
- Os 147 recibos anteriores e o derivado de Q0005 permaneceram byte a byte idênticos. Código, modelo, prompt, política, validadores e fontes locais permanecem iguais.
- Identificada diferença preexistente de fins de linha de `temas.csv` entre HEAD e fonte local, embora o arquivo local coincida com o manifesto. Correção do índice validada em ambiente temporário e documentada em `RETOMADA.md` para o commit do usuário; fonte e índice reais não foram alterados.
- Suíte offline: 213 testes, 212 aprovados e um pulado por limitação de privilégio do Windows. Última CLI encerrada com código zero, sem processo de API ativo ou lock residual.
- Registro: `artefatos/checkpoints/bloco_2026-10-16_01.json`. Pronto para revisão e commit; a próxima execução avançará aos IDs sem recibo, começando em Q0152.

### Módulo 4 concluído em 16 de outubro de 2026

- O usuário autorizou concluir as 197 questões restantes em uma continuação, substituindo as pausas a cada vinte chamadas. A base era o commit `6b86acd`, com 162 respostas válidas.
- Foram 227 novas chamadas em 29 invocações internas: 197 sucessos, vinte falhas HTTP 503 e dez rejeições locais, todas recuperadas. Intervalo de dez segundos entre chamadas e esperas após indisponibilidade; nenhuma alteração de modelo, prompt, política ou validador.
- As dez falhas locais atingiram Q0171, Q0197, Q0208, Q0209, Q0215, Q0254, Q0322, Q0324, Q0339 e Q0345. Sete repetiram temas entre extras e alternativas; três alteraram ou juntaram trechos de evidência. Todas passaram na segunda tentativa, preservando a resposta rejeitada e seu consumo.
- Estado final: 359 sugestões tecnicamente válidas, sendo 358 sucessos originais e a revalidação anterior de Q0005; zero falhas atuais e zero IDs sem recibo. Os 162 recibos anteriores e o derivado de Q0005 permaneceram byte a byte idênticos.
- Consumo da continuação: 6.257.155 tokens informados em 207 tentativas; vinte falhas HTTP 503 sem metadados. Total do lote: 404 tentativas, 11.350.512 tokens informados e 28 tentativas com uso desconhecido. O piloto v2 já está incluído; revalidação offline não é chamada.
- Tempo de relógio: 87 min 31,91 s, das 10:16:03 às 11:43:35 em São Paulo. Duração somada das chamadas: 2.355,46 s, sem contar intervalos, esperas e processamento local.
- Suíte desta retomada: 213 testes, 212 aprovados e um pulado por privilégio do Windows, em 46,556 s. Conferência final independente dos 359 recibos, históricos, fontes e revalidação aprovada; executor encerrado com código zero e sem lock residual.
- A diferença de fins de linha de `temas.csv` no Git continua pendente. O arquivo local está intacto e coincide com o manifesto; o comando para preparar seus bytes exatos no índice está em `RETOMADA.md`.
- Registros: `artefatos/checkpoints/conclusao_modulo4_2026-10-16.json` e `artefatos/experimentos/conclusao-lote-v2-2026-10-16.json`. Módulo 4 pronto para revisão e commit do usuário. A aplicação da política, a auditoria e as entregas finais não foram iniciadas nesta continuação.

### Módulo 5A concluído em 16 de outubro de 2026

- Base Git `d22435a`; exportação offline sobre as 359 sugestões válidas. Modelo Gemini 3.5 Flash-Lite, prompt de classificação v2 e política v1 preservados. Nenhuma nova chamada Gemini.
- A política produziu 78 publicações, 273 revisões e oito candidatos a `fora`. Leitura separada por IA e adjudicação documentadas confirmaram quatro ausências de tema e encaminharam quatro questões para revisão com tema sugerido. Resultado congelado: 78 `publicar`, 277 `revisar`, quatro `fora`; cobertura observada de 21,73%, precisão ainda não avaliada.
- Q0039, Q0113, Q0142 e Q0168 ficaram `fora`. Q0154 → 5135, Q0261 → 5136, Q0298 → 5222 e Q0358 → 5133 seguem para `revisar`, com incertezas preservadas. Os 78 publicados não mudaram durante essas revisões.
- Contratos estendidos para registrar tema encontrado na revisão de `fora`, sempre com `requer_revisao: true`; trilha mantém resposta original, correção, política e origem da confiança. Saída completa só é reutilizada quando byte a byte idêntica; alterações exigem nova pasta.
- CLI integrada para decisões, preparação da auditoria e avaliação. Os dois comandos de auditoria foram testados apenas com dados sintéticos. Nenhuma seleção ou referência real da auditoria foi produzida.
- Suíte: 233 testes, 232 aprovados e um pulado por privilégio do Windows, em 71,644 s. Exportação idempotente sem regravar arquivos; reprodução em pasta temporária com quatro produtos idênticos. CSV na raiz idêntico ao congelado.
- Os 359 recibos, Q0005 revalidada, fontes, prompt e política permaneceram íntegros. Ajuste de fins de linha de `temas.csv` aplicado ao índice real, preservando a fonte local; precisa entrar neste commit. Acrescentado `-text` para o CSV da raiz.
- Registros: [decisões e método](DECISOES_V1.md), [checkpoint 5A](../artefatos/checkpoints/modulo5a_2026-10-16.json), `artefatos/decisoes-v1/` e `artefatos/revisao_fora-v1/`. Pronto para revisão e commit do usuário.
- Próximo módulo: avaliação dos publicados. Há cinco publicados no desenvolvimento e 73 no restante; o protocolo de censo mais `min(80,N)` levará a revisar todos os 78. A referência continuará sendo provisória e produzida por IA, sem equivaler a validação jurídica.

### Módulo 5B concluído em 16 de outubro de 2026

- A regra registrada produziu censo das 78 decisões `publicar`: cinco do desenvolvimento e 73 restantes. Três agentes revisaram 26 questões cada sem consultar sugestões Gemini; referências e fontes foram congeladas antes da comparação. Nenhuma nova chamada Gemini.
- Resultado: 77 coincidências exatas, uma divergência em Q0180, zero correspondências apenas pai/filho e zero inconclusivos. Concordância condicional de `77/78 = 98,7179%` frente à referência de IA, sem comprovação de precisão jurídica de 95%.
- O intervalo condicional `[77/78,77/78]` reflete censo, sem incerteza amostral. Não inclui erro da referência de IA, desempenho futuro ou qualidade dos extras e das decisões `revisar` e `fora`.
- Sensibilidade exploratória posterior: tratar as referências com múltiplos temas de Q0009, Q0088 e Q0187 como não confirmadas produz `74/78 = 94,87%`, mantendo o denominador. Resultado principal, referências e CSV preservados.
- Incidente de Q0179 registrado no dossiê do bloco 01: exposição incidental a trecho de gabarito de alternativas em busca, não aos rótulos temáticos reservados. Não é possível excluir influência; a questão permanece no denominador.
- Diagnóstico reproduzível de cobertura: 277 revisões, com sinais sobrepostos de alternativas (232), baixa confiança (218), revisão solicitada (193), tema ambíguo (60), extras acima do limite (32) e correção de `fora` (4). Grupos exclusivos: 41 só alternativas, sete só baixa confiança e um só ambiguidade; 228 têm múltiplos sinais.
- Suíte final: 237 testes, 236 aprovados e um pulado por privilégio de symlink no Windows, em 139,823 s. Modelo, prompt, política e CSV de 359 decisões preservados; cobertura mantida em 78/359 = 21,73%.
- Registros: [auditoria e limites](AUDITORIA_V1.md), [diagnóstico de cobertura](COBERTURA_V1.md), [avaliação](../artefatos/avaliacao-v1/relatorio_avaliacao.json), [referências congeladas](../artefatos/revisao_auditoria-v1/manifesto_revisoes.json) e [checkpoint 5B](../artefatos/checkpoints/modulo5b_2026-10-16.json). No encerramento do 5B, o próximo passo recomendado era o experimento 5C, concluído no registro seguinte.

### Módulo 5C concluído em 16 de outubro de 2026

- Intervenção, seleção e critérios registrados previamente na [política v2](../config/politica_v2.json) e no [pré-registro](../artefatos/experimento-cobertura-v2/preregistro.json). Escopo de 41 questões cujo único sinal de revisão era `temas_alternativos`, com fontes, decisões e referências v1 preservadas.
- Foram realizadas 50 chamadas Gemini, com 37 sucessos técnicos finais e quatro falhas após esgotar as tentativas permitidas: Q0086, Q0119, Q0194 e Q0322. Há 1.134.040 tokens conhecidos e doze tentativas sem uso informado; o consumo dos agentes Codex não está incluído e não é conhecido por esses recibos.
- O segundo passe produziu 23 propostas que mantinham central e conjunto de extras originais e passavam pela política base. As propostas foram congeladas antes de consultar as referências cegas dos 41 selecionados. Confiança original preservada, sem recalibração por concordância.
- Resultado negativo: 20/23 coincidências estritas, ou 86,9565%, abaixo de 95%. A regra hierárquica v1 encontrou 21 coincidências exatas, uma relação pai/filho e uma divergência em Q0024: 22/23 = 95,6522%. Essa taxa secundária não atende ao critério estrito e não elimina a exigência de zero divergências explícitas. Nenhuma proposta foi adotada, mantendo as 23 no denominador.
- Q0180 foi encaminhada separadamente a `revisar`, por achado conhecido da auditoria v1, preservando central, extras e confiança. Resultado final v2: 77 `publicar`, 278 `revisar` e quatro `fora`; cobertura de 77/359 = 21,4485%. A retirada não constitui ganho de precisão validado.
- Suíte final: 270 testes, 269 aprovados e um pulado por privilégio de symlink no Windows, em 116,632 s. Reprodução offline das propostas e decisões em novas pastas, com validação dos hashes e preservação das saídas congeladas.
- Registros: [método e limites do 5C](EXPERIMENTO_COBERTURA_V2.md), [propostas congeladas](../artefatos/experimento-cobertura-v2/propostas/manifesto_propostas.json), [resultado](../artefatos/decisoes-v2/relatorio_experimento.json) e [manifesto v2](../artefatos/decisoes-v2/manifesto_decisoes.json). A referência é provisória de IA, e a avaliação foi usada para escolher a versão: evidência de desenvolvimento, sem comprovação de precisão jurídica ou validação independente da versão escolhida.
- Ponto de parada: revisão e commit do usuário. Próxima etapa: módulo 6, com previsão, relatório e memo; nenhuma dessas entregas foi iniciada neste fechamento.

## Módulo 6 concluído em 16/10/2026

- Base Git: `94066155ae648f11aacfcceabdff0223c4a9c2d2`, inicialmente limpa. Nenhuma alteração nas 359 decisões, fontes ou referências anteriores.
- Entrega: [previsão](../previsao.txt), [relatório de cinco páginas](../relatorio.pdf), [Markdown equivalente](../relatorio.md), com memo na quinta página, e [evidências reproduzíveis](../artefatos/entrega-v2/evidencias.json).
- Previsão de precisão subjetiva: 73/77 = 94,8052%; intervalo de cenários zero a oito erros, 89,6104% a 100%, sem calibração ou limite garantido. Cobertura contada: 77/359 = 21,4485%.
- Produção proposta para 50 mil questões/semana, preços oficiais datados, simulação de custo por questão, capacidade de revisão, integração com importação/reportes e critério futuro de homologação por especialistas. A projeção não representa arquitetura implementada ou custo total observado.
- Gerador offline com conferência dos IDs esperados e históricos de recibos; PDF opcional com dependências isoladas. Suíte final: 278 testes, 277 aprovados e um pulado por permissão de symlink no Windows, em 108,497 s.
- Quatro produtos documentais reproduzidos byte a byte em pasta temporária com rede e `.env` bloqueados. PDF final renderizado e revisado nas cinco páginas. A revisão independente confirmou requisitos e métricas e identificou a proteção adicional contra recibos faltantes, já corrigida e testada.
- Registro: [método documental](ENTREGA_DOCUMENTAL.md) e [checkpoint 6](../artefatos/checkpoints/modulo6_2026-10-16.json). Nenhuma chamada Gemini, commit, push ou envio externo. Próxima etapa após revisão e commit: módulo 7, reprodução completa em checkout limpo e conferência final.

## Registro de execução

### Preparação concluída em 14 de outubro de 2026

- Comando: `python -m classificacao_topicos preparar`.
- Produtos: `artefatos/preparacao/`, incluindo dados preparados, diagnóstico, árvore, avisos e manifesto SHA-256.
- Conferidos 359 IDs únicos de questões e 377 registros da árvore, com quatro raízes, 375 registros ativos e dois inativos.
- Os campos textuais passaram de 443.917 para 327.922 caracteres após a remoção de marcação e a normalização de espaços. Nenhum enunciado ou alternativa ficou vazio.
- Há 94 comandos vazios no original e 101 após a preparação, pois sete continham apenas marcação de apresentação. Isso é um sinal estrutural, não uma decisão de classificação.
- Testes confirmam preservação dos originais e igualdade dos produtos em duas execuções com as mesmas entradas. Regressões específicas cobrem o HTML do Word em Q0099 e o comando substantivo de Q0107.
- A árvore não contém ciclos, pais ausentes ou divergências entre caminhos declarados e reconstruídos. Títulos repetidos permanecem separados.
- Execução local, sem chamadas a modelos e sem instalação de dependências.

### Piloto preparado em 14 de outubro de 2026

- Comando: `python -m classificacao_topicos preparar-piloto`.
- Produtos: `artefatos/piloto/entradas.jsonl` e `manifesto_piloto.json`, com vinte IDs, motivos de seleção, semente e hashes dos prompts e da preparação.
- Dez casos deliberados: Q0020, Q0036, Q0078, Q0099, Q0107, Q0137, Q0142, Q0219, Q0239 e Q0284. Dez complementares por diversidade estrutural: Q0059, Q0014, Q0309, Q0169, Q0218, Q0244, Q0296, Q0337, Q0179 e Q0277.
- Cada prompt contém o catálogo completo dos 375 temas ativos e a questão com enunciado, comando e alternativas. Metadados de origem ficam fora do prompt como hipótese inicial para reduzir influência de classificações anteriores.
- Prompts têm aproximadamente 86 a 90 mil caracteres cada. Isso não é uma contagem de tokens; consumo real será registrado a partir dos recibos do provedor.
- Cliente REST, validação de respostas, persistência, retomada e histórico de tentativas verificados com respostas simuladas. Nenhuma chamada real executada; qualidade temática ainda não medida.
- Verificação final: `python -B -m unittest discover -s tests -v`, com 90 testes descobertos, 89 aprovados e um pulado por falta de privilégio do Windows para criar links simbólicos reais. A rejeição de links também está coberta por teste simulado aprovado. Essa suíte verifica o software; não mede precisão temática.
- O piloto é conjunto de desenvolvimento. Os 339 itens restantes também foram inspecionados anteriormente e não serão descritos como dados nunca vistos.

### Integração e dois pilotos concluídos em 14 de outubro de 2026

- Projeto gratuito e cotas confirmados pelo usuário; chave guardada no `.env` ignorado pelo Git.
- Correção do enum REST de resposta JSON; indisponibilidade HTTP 503 nos modelos 3.8 Flash e 3.6 Flash. O 3.5 Flash-Lite respondeu ao teste sintético e foi usado nos dois pilotos.
- V1: 20 sugestões válidas em 20 chamadas; v2: 20 em 21 chamadas, incluindo uma resposta rejeitada por evidência sem correspondência literal na validação então vigente.
- A v2 sinalizou dez casos para revisão, ante três na v1. Essa diferença orientou a escolha do prompt, sem ser apresentada como ganho de precisão medido.
- Resultados e limites em `docs/PILOTO_V1.md`; recibos e comparações em `artefatos/execucoes/` e `artefatos/analises/`.
- Lote completo preparado com 359 IDs; os 20 recibos da v2 foram copiados sem alteração e validados para reutilização. O consumo desses recibos não deve ser somado novamente ao contabilizar o projeto inteiro.
- Política v1 registrada com limiar operacional 0,95, restrições temáticas e exigência de confirmação separada para `fora`. Amostra fixada em até 80 demais publicados, além do censo dos publicados do desenvolvimento.
- Ausência de especialista jurídico confirmada pelo usuário. A referência de avaliação será assistida por IA e sua incerteza não será confundida com a incerteza amostral.
