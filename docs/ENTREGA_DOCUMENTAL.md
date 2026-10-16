# Entrega documental da versão 2

O módulo 6 conclui [previsao.txt](../previsao.txt), o [relatório em Markdown](../relatorio.md) e o [PDF de cinco páginas](../relatorio.pdf). A página cinco é o memo ao professor. A versão congelada de [publicacao.csv](../publicacao.csv) permanece com 77 `publicar`, 278 `revisar` e quatro `fora`; nenhuma decisão foi alterada.

## Como foi escolhida a previsão

O número solicitado pelo case é uma previsão antes da avaliação oficial. Não dispomos de referência jurídica independente. O censo da v1 mediu concordância com uma referência provisória de IA: 77/78. A retirada posterior de Q0180 e a reutilização desses julgamentos na seleção da v2 impedem chamar 77/77 de precisão validada. Não aplicamos um intervalo binomial sobre esses julgamentos como se fossem rótulos verdadeiros independentes.

Para responder ao pedido sem esconder o julgamento, a previsão central adota uma reserva de **quatro erros possíveis**, resultando em **73/77 = 94,8052%**. As três referências com múltiplos temas aceitáveis (Q0009, Q0088, Q0187) e o incidente registrado em Q0179 motivam essa cautela; não são quatro erros comprovados, nem se presume que os erros estariam nesses IDs. Não há calibração que torne quatro uma estimativa empírica.

O intervalo principal é **de cenários**, de zero a oito erros: **69/77 a 77/77 = 89,6104% a 100%**. Oito duplica a reserva para explorar mais quatro erros não detectados; não há evidência de que seja um teto. Essa faixa não tem nível de confiança nem cobertura probabilística validada; erros compartilhados podem levar o resultado para fora dela. Sem hipóteses sobre o erro da referência, os limites identificáveis seriam [0,1]. Preferimos declarar uma previsão subjetiva com essas hipóteses a apresentar concordância entre IAs como precisão jurídica medida.

A cobertura **77/359 = 21,4485%** é conhecida exatamente neste conjunto; o intervalo degenerado não faz previsão sobre futuras importações. Para atingir 95% nas 77 publicadas, podem existir no máximo três erros; quatro já resultam em 94,8052%. Não alteramos o conjunto para aproximar a previsão da meta. Os campos numéricos usam seis casas decimais, com ponto decimal e os nomes do formato oficial.

## Consumo, preço e projeção

O gerador reconcilia os recibos originais e seus históricos; exige todos os IDs de cada etapa. O piloto v2 está incluído no lote de 359. A revalidação offline de Q0005 é fonte de rastreabilidade, mas não chamada adicional.

| Etapa | Tentativas | Tokens conhecidos | Tentativas sem uso informado |
| --- | ---: | ---: | ---: |
| Piloto v1 | 20 | 595.370 | 0 |
| Lote v2, incluindo piloto v2 | 404 | 11.350.512 | 28 |
| Experimento 5C | 50 | 1.134.040 | 12 |
| Total desses escopos | 474 | 13.079.922 | 40 |

Esses totais excluem testes sintéticos, possível chamada interrompida antes do recibo e uso dos agentes Codex. Uso ausente não é zero. As revisões Codex não têm modelo específico ou consumo identificados nos recibos Gemini. A execução usou projeto gratuito, sem ativar faturamento; não consultamos fatura nem declaramos custo total zero.

Em 16/10/2026, os [preços oficiais Standard do Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite) eram US$0,30/M de entrada, US$0,03/M de entrada em cache e US$2,50/M de saída incluindo raciocínio. O preço é uma referência datada para simulação, não promessa de tarifa futura. [UsageMetadata](https://ai.google.dev/api/generate-content#UsageMetadata) distingue entrada, resposta, raciocínio e cache; cache já integra a entrada.

No lote: 10.828.291 tokens de entrada, 9.329.529 em cache, 71.381 de resposta e 450.840 de raciocínio. A fórmula é `[(entrada - cache) * preço_entrada + cache * preço_cache + (resposta + raciocínio) * preço_saída] / 1.000.000`. Sem desconto de cache, toda a entrada recebe a tarifa cheia.

O equivalente pago sobre uso conhecido é US$2,035067 com cache, ou US$4,554040 sem desconto. Dividido pelas 359 questões, corresponde a US$0,005669 ou US$0,012685 por questão. A 50 mil: US$283,44 ou US$634,27. Não são limites de gasto: faltam consumo ausente, infraestrutura, trabalho humano e auditoria. Ausência de informação de cache é tratada à tarifa cheia, sem inventar desconto.

A proposta de candidatos reduzidos usa hipótese de 4 mil tokens de entrada, 1,5 mil de saída e raciocínio e 1,15 tentativas por questão, sem cache: US$0,0056925 por item, US$284,625 por 50 mil antes do arredondamento. Não houve medição dessa abordagem. Reduzir o catálogo não garante economia frente ao cache observado; precisa preservar a recuperação do tema correto e demonstrar custo líquido menor.

O esforço humano é o maior custo potencial: mantendo a composição do recorte, `50000 * 278 / 359 = 38.718,66` revisões/semana. Dois minutos por revisão implicam 1.290,62 horas; a US$20/h **hipotéticos**, são US$0,51625 por questão importada, antes de API, infraestrutura e auditoria. Não se trata de preço de mercado nem tempo observado. A cota gratuita informada de 500 chamadas/dia não sustenta a demanda; [limites são por projeto](https://ai.google.dev/gemini-api/docs/rate-limits).

## Reprodução e manutenção

Da raiz, com Python 3.11+:

```powershell
python -B scripts/gerar_relatorio.py
python -B scripts/gerar_relatorio.py --verificar
```

O primeiro comando gera três arquivos: previsão, Markdown e [evidências](../artefatos/entrega-v2/evidencias.json). `--verificar` exige igualdade de bytes sem gravar. Todos os cálculos são locais; não carrega `.env`, não faz chamadas de IA e não precisa dos prompts expandidos. Os hashes das fontes textuais de código/modelo usam LF; os CSVs, recibos e artefatos preservam bytes. A previsão e os relatórios têm atributo Git `-text` para preservar as saídas.

PDF opcional, em ambiente isolado no Windows:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-relatorio.txt
.venv/Scripts/python.exe -B scripts/gerar_relatorio.py --pdf
.venv/Scripts/python.exe -B scripts/gerar_relatorio.py --pdf --verificar
```

Em Linux/macOS, substituir o executável por `.venv/bin/python`. As dependências de autoria do PDF não são exigidas pelo classificador. O PDF usa fontes Vera embarcadas pelo ReportLab e metadados determinísticos. O gerador recusa um PDF que não tenha exatamente cinco páginas. A inspeção visual continua necessária após mudar texto ou layout; a checagem de páginas não detecta toda falha visual.

`--saida DIRETORIO` gera o mesmo conjunto em outra pasta. Para editar a narrativa, usar [modelo_relatorio.md](modelo_relatorio.md); para auditar as hipóteses, [previsao_v2.json](../config/previsao_v2.json). Esta edição descreve especificamente o conjunto congelado v2: alterar cenários, tarifas ou hipóteses também exige revisar a explicação textual e as premissas exibidas. Não editar só o relatório gerado, pois a reconstrução o substituirá.

## Encerramento do módulo

Relatório conferido em cinco páginas, com memo na quinta; conteúdo revisado contra o enunciado e os artefatos. A revisão independente identificou o risco de aceitar recibos faltantes no cálculo de custo; a geração agora recusa conjuntos incompletos ou excedentes, com teste específico. Os oito testes documentais cobrem denominadores, cenários, contrato, custo com raciocínio/cache e integridade dos insumos. Os resultados finais da suíte e da reprodução estão no [checkpoint do módulo 6](../artefatos/checkpoints/modulo6_2026-10-16.json).

O próximo módulo é a reprodução completa em checkout limpo, revisão do pacote público e preparação para apresentação. Não houve nova classificação, commit, push ou envio de mensagem externa nesta etapa.
