# Entrega da etapa complementar

**João Roberto de Oliveira Felix**

A entrega atual está em **`etapa-complementar/`**. Os arquivos de mesmo nome na raiz do repositório pertencem à primeira entrega e foram preservados. Compartilhe o endereço desta pasta para evitar que o avaliador abra o CSV, a previsão ou o relatório antigos.

O sistema está implementado, mas não atingiu a meta de publicação automática: foram 6/20 sugestões corretas no teste reservado e zero publicações nas 559 questões avaliadas oficialmente. O relatório e a previsão registram esse resultado, sem apresentar a precisão indefinida como 0% ou 100%.

## Arquivos para o avaliador

| Arquivo | Função |
|---|---|
| [README](../README.md) | Como executar e de onde vêm os dados e artefatos |
| [publicacao.csv](../publicacao.csv) | 659 linhas no esquema oficial |
| [previsao.txt](../previsao.txt) | Previsão para as 559 questões sem referência, com explicação da sentinela numérica |
| [relatorio.pdf](../relatorio.pdf) | Relatório para leitura e compartilhamento |
| [relatorio.md](../relatorio.md) | Conteúdo do relatório em formato revisável |
| [Defesa técnica](DEFESA_TECNICA.md) | Roteiro de seis minutos, demonstração e perguntas técnicas |
| [Checkpoint do módulo 4](../artefatos/checkpoints/modulo4.json) | Evidência da avaliação congelada e da reprodução registrada |

Os diretórios de código, `config/`, `anexos/`, `tests/` e `artefatos/` completam a reprodução. As dependências extras de preparação são separadas: classificar a partir do cache usa somente a biblioteca padrão do Python.

## Revisão antes de publicar o link

Na pasta `etapa-complementar/`, execute:

```console
python -B -S scripts/verificar_entrega.py
python -B -m classificacao_decisao regenerar
python -B -m classificacao_decisao verificar
```

O primeiro comando materializa uma cópia temporária dos arquivos de uma lista permitida e reproduz M1 e M4, conferindo os bytes. Ele reutiliza o Python instalado e sua biblioteca padrão, sem herdar credenciais, ambientes virtuais ou pesos. Os caches versionados entram como insumos; os experimentos M2 e M3 têm seus hashes conferidos, mas não são refeitos nesse comando. Isso não equivale a um clone Git nem a uma máquina virtual limpa.

Os demais comandos regeneram e verificam o resultado do classificador na pasta atual. Use a versão de Python e os resultados de reprodução registrados no README. Os comandos devem concluir com código de saída zero. A reprodução técnica não cria uma nova amostra estatística. Não execute duas gerações simultaneamente no mesmo diretório.

Antes do commit, confira o diff e o estado do Git a partir da raiz:

```console
git diff --check
git status --short
git diff --stat
```

O verificador não avalia documentos editoriais, PDF, estado do Git ou acesso remoto. Confira separadamente que o PDF tem no máximo quatro páginas, começa com o nome completo do autor e corresponde ao Markdown. Confira que os links do README apontam para esta etapa. Leia a explicação de precisão indefinida em `previsao.txt` e a limitação do reajuste final no relatório. Não altere configurações, código ou artefatos congelados para melhorar resultados depois de observar a reserva.

O commit e o push são feitos pelo autor após essa revisão. Sugestão de mensagem: `Conclui relatório, reprodução e defesa da etapa complementar`. Depois do push, abra o link público sem autenticação e confira o README, o PDF e os dois arquivos oficiais. A revisão local não confirma, por si só, que a versão remota contém esses arquivos.

## Arquivos públicos e gitignore

A conferência de nomes e tamanhos realizada em 21/10/2026, antes dos novos documentos do módulo 5, encontrou 733 arquivos rastreados, somando aproximadamente 44,5 MB; 118 arquivos e 34,3 MB pertenciam à etapa complementar. Esses valores representam os arquivos de trabalho rastreados, não o tamanho do histórico Git ou de um clone.

| Conteúdo | Decisão e motivo |
|---|---|
| Anexos oficiais, código, configurações, testes e documentação | Manter públicos para executar e revisar a entrega |
| Modelos numéricos, métricas, manifestos e checkpoints | Manter para rastrear seleção, congelamento e resultados negativos |
| Caches de embeddings M3 e M4 | Manter ambos: são entradas assinadas de etapas distintas; removê-los quebra a cadeia de reprodução |
| CSV e previsão na pasta e em `artefatos/decisoes-v1/` | Manter: a cópia da pasta é a entrega e a cópia assinada participa da verificação |
| `.env`, contexto pessoal, ambientes virtuais, pesos e temporários | Manter ignorados pelo Git |
| Primeira entrega na raiz e histórico anterior | Preservar; distingui-los no README e no link enviado |

Os dois arquivos de vetores ocupam 8.085.275 e 8.245.364 bytes. Eles são dados necessários à classificação sem codificador. Os pesos e o tokenizador somam cerca de 487 MB na preparação local e já ficam em `.cache-modelos/`, ignorada pelo Git. Não há motivo para adicionar esses pesos ao pacote público.

`git check-ignore` confirmou as regras para `.env`, contexto local, ambientes, temporários e pesos. A pesquisa de nomes potencialmente sensíveis entre os arquivos rastreados encontrou somente `.env.example`. Essa conferência não leu credenciais e não equivale a uma auditoria de segredos em todo o conteúdo ou no histórico. Não foi necessária uma mudança de `.gitignore` para este módulo. Uma regra de ignore também não retira um arquivo já rastreado.

## Envio pelo autor

O prazo comunicado é **22/10/2026 às 14h, no horário de São Paulo**. O endereço informado para envio é **carla@viciodeumaestudante.com.br**. Uma extensão dependeria de acordo com a recrutadora; não há extensão concedida registrada.

Use a URL pública da pasta `etapa-complementar/` na branch enviada e registre também o hash do commit entregue. A referência imutável por commit ajuda a identificar exatamente o material avaliado. O nome da branch deve corresponder à branch efetivamente publicada.

Texto sugerido, a ser preenchido e enviado pelo autor:

> Assunto: Etapa complementar do case de IA — João Roberto de Oliveira Felix
>
> Olá, Carla! Tudo bem?
>
> Segue minha entrega da etapa complementar: [link público da pasta etapa-complementar].
>
> O README reúne as instruções de execução; a pasta contém o CSV, a previsão, o relatório e os artefatos versionados. O relatório apresenta os resultados e as limitações, incluindo a ausência de cobertura automática sustentada pela calibração.
>
> Commit entregue: [hash].
>
> Obrigado pela oportunidade. Fico à disposição para a conversa técnica.
>
> João Roberto de Oliveira Felix

Este guia prepara a revisão e o envio. Ele não registra a realização de commit, push ou envio de e-mail.
