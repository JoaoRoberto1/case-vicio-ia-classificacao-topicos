# Decisões da versão 1

O módulo 5A foi concluído em 16/10/2026 com **359 decisões: 78 `publicar`, 277 `revisar` e 4 `fora`**, sem pendências. A cobertura observada é 78/359, ou 21,73%. O [publicacao.csv da raiz](../publicacao.csv) é idêntico à versão congelada; a trilha e o manifesto estão em [artefatos/decisoes-v1](../artefatos/decisoes-v1/manifesto_decisoes.json). Este é o ponto de revisão e commit anterior ao módulo 5B.

Esta etapa aplicou regras aos recibos já existentes e revisou separadamente os candidatos sem tema. Não mediu a precisão jurídica das 78 decisões `publicar`. As revisões são de IA, sem especialista jurídico, e não substituem os rótulos reservados pela organização.

## Aplicação da política

A [política v1](../config/politica_v1.json), registrada em 14/10/2026, foi preservada, assim como o prompt `classificacao-v2` e o modelo `gemini-3.5-flash-lite`. O módulo 5A não fez novas chamadas Gemini nem acessou credenciais.

Antes de aplicar a política, o programa confere os hashes das fontes, os 359 recibos e a revalidação derivada de Q0005. Exige sugestões tecnicamente válidas, IDs ativos, contrato JSON correto e evidência presente na questão. Os recibos originais e seus históricos permanecem intactos.

Uma sugestão só pode receber `publicar` se atender a todos os critérios:

- Confiança autodeclarada de pelo menos 0,95.
- Ausência de solicitação de revisão e de temas alternativos.
- Tema central abaixo do nível de disciplina e fora dos IDs ambíguos registrados.
- No máximo um tema extra.

O descumprimento desses critérios gera `revisar`, com motivo. Uma proposta `sem_tema=true` fica pendente até a revisão separada; falhas técnicas nunca são convertidas em `fora`.

## Revisão dos oito candidatos fora

A [revisão documentada](../artefatos/revisao_fora-v1/revisoes.json) registra a leitura separada das questões e do catálogo, as alternativas consideradas, as fontes oficiais consultadas, as limitações e a adjudicação por IA. O arquivo [confirmacoes_fora.jsonl](../artefatos/revisao_fora-v1/confirmacoes_fora.jsonl) contém a versão utilizada pelo programa.

| Questão | Resultado da revisão | Tema sugerido | Confiança exportada |
| --- | --- | --- | ---: |
| Q0039 | `fora` | Vazio | 0, sentinela |
| Q0113 | `fora` | Vazio | 0, sentinela |
| Q0142 | `fora` | Vazio | 0, sentinela |
| Q0168 | `fora` | Vazio | 0, sentinela |
| Q0154 | `revisar` | 5135 | 0,75 |
| Q0261 | `revisar` | 5136 | 0,80 |
| Q0298 | `revisar` | 5222 | 0,65 |
| Q0358 | `revisar` | 5133 | 0,98 |

Os quatro temas encontrados são propostas para revisão. Mesmo Q0358, com confiança autodeclarada de 0,98 na correção, permanece em `revisar`: uma correção de candidato `fora` não autoriza publicação automática.

Cada registro de revisão exige `id`, `sem_tema`, `situacao`, `justificativa`, `responsavel` e `tipo_referencia`:

- Ausência confirmada: `sem_tema=true` e `situacao="confirmado"`.
- Tema encontrado: `sem_tema=false`, `situacao="tema_encontrado"` e `sugestao_corrigida` completa no contrato de classificação. A sugestão corrigida exige `requer_revisao=true`, tema ativo de nível maior que zero e evidência válida.

A trilha conserva a sugestão original, a política aplicada a ela, a revisão e a eventual sugestão corrigida. A correção também passa pela política, mas seu destino final é sempre `revisar`. Uma dúvida de escopo com candidato plausível não é tratada como ausência confirmada de tema.

## Formato e origem da confiança

O [CSV congelado](../artefatos/decisoes-v1/publicacao.csv) usa UTF-8, vírgula como delimitador, cabeçalho e 359 registros na ordem original:

```text
id,decisao,tema_central_id,extras_ids,confianca,motivo
```

| Campo | Contrato |
| --- | --- |
| `id` | Um registro para cada ID fornecido, sem duplicatas. |
| `decisao` | `publicar`, `revisar` ou `fora`. |
| `tema_central_id` | ID ativo em `publicar` e `revisar`; vazio em `fora`. |
| `extras_ids` | IDs ativos separados por ponto e vírgula; sem duplicatas nem repetição do central. Vazio nos quatro casos `fora`. |
| `confianca` | Número entre 0 e 1, com ponto decimal no CSV. |
| `motivo` | Obrigatório para `revisar` e `fora`; pode ser vazio para `publicar`. Justificativas completas ficam na trilha. |

Em `publicar` e nas revisões sem correção de candidato `fora`, a confiança vem da sugestão original do Gemini. Nos quatro temas encontrados, vem da sugestão corrigida pelo revisor de IA. Ambas são autodeclaradas e não calibradas; nenhuma representa precisão medida. A origem aparece em `origem_confianca` na trilha.

Nas decisões `fora`, o valor zero é uma **sentinela de não aplicabilidade**: não existe tema central cuja confiança possa ser exportada. Zero não significa probabilidade nula de a decisão `fora` estar correta. A confiança original do Gemini continua preservada na sugestão da trilha.

## Produtos e congelamento

| Produto | Conteúdo |
| --- | --- |
| [publicacao.csv](../artefatos/decisoes-v1/publicacao.csv) | As 359 decisões no formato de entrega. |
| [trilha_decisoes.jsonl](../artefatos/decisoes-v1/trilha_decisoes.jsonl) | Sugestões, política, revisões, correções, decisões e vínculos com os recibos. |
| [pendentes_fora.jsonl](../artefatos/decisoes-v1/pendentes_fora.jsonl) | Vazio nesta versão concluída. |
| [manifesto_decisoes.json](../artefatos/decisoes-v1/manifesto_decisoes.json) | Contagens, parâmetros, limites e hashes das fontes e produtos. |

O congelamento ocorre quando o conjunto está completo. Reexecutar o comando com as mesmas fontes e produtos retorna o mesmo resultado sem regravar arquivos. Se uma saída completa divergir da nova execução, o programa recusa a substituição e exige uma nova pasta. Uma saída preliminar válida pode avançar para completa quando as revisões faltantes forem fornecidas.

O CSV da raiz e a cópia congelada têm SHA-256 `fd6d504169d86c4002ed27ac892a5080f16c4533c27e4bf80daf6de501dd9ca3`.

Arquivos ausentes, extras, alterados ou incompatíveis com o manifesto são rejeitados. Não edite o CSV congelado para mudar decisões: uma mudança de dados, revisão ou política precisa gerar outra versão, mantendo esta como referência anterior à auditoria.

## Reprodução offline

Use Python 3.11 ou superior, sem dependências externas. Em um novo checkout, reconstrua os produtos preparados e os prompts expandidos, que são ignorados pelo Git:

```powershell
python -m classificacao_topicos preparar
python -m classificacao_topicos preparar-piloto
python -m classificacao_topicos preparar-piloto --saida artefatos/piloto-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -m classificacao_topicos preparar-lote --piloto-desenvolvimento artefatos/piloto-v2 --saida artefatos/lote-v2 --prompt prompts/classificacao_v2.txt --versao-prompt classificacao-v2
python -m classificacao_topicos preparar-decisoes --lote artefatos/lote-v2 --preparacao artefatos/preparacao --execucao artefatos/execucoes/lote-v2-35-flash-lite --politica config/politica_v1.json --confirmacoes-fora artefatos/revisao_fora-v1/confirmacoes_fora.jsonl --saida artefatos/decisoes-v1
```

Esses comandos não chamam a API nem leem `.env`; os recibos e a revalidação de Q0005 são reutilizados. A última chamada retorna um resumo JSON com contagens, revisões e zero chamadas de API.

| Código de saída de `preparar-decisoes` | Significado |
| --- | --- |
| 0 | Decisões completas, CSV gerado ou versão idêntica reutilizada. |
| 1 | Revisões de candidatos `fora` ainda pendentes; trilha salva, CSV não gerado. |
| 2 | Entradas inválidas ou conflito com a versão existente. |

O parâmetro `--confirmacoes-fora` é opcional para preparar uma saída preliminar. Neste lote ele é necessário para concluir os oito candidatos. Use outra pasta para uma inspeção preliminar, preservando `artefatos/decisoes-v1`.

## Verificações e próximo módulo

A suíte completa executou 233 testes em 71,644 segundos: **232 aprovados e um pulado**, por permissão de symlink no Windows. Os testes incluem geração do CSV, correção de candidatos `fora`, preservação dos recibos, congelamento, repetição idempotente e integração da CLI sem rede ou credenciais.

Na verificação dos artefatos reais, repetir a CLI preservou bytes e datas de modificação dos quatro produtos. A reprodução de `preparar_decisoes` em pasta temporária gerou os mesmos quatro arquivos, byte a byte, e a cópia de `publicacao.csv` na raiz foi conferida. Essa verificação reutilizou as entradas locais; a reprodução completa a partir de um novo checkout fica no módulo 7.

A auditoria real ainda não foi iniciada. Após a revisão e o commit do módulo 5A, o módulo 5B usará os comandos abaixo, com caminhos explícitos:

```powershell
python -m classificacao_topicos preparar-auditoria --preparacao artefatos/preparacao --lote artefatos/lote-v2 --decisoes artefatos/decisoes-v1 --politica config/politica_v1.json --saida artefatos/auditoria-v1
```

Esse comando prepara a seleção e o pacote para revisão cega. As referências precisam ser produzidas antes da avaliação:

```powershell
python -m classificacao_topicos avaliar-auditoria --preparacao artefatos/preparacao --auditoria artefatos/auditoria-v1 --decisoes artefatos/decisoes-v1 --revisoes artefatos/revisao_auditoria-v1 --saida artefatos/avaliacao-v1
```

O plano registrado separa o censo dos publicados do desenvolvimento e `min(80, N)` demais publicados. Nesta versão, há cinco publicados no desenvolvimento e 73 no restante: a regra resulta em **censo das 78 decisões `publicar`**, sem necessidade de amostragem parcial. A avaliação mantém o caráter provisório da referência por IA e não autoriza mudanças retroativas nesta versão. A previsão e o relatório final dependem dessa etapa. Os comandos de commit e o estado operacional estão no [ponto de retomada](RETOMADA.md).
