# Ponto de retomada do case

**Módulo 7 concluído em 16/10/2026, pronto para revisão e commit.** Os sete módulos técnicos estão encerrados. A reprodução em clone novo passou em 14 etapas e 36 comparações, incluindo o PDF; suíte com 282 testes, 281 aprovados e um pulado. [Validação final](VALIDACAO_FINAL.md), [roteiro de apresentação](APRESENTACAO.md) e [checkpoint](../artefatos/checkpoints/modulo7_2026-10-16.json) estão prontos. Próximos passos do usuário: revisar, commitar, fazer push, conferir acesso público e enviar o link.

Entregas preservadas: [CSV final](../publicacao.csv), [previsao.txt](../previsao.txt), [relatório PDF de cinco páginas](../relatorio.pdf), [Markdown equivalente](../relatorio.md), com memo na quinta página, e [cálculos rastreáveis](../artefatos/entrega-v2/evidencias.json). A previsão de precisão é subjetiva: **94,8052%**, cenários de **89,6104% a 100%**, sem nível de confiança ou calibração. A cobertura conhecida continua **77/359 = 21,4485%**. A reprodução não comprova precisão jurídica.

**Ajuste posterior ao commit do módulo 6:** o relatório foi reconstruído após uma edição direta do PDF ter deixado caracteres acentuados corrompidos. O início do documento e os metadados agora usam **João Roberto de Oliveira Felix**, conforme solicitado. As cinco páginas foram renderizadas e revisadas; a geração determinística foi conferida. O texto restante, a previsão e as classificações foram preservados. Registro: [ajuste de autoria e recuperação do PDF](../artefatos/checkpoints/ajuste_relatorio_nome_2026-10-16.json). Para futuras edições, alterar `docs/modelo_relatorio.md` e regenerar com `scripts/gerar_relatorio.py --pdf`; o checkpoint original do módulo 6 permanece como histórico.

## Estado salvo

| Parte | Estado |
| --- | --- |
| Módulo 1: dados e árvore | Concluído: 359 questões preparadas, 377 temas validados, 375 ativos |
| Módulo 2: protocolo | Definido: política v1, referências por IA, censo do desenvolvimento e amostra de até 80 demais publicados |
| Módulo 3: integração e pilotos | Concluído: dois pilotos de vinte casos, prompt v2 selecionado |
| Módulo 4: lote completo | Concluído e commitado: 359 sugestões tecnicamente válidas |
| Módulo 5A: decisões | Concluído e commitado: 359 decisões e trilha congeladas |
| Módulo 5B: avaliação | Concluído e commitado: censo de 78, referências congeladas, comparação e diagnóstico |
| Módulo 5C: cobertura | Concluído e commitado: experimento não adotado, v2 congelada |
| Módulo 6: relatório e memo | Concluído e commitado; autoria e caracteres corrigidos |
| Módulo 7: entrega final e reprodução | Concluído; pronto para revisão e commit do usuário |

## Conclusão do módulo 7

Base: commit `b1e8539021f2417fd3f2513681745d2c50c6a0dc`, com repositório limpo no início. Um clone local novo, inicialmente sem `.env`, ambiente virtual ou prompts expandidos, recebeu somente o verificador e seu teste novos. O ambiente de PDF foi criado nesse clone. O registro identifica essas duas adições antes do commit e contém os hashes dos 610 arquivos de entrada; a documentação de fechamento foi atualizada posteriormente e consta no checkpoint.

A execução final usou `scripts/verificar_entrega.py --pdf --testes`: 14 etapas, 35 comparações byte a byte e uma comparação integral de JSON normalizando apenas os prefixos locais das fontes. Os nove diretórios reconstruídos contêm os 28 produtos versionados e quatro prompts regeneráveis esperados. Todas as fontes de entrada foram preservadas. O PDF reproduzido é idêntico ao arquivo corrigido e inspecionado no ajuste de autoria.

Suíte: **282 testes, 281 aprovados e um pulado**, em 183,900 s; o skip é a permissão de symlink real no Windows, com proteção também testada por simulação. Reprodução completa: **359,501 s**, Windows e Python 3.14.7. Os quatro testes novos cobrem normalização dos caminhos, preservação de métricas/hashes, rejeição de colisões e inventário incompleto ou excedente. Não foi testada uma matriz de sistemas operacionais.

A revisão do pacote conferiu CSV, previsão, relatório, requisitos, links locais e ausência de padrões conhecidos de credenciais nos arquivos examinados e no histórico Git. O novo guia explica o escopo da reprodução, distingue as entradas históricas dos produtos reconstruídos e traz um rascunho de e-mail. O roteiro inclui cinco minutos de apresentação e oito perguntas de defesa. Nenhuma chamada Gemini, leitura de `.env`, staging, commit, push ou envio externo foi realizado.

Registros: [execução completa](../artefatos/verificacao-final/reproducao-checkout-limpo.json), [checkpoint 7](../artefatos/checkpoints/modulo7_2026-10-16.json) e [guia de validação e envio](VALIDACAO_FINAL.md).

## Histórico do módulo 6

Base: commit `94066155ae648f11aacfcceabdff0223c4a9c2d2`, com repositório limpo. O relatório cobre raciocínio, tentativas rejeitadas, diagnóstico, avaliação, consumo/tempo, produção para 50 mil questões por semana e memo sem jargão de IA. A previsão usa reserva editorial de quatro erros possíveis (73/77), com cenários de zero a oito (69/77 a 77/77); não são erros observados ou limite garantido. O [método](ENTREGA_DOCUMENTAL.md) explica as escolhas, as limitações da referência e as fontes.

O gerador `scripts/gerar_relatorio.py` reproduz previsão, Markdown e evidências sem dependências externas ou API; `--pdf` usa dependências opcionais em ambiente isolado. Confere o CSV v2, todos os recibos esperados, os históricos e checksums. O PDF é determinístico, tem cinco páginas e foi renderizado para revisão visual; o memo ocupa a última. A revisão independente identificou e motivou a proteção contra custo subestimado por recibos ausentes.

Preços oficiais Standard do Gemini 3.5 Flash-Lite foram consultados em 16/10/2026. Sobre o consumo conhecido do lote, a simulação paga é US$0,005669 por questão com cache informado, ou US$0,012685 sem desconto. Não é fatura: faltam uso ausente, infraestrutura, auditoria e trabalho humano. A projeção de 38.719 revisões por semana e 1.291 horas a dois minutos por revisão é hipotética, mantendo a mistura deste recorte. Nenhuma arquitetura de produção ou economia de recuperação foi implementada/validada.

O [checkpoint do módulo 6](../artefatos/checkpoints/modulo6_2026-10-16.json) registra hashes e verificações. Nenhuma chamada Gemini, leitura de `.env`, alteração de classificações, ativação de faturamento, staging, commit, push ou envio externo nesta etapa. O uso dos agentes Codex permanece sem medição pelos recibos. A suíte e a reprodução final estão registradas no checkpoint.

Suíte final: **278 testes, 277 aprovados e um pulado** por permissão de symlink no Windows, em 108,497 s. Previsão, Markdown, evidências e PDF foram reconstruídos em pasta temporária com igualdade byte a byte e rede/acesso a `.env` bloqueados. As cinco páginas da versão final foram renderizadas e inspecionadas, com cabeçalhos, tabelas e memo legíveis.

Comandos documentais, sem credenciais:

```powershell
python -B scripts/gerar_relatorio.py --verificar
.venv/Scripts/python.exe -B scripts/gerar_relatorio.py --pdf --verificar
```

O segundo comando pressupõe `requirements-relatorio.txt` instalado no ambiente isolado; em outro ambiente, seguir [ENTREGA_DOCUMENTAL.md](ENTREGA_DOCUMENTAL.md). A versão PDF usa fontes embarcadas pelo ReportLab. Não editar somente as saídas: narrativa em `docs/modelo_relatorio.md`, hipóteses em `config/previsao_v2.json`; alterações precisam manter a explicação coerente e passar por nova renderização.

## Histórico do módulo 5C

A base foi o commit `80c4a1593cc9da1bf49a5da98fc35f685983b928`, com repositório limpo. O [pré-registro](../artefatos/experimento-cobertura-v2/preregistro.json) congelou regras, fontes e os 41 IDs retidos apenas por alternativas antes da análise específica do grupo. O segundo passe usou o mesmo modelo Gemini, um novo prompt e pasta de recibos separada, sem receber sugestões anteriores.

Foram 50 chamadas em treze invocações: 37 sucessos, doze falhas HTTP 503 e uma rejeição local. Q0086, Q0119, Q0194 e Q0322 esgotaram as duas tentativas; ficaram sem proposta. Não retomar essas chamadas neste experimento encerrado. O lote original continua com 359 sugestões tecnicamente válidas. Consumo novo: 1.134.040 tokens conhecidos e doze tentativas sem uso informado; consumo Codex desconhecido. A execução durou 21 min 47,67 s de relógio, incluindo esperas.

As 23 propostas exigiram segundo passe aprovado pela política base e igualdade de central e extras, preservando a confiança original. Foram congeladas antes de o coordenador abrir os julgamentos dos dois revisores cegos. A referência cobriu todos os 41 selecionados, em blocos de 21 e vinte questões.

| Resultado nas 23 propostas | Quantidade |
| --- | ---: |
| Coincidência estrita com referência única | 20 |
| Mesmo ID, com referência múltipla | 1 — Q0130 |
| Pai/filho imediato | 1 — Q0293 |
| Divergência explícita | 1 — Q0024 |

O indicador estrito foi **20/23 = 86,96%**, abaixo de 95%; pela regra hierárquica v1 foram **22/23 = 95,65%** de concordância condicional. O critério registrado também exigia zero divergências explícitas. O lote inteiro foi rejeitado; não houve seleção retrospectiva apenas dos itens concordantes. Q0024 contrapõe nós irmãos de teorias criminológicas, com fronteira editorial pouco definida; a referência é provisória de IA, sem especialista.

Q0180 foi encaminhada a `revisar` como achado conhecido da auditoria v1. Central, extras e confiança permaneceram iguais. Essa é a única mudança de decisão e motivo entre os CSVs; as outras 358 linhas mantêm seus campos. A cobertura passou de 78/359 = 21,73% para 77/359 = 21,45%, redução de 0,28 ponto percentual. A tentativa de ampliar cobertura não foi incorporada. A retirada do caso conhecido não é um acerto novo validado nem autoriza tratar referências reutilizadas como avaliação independente.

O [CSV v2 congelado](../artefatos/decisoes-v2/publicacao.csv) e a cópia da raiz têm SHA-256 `2f9ca44feef9998810c18bfb49933737470b758bcde7697b0c8673c531d6d53e`. O [manifesto](../artefatos/decisoes-v2/manifesto_decisoes.json), o [relatório do experimento](../artefatos/decisoes-v2/relatorio_experimento.json) e o [antes/depois](../artefatos/decisoes-v2/alteracoes.jsonl) tornam a escolha rastreável. Consulte [EXPERIMENTO_COBERTURA_V2.md](EXPERIMENTO_COBERTURA_V2.md) para método, diagnósticos, consumo e limites.

### Verificações do módulo 5C

- Suíte final: 270 testes, 269 aprovados e um pulado por privilégio de link simbólico no Windows, em 116,632 s. A revisão de código reforçou a validação das propostas congeladas antes da leitura das referências, antes da comparação real.
- Reprodução offline independente em diretórios temporários: dois produtos de propostas e seis finais idênticos byte a byte, com rede e acesso à configuração da API bloqueados.
- Conferência de todos os IDs, decisões, rótulos, confiança, contagens, denominadores e consumo; v1, 359 recibos originais e derivado de Q0005 preservados.
- As fontes registram falhas de acesso e um resultado incidental de busca com trecho de questão no bloco 02, sem resposta correta exibida e sem abertura da página. Não houve consulta aos rótulos temáticos reservados.
- Executor encerrado e sem lock residual. Nenhum faturamento ativado, commit, push ou envio externo realizado pelo assistente.
- Checkpoint: [modulo5c_2026-10-16.json](../artefatos/checkpoints/modulo5c_2026-10-16.json).

## Histórico do módulo 5B

A base desta etapa foi o commit `69c512be315cb7502c82391a6298c474bc39ef65`, com repositório limpo. O usuário informou ter feito commit e push do módulo 5A. As fontes e decisões anteriores foram conferidas e preservadas.

O [pacote de auditoria](../artefatos/auditoria-v1/manifesto_auditoria.json) selecionou os cinco publicados do desenvolvimento e os 73 restantes. A regra prévia de `min(80,N)` levou a censo dos dois estratos. Três agentes em contextos separados revisaram 26 questões cada, sem acesso às sugestões Gemini. As 78 referências passaram pelo contrato e foram [congeladas antes da comparação](../artefatos/revisao_auditoria-v1/manifesto_revisoes.json).

| Resultado | Desenvolvimento | Restante | Total |
| --- | ---: | ---: | ---: |
| Revisadas | 5 | 73 | 78 |
| Correspondências exatas | 5 | 72 | 77 |
| Divergências | 0 | 1 | 1 |
| Inconclusivas | 0 | 0 | 0 |

A divergência Q0180 contrapõe o central 5554 (Busca e Apreensão) à referência 5594 (Prova Ilegal e Prova Ilícita). O segundo ID aparece como extra do classificador, mas extras não corrigem a métrica do central. Nenhuma decisão foi alterada após a auditoria.

Três referências aceitam dois temas centrais: Q0009, Q0088 e Q0187, com justificativas cegas preservadas. Uma sensibilidade exploratória posterior trata essas três correspondências como não confirmadas, mantendo o denominador: 74/78 = 94,87%. Ela não altera o resultado principal e não é intervalo de confiança. O incidente de exposição incidental a trecho de gabarito de alternativa em uma busca sobre Q0179 está documentado; não houve acesso aos rótulos temáticos reservados ou às sugestões Gemini durante a revisão.

Os cenários conservador e otimista previstos coincidem em 77/78, pois não há inconclusivos. Os intervalos amostrais são degenerados por se tratar de censo; não cobrem erros da referência de IA. Método, limitações, fontes e comandos estão em [AUDITORIA_V1.md](AUDITORIA_V1.md). Os cálculos estão no [relatório de avaliação](../artefatos/avaliacao-v1/relatorio_avaliacao.json) e na [comparação por questão](../artefatos/avaliacao-v1/comparacao_auditoria.csv).

O [diagnóstico de cobertura](COBERTURA_V1.md) explica as 277 revisões: 232 têm temas alternativos, 218 confiança abaixo do limiar, 193 revisão solicitada, 60 ambiguidade mapeada, 32 excesso de extras e quatro correções de `fora`. Os sinais se sobrepõem. Há 41 questões retidas somente por temas alternativos, sete apenas pela confiança e uma somente por ambiguidade; 228 acumulam sinais. Diminuir apenas o limiar não resolve o principal gargalo.

### Verificações do módulo 5B

- Suíte final: 237 testes, 236 aprovados e um pulado por privilégio de link simbólico no Windows, em 139,823 s. A proteção de links também tem teste simulado aprovado.
- Pacote de auditoria reproduzido com seis arquivos idênticos; avaliação reproduzida em pasta temporária com dois arquivos idênticos, usando as mesmas entradas locais. Diagnóstico repetido sem alterar bytes ou data de modificação.
- Conferência independente de todas as linhas, hashes, contagens e frações; referências congeladas, CSV 5A, 359 recibos e Q0005 derivado preservados.
- Nenhuma nova chamada Gemini ou leitura de `.env`. O uso dos agentes Codex não foi medido pelos recibos; permanece desconhecido.
- Checkpoint: [modulo5b_2026-10-16.json](../artefatos/checkpoints/modulo5b_2026-10-16.json). Nenhum commit ou push realizado pelo assistente.

## Histórico do módulo 5A

A base desta etapa foi o commit `d22435a54c59021f3eeea5dd698aad10d8e32d29`. Na conclusão do 5A, o CSV da raiz correspondia byte a byte ao [CSV v1 congelado](../artefatos/decisoes-v1/publicacao.csv); atualmente a raiz contém a v2 descrita acima. O [manifesto de decisões v1](../artefatos/decisoes-v1/manifesto_decisoes.json) registra contagens e hashes; a [trilha](../artefatos/decisoes-v1/trilha_decisoes.jsonl) preserva sugestões originais, aplicação da política e intervenções. O arquivo de pendências está vazio.

A política v1 foi aplicada sem alteração de limiar, modelo, prompt de classificação ou validadores das respostas. A aplicação inicial produziu 78 propostas de publicação, 273 de revisão e oito candidatos a `fora`. Os oito receberam uma leitura separada por IA, sem acesso inicial às respostas Gemini, seguida de adjudicação registrada com os resultados originais. Essa revisão não é validação por especialista nem auditoria das publicadas.

| Resultado da revisão de `fora` | Questões |
| --- | --- |
| Ausência de tema confirmada | Q0039, Q0113, Q0142, Q0168 |
| Tema encontrado; encaminhamento para `revisar` | Q0154 → 5135; Q0261 → 5136; Q0298 → 5222; Q0358 → 5133 |

As justificativas, evidências, dúvidas de escopo, fontes oficiais e o antes/depois estão em [revisoes.json](../artefatos/revisao_fora-v1/revisoes.json). A entrada reproduzível do exportador é [confirmacoes_fora.jsonl](../artefatos/revisao_fora-v1/confirmacoes_fora.jsonl). As quatro correções sempre exigem revisão; nenhuma foi promovida a `publicar`. As 78 publicações permaneceram iguais às propostas pela política.

O exportador recusa substituir uma saída completa por decisões diferentes. Reexecutar com entradas idênticas valida e reutiliza os mesmos arquivos, sem regravá-los; uma mudança posterior exige outra pasta/versionamento. A CLI inclui `preparar-decisoes`, `preparar-auditoria` e `avaliar-auditoria`; as duas últimas foram exercitadas apenas com dados sintéticos nos testes. Nenhuma amostra ou referência real da auditoria foi produzida nesta etapa.

O [checkpoint 5A](../artefatos/checkpoints/modulo5a_2026-10-16.json) reúne a base Git, os hashes, as verificações e os limites. Consulte [DECISOES_V1.md](DECISOES_V1.md) para os contratos e a reprodução.

### Verificações do módulo 5A

- Suíte completa: `python -B -m unittest discover -s tests -q`, com 233 testes, 232 aprovados e um pulado por falta de privilégio do Windows para criar link simbólico real; a proteção também tem teste simulado aprovado. Duração: 71,644 s.
- CSV com cabeçalho oficial, 359 IDs únicos na ordem preparada, temas ativos, extras válidos e motivos exigidos. As oito revisões estão coerentes com a trilha.
- Os 359 recibos originais e a revalidação de Q0005 permanecem idênticos ao checkpoint do módulo 4. As fontes locais, o prompt v2 e a política v1 foram preservados.
- Exportação repetida sem alterar bytes ou datas de modificação; reprodução em pasta temporária com os mesmos quatro produtos; cópia da raiz idêntica ao CSV congelado.
- Nenhuma chamada Gemini nesta etapa. As consultas às fontes públicas e a revisão por IA no Codex não têm consumo de tokens medido pelos recibos Gemini; não tratá-lo como zero.
- Conferência final dos hashes, links locais, arquivos versionáveis e `git diff --check`. `.env`, `contexto_local/` e os prompts expandidos continuam ignorados.

## Histórico preservado do módulo 4

O lote está em `artefatos/execucoes/lote-v2-35-flash-lite/`: 358 recibos originais com sucesso e a recuperação offline anterior de Q0005, totalizando 359 sugestões válidas. Os vinte sucessos do piloto v2 estão incluídos, pois foram reutilizados sem novas chamadas. Q0005 conserva o recibo original com status histórico de erro e quatro tentativas; `Q0005.revalidacao.json` fornece a sugestão efetiva após validar a origem. Validade técnica não representa decisão de publicação nem precisão jurídica medida.

O [checkpoint final](../artefatos/checkpoints/conclusao_modulo4_2026-10-16.json) registra os 359 IDs, hashes dos recibos e da revalidação, consumo, falhas e verificações. O [registro da execução contínua](../artefatos/experimentos/conclusao-lote-v2-2026-10-16.json) preserva as 29 invocações, seus horários e resumos. Seu estado `concluido_aguardando_verificacao_final` é o encerramento original do executor; a conferência posterior consta no checkpoint final. O [resumo do experimento](../artefatos/experimentos/lote-v2-35-flash-lite.json) aponta para esse checkpoint.

### Conclusão das 197 questões restantes

A continuação partiu do commit `6b86acdf4a09c868c92a3fd6c8a8ba380e1da6c3`, com 162 sugestões válidas e repositório limpo. Foram 227 novas chamadas: 197 sucessos, vinte falhas HTTP 503 e dez respostas rejeitadas pela validação local. Todas as falhas foram recuperadas em novas tentativas e permanecem nos históricos. As invocações internas fizeram até vinte chamadas cada, avançando automaticamente e aguardando após indisponibilidade transitória. O limite de proteção da continuação era 450 chamadas; ele não foi atingido.

As dez rejeições locais ocorreram em Q0171, Q0197, Q0208, Q0209, Q0215, Q0254, Q0322, Q0324, Q0339 e Q0345. Sete repetiram IDs entre extras e alternativas; três alteraram ou juntaram trechos da evidência. Todas passaram na segunda tentativa. Os validadores, o modelo, o prompt e a política permaneceram iguais; nenhum tema foi escolhido manualmente para contornar uma falha.

A execução durou 87 min 31,91 s de relógio, das 10:16:03 às 11:43:35 de 16/10, horário de São Paulo. A soma da duração das chamadas foi 2.355,46 s; o restante inclui intervalos, esperas e processamento local. Esse tempo observado não mede o esforço humano total das vinte horas estimadas para o projeto.

| Consumo registrado | Esta continuação | Lote acumulado |
| --- | ---: | ---: |
| Tentativas reais, incluindo erros | 227 | 404 |
| Tokens totais informados | 6.257.155 | 11.350.512 |
| Tentativas com uso informado | 207 | 376 |
| Tentativas sem metadados de uso | 20 | 28 |

Uso ausente é desconhecido, não zero. O total do lote já inclui as 21 tentativas do piloto v2 reutilizado; não somá-las novamente. Somando as vinte tentativas do piloto v1, são 424 tentativas únicas registradas nos experimentos de classificação. Houve 247 chamadas registradas desse modelo em 16/10, das quais vinte pertencem ao bloco anterior e 227 a esta continuação. Isso é contagem local dos recibos, não consulta de saldo ao provedor. A interrupção de 14/10 pode ter ocorrido após uma chamada ainda sem recibo; eventual uso não registrado permanece desconhecido.

A última invocação terminou com código zero. O executor encerrou, nenhum processo desse lote ficou em execução e não há lock residual. Os checkpoints anteriores, incluindo a [base de 162 válidas](../artefatos/checkpoints/bloco_2026-10-16_01.json), permanecem preservados; o histórico dos blocos está em [PLANO_EXECUCAO.md](PLANO_EXECUCAO.md).

### Verificações da conclusão do módulo 4

- `python -B -m unittest discover -s tests -q`: 213 testes, 212 aprovados e um pulado por falta de privilégio do Windows para criar link simbólico real; a proteção também tem teste simulado aprovado. Duração: 46,556 s. A suíte foi executada nesta retomada; não foi repetida após alterações apenas de dados e documentação.
- Os 359 recibos tiveram identidade do experimento, checksum e histórico conferidos. As 359 sugestões efetivas passaram pelo esquema, IDs ativos e correspondência de evidência. A revalidação de Q0005 teve origem e seleção cronológica conferidas novamente.
- Os 162 recibos anteriores e o derivado de Q0005 permaneceram byte a byte idênticos. As 197 questões novas conservam suas tentativas, erros e metadados de uso.
- Fontes originais, manifestos, código, testes, modelo, prompt, política e regras de validação permaneceram iguais.
- A preparação e os prompts já haviam sido reconstruídos offline em pasta temporária com hashes idênticos. Os hashes foram reconferidos no encerramento; a pendência de fins de linha no Git está descrita abaixo.
- `.env` e `contexto_local/` continuam ignorados. A conferência final inclui busca de credencial Google nos arquivos versionáveis, links locais da documentação e `git diff --check`.
- Nenhum commit, push, aplicação da política, auditoria ou exportação final foi realizado nesta continuação.

## Ajuste de reprodução já incluído no commit 5A

O `temas.csv` local usa CRLF e coincide exatamente com o hash do manifesto (`9c6e98a6cd568816671c0fa14e2449b152cee10e20cb1327b3b097c1c5ce4cbc`). O commit 5A incluiu os mesmos bytes no Git; `HEAD:temas.csv`, índice e fonte local foram conferidos como idênticos nesta retomada. A pendência histórica de LF no repositório foi resolvida, sem editar o conteúdo da fonte.

Foi executado `git add --renormalize -- temas.csv`, com o atributo atual `-text`. A fonte local não foi editada; o índice agora contém seus bytes exatos. `git ls-files --eol temas.csv` mostra `i/crlf w/crlf attr/-text`, e a comparação ignorando fins de linha não mostra mudança textual. Os checkpoints históricos registram corretamente a pendência existente quando foram criados e permanecem intactos. O atributo `-text` também foi acrescentado para `publicacao.csv`, para preservar seu hash em outros checkouts.

A regra de whitespace de `temas.csv` reconhece o CRLF preservado como fim de linha, mantendo a checagem de espaços finais. Assim, `git diff --cached --check` não confunde a restauração dos bytes originais com espaços excedentes.

## Commit deste módulo

Este commit reúne o módulo 7: verificador de reprodução, testes de integridade, registro da execução em checkout separado, conferência das entregas, roteiro de apresentação e documentação. O assistente não fez commit, push ou staging nesta etapa.

Comandos sugeridos, a partir da raiz:

```powershell
git status --short
git add README.md docs/RETOMADA.md docs/PLANO_EXECUCAO.md docs/VALIDACAO_FINAL.md docs/APRESENTACAO.md
git add scripts/verificar_entrega.py tests/test_verificar_entrega.py
git add artefatos/verificacao-final/reproducao-checkout-limpo.json artefatos/checkpoints/modulo7_2026-10-16.json
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git commit -m "chore: valida entrega reproduzivel"
```

Os arquivos grandes `artefatos/piloto/entradas.jsonl`, `artefatos/piloto-v2/entradas.jsonl` e `artefatos/lote-v2/entradas.jsonl` continuam locais e ignorados: repetem o catálogo e são regeneráveis. Não usar `git add -f` para incluir `.env`, contexto privado ou prompts expandidos.

## Retomada e reprodução

Na mesma pasta, ler este registro e conferir `git status --short`. O módulo 4 está completo: não é necessário executar novas chamadas de classificação. As cotas informadas pelo usuário para o modelo eram 15 RPM, 250 mil TPM e 500 RPD; uma futura etapa com API precisa considerar o uso do dia. Nenhum gasto ou ativação de faturamento foi autorizado.

Em outro checkout, o comando recomendado reproduz os produtos em uma pasta temporária e confere os resultados sem credenciais:

```powershell
python -B scripts/verificar_entrega.py --testes
```

Para incluir o PDF e salvar um registro, seguir [VALIDACAO_FINAL.md](VALIDACAO_FINAL.md). A sequência abaixo permite reconstruir individualmente os produtos locais; os prompts expandidos não estarão no Git e precisam ser preparados antes de validar recibos ou decisões:

```powershell
python -B -m classificacao_topicos preparar
python -B -m classificacao_topicos preparar-piloto
python -B -m classificacao_topicos preparar-piloto --saida artefatos/piloto-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -B -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -B -m classificacao_topicos preparar-decisoes --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --politica config/politica_v1.json --confirmacoes-fora artefatos/revisao_fora-v1/confirmacoes_fora.jsonl --saida artefatos/decisoes-v1
python -B -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-desambiguacao-v1 --prompt prompts/desambiguacao_v1.txt --versao-prompt desambiguacao-v1
python -B -m classificacao_topicos.experimento_cobertura propor
python -B -m classificacao_topicos.experimento_cobertura concluir
python -B -m unittest discover -s tests -q
```

Esses comandos são offline. A chave deve ser configurada localmente conforme [CONFIGURACAO_API.md](CONFIGURACAO_API.md) quando necessária. Não repetir `verificar-api` se a integração já estiver funcionando: cada teste sintético é uma chamada real.

### Recuperação técnica de Q0005

A primeira resposta salva passa integralmente na validação atual, que tolera apenas caixa e espaços. A recuperação anterior foi registrada em `Q0005.revalidacao.json`; o recibo original, suas quatro tentativas e seus 122.031 tokens permanecem intactos. Não houve chamada de API, escolha manual de tema ou relaxamento adicional nesta continuação.

```powershell
python -B -m classificacao_topicos revalidar-recibo --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --id Q0005
```

O comando é offline e idempotente quando o derivado existente é válido. O executor e o módulo de decisões validam o derivado antes de usar a sugestão; o histórico original é a fonte exclusiva do consumo. Um derivado adulterado ou incompatível interrompe o processamento. Não editar o status do recibo original.

Ao conferir o lote por scripts, selecionar recibos por `Q[0-9]{4}\.json`, pois `Q*.json` inclui também o derivado. Separar status original e status efetivo. A função `carregar_revalidacao` verifica a origem e a seleção antes de `status_efetivo` ou `sugestao_efetiva`.

## Próximos passos do usuário

1. Revisar as alterações deste módulo e fazer o commit com os comandos acima; em seguida, fazer o push para o repositório remoto.
2. Abrir o repositório sem estar autenticado e confirmar acesso ao CSV, à previsão, ao PDF e às instruções. A acessibilidade pública não foi verificada nesta execução local.
3. Ensaiar com [APRESENTACAO.md](APRESENTACAO.md) e usar o rascunho de e-mail em [VALIDACAO_FINAL.md](VALIDACAO_FINAL.md) para enviar o link até 18/10/2026.

Não são necessárias novas chamadas de classificação. A reprodução valida a integridade dos cálculos salvos; a precisão jurídica permanece sem avaliação por especialista.

## Decisões que devem ser preservadas

O usuário não tem apoio jurídico disponível e não há rótulos temáticos oficiais. A referência está identificada como produzida por IA. Concordância entre IAs não comprova precisão jurídica. O limiar 0,95 é operacional e a confiança é autodeclarada, não calibrada. A política foi registrada antes de inspecionar as novas classificações; não ajustá-la sobre a avaliação e depois chamar essa avaliação de independente.

Na avaliação local, igualdade de ID ou relação imediata pai/filho é aceita; irmãos e ancestrais distantes permanecem distintos. Essa interpretação conservadora do case está documentada. A confiança das quatro sugestões corrigidas vem do revisor; a de `fora` é zero como sentinela de não aplicável. O intervalo da cobertura observada será degenerado. As convenções estão em [AVALIACAO.md](AVALIACAO.md).

Para retomar: **“Leia docs/RETOMADA.md e docs/APRESENTACAO.md e me ajude a ensaiar a defesa do case; preserve as entregas e não faça novas chamadas de classificação.”**
