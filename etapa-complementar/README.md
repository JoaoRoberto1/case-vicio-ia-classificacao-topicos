# Classificação de tópicos da Vício

**João Roberto de Oliveira Felix**

Implementação da etapa complementar do case de IA da Vício. O objetivo é classificar 659 questões jurídicas, estimar a chance de acerto e decidir entre `publicar`, `revisar` e `fora`, buscando pelo menos 95% de precisão nas publicadas e a maior cobertura compatível com essa meta.

**Estado atual: módulo 2 concluído, pronto para revisão e commit.** O primeiro classificador local usa texto, catálogo de temas e referências humanas, sem chamadas a modelos. A primeira comparação acertou 31/80 referências de desenvolvimento (38,75% pelo critério do case). É uma base de comparação ainda insuficiente para publicação automática; calibração, `publicacao.csv`, previsão e relatório final pertencem aos próximos módulos.

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

O [plano de execução](docs/PLANO_EXECUCAO.md) define cinco módulos e os critérios de conclusão. A próxima etapa é o **módulo 3, experimentos de melhoria**: comparar representações e sinais nas mesmas 80 referências, preservando a reserva de 20. Cada módulo termina em um ponto de revisão e commit pelo autor.

O prazo comunicado pela recrutadora é **22/10/2026, às 14h, no horário de São Paulo**; o PDF mantém o prazo “a combinar”.
