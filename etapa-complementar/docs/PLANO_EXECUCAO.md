# Plano de execução da etapa complementar

O projeto terá cinco módulos, cada um com resultados verificáveis e uma parada para revisão e commit. A meta é entregar um classificador local reproduzível e uma estimativa de qualidade sustentada pelas 100 referências humanas, respeitando a proibição de LLMs escolherem ou validarem temas.

**Estado atual: módulos 1 e 2 concluídos; módulo 2 pronto para revisão e commit em 20/10/2026.** Os módulos 3 a 5 ainda não foram executados. Antes da primeira medição, o protocolo foi revisado para preservar 20 referências para o teste final e usar somente as outras 80 no desenvolvimento. O prazo informado pela recrutadora é 22/10/2026 às 14h, no horário de São Paulo. A extensão mencionada na mensagem não foi solicitada nem concedida.

## Módulo 1 Dados e protocolo de avaliação

Preparar os insumos e definir como os experimentos serão medidos antes de observar resultados do classificador.

- [x] Preservar os anexos oficiais e registrar sua origem e seus hashes.
- [x] Preparar texto, árvore, rótulos humanos e diagnóstico de forma determinística.
- [x] Identificar duplicatas e semelhanças fortes e mantê-las no mesmo grupo de avaliação.
- [x] Fixar semente, partições externas e internas, critérios de acerto e regras contra vazamento.
- [x] Verificar integridade, reprodução e comportamento diante de saída divergente.
- [x] Registrar os testes executados e as limitações encontradas.

**Critério de conclusão:** comandos `preparar` e `verificar` funcionais, produtos consistentes e testes aprovados. Não inclui classificador nem estimativa de precisão.

**Parada:** revisar fontes, manifesto, diagnóstico e [protocolo](PROTOCOLO_AVALIACAO.md); deixar o módulo pronto para commit pelo autor.

**Validação realizada:** 33 testes aprovados em 28,020 segundos; preparação e verificação pela CLI concluídas em 1,333 e 1,587 segundo, respectivamente. As fontes permaneceram idênticas e a reprodução conferiu os seis arquivos gerados. As partições têm cinco testes externos de 20 questões, com três partições internas por treino. A ausência de rótulos recentes permanece registrada como limitação. Evidência: [checkpoint do módulo](../artefatos/checkpoints/modulo1.json).

**Retomada registrada ao concluir o módulo 1:** iniciar o módulo 2 a partir dos dados preparados e das partições versionadas. O módulo 1 e seus artefatos continuam preservados.

## Módulo 2 Primeiro classificador local

Obter cedo uma referência mensurável para orientar os próximos experimentos.

- [x] Implementar busca lexical sobre os textos e a árvore, com candidatos ativos.
- [x] Extrair leis e artigos por regras auditáveis e avaliar seu uso como sinais.
- [x] Fixar atributos, duas receitas e regra de seleção antes da primeira medição; reservar calibração e política de publicação para o módulo 4.
- [x] Produzir medições fora da amostra nas três partições internas das 80 referências; manter as 20 reservadas sem inferência ou avaliação.
- [x] Registrar acertos e erros por comparação programática, suporte por grupo e curva diagnóstica de acerto versus fração retida por escore.

**Critério de conclusão:** primeira receita executável sem chamadas a modelos de linguagem, com sugestões e medições reproduzíveis. Escores de similaridade ainda não validados como probabilidade devem permanecer identificados como escores.

**Parada:** revisar as medições internas e os riscos do primeiro classificador; salvar configuração e resultados para commit.

**Validação realizada:** 87 testes aprovados em duas chamadas (72 + 15), experimento concluído e sete produtos reconstruídos com bytes idênticos. A verificação com rede e leitura de `.env` bloqueadas durou 83,159 segundos. Ambas as receitas acertaram 31/80 referências pelo critério de ramo e 18/80 pelo exato; o desempate fixo selecionou `lexical`. Foram geradas 559 sugestões intermediárias, sem predições para as 20 reservadas. Os resultados ainda não sustentam publicação automática. Evidências: [documentação do módulo](MODULO2_CLASSIFICADOR.md), [métricas](../artefatos/lexical-v1/metricas_desenvolvimento.json) e [checkpoint](../artefatos/checkpoints/modulo2.json).

**Retomada:** iniciar o módulo 3 usando este resultado como referência, com foco na recuperação e ordenação de candidatos. Manter a reserva final fechada e salvar novas receitas em outro diretório. Sugestão de mensagem de commit: `Implementa classificador lexical local e avaliação de desenvolvimento`.

## Módulo 3 Experimentos de melhoria

Comparar poucas alternativas com o mesmo protocolo e preservar tanto os resultados positivos quanto os negativos.

- [ ] Comparar até três famílias: lexical, lexical com leis e recuperação híbrida com embeddings previamente calculados.
- [ ] Medir a contribuição dos exemplos humanos semelhantes, já incluídos no módulo 2, retirando ou variando esse sinal somente nas partições de desenvolvimento.
- [ ] Se houver preparação com modelos, versionar origem, versão, instruções, parâmetros, custos conhecidos e artefatos gerados.
- [ ] Medir a contribuição dos sinais e respeitar a seleção de receita na validação interna.
- [ ] Registrar todas as mudanças orientadas pelas métricas das 80 referências como desenvolvimento exploratório, sem consultar as 20 reservadas.

**Critério de conclusão:** seleção rastreável nas 80 referências, preservando as 20 reservadas para avaliar a receita completa no módulo 4.

**Parada:** revisar comparação, custo e complexidade; congelar a receita para calibração e commit.

## Módulo 4 Calibração e decisões

Transformar a saída do classificador em uma política de publicação, revisão e identificação de questões fora da taxonomia.

- [ ] Calibrar a chance de acerto e selecionar o limiar usando somente as 80 referências de desenvolvimento, com predições fora da amostra e as limitações da seleção explicitadas.
- [ ] Congelar classificador, calibrador e política; avaliar uma única vez nas 20 referências reservadas, sem alterar os componentes após observar os resultados.
- [ ] Medir precisão, cobertura, quantidade publicada e incerteza sobre a precisão.
- [ ] Impedir que disciplinas ou temas genéricos sejam usados para ampliar artificialmente a publicação.
- [ ] Tratar `fora` como ausência de tema adequado, com evidência própria; baixa confiança deve levar a revisão.
- [ ] Após o teste final, reajustar a receita congelada com as 100 referências para as 559 questões sem rótulo; documentar que esse reajuste não recebe outro teste independente. Definir o tratamento rastreável das 100 referências no CSV de 659 linhas, sem medir ressubstituição como desempenho.
- [ ] Calcular a previsão e a cobertura somente sobre as 559 questões avaliadas oficialmente.

**Critério de conclusão:** `publicacao.csv` tecnicamente válido e previsão com método, suporte e limitações explícitos. A meta de 95% não será declarada atingida sem evidência suficiente.

**Parada:** revisar a política, a previsão e os casos limítrofes por critérios técnicos, sem pedir a LLMs julgamentos jurídicos; preparar commit.

## Módulo 5 Entrega e defesa

Fechar o pacote público, verificar a reprodução e preparar a explicação das escolhas.

- [ ] Disponibilizar um comando que regenere o CSV a partir dos anexos e artefatos versionados, sem chamadas a modelos de linguagem.
- [ ] Produzir relatório de até quatro páginas, acomodando o memo de uma página, conforme o enunciado.
- [ ] Explicar diagnóstico, experimentos, calibração, custos, tempo e operação para 50 mil questões por semana.
- [ ] Verificar os arquivos obrigatórios e a reprodução em um ambiente limpo.
- [ ] Preparar roteiro de defesa com resultados, limitações e alternativas descartadas.
- [ ] Revisar o conteúdo público e orientar o envio do link à recrutadora.

**Critério de conclusão:** CSV, previsão, relatório, código e artefatos necessários completos e coerentes, com validação registrada.

**Parada:** revisão final e commit pelo autor. O envio do repositório à recrutadora é uma ação separada.

## Limites de reaproveitamento

O projeto anterior forneceu o parser de texto, a representação da árvore e parte da leitura e preparação das questões. A [procedência do reaproveitamento](../config/reuso_codigo.json) registra o commit e os hashes de origem. Rótulos, votos, decisões e avaliações de IA anteriores não foram incorporados.

Não haverá commit ou push automático. Mudanças de escopo, resultados e próximo ponto de retomada serão registrados ao encerrar cada módulo.
