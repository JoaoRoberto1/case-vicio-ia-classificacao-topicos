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

Os requisitos são definidos pelo PDF oficial e pelo `LEIA-ME.md`. O arquivo `entrega_modelo.csv` não é a entrega final; `publicacao.csv` ainda será produzido.

## Regras importantes

- Todas as 359 questões precisam receber uma decisão.
- Temas inativos não podem ser utilizados.
- `disciplina_origem` e `assunto_origem` podem estar errados e não constituem um gabarito.
- Os rótulos dos especialistas foram reservados pela organização para avaliação e não foram disponibilizados.
- Dúvida entre temas não é, por si só, motivo para usar `fora`; essa decisão indica que nenhum tema da árvore serve.
- Conforme o `LEIA-ME.md`, `tema_central_id` é obrigatório em `publicar` e em `revisar` e fica vazio em `fora`. O campo `motivo` é obrigatório em `revisar` e em `fora`.

## Estado atual

O módulo de preparação dos dados e da árvore está implementado e verificado. Ele preserva as fontes, prepara as 359 questões, valida os 377 registros da árvore e gera um diagnóstico reproduzível.

**Terceiro bloco de 20 chamadas concluído em 15/10/2026; aguardando revisão e commit do usuário.** Consulte [Ponto de retomada](docs/RETOMADA.md) para o estado salvo, módulos e próximos comandos.

Dois pilotos reais com os mesmos 20 casos estão concluídos. O prompt v2 reconheceu melhor condições de revisão e foi escolhido para o lote de 359 questões com Gemini 3.5 Flash-Lite no plano gratuito. O lote contém 109 respostas tecnicamente válidas, uma resposta rejeitada e 249 IDs sem recibo. Os vinte sucessos do segundo piloto estão incluídos nesse total, sem novas chamadas. O terceiro bloco de 15/10 acrescentou dezenove sucessos em vinte chamadas, sem falha da API. Q0083 ficou pendente porque a evidência juntou trechos separados usando reticências, contrariando a exigência de trecho literal. Q0005 continua recuperada pela revalidação offline do bloco anterior, com o recibo original e suas quatro tentativas preservados. A avaliação temática e as entregas finais ainda estão pendentes.

Sem revisor jurídico disponível, a referência local será produzida por IA e identificada dessa forma. Concordância entre modelos e intervalos amostrais condicionados a essa referência não comprovam a meta de precisão jurídica. A política operacional foi registrada antes da inspeção dos novos resultados; a auditoria será sorteada após congelar as decisões.

- [Plano e acompanhamento dos módulos](docs/PLANO_EXECUCAO.md)
- [Protocolo de avaliação e ambiguidades](docs/AVALIACAO.md)
- [Configuração da API gratuita para o piloto](docs/CONFIGURACAO_API.md)
- [Experimentos dos pilotos e resultados observados](docs/PILOTO_V1.md)
- [Política operacional registrada](config/politica_v1.json)

```mermaid
flowchart LR
    A[Questões e árvore originais] --> B[Preparação e validação]
    B --> C[Prompt com catálogo ativo]
    C --> D[Gemini e recibos com retomada]
    D --> E[Política de decisão]
    E --> F[Congelamento e amostra cega]
    F --> G[Avaliação e previsão]
    G --> H[CSV e relatório]
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

Cada bloco faz no máximo vinte novas chamadas; sucessos válidos são reutilizados. Ao terminar o comando, é possível revisar o resumo, parar e commitar os recibos antes de iniciar outro bloco. A opção de continuar salva falhas locais de validação e avança para outros IDs. Falhas do provedor, autenticação ou cota continuam interrompendo a execução. Falhas nunca viram `fora`. O retorno da CLI é diferente de zero se restarem respostas inválidas ou se a execução parar em erro. A evidência precisa existir em um campo da questão; são toleradas apenas diferenças de caixa e espaços, sem corrigir palavras, acentos, pontuação ou OCR.

Os prompts expandidos `entradas.jsonl` são ignorados pelo Git para evitar aproximadamente 39 MB de catálogo repetido. Em um novo checkout, execute a preparação e os comandos `preparar-piloto`/`preparar-lote` antes de ler os recibos; os arquivos são reconstruídos com os mesmos hashes. `.gitattributes` preserva os bytes dos dados, prompts, configurações e artefatos assinados, inclusive no Windows.

As instruções de exportação e auditoria serão acrescentadas quando esses módulos estiverem integrados e verificados.

### Revalidação de uma resposta já salva

Se uma falha local decorreu de um validador posteriormente corrigido, é possível reexaminar as respostas existentes sem chamar a API:

```powershell
python -m classificacao_topicos revalidar-recibo --lote artefatos/lote-v2 --execucao artefatos/execucoes/lote-v2-35-flash-lite --id Q0005
```

O comando seleciona a primeira tentativa cronológica que passa integralmente pelo extrator JSON, pelo esquema, pelos IDs ativos e pela validação atual de evidência. Não escolhe pelo tema ou pela confiança. Se nenhuma tentativa passar, não grava recuperação. O resultado fica em `Q0005.revalidacao.json`, com hashes da origem e da tentativa selecionada; `Q0005.json` permanece intacto.

O executor do lote e o módulo de decisões verificam esse arquivo derivado antes de utilizá-lo. A recuperação não é uma chamada nova, não altera consumo e não autoriza publicação: a sugestão continua sujeita à política temática. Uma derivação inconsistente interrompe o processamento. Ao contar recibos diretamente, selecionar apenas nomes no formato `Q` + quatro dígitos + `.json`; `Q*.json` também inclui arquivos de revalidação e não representa uma contagem de chamadas.

## Entregas previstas

Todas as entregas abaixo estão **pendentes**:

- **`publicacao.csv`**: uma linha com a decisão para cada uma das 359 questões, seguindo o formato definido no `LEIA-ME.md`.
- **`previsao.txt`**: previsão de precisão nas publicadas e de cobertura, cada uma com seu intervalo e uma explicação da metodologia, antes de conhecer o resultado da avaliação da organização.
- **Relatório de até 5 páginas, em PDF ou Markdown**: raciocínio, hipóteses e experimentos; diagnóstico dos dados e temas; proposta de produção; e memo para o professor, especialista em Direito. A proposta de produção deverá abordar 50 mil questões por semana e novas importações, técnicas de IA, custo por questão, medição contínua da qualidade e integração com importação, revisão e reportes dos alunos.
- **Código, prompts, regras de decisão e instruções de reprodução**: documentação do processo completo de classificação e estimativa de precisão, incluindo as chamadas a modelos que forem utilizadas.

O enunciado solicita um memo de uma página, cobrindo achados, mudanças recomendadas nos temas e apoio necessário do especialista. Como proposta de organização da entrega, será reservada uma das cinco páginas do relatório para esse memo.

## Rastreabilidade

Serão registrados os experimentos, as decisões manuais e seus motivos, os modelos utilizados, o custo aproximado, o tempo gasto e as limitações. Esses registros acompanharão a implementação e a avaliação, distinguindo propostas, procedimentos executados e resultados observados.
