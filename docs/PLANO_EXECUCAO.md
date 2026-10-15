# Plano de execução do case

O trabalho está organizado em sete módulos, com 18 horas estimadas de esforço e duas horas de reserva. O objetivo é maximizar a cobertura com precisão de pelo menos 95% nas publicadas, sustentando a previsão com evidências. Essa meta ainda não foi validada.

| Módulo | Esforço previsto | Entrega e critério de conclusão | Estado |
| --- | --- | --- | --- |
| 1. Dados e árvore | 2 h | Preparação reproduzível das 359 questões e dos 377 registros, originais preservados, verificações de conteúdo e hierarquia | Concluído |
| 2. Protocolo de avaliação | 1,5 h | Piloto, critérios de revisão, cálculo de métricas e registro das ambiguidades | Definido; referência por IA, censo do desenvolvimento e amostra de até 80 demais publicados |
| 3. Primeira versão e piloto | 3 h | Classificador simples, respostas estruturadas e análise de erros do piloto | Dois pilotos reais concluídos; v2 selecionada |
| 4. Execução completa | 1,5 h | Resultados persistidos para as 359 questões, sem perdas e com retomada | Terceiro bloco de 15/10 concluído: 109 válidas, Q0083 rejeitada, 249 sem recibo; aguarda revisão/commit |
| 5. Auditoria e decisão | 5 h | Revisões registradas, política de publicação e previsão fundamentada | Política registrada; módulos offline preparados, integração e aplicação real pendentes |
| 6. Relatório e produção | 3 h | Até cinco páginas, com diagnóstico, raciocínio, proposta de escala e memo | Pendente |
| 7. Reprodução e entrega | 2 h | Arquivos finais verificados, README executável e preparação para defesa | Pendente |

O esforço previsto não representa tempo já gasto. Limites de API e achados da avaliação podem exigir ajustes. A conclusão de um módulo depende de seus artefatos e verificações.

## Pontos de parada e commits

O estado completo da pausa está em [RETOMADA.md](RETOMADA.md). A partir deste checkpoint, avançar uma etapa por vez e informar quando ela estiver pronta para revisão e commit. Não iniciar automaticamente a etapa seguinte.

| Etapa de retomada | Tamanho do bloco | Ponto de parada | Commit sugerido |
| --- | --- | --- | --- |
| Base atual dos módulos 1 a 3 | Código, documentação e evidências já salvos | Suíte offline aprovada, originais íntegros, nenhum processo de API ativo | `feat: prepara dados e conclui pilotos de classificacao` |
| Módulo 4 | Até 20 novas chamadas por bloco, incluindo retomadas | Recibos persistidos e resumo conferido; erros permanecem explícitos | `data: registra progresso do lote de classificacao` |
| Módulo 4 concluído | Resolver pendências técnicas | Todos os 359 recibos válidos | `data: conclui lote de classificacao v2` |
| Módulo 5A | Integrar CLI, aplicar política e confirmar propostas fora | CSV completo e decisões congeladas, sem iniciar revisão da amostra | `feat: congela decisoes e prepara auditoria` |
| Módulo 5B | Revisar amostra e calcular estimativa | Referências e métricas rastreáveis, limitações explícitas | `eval: registra auditoria e previsao` |
| Módulo 6 | Relatório de até cinco páginas e memo | Texto e números revisados | `docs: adiciona relatorio do case` |
| Módulo 7 | Reprodução em checkout limpo | Entrega final verificada | `chore: valida entrega reproduzivel` |

Os commits são sugestões para o usuário; nenhum foi criado pelo assistente. Os módulos de decisão, auditoria e estatística já escritos pertencem à base de software, mas sua implementação não significa conclusão da avaliação real.

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
