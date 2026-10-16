# Case Vício — Classificação de tópicos

## Visão geral

Solução em desenvolvimento para o processo seletivo de IA da Vício (Método VDE), voltada à classificação de questões de concursos jurídicos por tópico.

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

O módulo de preparação dos dados e da árvore está implementado e verificado. Ele preserva as fontes, prepara as 359 questões, valida os 377 registros da árvore e gera um diagnóstico reproduzível.

**Módulo 5A concluído em 16/10/2026: 359 decisões, sem pendências técnicas ou de confirmação de `fora`.** O CSV e sua trilha estão congelados em [artefatos/decisoes-v1](artefatos/decisoes-v1/manifesto_decisoes.json). Consulte [Decisões da versão 1](docs/DECISOES_V1.md) para as regras e a reprodução offline, e [Ponto de retomada](docs/RETOMADA.md) para o checkpoint e os comandos de commit.

| Decisão | Quantidade |
| --- | ---: |
| `publicar` | 78 |
| `revisar` | 277 |
| `fora` | 4 |
| Total | 359 |

A cobertura observada é **78/359 = 21,73%**. A precisão das decisões `publicar` ainda não foi medida; confiança autodeclarada e validação técnica não comprovam a meta de 95%.

Dois pilotos reais com os mesmos 20 casos estão concluídos. O prompt v2 reconheceu melhor condições de revisão e foi escolhido para o lote de 359 questões com Gemini 3.5 Flash-Lite no plano gratuito. O lote completo contém 358 recibos com sucesso e a recuperação offline anterior de Q0005, totalizando 359 sugestões válidas, sem falhas técnicas pendentes. Os vinte sucessos do segundo piloto estão incluídos nesse total, sem novas chamadas.

A continuação final concluiu as 197 questões restantes em 227 chamadas: 197 sucessos, vinte falhas HTTP 503 e dez respostas rejeitadas pela validação local, todas recuperadas nas novas tentativas. As 29 invocações internas avançaram automaticamente conforme autorizado pelo usuário. Os 162 recibos anteriores, o derivado de Q0005 e os históricos foram preservados. Modelo, prompt, política e validadores permaneceram iguais. O lote acumula 404 tentativas, incluindo as do piloto v2 reutilizado; revalidação offline não conta como chamada.

O módulo 5A aplicou a política registrada sem alterar modelo, prompt ou seus parâmetros. A revisão separada por IA dos oito candidatos a `fora` confirmou quatro e encaminhou outros quatro a `revisar`, com temas sugeridos e justificativas rastreáveis. Foram reutilizados todos os recibos; esta etapa fez **zero chamadas Gemini**. A suíte local executou 233 testes: 232 aprovados e um pulado por limitação de permissão de symlink no Windows.

O projeto está no ponto de revisão e commit do módulo 5A. O próximo módulo é o 5B: preparar a auditoria, produzir referências e avaliar as classificações. Pela regra registrada, serão revisadas todas as 78 decisões `publicar`: cinco do desenvolvimento e 73 restantes. A auditoria real, a previsão de precisão e o relatório final ainda estão pendentes.

Sem revisor jurídico disponível, a referência local será produzida por IA e identificada dessa forma. Concordância entre modelos e intervalos amostrais condicionados a essa referência não comprovam a meta de precisão jurídica. A política operacional foi registrada antes da inspeção dos novos resultados; o pacote de auditoria será preparado a partir das decisões congeladas, seguindo o protocolo registrado.

- [Plano e acompanhamento dos módulos](docs/PLANO_EXECUCAO.md)
- [Protocolo de avaliação e ambiguidades](docs/AVALIACAO.md)
- [Configuração da API gratuita para o piloto](docs/CONFIGURACAO_API.md)
- [Experimentos dos pilotos e resultados observados](docs/PILOTO_V1.md)
- [Decisões congeladas e revisão dos candidatos fora](docs/DECISOES_V1.md)
- [Política operacional registrada](config/politica_v1.json)

```mermaid
flowchart LR
    A[Questões e árvore originais] --> B[Preparação e validação]
    B --> C[Prompt com catálogo ativo]
    C --> D[Gemini e recibos com retomada]
    D --> E[Política de decisão]
    E --> F[CSV e trilha congelados]
    F --> G[Revisão cega e avaliação]
    G --> H[Previsão e relatório]
```

## Como executar

Use Python 3.11 ou superior. A implementação atual utiliza somente a biblioteca padrão e foi verificada localmente com Python 3.14.7. Não é necessário instalar dependências.

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

Depois de seguir a [configuração gratuita](docs/CONFIGURACAO_API.md), confirmar o Free Tier e conferir as cotas, valide a integração com uma chamada sintética curta. O modelo que funcionou neste ambiente foi selecionado assim no PowerShell:

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

Para reproduzir a versão v2 e preparar o lote completo:

```powershell
python -m classificacao_topicos preparar-piloto --saida artefatos/piloto-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -m classificacao_topicos executar-lote --lote artefatos/lote-v2 --saida artefatos/execucoes/lote-v2-35-flash-lite --limite 20 --intervalo-segundos 10 --continuar-erros-validacao
```

Com `--limite 20`, cada invocação faz no máximo vinte novas chamadas; sucessos válidos são reutilizados. Ao terminar o comando, é possível revisar o resumo, parar e commitar os recibos antes de iniciar outro bloco. Para a conclusão de 16/10, as invocações foram repetidas automaticamente, com espera após falhas transitórias, conforme o [registro da execução contínua](artefatos/experimentos/conclusao-lote-v2-2026-10-16.json). O limite de proteção dessa continuação era de 450 novas chamadas; foram necessárias 227.

A opção de continuar salva falhas locais de validação e avança para outros IDs. Falhas do provedor, autenticação ou cota continuam interrompendo cada invocação. Falhas nunca viram `fora`. O retorno da CLI é diferente de zero se restarem respostas inválidas ou se a execução parar em erro. A evidência precisa existir em um campo da questão; são toleradas apenas diferenças de caixa e espaços, sem corrigir palavras, acentos, pontuação ou OCR. Com o lote completo e os arquivos íntegros, a repetição do comando reutiliza os 359 resultados e não faz novas chamadas.

Os prompts expandidos `entradas.jsonl` são ignorados pelo Git para evitar aproximadamente 39 MB de catálogo repetido. Em um novo checkout, execute a preparação e os comandos `preparar-piloto`/`preparar-lote` antes de ler os recibos; os arquivos são reconstruídos com os mesmos hashes. `.gitattributes` preserva os bytes dos dados, prompts, configurações e artefatos assinados, inclusive no Windows.

### Decisões sem API

Com os dados preparados, os prompts reconstruídos e os recibos versionados disponíveis, execute:

```powershell
python -m classificacao_topicos preparar-decisoes --lote artefatos/lote-v2 --preparacao artefatos/preparacao --execucao artefatos/execucoes/lote-v2-35-flash-lite --politica config/politica_v1.json --confirmacoes-fora artefatos/revisao_fora-v1/confirmacoes_fora.jsonl --saida artefatos/decisoes-v1
```

Esse comando não lê `.env` nem acessa a API. Ele revalida as fontes e as sugestões, aplica a política e usa as oito revisões registradas. Uma saída completa idêntica é reutilizada sem regravar arquivos; mudanças exigem uma nova pasta, preservando a versão congelada. Sem todas as revisões necessárias, grava a trilha e as pendências, não gera o CSV e retorna código 1. Entradas inválidas retornam código 2.

A execução repetida preservou bytes e datas de modificação dos produtos. Uma reprodução de decisões em pasta temporária gerou os mesmos quatro arquivos, byte a byte. O [publicacao.csv da raiz](publicacao.csv) é idêntico à cópia congelada. A reprodução completa em um novo checkout será verificada no módulo 7.

Os comandos `preparar-auditoria` e `avaliar-auditoria` também estão integrados e testados com dados sintéticos. Seu uso na população real pertence ao módulo 5B. Os argumentos e os contratos dos arquivos estão em [Decisões da versão 1](docs/DECISOES_V1.md).

### Revalidação de uma resposta já salva

Se uma falha local decorreu de um validador posteriormente corrigido, é possível reexaminar as respostas existentes sem chamar a API:

```powershell
python -m classificacao_topicos revalidar-recibo --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --id Q0005
```

O comando seleciona a primeira tentativa cronológica que passa integralmente pelo extrator JSON, pelo esquema, pelos IDs ativos e pela validação atual de evidência. Não escolhe pelo tema ou pela confiança. Se nenhuma tentativa passar, não grava recuperação. O resultado fica em `Q0005.revalidacao.json`, com hashes da origem e da tentativa selecionada; `Q0005.json` permanece intacto.

O executor do lote e o módulo de decisões verificam esse arquivo derivado antes de utilizá-lo. A recuperação não é uma chamada nova, não altera consumo e não autoriza publicação: a sugestão continua sujeita à política temática. Uma derivação inconsistente interrompe o processamento. Ao contar recibos diretamente, selecionar apenas nomes no formato `Q` + quatro dígitos + `.json`; `Q*.json` também inclui arquivos de revalidação e não representa uma contagem de chamadas.

## Entregas

- **CSV de decisões concluído e congelado**: [publicacao.csv](publicacao.csv), com uma decisão para cada uma das 359 questões, seguindo o formato definido no `LEIA-ME.md` e acompanhado de trilha e manifesto em `artefatos/decisoes-v1`.
- **`previsao.txt` pendente**: previsão de precisão nas publicadas e de cobertura, cada uma com seu intervalo e uma explicação da metodologia, antes de conhecer o resultado da avaliação da organização.
- **Relatório de até 5 páginas pendente, em PDF ou Markdown**: raciocínio, hipóteses e experimentos; diagnóstico dos dados e temas; proposta de produção; e memo para o professor, especialista em Direito. A proposta de produção deverá abordar 50 mil questões por semana e novas importações, técnicas de IA, custo por questão, medição contínua da qualidade e integração com importação, revisão e reportes dos alunos.
- **Código, prompts, regras de decisão e instruções disponíveis até o módulo 5A**: as interfaces de auditoria e avaliação estão testadas, mas seus resultados reais e a documentação final dependem do módulo 5B.

O enunciado solicita um memo de uma página, cobrindo achados, mudanças recomendadas nos temas e apoio necessário do especialista. Como proposta de organização da entrega, será reservada uma das cinco páginas do relatório para esse memo.

## Rastreabilidade

Os recibos preservam cada tentativa e o uso informado pelo provedor. As revisões dos candidatos a `fora` registram responsável, justificativa, fonte consultada e sugestão original. A trilha de decisões vincula esses elementos aos produtos por SHA-256. A avaliação acrescentará suas referências e métricas sem alterar retroativamente esta versão congelada.
