# Entrega da etapa complementar - módulo 8

Entrega atual da etapa complementar, concluída após a comparação das seis receitas M8 em 22/10/2026. O E5-large foi preparado localmente: 1.030 registros, 1.053 janelas, 1.024 dimensões e nenhum truncamento.

Autor: **João Roberto de Oliveira Felix**.

## Arquivos da entrega

Os arquivos abaixo descrevem a mesma execução. O [checkpoint de fechamento](../artefatos/checkpoints/modulo8.json) reúne testes, hashes e verificações; a [evidência de reprodução](../artefatos/checkpoints/reproducao_modulo8.json) detalha o escopo da cópia isolada.

| Arquivo | Conteúdo |
|---|---|
| [publicacao.csv](publicacao.csv) | Decisão, tema sugerido e confiança para as 659 questões. |
| [previsao.txt](previsao.txt) | Autoavaliação no formato solicitado, somente para as 559 fora da folha-verdade. |
| [previsao.json](previsao.json) | Contagens, procedência, hipóteses e intervalos da autoavaliação. |
| [relatorio.pdf](relatorio.pdf) | Até quatro páginas, incluindo uma página de memo para o professor. |
| [relatorio.md](relatorio.md) | Mesmos números e conteúdo do relatório em texto. |
| [DEFESA_TECNICA.md](DEFESA_TECNICA.md) | Roteiro de cinco minutos, perguntas técnicas e demonstração pelo terminal. |

## Resultado medido

**Cobertura final: 0/559. A precisão entre publicadas é indefinida.** Todas as 659 linhas do CSV são encaminhadas à revisão com tema sugerido e confiança estimada; a previsão exclui as 100 referências humanas. O TXT usa zero como sentinela para manter o formato numérico, e o JSON explicita `null` para a precisão sem publicações.

A receita escolhida foi `sinais_large`, com 53/80 acertos por ramo, 39 exatos e 67 no top 5. Seu grupo interno com confiança de pelo menos 0,90 teve 14/14 acertos; o RRF também teve uma regra com 14/14, mas perdeu o desempate por ter 50/80 acertos globais. O M7 preservado acertou 54/80, mas não teve regra elegível. Os grupos internos serviram à escolha e não constituem validação independente.

O procedimento externo teve 54/80 acertos por ramo e 66/80 no top 5. Aceitou quatro casos e acertou os quatro, mas ficou abaixo do suporte mínimo de dez, registrado antes das métricas. O intervalo de Wilson exploratório para 4/4 vai de 51,01% a 100%. Os quatro vieram de `large_rrf20` no terceiro bloco, enquanto os outros blocos não publicaram; não são comprovação direta da receita final. Por isso, a política automática permaneceu desabilitada. Nas 20 referências já conhecidas, o diagnóstico posterior teve 13/20 acertos por ramo.

O resultado não sustenta a meta de precisão de 95% com cobertura. A ausência de publicações não equivale a precisão de 100%, e a qualidade das 559 sugestões não pode ser medida sem seus rótulos.

## Regenerar as decisões

Requer Python 3.11 ou superior. Na raiz do repositório:

```console
cd etapa-complementar
python -E -X utf8 -B -S scripts/entregar_precisao.py
```

O comando verifica as fontes e os caches, recompõe a comparação e gera o CSV e as duas previsões nesta pasta. Usa apenas a biblioteca padrão: não exige chave, instalação de dependências, pesos ou chamada de modelo de linguagem. Os embeddings já preparados são insumos numéricos versionados. Se uma saída existente divergir, o comando recusa sobrescrevê-la.

A execução completa observada levou **822,052 segundos (aproximadamente 13 min 42 s)** em notebook Windows compartilhado. Esse tempo inclui comparação e ajustes; o benchmark abaixo mede separadamente a aplicação do modelo pronto. Não é uma promessa de duração em outra máquina.

Para comparar as saídas sem gravá-las:

```console
python -E -X utf8 -B -S scripts/entregar_precisao.py --verificar
```

## Reproduzir em cópia isolada

```console
python -E -X utf8 -B -S scripts/verificar_precisao.py --evidencia tmp/verificacao-m8-01.json
```

Use um nome novo para cada evidência. O verificador copia somente arquivos permitidos, executa com rede, credenciais, importação de encoders e acesso a pesos bloqueados, e compara os produtos byte a byte. Reutiliza o Python instalado; não é uma máquina virtual. Embeddings e descritores são dados de preparação recebidos pela cópia. O PDF e os textos editoriais são preservados por hash, sem avaliar seu layout nessa rotina.

Para os testes de software:

```console
python -E -X utf8 -B -S -m unittest discover -s tests -q
```

Verificação registrada: **496 testes aprovados em 329,929 s**, com as fontes preservadas. A [evidência da suíte](../artefatos/checkpoints/testes_modulo8.json) informa comando, ambiente e hashes. Esses testes verificam software; não medem a precisão temática nas 559 questões.

## Medir somente a decisão

```console
python -E -X utf8 -B -S scripts/medir_precisao.py --evidencia tmp/benchmark-m8-01.json
```

O benchmark carrega o modelo salvo e aplica ranking, confiança e política às 559 questões, comparando todos os campos com as sugestões entregues. Separa carga/verificação do tempo de decisão. Não treina, recalibra nem executa encoder. A projeção para 50 mil pressupõe os vetores prontos; preparação e revisão humana têm custos separados no relatório.

Na [medição registrada](../artefatos/checkpoints/benchmark_modulo8.json), as 559 predições foram idênticas às entregues: **330,730 s de inferência**, **23,471 s de carga/verificação inicial** e **358,880 s no total com verificações finais**. A extrapolação linear é de 8,22 horas de decisão para 50 mil questões com vetores prontos. É uma execução em máquina compartilhada, não um teste de carga de produção.

## Preparação opcional dos embeddings

Esta etapa é separada da regeneração oficial. Os artefatos entregues permitem classificar sem executá-la. Para reconstruir o E5-large em uma nova máquina Windows:

```console
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-preparacao-large-m8.txt
.venv/Scripts/python.exe -E -X utf8 -B -m classificacao_precisao.preparar_large baixar
.venv/Scripts/python.exe -E -X utf8 -B -m classificacao_precisao.preparar_large preparar
```

Em Linux/macOS, o executável do ambiente fica em `.venv/bin/python`. O download exige rede e confere pesos/tokenizer por tamanho e SHA-256. O encoder roda localmente, com batch 1, duas threads e janelas de texto; nunca decide temas. As receitas Large também usam vetores Small. Para sua preparação histórica, consulte os registros dos [módulos 3](../docs/MODULO3_EXPERIMENTOS.md), [4](../docs/MODULO4_CALIBRACAO_DECISOES.md) e [7](../docs/MODULO7_CATALOGO.md).

O preparador guarda checkpoints locais e recusa uma identidade de entradas/configuração/fontes diferente. Não execute duas instâncias. Pesos, ambiente e checkpoints transitórios são ignorados pelo Git. A [procedência dos pilotos e da retomada](../artefatos/embeddings-e5-large-m8/PROCEDENCIA_PILOTOS.md) documenta o primeiro snapshot incompleto e a migração explícita do índice; esses registros históricos não são comandos necessários para classificar.

## Gerar o PDF

Somente o relatório exige bibliotecas de documentos:

```console
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-relatorio.txt
.venv/Scripts/python.exe -E -X utf8 -B scripts/gerar_relatorio_precisao.py
```

Use `--verificar` para regenerar em memória e comparar os bytes. A geração usa métricas, diagnóstico e benchmark já produzidos; não altera classificações. O PDF deve ter quatro páginas, nome completo na primeira e memo na quarta.

## Procedência e limites

- [Anexos oficiais](../anexos/LEIA-ME.md): 659 questões, 100 referências humanas e árvore original.
- [Protocolo M8](../config/modulo8/protocolo.json): seis receitas, sinais, confiança, regras e critérios fixados antes da comparação desta rodada.
- [Catálogo enriquecido](../config/modulo7/preparacao_catalogo.json) e [âncoras](../config/modulo8/ancoras_normativas.json): preparação documentada, sem consultar classificações das questões avaliadas.
- [Configuração E5-large](../config/modulo8/embeddings_large.json): revisão, licença, hashes, dependências, janelas e limites da quantização.
- [Registro M8](../docs/MODULO8_PRECISAO.md): comparação, avaliação e limitações.

As 80 referências de desenvolvimento foram reutilizadas em rodadas anteriores. As outras 20 já eram conhecidas e servem a diagnóstico posterior, sem escolher a receita nesta rodada. A validação aninhada separa os ajustes da grade atual, mas não elimina a adaptação histórica. Não há novo teste independente nem precisão observada nas 559 questões sem rótulos disponíveis.

As pastas antigas foram preservadas para rastreabilidade. Os arquivos de entrega na raiz do repositório pertencem ao case anterior, de 359 questões; os arquivos diretamente em `etapa-complementar` pertencem à versão M5. A entrega M8 fica exclusivamente nesta pasta.
