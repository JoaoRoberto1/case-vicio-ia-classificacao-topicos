# Experimento controlado de cobertura — módulo 5C

O módulo 5C investiga se um segundo passe de classificação consegue resolver a concorrência temática nas **41 questões retidas somente por `temas_alternativos`**, preservando os rótulos originais. A versão 1 continua congelada: 78 decisões `publicar`, 277 `revisar` e quatro `fora`, com cobertura de 78/359 = 21,73%. Sua auditoria encontrou 77/78 correspondências com referência provisória de IA; isso não comprova precisão jurídica de 95%.

O protocolo foi registrado antes da análise dos 41 casos nesta etapa. **O experimento terminou sem adoção das 23 propostas:** houve 20 coincidências estritas e uma divergência explícita, abaixo dos critérios registrados. A versão 2 mantém essas questões em revisão e retém separadamente Q0180, com **77 `publicar`, 278 `revisar` e quatro `fora`**, cobertura de **77/359 = 21,45%**. O módulo termina para revisão e commit antes do relatório.

## Registro e escopo

O [pré-registro](../artefatos/experimento-cobertura-v2/preregistro.json), gravado em `2026-10-16T18:25:46.454159+00:00`, vincula a seleção, a política, os prompts e as fontes por SHA-256. Seu commit-base é `80c4a1593cc9da1bf49a5da98fc35f685983b928` e seu próprio SHA-256 é:

```text
76250308da348336ebc779319319828bf73ff69857ca65a33a4cb1deeee13713
```

A [política v2](../config/politica_v2.json) define a intervenção sobre a [política v1](../config/politica_v1.json). Os [IDs selecionados](../artefatos/experimento-cobertura-v2/ids_selecionados.json) são os 41 casos cuja decisão é `revisar` e cujo único sinal é `temas_alternativos`, conforme o [diagnóstico de cobertura](COBERTURA_V1.md). A seleção não depende dos julgamentos novos. Não se amplia o experimento para os demais retidos, não se reduz o limiar de confiança e não se alteram as quatro decisões `fora`.

Todos os textos já haviam sido inspecionados na exploração anterior. O registro antecede a análise específica desta intervenção, mas não torna o conjunto um teste nunca visto. Os achados e as referências da v1 permanecem históricos; não passam a ser uma validação independente da política ajustada.

## Segundo passe e formação das propostas

O segundo passe usa `gemini-3.5-flash-lite` e o [prompt `desambiguacao-v1`](../prompts/desambiguacao_v1.txt). Cada chamada recebe a questão completa e o catálogo de temas ativos, sem receber a resposta anterior. O prompt distingue o objeto efetivamente cobrado do contexto narrativo, separa conhecimentos adicionais cobrados de assuntos incidentais e exige manter alternativas quando persistir concorrência real pelo tema central.

Uma questão só integra as propostas de publicação quando satisfaz simultaneamente estas condições:

1. O segundo passe é tecnicamente válido e recebe `publicar` pela política base: confiança autodeclarada de pelo menos 0,95, até um extra e ausência dos demais bloqueios da v1.
2. O tema central do segundo passe é exatamente igual ao original.
3. O conjunto de extras do segundo passe é exatamente igual ao original, independentemente da ordem.

A proposta preserva tema central, extras e confiança originais. O segundo passe constitui evidência adicional; sua confiança não substitui nem calibra a confiança exportada. Uma mudança de central ou extras, concorrência persistente, outro bloqueio ou falha técnica mantém a questão em `revisar`. Não se troca o central para aproveitar a confiança atribuída ao tema anterior.

Os recibos novos ficam em `artefatos/execucoes/desambiguacao-v1-35-flash-lite`, separados dos recibos da v1. A execução registrada permite apenas a API gratuita já configurada, sem faturamento autorizado, com intervalo mínimo de dez segundos, até duas tentativas por ID e no máximo 82 chamadas. Esgotadas as tentativas, a falha não gera proposta. Esses números são limites prévios, não consumo observado.

As propostas e sua procedência devem ser congeladas em `artefatos/experimento-cobertura-v2/propostas` antes de o coordenador abrir ou comparar os julgamentos de referência.

## Referência cega e regra de adoção

A referência é um censo dos 41 selecionados, distribuído previamente em dois blocos de 21 e vinte questões. Os revisores Codex seguem o [protocolo de revisão](../prompts/revisao_desambiguacao_v1.txt): recebem somente esse protocolo, as entradas cegas atribuídas e a taxonomia completa. Não recebem sugestões de nenhum passe, propostas, política, referências de outros blocos ou avaliações anteriores. Os julgamentos podem ser produzidos em paralelo à execução, mas não são revelados ao coordenador antes do congelamento das propostas.

Cada revisão mantém o contrato de oito campos da auditoria: ID, temas centrais aceitáveis, presença de tema, situação, justificativa, limitações, tipo da referência e responsável. A origem é `IA_sem_especialista`. Fontes e procedência são registradas separadamente. Quando necessária, a pesquisa consulta conceitos em fontes primárias públicas, sem buscar trechos exatos da questão ou gabaritos; dúvidas, indisponibilidade de fontes e exposições incidentais devem ser registradas.

Seja `K` o número de propostas congeladas. A adoção exige **todas** as condições abaixo:

- `K > 0`.
- Pelo menos 95% das propostas têm coincidência estrita: referência `provisorio`, `sem_tema=false` e lista de temas aceitáveis contendo somente o central original. Em números inteiros, `100 × coincidências_estritas >= 95 × K`.
- Nenhuma proposta é classificada como divergência explícita pela regra hierárquica da auditoria v1, que aceita o mesmo ID ou relação imediata pai/filho no mesmo ramo. Irmãos, ancestrais distantes, ramos distintos e referência provisória sem tema não atendem a essa regra.

Referências inconclusivas, múltiplos temas aceitáveis e coincidências apenas por pai/filho são **não confirmadas no indicador estrito** e permanecem no denominador. A comparação pela regra v1 é relatada separadamente; ela não transforma esses casos em coincidências estritas. O requisito de zero divergências impede compensar uma divergência explícita com os acertos das outras propostas.

A decisão é adotar o lote inteiro de propostas ou não adotar nenhuma. Não se removem individualmente os discordantes após a comparação para elevar a taxa, não se reescrevem referências e não se mudam os critérios durante esta execução. O indicador de adoção usa somente as propostas congeladas; as referências dos demais selecionados não autorizam promoções adicionais neste experimento.

## Tratamento separado de Q0180

Q0180 não pertence ao grupo experimental. A [auditoria v1](AUDITORIA_V1.md) registrou divergência entre o central `5554 — Busca e Apreensão` e a referência `5594 — Prova Ilegal e Prova Ilícita`.

Na versão 2, a política determina `revisar` para Q0180, preservando central, extras e confiança e registrando o motivo. Essa ação vale independentemente da adoção das propostas. É uma retenção decorrente de achado conhecido, sem correção jurídica confirmada. A versão 1 e sua avaliação não são alteradas, e a retirada não conta como acerto novo ou melhoria de precisão validada.

Se `A` propostas forem adotadas, a versão 2 terá `77 + A` publicadas, `278 − A` em revisão e quatro fora. `A` será `K` quando o lote passar pelos critérios, ou zero quando não passar. A cobertura será `(77 + A)/359`; a variação líquida frente à v1 será `(A − 1)/359`. Uma promoção apenas repõe a cobertura original após a retenção de Q0180.

## Preparação, execução e reprodução

Com a preparação e o piloto v2 reconstruídos conforme o README, os comandos abaixo preparam o novo lote e executam somente os IDs registrados:

```powershell
python -B -m classificacao_topicos preparar-lote --preparacao artefatos/preparacao --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-desambiguacao-v1 --prompt prompts/desambiguacao_v1.txt --versao-prompt desambiguacao-v1
python -B -m classificacao_topicos executar-lote --preparacao artefatos/preparacao --lote artefatos/lote-desambiguacao-v1 --saida artefatos/execucoes/desambiguacao-v1-35-flash-lite --ids-arquivo artefatos/experimento-cobertura-v2/ids_selecionados.json --limite 41 --intervalo-segundos 10 --continuar-erros-validacao
```

A preparação monta o lote completo para preservar seus contratos e a identificação dos casos de desenvolvimento. `--ids-arquivo` restringe as chamadas e as contagens ao grupo selecionado, mantendo a ordem do manifesto. O executor valida a pasta de recibos e reutiliza sucessos compatíveis. Falhas locais de validação podem ser registradas enquanto a execução avança; falhas da API interrompem a invocação.

`--limite 41` limita novas chamadas nessa invocação, não estabelece sozinho o teto acumulado de tentativas. Qualquer retomada precisa respeitar o histórico: até duas tentativas por ID e até 82 no total, incluindo chamadas que falharam. Não se deve repetir o comando indiscriminadamente nem substituir os recibos para contornar os limites. O segundo comando realiza chamadas reais quando há IDs pendentes; ele não é necessário para reproduzir cálculos a partir dos artefatos já salvos.

O fechamento deve preservar recibos, histórico de tentativas, propostas, referências, fontes e seus hashes. A avaliação e as decisões v2 têm destino previsto em `artefatos/decisoes-v2`. A reprodução offline deverá conferir propostas, critério de adoção, decisões, contagens e integridade das fontes a partir desses artefatos, sem novas chamadas. Uma nova execução dos modelos pode produzir julgamentos diferentes.

## Limites da evidência

O experimento avalia uma política composta, com segundo passe e revisão assistida por IA. Confiança autodeclarada, concordância entre passes e referência Codex não são calibração nem garantia jurídica. Revisores separados podem compartilhar vieses com o classificador. O censo elimina a incerteza de amostragem dos itens efetivamente avaliados, mas não o erro da referência, e não sustenta previsão para futuras importações.

A escolha de adotar a versão usa a própria avaliação e constitui desenvolvimento. O resultado deve ser descrito como concordância condicional com referência provisória de IA, sem alegação de validação independente posterior à escolha ou comprovação da meta de precisão de 95%. A qualidade dos extras não é medida pelo indicador de tema central, apesar da exigência de igualdade entre os dois passes.

Recibos Gemini permitem registrar chamadas e consumo informado pelo provedor. O pré-registro não autoriza faturamento. O consumo dos agentes Codex e das consultas públicas não é medido nesses recibos; não se deve apresentar o trabalho inteiro como custo computacional zero.

## Resultados e fechamento em 16 de outubro de 2026

Foram realizadas **50 chamadas em treze invocações**: 37 sucessos, doze falhas HTTP 503 e uma resposta rejeitada pelo validador local. As tentativas permanecem nos recibos. Q0086, Q0119, Q0194 e Q0322 esgotaram as duas tentativas e não geraram proposta. Isso não altera a conclusão técnica do módulo 4: suas 359 sugestões válidas continuam preservadas.

O consumo conhecido foi de **1.134.040 tokens**, informado em 38 tentativas; as doze falhas HTTP 503 não informaram uso. A execução decorreu entre 18:28:22 e 18:50:09 UTC, com 21 min 47,67 s de relógio, incluindo pausas e verificações entre invocações. Não é uma medição do esforço humano do projeto. Os treze registros `execucao_*.json` e os recibos distinguem uso informado, falhas e retomadas. O consumo Codex permanece não mensurado.

As regras produziram **23 propostas**, congeladas em [propostas.jsonl](../artefatos/experimento-cobertura-v2/propostas/propostas.jsonl). Os outros dezoito selecionados foram retidos antes de consultar a referência. Seus bloqueios se sobrepõem: nove tiveram extras diferentes entre passes, cinco confiança insuficiente, quatro falha técnica, dois central diferente, dois revisão solicitada, dois alternativas persistentes e um excesso de extras. Essas contagens não devem ser somadas como se fossem grupos exclusivos.

O [registro de congelamento](../artefatos/experimento-cobertura-v2/congelamento_propostas.json) marca 18:50:41 UTC e os hashes dos dois produtos. As 41 referências foram validadas e [congeladas às 18:50:44 UTC](../artefatos/experimento-cobertura-v2/manifesto_referencias.json), antes da comparação. O coordenador não havia aberto esses julgamentos ao congelar as propostas.

| Comparação nas 23 propostas congeladas | Quantidade |
| --- | ---: |
| Coincidência estrita com referência única | 20 |
| Mesmo ID, mas referência com dois temas aceitáveis | 1 |
| Apenas pai/filho imediato | 1 |
| Divergência explícita | 1 |
| Inconclusivos | 0 |

A coincidência estrita foi **20/23 = 86,96%**, abaixo dos 95% exigidos. Pela convenção hierárquica v1, houve 21 coincidências exatas e uma por pai/filho: **22/23 = 95,65%** de concordância condicional. Esse segundo indicador não substitui o critério estrito registrado, e a divergência explícita também impede a adoção.

| Questão | Central preservado nos passes | Referência cega | Consequência no critério estrito |
| --- | --- | --- | --- |
| Q0024 | 4388 — Teorias Criminológicas em Espécie | 4387 — Teorias de Nível Sociológico | Divergência entre nós irmãos; impede adoção do lote |
| Q0130 | 5160 — Roubo | 5160 e 5205 — Penas Restritivas de Direitos | Referência múltipla; não confirmada no indicador estrito |
| Q0293 | 5185 — Prescrição | 5189 — Prescrição da Pretensão Executória | Pai/filho imediato; não confirmada no indicador estrito |

Esses registros descrevem julgamentos provisórios de IA. Em Q0024, a própria referência ressalva a fronteira pouco definida entre os títulos da árvore; a divergência não é uma adjudicação especializada de qual ID está certo. Em Q0130 há dois eixos expressos na questão; em Q0293 a diferença é de granularidade. Justificativas e limitações completas estão na [comparação dos 41 selecionados](../artefatos/decisoes-v2/comparacao_experimento.jsonl).

**Nenhuma proposta foi adotada.** Não se retirou apenas Q0024 ou as três referências não estritas para elevar a taxa. Promover retrospectivamente as vinte coincidências constituiria outra intervenção guiada pelos julgamentos; não foi o experimento registrado. O resultado mostra que a concordância de dois passes, mesmo com o mesmo central e extras, não basta para liberar este grupo automaticamente sob o critério escolhido.

### Versão final deste módulo

Q0180 passou de `publicar` para `revisar` pelo achado conhecido da auditoria v1. Seu central, extras e confiança foram preservados. Essa é a **única alteração de decisão entre as versões**; as outras 358 linhas mantêm os mesmos campos. O [antes/depois](../artefatos/decisoes-v2/alteracoes.jsonl) identifica a intervenção e seu responsável.

| Versão | Publicar | Revisar | Fora | Cobertura |
| --- | ---: | ---: | ---: | ---: |
| v1 histórica | 78 | 277 | 4 | 21,73% |
| v2 selecionada | 77 | 278 | 4 | 21,45% |

A redução de uma publicação equivale a **0,28 ponto percentual**. A tentativa de ampliar cobertura não foi incorporada; a v2 incorpora somente a retenção de Q0180. Não se apresenta a retirada do caso conhecido como novo acerto nem se recalcula uma precisão aparentemente perfeita a partir das referências já vistas.

O [CSV da raiz](../publicacao.csv) é cópia da [v2 congelada](../artefatos/decisoes-v2/publicacao.csv), com SHA-256 `2f9ca44feef9998810c18bfb49933737470b758bcde7697b0c8673c531d6d53e`. O [manifesto v2](../artefatos/decisoes-v2/manifesto_decisoes.json) preserva a ligação com a base, política, propostas, recibos e referências. A v1, sua auditoria e os 359 recibos originais continuam intactos.

### Procedência e verificações

Os dossiês [01](../artefatos/experimento-cobertura-v2/fontes/bloco_01.json) e [02](../artefatos/experimento-cobertura-v2/fontes/bloco_02.json) registram fontes, dificuldades de acesso, leitura e recorte temporal. No bloco 02, uma busca por obra primária de Roxin retornou incidentalmente um trecho de questão e referência bibliográfica em material de concurso. Não apareceu resposta correta no trecho; a página não foi aberta nem usada. O incidente foi preservado, sem afirmar que toda influência é impossível. Não houve acesso aos rótulos temáticos reservados da organização.

A suíte final executou **270 testes: 269 aprovados e um pulado** por privilégio de link simbólico no Windows, em 116,632 s. Os testes verificam seleção restrita, denominadores, regras de adoção, confiança preservada, adulteração, reprodução e congelamento das propostas antes da leitura das referências. A revisão de código identificou e corrigiu uma lacuna nessa última proteção antes da comparação real.

Os cálculos e os produtos são reproduzidos sem chave ou rede:

```powershell
python -B -m classificacao_topicos.experimento_cobertura propor --saida artefatos/propostas-v2-reproduzidas
python -B -m classificacao_topicos.experimento_cobertura concluir --saida artefatos/decisoes-v2-reproduzidas
python -B -m unittest discover -s tests -q
```

Em checkout novo, primeiro reconstruir a preparação e o lote de desambiguação pelo comando de preparação acima. As referências salvas já têm manifesto de congelamento; não é necessário chamar modelos ou refazer julgamentos. As saídas existentes só são reutilizadas quando idênticas; divergências exigem outra pasta. O comando `congelar-referencias` documenta a etapa original e valida as propostas antes de abrir referências, mas não é requisito para reproduzir o fechamento com o manifesto salvo.

O [checkpoint 5C](../artefatos/checkpoints/modulo5c_2026-10-16.json) reúne hashes, consumo, verificações e o ponto de parada. Próxima etapa: módulo 6, com `previsao.txt`, relatório de até cinco páginas e memo, distinguindo resultados históricos, seleção da versão e incerteza da referência. Nenhum commit ou push foi realizado pelo assistente.
