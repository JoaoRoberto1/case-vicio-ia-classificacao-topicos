# Case Vício — Classificação de tópicos

**Entrega atual: etapa complementar, com 659 questões e 100 referências humanas.** Abra a pasta [etapa-complementar](etapa-complementar/README.md) para executar e avaliar esta versão. O teste reservado teve 6/20 acertos; a política encaminha todas as questões para revisão. A meta de precisão de 95% com cobertura não foi atingida. O relatório preserva esse resultado e explica os próximos experimentos.

Arquivos atuais: [CSV de 659 questões](etapa-complementar/publicacao.csv), [previsão](etapa-complementar/previsao.txt), [relatório de quatro páginas](etapa-complementar/relatorio.pdf), [relatório em Markdown](etapa-complementar/relatorio.md), [defesa técnica](etapa-complementar/docs/DEFESA_TECNICA.md) e [guia de entrega](etapa-complementar/docs/ENTREGA.md). Os arquivos de mesmo nome na raiz pertencem à primeira entrega.

A [rodada extra de refinamento](etapa-complementar/docs/MODULO6_REFINAMENTO.md) comparou oito receitas de ranking. Nenhuma variação superou os 37/80 acertos do classificador anterior, que permanece selecionado. A entrega acima foi preservada; os resultados novos são exploratórios, pois as referências já foram utilizadas no desenvolvimento e na avaliação anteriores.

O [módulo 7 de catálogo enriquecido](etapa-complementar/docs/MODULO7_CATALOGO.md) melhorou as sugestões para **54/80 acertos por ramo (67,5%)**, com 53/80 na seleção aninhada. Nas 20 referências já conhecidas, passou de 6 para 12 acertos. A cobertura com precisão de 95% continua sem sustentação; os novos resultados são experimentais e os arquivos da entrega M5 acima permanecem congelados.

O [plano dos cinco módulos](etapa-complementar/docs/PLANO_EXECUCAO.md) e o [protocolo de avaliação](etapa-complementar/docs/PROTOCOLO_AVALIACAO.md) orientam a continuação. A [folha-verdade](etapa-complementar/anexos/folha_verdade.csv), as [659 questões](etapa-complementar/anexos/questoes.jsonl), o [novo enunciado](<etapa-complementar/case-ia-classificacao-de-topicos (2).pdf>) e os demais anexos foram importados junto com o módulo 1 já validado.

Para executar a etapa complementar, entre na pasta correspondente:

```console
cd etapa-complementar
python -B -m classificacao_decisao regenerar
python -B -S scripts/verificar_entrega.py
```

O segundo comando reproduz preparação e decisões em uma cópia temporária, usando somente Python e artefatos versionados. Não precisa de chave ou pesos de modelos. A [documentação atual](etapa-complementar/README.md) separa essa verificação da reconstrução de embeddings e da geração do PDF.

Os arquivos e resultados apresentados abaixo pertencem à **primeira entrega, com 359 questões**. Eles foram preservados e não representam a etapa complementar. O [registro de importação](docs/IMPORTACAO_ETAPA_COMPLEMENTAR.json) identifica o commit de origem e os hashes dos 33 arquivos trazidos.

## Visão geral

Solução para o processo seletivo de IA da Vício (Método VDE), voltada à classificação de questões de concursos jurídicos por tópico. Autor: **João Roberto de Oliveira Felix**.

Entregas para leitura: [publicacao.csv](publicacao.csv), [previsao.txt](previsao.txt), [relatório PDF de cinco páginas](relatorio.pdf) e [mesmo relatório em Markdown](relatorio.md). O memo ao professor ocupa a quinta página do PDF. Os cálculos e suas fontes estão em [evidencias.json](artefatos/entrega-v2/evidencias.json).

Preparação para a defesa: [roteiro de cinco minutos e oito perguntas com respostas](docs/APRESENTACAO.md).

## Comece pela reprodução offline

Requisitos: **Git e Python 3.11+**. A reprodução usa os recibos e julgamentos salvos. A API e uma chave não são necessárias. Em uma cópia do repositório, na raiz:

```sh
python -B scripts/verificar_entrega.py --testes
```

O verificador copia as fontes versionadas para uma pasta temporária, reconstrói preparação, prompts, decisões v1, pacote de auditoria, propostas do segundo passe e decisões v2. Compara os resultados com os arquivos entregues, confere previsão/Markdown/evidências e executa os testes. A pasta temporária é removida ao terminar; os arquivos da cópia de origem ficam preservados. Rede Python e leitura do `.env` da cópia são bloqueadas durante as etapas.

O CSV final é gerado por `classificacao_topicos.experimento_cobertura concluir`, que reaplica a seleção da v2 às decisões e evidências salvas. O verificador exige que esse resultado seja idêntico a `publicacao.csv` da raiz. Isso reproduz a entrega registrada; uma nova chamada de IA pode gerar outro julgamento.

Para conferir também o PDF, instale as dependências opcionais e use:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-relatorio.txt
.venv/Scripts/python.exe -B scripts/verificar_entrega.py --pdf --testes
```

Em Linux/macOS, o executável é `.venv/bin/python`. Apenas o PDF exige essas dependências. O verificador retorna código zero se todas as comparações passarem; `--registro caminho/novo.json` salva um registro sem substituir um anterior. Consulte [validação final](docs/VALIDACAO_FINAL.md) para o escopo e a evidência do checkout limpo.

## Objetivo

Classificar as 359 questões fornecidas usando a árvore de temas de Penal, Processo Penal, Direito Penal - Legislação Especial e Criminologia. Cada questão receberá uma das seguintes decisões:

- **`publicar`**: vai diretamente ao aluno no tema escolhido.
- **`revisar`**: vai ao especialista com uma sugestão de tema.
- **`fora`**: nenhum tema da árvore serve; a questão sai do recorte até que um tema seja criado.

A **meta é atingir pelo menos 95% de precisão nas questões publicadas**, buscando a maior cobertura possível (fração do total de questões publicada). Essa é uma meta do case, ainda não um resultado alcançado ou validado.

## Materiais fornecidos

| Arquivo | Descrição |
| --- | --- |
| [case-ia-classificacao-de-topicos.pdf](case-ia-classificacao-de-topicos.pdf) | Enunciado oficial: contexto, critérios de avaliação, regras e entregas exigidas. |
| [LEIA-ME.md](LEIA-ME.md) | Documento original do organizador, com o dicionário dos campos e os formatos de entrega. |
| [questoes.jsonl](questoes.jsonl) | As 359 questões, com enunciado em HTML, comando, alternativas e campos de origem. |
| [temas.csv](temas.csv) | Árvore com 377 registros de disciplinas, temas e subtemas, incluindo descrições e status. |
| [entrega_modelo.csv](entrega_modelo.csv) | Exemplo de formato da futura entrega `publicacao.csv`. As duas linhas são fictícias e não representam classificações reais. |

Os requisitos são definidos pelo PDF oficial e pelo `LEIA-ME.md`. O arquivo `entrega_modelo.csv` é apenas o exemplo fornecido; o [CSV gerado](publicacao.csv) contém as 359 decisões desta versão.

## Regras importantes

- Todas as 359 questões precisam receber uma decisão.
- Temas inativos não podem ser utilizados.
- `disciplina_origem` e `assunto_origem` podem estar errados e não constituem um gabarito.
- Os rótulos dos especialistas foram reservados pela organização para avaliação e não foram disponibilizados.
- Dúvida entre temas não é, por si só, motivo para usar `fora`; essa decisão indica que nenhum tema da árvore serve.
- Conforme o `LEIA-ME.md`, `tema_central_id` é obrigatório em `publicar` e em `revisar` e fica vazio em `fora`. O campo `motivo` é obrigatório em `revisar` e em `fora`.

## Estado atual

**Sete módulos concluídos; pacote validado para entrega.** A previsão subjetiva de precisão é **94,8052%**, com cenários de **89,6104% a 100%**, sem nível de confiança ou calibração empírica. A reserva de quatro erros possíveis é julgamento editorial, não quatro erros observados; o cenário de oito erros não é um teto garantido. A cobertura é a contagem conhecida **77/359 = 21,4485%**. O [método documental](docs/ENTREGA_DOCUMENTAL.md) explica as hipóteses e como reproduzir os arquivos.

Verificação final do módulo 7: **282 testes, 281 aprovados e um pulado** pela permissão de symlink no Windows; suíte em 183,900 s. Em um clone novo da base commitada, com apenas o verificador e seu teste adicionados antes do commit, passaram **14 etapas e 36 comparações**: 35 byte a byte e uma comparação integral de JSON normalizando somente prefixos locais das fontes. O PDF coincidiu com a versão já inspecionada nas cinco páginas. Nenhuma nova chamada de API. A execução completa levou 359,501 s; escopo, ambiente e [registro verificável](artefatos/verificacao-final/reproducao-checkout-limpo.json) estão explicados em [VALIDACAO_FINAL.md](docs/VALIDACAO_FINAL.md).

O módulo de preparação dos dados e da árvore está implementado e verificado. Ele preserva as fontes, prepara as 359 questões, valida os 377 registros da árvore e gera um diagnóstico reproduzível.

**Módulo 5C concluído em 16/10/2026, com resultado negativo para ampliar a cobertura.** Das 23 propostas congeladas, 20 tiveram coincidência estrita com a referência provisória de IA: **20/23 = 86,96%**. A comparação hierárquica encontrou 22/23 = 95,65%, mas incluiu uma divergência explícita, em Q0024. O protocolo exigia pelo menos 95% de coincidências estritas e zero divergências; nenhuma proposta foi adotada. O [relatório do experimento](artefatos/decisoes-v2/relatorio_experimento.json) registra a decisão e seus denominadores.

| Decisão | Versão 1 preservada | Versão 2 atual |
| --- | ---: | ---: |
| `publicar` | 78 | 77 |
| `revisar` | 277 | 278 |
| `fora` | 4 | 4 |
| Total | 359 | 359 |

A cobertura atual é **77/359 = 21,4485%**. A única alteração nas decisões foi encaminhar Q0180 a `revisar`, por achado conhecido da auditoria v1, preservando central, extras e confiança. Sua retirada não conta como acerto novo nem comprova ganho de precisão. O [CSV atual](publicacao.csv) segue a [trilha v2](artefatos/decisoes-v2/manifesto_decisoes.json); a [versão 1](artefatos/decisoes-v1/manifesto_decisoes.json) permanece intacta.

O resultado histórico do módulo 5B permanece **77/78 = 98,72% de concordância condicional à referência de IA**, por censo dos 78 publicados da v1. Não comprova precisão jurídica de 95% e não é uma avaliação independente da versão ajustada. O censo elimina a incerteza de amostragem, mas não mede o erro da referência, a qualidade dos extras ou das decisões `revisar` e `fora`.

Dois pilotos reais com os mesmos 20 casos estão concluídos. O prompt v2 reconheceu melhor condições de revisão e foi escolhido para o lote de 359 questões com Gemini 3.5 Flash-Lite no plano gratuito. O lote completo contém 358 recibos com sucesso e a recuperação offline anterior de Q0005, totalizando 359 sugestões válidas, sem falhas técnicas pendentes. Os vinte sucessos do segundo piloto estão incluídos nesse total, sem novas chamadas.

A continuação final concluiu as 197 questões restantes em 227 chamadas: 197 sucessos, vinte falhas HTTP 503 e dez respostas rejeitadas pela validação local, todas recuperadas nas novas tentativas. As 29 invocações internas avançaram automaticamente conforme autorizado pelo usuário. Os 162 recibos anteriores, o derivado de Q0005 e os históricos foram preservados. Modelo, prompt, política e validadores permaneceram iguais. O lote acumula 404 tentativas, incluindo as do piloto v2 reutilizado; revalidação offline não conta como chamada.

O módulo 5A aplicou a política registrada sem alterar modelo, prompt ou seus parâmetros. A revisão separada por IA dos oito candidatos a `fora` confirmou quatro e encaminhou outros quatro a `revisar`, com temas sugeridos e justificativas rastreáveis. Foram reutilizados todos os recibos; esta etapa fez **zero chamadas Gemini**.

No módulo 5B, três agentes revisaram 26 questões cada, sem acesso às sugestões Gemini, e as referências foram congeladas antes da comparação. O censo abrangeu cinco publicados do desenvolvimento e 73 restantes, sem julgamentos inconclusivos ou correspondências apenas por parentesco. A exposição incidental de Q0179 a um trecho de gabarito de alternativas foi registrada; não houve acesso aos rótulos temáticos reservados. Método, resultado e limites estão em [Auditoria da versão 1](docs/AUDITORIA_V1.md).

Uma sensibilidade exploratória posterior trata as três referências com vários temas aceitáveis como não confirmadas, preservando o denominador: o resultado seria 74/78 = 94,87%. Isso não altera o resultado principal nem as referências e mostra a dependência do indicador em relação ao julgamento de IA. Consulte a [análise de sensibilidade](artefatos/analises/sensibilidade-referencia-v1.json).

O [experimento 5C](docs/EXPERIMENTO_COBERTURA_V2.md) classificou novamente os 41 casos retidos apenas por alternativas, em 50 chamadas Gemini: 37 sucessos técnicos e quatro falhas com tentativas esgotadas, em Q0086, Q0119, Q0194 e Q0322. Foram observados 1.134.040 tokens; doze tentativas não informaram uso, e o consumo dos agentes Codex não está incluído. As propostas foram congeladas antes da comparação com as referências cegas. A escolha da versão usa essa avaliação e constitui desenvolvimento, sem validação independente posterior à escolha.

O módulo 5C foi commitado pelo usuário. Sua suíte final executou 270 testes: 269 aprovados e um pulado por limitação de permissão de symlink no Windows, em 116,632 s. O módulo 6 acrescentou previsão, relatório, memo e projeções de produção para 50 mil questões por semana. O módulo 7 reúne o verificador de reprodução, a conferência do pacote e o roteiro de apresentação.

- [Plano e acompanhamento dos módulos](docs/PLANO_EXECUCAO.md)
- [Protocolo de avaliação e ambiguidades](docs/AVALIACAO.md)
- [Configuração da API gratuita para o piloto](docs/CONFIGURACAO_API.md)
- [Experimentos dos pilotos e resultados observados](docs/PILOTO_V1.md)
- [Decisões congeladas e revisão dos candidatos fora](docs/DECISOES_V1.md)
- [Auditoria da versão 1 e limitações da referência](docs/AUDITORIA_V1.md)
- [Diagnóstico reproduzível da cobertura](docs/COBERTURA_V1.md)
- [Experimento 5C, resultado negativo e versão 2](docs/EXPERIMENTO_COBERTURA_V2.md)
- [Entrega documental, previsão e custos](docs/ENTREGA_DOCUMENTAL.md)
- [Política original preservada](config/politica_v1.json)
- [Política da versão 2](config/politica_v2.json)

```mermaid
flowchart LR
    A[Questões e árvore originais] --> B[Preparação e validação]
    B --> C[Prompt com catálogo ativo]
    C --> D[Gemini e recibos com retomada]
    D --> E[Política de decisão]
    E --> F[CSV e trilha congelados]
    F --> G[Revisão cega e avaliação]
    G --> I[Experimento de desambiguação]
    I --> J[Propostas congeladas e referência cega]
    J --> K[Adoção ou rejeição do lote de propostas]
    K --> H[Previsão e relatório]
```

## Como executar

Use Python 3.11 ou superior. O pipeline de classificação, os cálculos documentais e os testes usam somente a biblioteca padrão e foram verificados localmente com Python 3.14.7. Apenas a geração opcional do PDF requer as dependências separadas abaixo.

### Reproduzir a previsão e o relatório, sem API

Com os recibos versionados já presentes, estes comandos não precisam de chave ou prompts expandidos:

```sh
python -B scripts/gerar_relatorio.py
python -B scripts/gerar_relatorio.py --verificar
```

Eles geram ou conferem `previsao.txt`, `relatorio.md` e `artefatos/entrega-v2/evidencias.json`. O gerador verifica o hash do CSV v2, a presença de todos os recibos esperados, os históricos de tentativas e os checksums; não modifica classificações. A estimativa inclui tentativas malsucedidas com consumo informado, sem duplicar o piloto v2 ou a revalidação offline de Q0005.

Para reconstruir também o PDF no Windows:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-relatorio.txt
.venv/Scripts/python.exe -B scripts/gerar_relatorio.py --pdf
.venv/Scripts/python.exe -B scripts/gerar_relatorio.py --pdf --verificar
```

Em Linux/macOS, usar `.venv/bin/python` no lugar de `.venv/Scripts/python.exe`. O conteúdo editável está em [docs/modelo_relatorio.md](docs/modelo_relatorio.md); os parâmetros ficam em [config/previsao_v2.json](config/previsao_v2.json). Após editar, regenerar as saídas e revisar as cinco páginas. `--saida DIRETORIO` permite reproduzir em outra pasta. `--verificar` compara bytes sem gravar.

### Preparação e classificação

Na raiz do repositório, prepare os dados:

```sh
python -m classificacao_topicos preparar
```

Os produtos são gravados em `artefatos/preparacao/`:

| Produto | Conteúdo |
| --- | --- |
| `questoes_preparadas.jsonl` | Enunciado, comando, alternativas e texto completo; metadados de origem preservados e referência ao registro original |
| `temas_preparados.json` | Campos originais, ancestrais, filhos, caminhos calculados e sinalização de status |
| `diagnostico.json` | Contagens, verificações estruturais e limitações |
| `avisos_questoes.csv` | IDs e sinais de ausência ou necessidade de inspeção, sem atribuir decisões |
| `arvore_temas.md` | Visualização textual de todos os ramos, IDs e status |
| `manifesto.json` | Hashes SHA-256 das entradas e dos produtos da execução concluída |

As entradas permanecem na raiz. O manifesto permite conferir sua integridade e a dos produtos. Para entradas idênticas, a preparação produz arquivos idênticos. Ela remove marcação HTML e configurações do Word, preserva o texto útil e não tenta corrigir OCR ou conteúdo jurídico.

Prepare os casos do piloto, também sem chamadas externas:

```sh
python -m classificacao_topicos preparar-piloto
```

Isso grava `artefatos/piloto/entradas.jsonl` e `manifesto_piloto.json`. São dez casos deliberados e dez selecionados por diversidade estrutural, com semente fixa. O catálogo contém todos os 375 temas ativos, mantendo os IDs e os ramos distintos. Os campos de origem não entram no prompt. Essa seleção serve ao desenvolvimento e não constitui amostra representativa para medir precisão.

### Novas chamadas de IA, opcionais

Os comandos `verificar-api`, `executar-piloto` e `executar-lote` podem acessar o provedor; os comandos de preparação e os testes são offline. Os exemplos abaixo registram a execução histórica e apontam para suas pastas de artefatos. Para um novo experimento, siga a [configuração da API](docs/CONFIGURACAO_API.md), confira o Free Tier e as cotas do seu projeto e adapte `--saida` dos comandos de execução para um diretório novo, preservando os recibos existentes. O modelo que funcionou neste ambiente foi selecionado assim no PowerShell:

```powershell
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
python -m classificacao_topicos verificar-api
```

O recibo fica em `artefatos/execucoes/verificacoes_api.jsonl`. Após o sucesso desse teste, execute inicialmente uma questão:

```sh
python -m classificacao_topicos executar-piloto --limite 1
```

Cada invocação faz no máximo o número informado de novas chamadas, com padrão de uma e teto de vinte. O executor valida os arquivos, salva recibos em `artefatos/execucoes/piloto-v1/`, reaproveita sucessos válidos e interrompe na primeira falha. Uma nova invocação pode tentar novamente uma questão com erro, preservando suas tentativas anteriores. Alterações de modelo, prompt ou preparação exigem outra pasta de execução. O intervalo padrão entre novas chamadas é de dez segundos; a adequação desse intervalo depende da cota real do projeto.

As respostas são sugestões do piloto: ainda não geram decisões de publicação. O resumo de tokens inclui todos os recibos disponíveis na pasta, inclusive cache e falhas com uso informado. Uso ausente não é tratado como zero. Uma interrupção abrupta pode deixar `.execucao.lock`; antes de removê-lo, confirme que nenhum processo está executando nessa pasta. Se a interrupção ocorreu após o envio e antes de salvar o recibo, não é possível confirmar localmente se houve consumo, e uma retomada pode repetir aquela chamada.

Execute as verificações locais:

```sh
python -m unittest discover -s tests -v
```

Os testes incluem os dados reais, preservação dos originais, repetibilidade, árvore inválida, alternativas da Q0099, comando da Q0107, validação das sugestões e retomada com histórico de consumo. Testes da API usam transporte simulado e não consomem cota.

Para reconstruir o prompt de classificação v2 e o lote completo da classificação base:

```powershell
python -m classificacao_topicos preparar-piloto --saida artefatos/piloto-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -m classificacao_topicos executar-lote --lote artefatos/lote-v2 --saida artefatos/execucoes/lote-v2-35-flash-lite --limite 20 --intervalo-segundos 10 --continuar-erros-validacao
```

Com `--limite 20`, cada invocação faz no máximo vinte novas chamadas; sucessos válidos são reutilizados. Ao terminar o comando, é possível revisar o resumo, parar e commitar os recibos antes de iniciar outro bloco. Para a conclusão de 16/10, as invocações foram repetidas automaticamente, com espera após falhas transitórias, conforme o [registro da execução contínua](artefatos/experimentos/conclusao-lote-v2-2026-10-16.json). O limite de proteção dessa continuação era de 450 novas chamadas; foram necessárias 227.

A opção de continuar salva falhas locais de validação e avança para outros IDs. Falhas do provedor, autenticação ou cota continuam interrompendo cada invocação. Falhas nunca viram `fora`. O retorno da CLI é diferente de zero se restarem respostas inválidas ou se a execução parar em erro. A evidência precisa existir em um campo da questão; são toleradas apenas diferenças de caixa e espaços, sem corrigir palavras, acentos, pontuação ou OCR. Com o lote completo e os arquivos íntegros, a repetição do comando reutiliza os 359 resultados e não faz novas chamadas.

Os quatro arquivos de prompts expandidos `entradas.jsonl` são ignorados pelo Git para evitar aproximadamente 74,6 MB de catálogo repetido. Em um novo checkout, execute a preparação e os comandos `preparar-piloto`/`preparar-lote` antes de ler os recibos; os arquivos são reconstruídos com os mesmos hashes. Os recibos de execução e os artefatos de referência ficam versionados para permitir a auditoria e a reprodução offline. `.gitattributes` preserva os bytes dos dados, prompts, configurações e artefatos assinados, inclusive no Windows.

### Decisões v1 sem API

Com os dados preparados, os prompts reconstruídos e os recibos versionados disponíveis, execute:

```powershell
python -m classificacao_topicos preparar-decisoes --lote artefatos/lote-v2 --preparacao artefatos/preparacao --execucao artefatos/execucoes/lote-v2-35-flash-lite --politica config/politica_v1.json --confirmacoes-fora artefatos/revisao_fora-v1/confirmacoes_fora.jsonl --saida artefatos/decisoes-v1
```

Esse comando não lê `.env` nem acessa a API. Ele revalida as fontes e as sugestões, aplica a política e usa as oito revisões registradas. Uma saída completa idêntica é reutilizada sem regravar arquivos; mudanças exigem uma nova pasta, preservando a versão congelada. Sem todas as revisões necessárias, grava a trilha e as pendências, não gera o CSV e retorna código 1. Entradas inválidas retornam código 2.

A execução repetida preservou bytes e datas de modificação dos produtos. Uma reprodução de decisões em pasta temporária gerou os mesmos quatro arquivos, byte a byte. Essa pasta preserva a versão 1; o [publicacao.csv da raiz](publicacao.csv) corresponde à versão 2 descrita abaixo. O verificador do módulo 7 também reconstrói essas decisões em uma pasta inicialmente vazia.

### Avaliação e diagnóstico sem API

O pacote da auditoria e as referências da versão 1 estão salvos. Para reproduzir a comparação com as referências congeladas e o diagnóstico de cobertura:

```powershell
python -B -m classificacao_topicos avaliar-auditoria --preparacao artefatos/preparacao --auditoria artefatos/auditoria-v1 --decisoes artefatos/decisoes-v1 --revisoes artefatos/revisao_auditoria-v1/referencias --saida artefatos/avaliacao-v1-reproduzida
python -B -m classificacao_topicos.diagnostico_cobertura --decisoes artefatos/decisoes-v1 --saida artefatos/analises/cobertura-v1.json
```

A avaliação revalida os hashes da seleção, das decisões e das referências e grava métricas e comparação por questão. O diagnóstico conta sinais e suas sobreposições, sem reclassificar questões. Ambos são offline e não carregam credenciais. Para preparar outra seleção, `preparar-auditoria` exige uma nova pasta vazia; preserve o pacote da versão 1. Os contratos e limites estão em [Protocolo de avaliação](docs/AVALIACAO.md) e [Auditoria da versão 1](docs/AUDITORIA_V1.md).

### Experimento 5C e decisões v2 sem API

Com a preparação, o piloto de classificação v2 e os artefatos congelados disponíveis, reconstrua os prompts do segundo passe e reproduza os cálculos em pastas novas:

```powershell
python -B -m classificacao_topicos preparar-lote --preparacao artefatos/preparacao --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-desambiguacao-v1 --prompt prompts/desambiguacao_v1.txt --versao-prompt desambiguacao-v1
python -B -m classificacao_topicos.experimento_cobertura propor --raiz . --saida artefatos/reproducao-5c/propostas
python -B -m classificacao_topicos.experimento_cobertura concluir --raiz . --saida artefatos/reproducao-5c/decisoes
```

Esses comandos são offline e não leem `.env`. `propor` revalida o manifesto completo e os recibos dos 41 IDs e reproduz as 23 propostas. `concluir` confere as propostas e referências congeladas nos caminhos originais, reaplica o critério ao lote inteiro e reproduz as decisões finais. `--saida` muda somente o destino da reprodução; não substitui as fontes congeladas. Uma saída divergente é recusada, e uma saída idêntica é reutilizada. Não é necessário executar novamente `executar-lote` ou recongelar referências.

O contrato de seleção `--ids-arquivo`, os limites das chamadas realizadas e a procedência estão em [Experimento controlado de cobertura](docs/EXPERIMENTO_COBERTURA_V2.md). As quatro falhas esgotadas do segundo passe permanecem registradas e não impedem reproduzir o resultado negativo do experimento.

### Revalidação de uma resposta já salva

Se uma falha local decorreu de um validador posteriormente corrigido, é possível reexaminar as respostas existentes sem chamar a API:

```powershell
python -m classificacao_topicos revalidar-recibo --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --id Q0005
```

O comando seleciona a primeira tentativa cronológica que passa integralmente pelo extrator JSON, pelo esquema, pelos IDs ativos e pela validação atual de evidência. Não escolhe pelo tema ou pela confiança. Se nenhuma tentativa passar, não grava recuperação. O resultado fica em `Q0005.revalidacao.json`, com hashes da origem e da tentativa selecionada; `Q0005.json` permanece intacto.

O executor do lote e o módulo de decisões verificam esse arquivo derivado antes de utilizá-lo. A recuperação não é uma chamada nova, não altera consumo e não autoriza publicação: a sugestão continua sujeita à política temática. Uma derivação inconsistente interrompe o processamento. Ao contar recibos diretamente, selecionar apenas nomes no formato `Q` + quatro dígitos + `.json`; `Q*.json` também inclui arquivos de revalidação e não representa uma contagem de chamadas.

## Entregas

- **CSV de decisões v2 concluído e congelado**: [publicacao.csv](publicacao.csv), com 77 `publicar`, 278 `revisar` e quatro `fora`, seguindo o formato definido no `LEIA-ME.md` e acompanhado de trilha e manifesto em `artefatos/decisoes-v2`. A versão 1 permanece em sua pasta original.
- **Previsão concluída**: [previsao.txt](previsao.txt), com ponto e intervalo para precisão e cobertura, antes de conhecer a avaliação da organização. A precisão é uma previsão subjetiva por cenários; a cobertura é contada.
- **Relatório concluído em cinco páginas**: [PDF](relatorio.pdf) e [Markdown](relatorio.md), com raciocínio, hipóteses e experimentos, diagnóstico, produção para 50 mil questões por semana e memo ao professor. Inclui custos, qualidade contínua e integração com importação, revisão e reportes.
- **Código e evidências disponíveis**: preparação, prompts, API, recibos, regras, revisões, auditoria, experimento negativo de cobertura, decisões v2, cálculo da previsão e geradores documentais. [Verificador offline](scripts/verificar_entrega.py) e [roteiro de apresentação](docs/APRESENTACAO.md) complementam a entrega.

O memo ocupa a quinta página do PDF, com achados, mudanças recomendadas nos temas e apoio necessário do especialista.

## Rastreabilidade

Os recibos preservam cada tentativa e o uso informado pelo provedor. As revisões dos candidatos a `fora` registram responsável, justificativa, fonte consultada e sugestão original. A trilha de decisões vincula esses elementos aos produtos por SHA-256. A auditoria e o experimento 5C acrescentam referências congeladas, propostas, fontes, incidentes e métricas. A versão 1 permanece preservada, e a intervenção em Q0180 está identificada na trilha v2.
