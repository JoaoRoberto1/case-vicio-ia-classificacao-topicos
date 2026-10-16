# Auditoria local da versão 1

O módulo 5B avaliou todas as **78 decisões `publicar`** do CSV congelado. A comparação encontrou **77 correspondências exatas, uma divergência e nenhum julgamento inconclusivo**, resultando em **77/78 = 98,72% de concordância condicional com a referência de IA**. A cobertura continua em **78/359 = 21,73%**.

Esse resultado não comprova precisão jurídica de 95%. As referências foram produzidas por IA, sem especialista e sem os rótulos temáticos reservados da organização. O censo elimina a incerteza de amostragem dessa população, mas não elimina erros do revisor nem erros compartilhados com o classificador.

## Versão e procedimento

O trabalho partiu do commit `69c512be315cb7502c82391a6298c474bc39ef65`. O CSV avaliado tem SHA-256 `fd6d504169d86c4002ed27ac892a5080f16c4533c27e4bf80daf6de501dd9ca3`. Modelo, prompt, política, recibos e decisões da versão 1 foram preservados.

O protocolo fixado antes da auditoria prevê censo dos publicados do desenvolvimento e amostra de `min(80,N)` demais publicados, com semente `2026101401`. Como o segundo estrato tem 73 itens, a aplicação dessa regra também resultou em censo. A distinção entre desenvolvimento e restante foi mantida; os cinco casos do desenvolvimento já participaram do piloto.

| Estrato | Publicadas | Revisadas | Correspondências | Divergências | Inconclusivas |
| --- | ---: | ---: | ---: | ---: | ---: |
| Desenvolvimento | 5 | 5 | 5 | 0 | 0 |
| Restante | 73 | 73 | 72 | 1 | 0 |
| Total | 78 | 78 | 77 | 1 | 0 |

A seleção e seus hashes estão no [manifesto da auditoria](../artefatos/auditoria-v1/manifesto_auditoria.json). O pacote para revisão contém ID, enunciado, comando e alternativas, acompanhado da taxonomia completa. Temas, confiança, motivos e respostas Gemini não entraram nos blocos enviados aos revisores.

Três agentes de IA em contextos separados receberam 26 questões cada, na ordem da seleção congelada. Cada um leu o catálogo completo, consultou fontes públicas quando necessário e produziu referências fundamentadas, identificadas como `IA_sem_especialista`. A distribuição foi feita antes das revisões, sem usar o tema atribuído ou o resultado da comparação. Os agentes não receberam o histórico desta conversa.

O [protocolo de revisão](../prompts/revisao_auditoria_v1.txt), a [distribuição](../artefatos/revisao_auditoria-v1/distribuicao.json), as referências e os dossiês de fontes foram registrados. Os 78 registros foram validados e [congelados antes da comparação](../artefatos/revisao_auditoria-v1/manifesto_revisoes.json). Nenhuma referência foi reescrita depois para elevar concordância.

O módulo não fez chamadas Gemini nem acessou `.env`. O consumo dos agentes Codex e das consultas públicas não é medido pelos recibos Gemini e permanece desconhecido.

## Comparação e divergência

A regra registrada aceita o mesmo ID ou relação imediata pai/filho no mesmo ramo. Irmãos e ancestrais distantes não contam como acerto. Não houve correspondências apenas por pai/filho nesta avaliação. Extras não corrigem um tema central divergente.

| Questão | Central do classificador | Referência cega | Resultado |
| --- | --- | --- | --- |
| Q0180 | 5554 — Busca e Apreensão | 5594 — Prova Ilegal e Prova Ilícita | Divergência de ramo |

A justificativa cega de Q0180 priorizou a avaliação da licitude da prova; o classificador priorizou o meio de obtenção. O ID 5594 já aparecia como extra na resposta do classificador, mas a métrica considera o tema central. Esse é um achado de distinção entre contexto e objeto cobrado, não uma adjudicação jurídica especializada. O CSV original continua preservado, inclusive nessa questão.

As 78 comparações, os caminhos e as justificativas estão em [comparacao_auditoria.csv](../artefatos/avaliacao-v1/comparacao_auditoria.csv). O [relatório de avaliação](../artefatos/avaliacao-v1/relatorio_avaliacao.json) contém os cálculos, estratos e hashes das fontes.

## Referências com mais de um tema e sensibilidade

Três referências aceitaram dois temas centrais, com justificativas produzidas antes de conhecer o resultado:

| Questão | IDs aceitos | Motivo registrado para a pluralidade |
| --- | --- | --- |
| Q0009 | 5159 e 5158 | Tipificação patrimonial e disposições gerais que tratam da imunidade |
| Q0088 | 4389 e 4381 | Comparação expressa entre vitimologia e objeto da criminologia |
| Q0187 | 5209 e 5201 | Efeitos da condenação e regime da pena privativa de liberdade |

As três coincidiram com um dos IDs aceitos. A lista não foi ampliada após a comparação. Ela não deve ser interpretada como gabarito oficial: a organização pode exigir um único centro em um desses casos.

Uma **análise exploratória adicional, definida após observar os resultados**, trata essas três correspondências como não confirmadas, mantendo as 78 questões no denominador. Nessa hipótese, a proporção seria **74/78 = 94,87%**. O cálculo está em [sensibilidade-referencia-v1.json](../artefatos/analises/sensibilidade-referencia-v1.json).

Essa hipótese não altera o resultado principal, as referências ou o CSV e não prova que os três casos estão errados. Também não é intervalo de confiança nem limite validado da precisão jurídica. Ela mostra que a conclusão sobre a meta depende dos critérios e da confiabilidade da referência.

## Limitações de procedência e incerteza

Durante a revisão de Q0179, uma busca por fonte primária retornou incidentalmente um trecho de justificativa oficial de gabarito de alternativa. O PDF não foi aberto; houve exposição ao trecho apresentado pelo buscador, e não se pode garantir ausência de influência. O item permaneceu na avaliação. O incidente, a URL, o momento e as fontes utilizadas estão no [dossiê do bloco 01](../artefatos/revisao_auditoria-v1/fontes/bloco_01.json). Trata-se de gabarito da resposta à questão, não dos rótulos temáticos reservados deste case.

As fontes e limitações dos outros blocos estão nos dossiês [02](../artefatos/revisao_auditoria-v1/fontes/bloco_02.json) e [03](../artefatos/revisao_auditoria-v1/fontes/bloco_03.json), incluindo dificuldades de acesso, descrições pouco informativas e recorte temporal. Revisores separados continuam sendo agentes de IA e podem compartilhar os mesmos vieses ou erros. A ausência de inconclusivos descreve os julgamentos registrados, não certeza de que todas as referências estejam corretas.

Como ambos os estratos foram censitados, os cenários conservador e otimista previstos coincidem: ponto `77/78` e intervalo amostral degenerado `[77/78, 77/78]`. Não existe extrapolação de uma amostra para itens não revisados. O intervalo inclui apenas incerteza amostral, condicionada à referência, e não mede erro dessa referência. A cobertura também é uma contagem conhecida, com intervalo `[78/359, 78/359]`, sem previsão para futuras importações.

Todos os textos haviam sido inspecionados durante a exploração anterior. A separação cega desta revisão reduz a influência das sugestões Gemini, mas não transforma o restante em dados nunca vistos. O resultado avalia apenas o tema central das publicadas; não avalia extras ou o mérito das 277 revisões e quatro decisões `fora`.

## Reprodução e verificações

Com a preparação reconstruída conforme o README, a avaliação é offline:

```powershell
python -B -m classificacao_topicos avaliar-auditoria --preparacao artefatos/preparacao --auditoria artefatos/auditoria-v1 --decisoes artefatos/decisoes-v1 --revisoes artefatos/revisao_auditoria-v1/referencias --saida artefatos/avaliacao-v1-reproduzida
python -B -m classificacao_topicos.diagnostico_cobertura
python -B -m unittest discover -s tests -q
```

Para reproduzir a seleção, use uma nova pasta, pois o comando não substitui um pacote congelado:

```powershell
python -B -m classificacao_topicos preparar-auditoria --preparacao artefatos/preparacao --lote artefatos/lote-v2 --decisoes artefatos/decisoes-v1 --politica config/politica_v1.json --saida artefatos/auditoria-v1-reproduzida
```

Foram verificados 237 testes: 236 aprovados e um pulado por privilégio de link simbólico no Windows, em 139,823 s. O diagnóstico teve testes de sobreposição, duplicatas, adulteração e preservação dos arquivos. O pacote de auditoria foi reproduzido com os mesmos seis produtos, byte a byte. A avaliação foi reproduzida em uma nova pasta com os mesmos dois produtos, usando as mesmas entradas locais; o diagnóstico repetido preservou bytes e data de modificação.

O relatório de avaliação registra caminhos absolutos das fontes locais junto dos hashes. Em outro checkout, esses caminhos podem mudar; o CSV de comparação e as métricas devem permanecer iguais ao reutilizar as mesmas referências. A verificação completa em checkout limpo pertence ao módulo 7. Reproduzir os cálculos com as referências salvas é diferente de garantir que uma nova execução de IA produziria os mesmos julgamentos.

## Próximo passo recomendado

O [diagnóstico de cobertura](COBERTURA_V1.md) identifica 41 questões retidas exclusivamente por temas alternativos. Recomenda-se um módulo 5C de experimento controlado de desambiguação, começando por esse grupo, preservando a versão 1 e registrando antecipadamente a intervenção e a avaliação dos novos publicados. O achado de Q0180 também deve orientar o tratamento do tema central, sem corrigir retroativamente a avaliação atual.

O módulo 5B termina neste ponto para revisão e commit. A previsão final e o relatório dependerão da versão escolhida para entrega. Uma nova política ajustada a partir destes achados não poderá apresentar esta mesma auditoria como validação independente.
