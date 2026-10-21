# Classificação de tópicos da Vício

**João Roberto de Oliveira Felix**

Implementação da etapa complementar do case de IA da Vício. O objetivo é classificar 659 questões jurídicas, estimar a chance de acerto e decidir entre `publicar`, `revisar` e `fora`, buscando pelo menos 95% de precisão nas publicadas e a maior cobertura compatível com essa meta.

**Estado atual: cinco módulos concluídos; entrega local validada em 21/10/2026.** O teste da receita congelada acertou 6/20 sugestões pelo critério do case. A calibração não sustentou publicação automática: a política envia as questões para revisão. O sistema está implementado, mas ainda não alcançou a meta de precisão com cobertura. O modelo semântico participa somente da preparação; a decisão usa vetores persistidos e código local.

## Entrega e execução rápida

| Arquivo | Conteúdo |
|---|---|
| [publicacao.csv](publicacao.csv) | 659 linhas; as 100 referências estão excluídas da cobertura oficial |
| [previsao.txt](previsao.txt) | Cobertura 0/559 e precisão indefinida, com sentinela numérica explicada |
| [Relatório PDF](relatorio.pdf) e [Markdown](relatorio.md) | Quatro páginas, incluindo o memo de uma página ao professor |
| [Defesa técnica](docs/DEFESA_TECNICA.md) | Roteiro de seis minutos, demonstração e perguntas técnicas |
| [Guia de entrega](docs/ENTREGA.md) | Revisão pública e orientação para commit, push e envio pelo autor |

Na pasta `etapa-complementar/`, com Python 3.11 ou superior:

```console
python -B -m classificacao_decisao regenerar
python -B -S scripts/verificar_entrega.py
```

Não é necessário instalar pacotes, fornecer `.env` ou baixar pesos para esses comandos. O primeiro refaz o CSV e a previsão a partir dos insumos e caches versionados; recusará arquivos existentes divergentes. O segundo copia apenas os arquivos necessários para uma pasta temporária e reconstrói os seis produtos M1, os quinze M4 e as duas entregas da pasta, comparando bytes. Os experimentos M2/M3 têm hashes conferidos, mas não são reexecutados por esse comando.

A cópia usa o Python instalado, com `-B -S -E`, sem pacotes externos, variáveis de credenciais, pesos ou conteúdo da primeira entrega. Rede Python e leitura de `.env` ficam bloqueadas. Isso é uma reprodução isolada por lista de arquivos, não um clone Git, contêiner ou teste em outro sistema operacional. Os caches são entradas; gerar embeddings é uma operação separada. A conferência editorial do PDF e do conteúdo público também é separada.

Cada execução sem argumentos grava uma nova evidência em `tmp/`. Para guardar uma evidência em outro caminho permitido e ainda inexistente, use `--evidencia tmp/minha-reproducao.json`. O comando recusa sobrescrever evidências.

A [reprodução registrada](artefatos/checkpoints/reproducao_modulo5.json) copiou 92 arquivos (33.954.493 bytes) e confirmou os 6 + 15 produtos e as duas entregas em **508,921 segundos**, cerca de oito minutos e meio. Os originais permaneceram idênticos. A suíte completa de **238 testes passou em 69,292 segundos**, com `python -X utf8 -B -S -m unittest discover -s tests -v`. O ambiente foi CPython 3.14.7 no Windows; houve outras tarefas concorrentes, portanto os tempos não são benchmark isolado. A geração M4 registrada levou 306,270 segundos. O [checkpoint M5](artefatos/checkpoints/modulo5.json) reúne as validações, os hashes e os limites.

## Relatório e diagnóstico reproduzíveis

O relatório começa com o nome completo do autor, contém quatro páginas e reserva a última ao memo. O Markdown é sua fonte editorial; o PDF incorpora a fonte tipográfica e pode ser reconstruído de forma determinística com as dependências documentais fixadas. A classificação não depende dessas bibliotecas.

Para regenerar e conferir o PDF em um ambiente separado no Windows:

```console
python -m venv tmp/venv-relatorio
tmp/venv-relatorio/Scripts/python.exe -m pip install -r requirements-relatorio.txt
tmp/venv-relatorio/Scripts/python.exe -B scripts/gerar_relatorio.py
tmp/venv-relatorio/Scripts/python.exe -B scripts/gerar_relatorio.py --verificar
```

A instalação das dependências documentais usa rede; a geração do PDF não usa modelo ou API. O gerador exige quatro páginas, confere o nome e a posição do memo; a revisão visual das páginas é registrada no checkpoint M5. Em outros sistemas, adapte o caminho do Python do ambiente virtual.

O [diagnóstico agregado](artefatos/entrega-m5-v1/diagnostico.json) reconcilia erros por relação na árvore e contas de escala sem reexecutar o classificador ou julgar questões com LLM. Para conferir seus bytes, use `python -B -S scripts/diagnosticar_entrega.py --verificar`. Os hashes vinculam as contagens às fontes congeladas.

Os módulos abaixo preservam a trajetória dos experimentos. Resultados e expressões no futuro nas seções históricas referem-se ao estado registrado ao encerrar cada módulo.

## Executar o módulo 1

Requisito: Python 3.11 ou superior. A preparação usa apenas a biblioteca padrão, sem chave de API ou conexão com modelos.

A partir da raiz deste repositório, entre na pasta da etapa complementar e execute:

```console
cd etapa-complementar
python -B -m classificacao_topicos preparar
python -B -m classificacao_topicos verificar
python -B -m unittest discover -s tests -v
```

O diretório padrão de saída é `artefatos/preparacao`. Para uma reprodução separada, os dois comandos aceitam `--saida CAMINHO`, em uma subpasta de `artefatos/` ou `tmp/`, por exemplo `--saida tmp/reproducao-m1`. A preparação é determinística: repetir com as mesmas fontes e configurações preserva os mesmos bytes. Se houver saída divergente, o comando recusa sobrescrevê-la; use outro diretório para experimentar.

| Arquivo gerado | Conteúdo |
|---|---|
| `questoes_preparadas.jsonl` | Texto preparado e metadados das 659 questões |
| `temas_preparados.json` | Árvore de temas e situação de cada nó |
| `rotulos_referencia.jsonl` | As 100 referências humanas fornecidas |
| `particoes.json` | Grupos de questões semelhantes e partições de avaliação |
| `diagnostico.json` | Contagens, verificações e limitações dos dados |
| `manifesto.json` | SHA-256 das fontes, configurações, código de preparação e produtos |

Validação de 20/10/2026: **33 testes aprovados**, sem erros ou testes pulados, em 28,020 segundos. A execução pela CLI preparou os dados em 1,333 segundo e verificou a reprodução em 1,587 segundo no ambiente registrado. O teste de integração também bloqueia conexões de rede durante a preparação, a repetição e a verificação. O [registro do módulo 1](artefatos/checkpoints/modulo1.json) contém ambiente, comandos, contagens e hashes.

As cinco partições externas têm 80 questões para treino e 20 para teste; cada treino externo tem três partições internas. O detector produziu 659 grupos unitários com o limiar adotado. O único aviso das partições é a ausência de rótulos nas questões recentes. Esses artefatos do módulo 1 continuam preservados.

## Executar o módulo 2

Na pasta `etapa-complementar`, com a preparação presente:

```console
python -B -m classificacao_local experimentar --saida artefatos/lexical-v1
python -B -m classificacao_local verificar --saida artefatos/lexical-v1
```

O experimento usa somente a biblioteca padrão, sem instalação adicional ou `.env`. O primeiro comando reutiliza arquivos idênticos e recusa divergências; o segundo reconstrói os sete produtos em memória e compara seus bytes. Para uma reprodução separada, use `--saida tmp/reproducao-m2`. Execute somente um processo por diretório de saída.

Antes da primeira medição, o [protocolo v2](docs/PROTOCOLO_AVALIACAO.md) reservou as 20 referências da primeira partição para o teste final, no módulo 4. Apenas as outras 80 orientam o desenvolvimento. A comparação atual usa suas três partições internas, sem treinar no exemplo que será avaliado.

| Resultado de desenvolvimento | Lexical | Lexical com leis |
|---|---:|---:|
| Acerto do primeiro tema, critério do case | 31/80 (38,75%) | 31/80 (38,75%) |
| Acerto exato, incluindo extras humanos | 18/80 (22,50%) | 18/80 (22,50%) |
| Tema aceitável entre cinco sugestões | 57/80 (71,25%) | 54/80 (67,50%) |

A receita lexical foi selecionada pelo desempate previamente fixado. Essas são métricas exploratórias sobre as 80 referências, incluindo seis fora da taxonomia. Não são precisão entre questões publicadas, probabilidade calibrada ou medição nas 559 questões sem rótulos.

O módulo deixa dois modelos em JSON, 160 predições internas e 559 sugestões intermediárias, além de protocolo, métricas e manifesto em [artefatos/lexical-v1](artefatos/lexical-v1/manifesto.json). **Nenhuma das 20 referências reservadas recebeu predição.** A [documentação do módulo 2](docs/MODULO2_CLASSIFICADOR.md) explica fórmulas, resultados, 87 testes aprovados e limitações.

A verificação reconstruiu os sete arquivos com os mesmos bytes em 83,159 segundos, com conexões de rede e leitura de `.env` bloqueadas. O [checkpoint do módulo 2](artefatos/checkpoints/modulo2.json) registra ambiente, validações e hashes. A reprodução byte a byte foi conferida em CPython 3.14.7 no Windows; outras plataformas ainda não foram testadas.

## Executar o módulo 3

Na pasta `etapa-complementar`, usando o cache versionado:

```console
python -B -m classificacao_experimentos experimentar --saida artefatos/melhorias-v1
python -B -m classificacao_experimentos verificar --saida artefatos/melhorias-v1
```

Esses comandos usam somente a biblioteca padrão do Python. Não precisam de chave, rede, bibliotecas de IA ou pesos do codificador. Para outra saída, use `--saida tmp/reproducao-m3`. Arquivos divergentes são recusados; execute somente um processo por diretório.

| Comparação de desenvolvimento | Lexical M2 | Híbrido selecionado |
|---|---:|---:|
| Acerto do primeiro tema, critério do case | 31/80 (38,75%) | 37/80 (46,25%) |
| Acerto exato, incluindo extras humanos | 18/80 (22,50%) | 24/80 (30,00%) |
| Tema aceitável entre cinco sugestões | 57/80 (71,25%) | 54/80 (67,50%) |

A diferença de seis acertos é exploratória: as mesmas 80 referências orientaram a escolha. O catálogo lexical sem exemplos acertou 34/80, enquanto embeddings sozinhos acertaram 21/80. A tabela completa, os resultados negativos e o desempate estão na [documentação do módulo 3](docs/MODULO3_EXPERIMENTOS.md). Esses valores não são precisão entre publicadas nem demonstram a meta de 95%.

A preparação local com `intfloat/multilingual-e5-small` gerou 639 vetores de questões e 371 de temas, sem vetor para a reserva de 20. O [cache e seu manifesto](artefatos/embeddings-e5-v1/manifesto.json) registram modelo, revisão, hashes, parâmetros e dependências. Os comandos para regenerá-lo estão na documentação; pesos e ambiente virtual ficam ignorados pelo Git.

O [experimento](artefatos/melhorias-v1/manifesto.json) preserva 560 predições de desenvolvimento, 559 sugestões intermediárias e o modelo selecionado. A [receita congelada](artefatos/melhorias-v1/receita_congelada.json) será a base da calibração. O [checkpoint do módulo 3](artefatos/checkpoints/modulo3.json) registra execução e validações.

Os 50 novos testes passaram. A verificação integral reconstruiu os sete produtos com bytes idênticos em 353,387 segundos, com rede, `.env`, pesos e importação das dependências do codificador bloqueados. Preparação e primeiro experimento levaram 316,514 e 274,690 segundos, respectivamente. A reprodução foi conferida em CPython 3.14.7 no Windows; os tempos não são um benchmark de produção.

## Executar o módulo 4

Na pasta `etapa-complementar`, a entrega é regenerada sem instalar bibliotecas de IA, fornecer chave ou chamar um codificador:

```console
python -B -m classificacao_decisao regenerar
python -B -m classificacao_decisao verificar
```

O primeiro comando refaz o ajuste final e produz [publicacao.csv](publicacao.csv) e [previsao.txt](previsao.txt). Reutiliza o cache, o calibrador, a política e os registros congelados. O segundo reconstrói a calibração, o congelamento, a avaliação reservada e a entrega, comparando os bytes. Ambos bloqueiam rede Python, leitura de `.env`, acesso aos pesos e importação das dependências do codificador. Arquivos divergentes são recusados; use uma cópia limpa para reproduzir, preservando resultados anteriores.

| Medição | Desenvolvimento | Teste reservado |
|---|---:|---:|
| Acerto por ramo | 37/80 (46,25%) | 6/20 (30,00%) |
| Acerto exato | 24/80 (30,00%) | 3/20 (15,00%) |
| Tema aceitável entre cinco sugestões | 54/80 (67,50%) | 12/20 (60,00%) |
| Publicações da política | 0 | 0 |

O calibrador constante teve o menor Brier entre as três alternativas no desenvolvimento. Ele estima uma taxa global, sem diferenciar o risco das questões. Os calibradores de escore e de escore com margem não melhoraram essa métrica nem atingiram probabilidades de 0,95. A política foi congelada antes do teste de 20 referências e não foi alterada após seu resultado.

A entrega contém 659 linhas; as 100 referências ficam excluídas da autoavaliação oficial. Nas 559 restantes, a cobertura automática é **0/559** e a precisão entre publicadas é **indefinida**, pois não há publicações. O `0.00000000` exigido no campo numérico da previsão é uma sentinela explicada no próprio arquivo; o [JSON de evidências](artefatos/decisoes-v1/previsao.json) registra `null`. O intervalo `0–1` indica ausência de informação, sem representar um intervalo de confiança estimado.

As 80 linhas de desenvolvimento usam temas OOF e probabilidades crossfit; as 20 da reserva mantêm as previsões do teste congelado. As 559 sem referência usam o classificador reajustado nos textos das 100 referências e o calibrador preservado das 80. Esse reajuste final não recebeu teste independente. `Fora` não foi automatizado com o suporte disponível.

Método, custos e limitações estão no [módulo 4](docs/MODULO4_CALIBRACAO_DECISOES.md). O [congelamento](artefatos/calibracao-v1/congelamento.json), o [teste reservado](artefatos/reserva-v1/metricas_reserva.json) e o [checkpoint](artefatos/checkpoints/modulo4.json) registram a ordem das etapas e suas validações. Os módulos 1 a 3 permanecem preservados.

Os **81 novos testes** passaram. A geração real levou 306,270 segundos; a verificação integral reconstruiu 15 produtos e conferiu as duas entregas da raiz com bytes idênticos em 268,722 segundos, com os bloqueios da CLI ativos. A auditoria estrutural confirmou o esquema, os hashes, o isolamento dos conjuntos e a procedência 80/20/559. Esses tempos foram medidos em CPython 3.14.7 no Windows e não são um benchmark de produção.

## Dados e regra desta etapa

As fontes estão preservadas em [anexos](anexos/LEIA-ME.md), no [enunciado](<case-ia-classificacao-de-topicos (2).pdf>) e no [README do case](README-do-case.md). Correspondem à [atualização oficial de 19/10/2026](https://github.com/viciod/case-vicio-ia/commit/0264e4ca2afd7afebdd45f542784e6079ee804ca).

- São 659 questões: 359 do banco anterior e 300 de concursos recentes.
- A árvore tem 377 temas, dos quais 375 estão ativos.
- As 100 referências humanas pertencem ao lote anterior; 8 são fora da taxonomia.
- A avaliação oficial exclui essas 100 referências: restam **559 questões**, sendo 259 antigas e 300 recentes.

O modelo de linguagem pode participar da preparação documentada, como na geração de embeddings em cache. Não pode escolher, votar, julgar ou validar temas. A classificação final deverá executar localmente, sem chamar modelos de linguagem. Rótulos e julgamentos de IA da primeira etapa ficam excluídos do treinamento e da avaliação.

Os rótulos humanos permitem medir o sistema, mas não comprovam, por si só, precisão de 95% nas questões recentes. O [protocolo de avaliação](docs/PROTOCOLO_AVALIACAO.md) separa ajuste, calibração e avaliação para controlar essa incerteza.

A [origem dos insumos](config/fontes_oficiais.json) e o [reaproveitamento de código](config/reuso_codigo.json) estão registrados. Dois módulos estruturais foram copiados integralmente do projeto anterior; a leitura e preparação das questões foram adaptadas. Os comandos deste repositório não dependem da presença do projeto antigo.

## Módulos e próxima parada

O [plano de execução](docs/PLANO_EXECUCAO.md) define cinco módulos e os critérios de conclusão. O módulo 5 fecha relatório, reprodução e defesa, incluindo o resultado negativo para publicação automática. A próxima parada é a revisão da entrega e o commit pelo autor. A reserva já foi avaliada; novos ajustes orientados por esse resultado serão desenvolvimento exploratório e precisarão de outras referências para avaliação independente.

O prazo comunicado pela recrutadora é **22/10/2026, às 14h, no horário de São Paulo**; o PDF mantém o prazo “a combinar”.
