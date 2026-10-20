# Plano de execução da etapa complementar

O projeto terá cinco módulos, cada um com resultados verificáveis e uma parada para revisão e commit. A meta é entregar um classificador local reproduzível e uma estimativa de qualidade sustentada pelas 100 referências humanas, respeitando a proibição de LLMs escolherem ou validarem temas.

**Estado atual: módulo 1 concluído em 20/10/2026, pronto para revisão e commit.** Os módulos 2 a 5 ainda não foram executados. O prazo informado pela recrutadora é 22/10/2026 às 14h, no horário de São Paulo. A extensão mencionada na mensagem não foi solicitada nem concedida.

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

**Retomada:** iniciar o módulo 2 a partir dos dados preparados e das partições versionadas. Sugestão de mensagem de commit: `Prepara dados e protocolo de avaliação da etapa complementar`.

## Módulo 2 Primeiro classificador local

Obter cedo uma referência mensurável para orientar os próximos experimentos.

- [ ] Implementar busca lexical sobre os textos e a árvore, com candidatos ativos.
- [ ] Extrair leis e artigos por regras auditáveis e avaliar seu uso como sinais.
- [ ] Definir atributos, grades de parâmetros, calibrador e seleção interna antes de abrir resultados externos.
- [ ] Produzir medições internas fora da amostra; abrir a avaliação externa somente depois de fixar toda a receita de seleção prevista.
- [ ] Registrar erros, suporte por grupo e curva de precisão versus cobertura.

**Critério de conclusão:** primeira receita executável sem chamadas a modelos de linguagem, com decisões e medições reproduzíveis. Escores de similaridade ainda não validados como probabilidade devem permanecer identificados como escores.

**Parada:** revisar as medições internas e os riscos do primeiro classificador; salvar configuração e resultados para commit.

## Módulo 3 Experimentos de melhoria

Comparar poucas alternativas com o mesmo protocolo e preservar tanto os resultados positivos quanto os negativos.

- [ ] Comparar até três famílias: lexical, lexical com leis e recuperação híbrida com embeddings previamente calculados.
- [ ] Testar exemplos humanos semelhantes como sinal adicional, usando somente rótulos de treinamento de cada partição.
- [ ] Se houver preparação com modelos, versionar origem, versão, instruções, parâmetros, custos conhecidos e artefatos gerados.
- [ ] Medir a contribuição dos sinais e respeitar a seleção de receita na validação interna.
- [ ] Documentar mudanças orientadas por resultados externos como exploratórias.

**Critério de conclusão:** seleção rastreável, sem usar os resultados externos para escolher o vencedor e depois apresentá-los como avaliação imparcial desse vencedor.

**Parada:** revisar comparação, custo e complexidade; congelar a receita para calibração e commit.

## Módulo 4 Calibração e decisões

Transformar a saída do classificador em uma política de publicação, revisão e identificação de questões fora da taxonomia.

- [ ] Calibrar a chance de acerto e selecionar o limiar com dados internos ao treinamento de cada avaliação externa.
- [ ] Avaliar externamente a receita completa e fixada, sem alterar seus componentes após observar os resultados.
- [ ] Medir precisão, cobertura, quantidade publicada e incerteza sobre a precisão.
- [ ] Impedir que disciplinas ou temas genéricos sejam usados para ampliar artificialmente a publicação.
- [ ] Tratar `fora` como ausência de tema adequado, com evidência própria; baixa confiança deve levar a revisão.
- [ ] Ajustar a receita final com as 100 referências e gerar as decisões das 659 questões.
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
