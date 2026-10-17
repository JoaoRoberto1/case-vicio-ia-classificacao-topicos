# Apresentação e defesa do case

**João Roberto de Oliveira Felix | Roteiro de cinco minutos**

Use os blocos abaixo como fala de estudo. Os tempos são referências para ensaio; as perguntas ficam para a defesa. Deixe abertos o [relatório](../relatorio.pdf), o [CSV final](../publicacao.csv) e a [previsão](../previsao.txt).

## 0:00–0:40 — Problema e resultado entregue

“O problema é classificar questões de concursos jurídicos pelo assunto central, para que o aluno encontre o conteúdo no tópico certo. A meta do case é pelo menos 95% de precisão nas publicadas, com a maior cobertura possível.

Entreguei uma decisão para cada uma das 359 questões: 77 para publicar, 278 para revisar e quatro fora do recorte. A cobertura é 21,45%. A meta de precisão ainda não foi comprovada. A entrega permite investigar as decisões, reproduzir os cálculos e localizar o que precisa de revisão.”

## 0:40–1:30 — Decisões de projeto

“Comecei preservando as fontes e validando textos e árvore. Classifiquei enunciado, comando e alternativas juntos; os campos de origem ficaram fora do prompt porque podem estar errados.

Usei os 375 temas ativos no catálogo completo. Escolhi Gemini 3.5 Flash-Lite porque funcionou no acesso gratuito disponível; não fiz um comparativo que provasse ser o melhor modelo.

Comparei dois prompts nos mesmos vinte casos de desenvolvimento. Escolhi o segundo pela maior sinalização de dúvidas, sem afirmar ganho de precisão. A publicação exige confiança declarada de pelo menos 0,95 e ausência de outros bloqueios, como temas concorrentes. Essa confiança não foi calibrada.”

## 1:30–2:15 — Execução e rastreabilidade

“Implementei em Python a preparação, a validação das respostas, as tentativas com retomada, a política e a exportação. O lote terminou com 359 sugestões válidas: 358 recibos de sucesso e uma resposta recuperada por revalidação offline. Falha técnica nunca vira decisão de que a questão está fora do recorte.

Cada tentativa e cada intervenção ficam registradas. Os arquivos têm hashes para conferir integridade. O CSV, a previsão e o relatório podem ser reconstruídos a partir dos artefatos salvos. Essa reprodução verifica a execução registrada; uma nova chamada ao modelo pode produzir outra resposta.”

## 2:15–3:15 — Evidências e experimento que não passou

“Na primeira versão, três revisores de IA, sem receber as sugestões do classificador, examinaram todas as 78 publicadas. Houve 77 concordâncias, ou 98,72%. Isso mede concordância com uma referência provisória de IA; falta uma referência jurídica independente.

A divergência em Q0180 mostrou uma dúvida entre o procedimento citado e o conhecimento central cobrado. Encaminhei o caso à revisão, sem declarar qual tema está juridicamente correto. Restaram 77 publicadas.

Para ampliar cobertura, testei um segundo passe em 41 questões retidas apenas por temas alternativos. Ele gerou 23 propostas, mas só vinte atenderam à coincidência estrita e houve uma divergência. O critério registrado exigia pelo menos 95% e zero divergências. Nenhuma proposta foi adotada.”

## 3:15–4:10 — Previsão e limites

“A previsão de precisão é 94,81%. Ela é subjetiva: reservei quatro possíveis erros entre as 77 publicadas. Esses quatro erros não foram observados. A faixa de 89,61% a 100% representa cenários de zero a oito erros, sem nível de confiança; o resultado real pode ficar abaixo dela.

Retirar Q0180 depois da auditoria não transforma os casos restantes em uma validação independente. Os revisores continuam sendo IA e podem compartilhar erros com o classificador. Também não medi, por essa concordância, a qualidade dos temas extras ou o mérito das revisões e exclusões. O julgamento jurídico especializado continua necessário.”

## 4:10–5:00 — Produção e próximos passos

“Para 50 mil questões por semana, proponho fila com retomada, controle de versões, revisão integrada e acompanhamento de erros reportados pelos alunos. Busca lexical e embeddings podem reduzir o catálogo, depois de testar se recuperam o tema correto.

O gargalo atual é editorial: mantendo esta distribuição, seriam cerca de 38,7 mil revisões por semana. A API gratuita usada no case não demonstra viabilidade nessa escala.

O próximo passo é esclarecer as fronteiras dos temas com um especialista e avaliar um lote novo, com referências independentes. Até essa validação, a operação proposta é em sombra, com aprovação editorial antes de chegar ao aluno.”

## Perguntas difíceis e respostas curtas

### 1. Publicar só 21,45% não torna a solução pouco útil?

“A cobertura é baixa e limita a utilidade atual. Ela mostra o custo da política escolhida diante de uma árvore ambígua. Na v1, só sete revisões dependiam exclusivamente da confiança; baixar esse limiar não resolveria o principal gargalo. Testei uma intervenção nos 41 casos retidos só por alternativas, mas ela não passou. Eu melhoraria as fronteiras dos temas e mediria o ganho em outro lote.”

Fonte: [diagnóstico de cobertura](COBERTURA_V1.md) e [experimento 5C](EXPERIMENTO_COBERTURA_V2.md).

### 2. Com 98,72% na auditoria, por que você diz que não atingiu 95%?

“Porque o denominador é 78 publicados da v1 e a referência também foi produzida por IA. As 77 correspondências são concordâncias condicionadas a essa referência. Ela pode estar errada. Depois usei a auditoria para reter Q0180; os 77 restantes não viram um teste independente nem uma precisão de 100%. Preciso de avaliação jurídica separada para sustentar a meta.”

Fonte: [auditoria v1](AUDITORIA_V1.md).

### 3. De onde saem 94,8052% e o intervalo de 89,6104% a 100%?

“De hipóteses declaradas. Quatro erros possíveis deixam 73 acertos em 77: 94,8052%. Zero a oito erros produzem a faixa de 69/77 a 77/77. A reserva é julgamento editorial, motivado pelas limitações da auditoria; não é estimativa calibrada nem contagem de erros encontrados. A faixa não é intervalo de confiança, e oito não é teto garantido. Para alcançar 95% neste conjunto, cabem no máximo três erros.”

Fonte: [método da previsão](ENTREGA_DOCUMENTAL.md#como-foi-escolhida-a-previsão).

### 4. Por que rejeitar o segundo passe se a concordância hierárquica chegou a 95,65%?

“Esse indicador aceita pai e filho imediato, mas o critério de adoção exigia referência única no mesmo ID e zero divergências. Só 20 das 23 propostas passaram pela regra estrita: 86,96%. Houve ainda a divergência de Q0024. Eu havia definido adotar todas ou nenhuma; aproveitar apenas as vinte concordâncias depois de olhar a referência mudaria o experimento.”

Fonte: [regra e resultado do segundo passe](EXPERIMENTO_COBERTURA_V2.md).

### 5. Confiança de 0,95 significa 95% de chance de estar certo?

“Não. É um valor declarado pelo modelo, sem calibração neste trabalho. Usei esse valor como um sinal entre vários, junto de alternativas, ambiguidade, extras e pedido de revisão. Em produção, eu mediria a relação entre confiança e acerto por ramo, usando rótulos adjudicados e dados separados, antes de usar o número como probabilidade.”

Fonte: [escolhas e política no relatório](../relatorio.md#1-raciocínio-e-escolhas).

### 6. Quanto custou? A solução foi gratuita?

“A API foi usada em projeto gratuito, sem ativar faturamento. Isso não significa custo total zero: o consumo Codex não foi medido, o modelo específico dos revisores não foi registrado e quarenta tentativas não informaram tokens. Nos escopos contabilizados, registrei 474 tentativas e 13,08 milhões de tokens conhecidos. Aplicando as tarifas documentadas em 16/10/2026 ao lote base, o equivalente pago seria cerca de US$0,0057 por questão com cache ou US$0,0127 sem desconto. São simulações sobre consumo conhecido, não faturas nem limites de gasto.”

Fonte: [consumo observado e cálculo contrafactual](ENTREGA_DOCUMENTAL.md#consumo-preço-e-projeção).

### 7. Como isso atenderia 50 mil questões por semana?

“O desenho ainda precisa de implementação e teste de carga. Usaria fila idempotente, cotas próprias, tentativas limitadas, falhas separadas e versões rastreáveis. Testaria recuperação de candidatos antes de reduzir o catálogo completo. A simulação do lote atual dá cerca de US$283 a US$634 de API para 50 mil itens, com exclusões de custo. Mantida a proporção de revisão, seriam 38.719 casos semanais: a hipótese de dois minutos por caso já implica cerca de 1.291 horas. Escalar exige reduzir retenções com qualidade demonstrada e dimensionar a equipe.”

Fonte: [proposta de produção](../relatorio.md#4-proposta-para-50-mil-questões-por-semana) e [premissas de capacidade](ENTREGA_DOCUMENTAL.md#consumo-preço-e-projeção).

### 8. O que o especialista faria e quando você liberaria publicação automática?

“O especialista definiria fronteiras entre temas, revisaria casos novos e adjudicaria discordâncias. A interface mostraria texto, tema sugerido, alternativas e motivo da retenção. Eu congelaria a política e avaliaria uma amostra probabilística de um lote novo, com revisão cega e pesos adequados. O critério proposto é limite inferior de confiança de 95% para a precisão dos publicados de pelo menos 95%. Extras, exclusões e perdas entre retidos precisam de avaliações próprias. Até lá, aprovação editorial; depois, amostragem contínua e triagem dos reportes dos alunos.”

Fonte: [qualidade contínua](../relatorio.md#qualidade-contínua-e-critério-de-liberação) e [memo ao professor](../relatorio.md#memo-ao-professor).
