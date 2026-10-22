# Retomada do módulo 8

**Retomada autorizada por João Roberto em 22/10/2026. Preparação, comparação completa e exportação concluídas.** A receita selecionada foi `sinais_large`, mas a política final está desabilitada por suporte externo insuficiente: as 659 sugestões foram encaminhadas à revisão e não há publicação entre as 559 questões de avaliação. A meta de precisão de 95% não foi demonstrada. O [checkpoint M8](../artefatos/checkpoints/modulo8.json) é o registro de fechamento, com o resultado e o escopo das verificações.

O [checkpoint da pausa de 21/10](../artefatos/checkpoints/pausa_modulo8.json) permanece inalterado como registro histórico. Ele descreve 594 vetores salvos e uma divergência de procedência já resolvida. O estado atual da preparação está na [conclusão da retomada](../artefatos/embeddings-e5-large-m8/retomada-v2/conclusao.json).

## Estado preservado

- Módulos 1 a 7 e seus hashes, sem substituir entregas antigas.
- Grade M8 com seis receitas, sem ampliação depois dos resultados parciais.
- Sete produtos da comparação E5-small em `artefatos/precisao-m8-small-v1`.
- Todos os 594 vetores salvos antes da pausa, byte a byte.
- Manifestos históricos dos pilotos, inclusive a ressalva sobre o snapshot incorreto do primeiro.
- Pesos, ambiente virtual e checkpoints transitórios fora do Git; os vetores completos e sua procedência integram os artefatos versionados.

Resultado parcial preservado: M7 com 54/80 acertos por ramo; small com sinais, 53/80; small com sinais e hierarquia, 54/80. Nenhuma política parcial atingiu a exigência de publicação. Brier externo parcial: 0,189694, contra 0,225916 da constante. O melhor grupo exploratório com pelo menos dez casos teve 16/17 acertos, ou 94,12%. O pacote completo, descrito abaixo, possui suas próprias métricas e não substitui esse histórico.

## Procedência resolvida

O índice anterior referenciava o protocolo com SHA-256 `dd178b70592028c3c03351a6d6f478d3a91b04dc4a91cdcfde810115ecf88e99`; o protocolo vigente tem SHA-256 `4ac9d655cf825b98bfc5b2151466e618637fd7d906deeaf0de6e3cd5730ba115`. O protocolo integra a procedência do preparador, mas não é consultado ao construir textos, tokenizar, executar o encoder ou agregar vetores.

A [migração de metadados](../artefatos/embeddings-e5-large-m8/migracao-protocolo-v1/manifesto.json) confirmou entradas, configuração e demais fontes idênticas. Conferiu os 594 arquivos: hash individual, hash do texto, 1.024 dimensões, finitude, norma L2, tokens, janelas e ausência de truncamento. Não havia órfãos ou temporários. Somente a referência do protocolo mudou, com substituição atômica e preservação dos índices:

- Índice original: `507d36b0f1ff93a1db64abfaf3f845be508abd7331624208023ee281aa1d6cad`.
- Índice migrado: `d116f87f65b654e69308e20bf9851f1ad8ee9ea10b0b91bf0e41fff432777cdc`.

Não repetir a migração: ela foi feita para essa transição exata. `preparar_large.py`, `embeddings_large.json` e as demais fontes do encoder não foram alteradas.

O snapshot em `piloto/fontes/` contém fontes posteriores ao primeiro piloto e não corresponde ao manifesto original. Esse piloto não é uma reprodução integralmente recuperável. O segundo piloto `piloto_memoria/` registra a implementação e a configuração do cache completo. A [nota de procedência](../artefatos/embeddings-e5-large-m8/PROCEDENCIA_PILOTOS.md) explica a diferença; nenhum manifesto histórico foi adulterado para ocultá-la.

## Execuções de 22/10 e cache completo

1. A [primeira retomada](../artefatos/embeddings-e5-large-m8/retomada-v1/inicio.json) partiu de 594 registros e gerou mais 257. A guarda de memória interrompeu a execução com 851 registros salvos, durante execução concorrente da suíte de testes na fase de temas. A [interrupção](../artefatos/embeddings-e5-large-m8/retomada-v1/interrupcao.json) registra o motivo e os hashes. Todos os 851 arquivos foram autenticados, sem órfãos ou temporários.
2. A suíte encerrou com **493 testes aprovados em 251,646 segundos**. Isso verifica software, não precisão nas 559 questões sem rótulos.
3. A [segunda retomada](../artefatos/embeddings-e5-large-m8/retomada-v2/inicio.json) começou após a suíte, reutilizou os 851 registros e gerou os 179 temas restantes. Terminou com código de saída zero.
4. A [auditoria final](../artefatos/embeddings-e5-large-m8/retomada-v2/conclusao.json) conferiu fontes, entradas, configuração, cache e todos os parciais. A reconstrução dos índices de 594 e 851 registros produziu os hashes esperados, comprovando preservação dos vetores anteriores.

O [cache completo](../artefatos/embeddings-e5-large-m8/manifesto.json) contém **659 questões + 371 temas = 1.030 registros**, **1.053 janelas**, **1.024 dimensões** e **nenhum truncamento**. SHA-256 de `vetores.json`: `ccc440ce7edb031a03bdd16b235aa394d02be3505907e527f5cdaef1399dd74c`. Não há encoder ativo nem necessidade de executá-lo para classificar ou reproduzir a decisão.

## Tempo observado e limites

`execucao.json` mede **161,044 segundos da última tentativa**, com 851 registros reutilizados e somente 179 temas novos. Não é o custo integral dos 1.030 registros. A duração completa das execuções interrompidas não está disponível; não dividir 161,044 por 1.030 para estimar produção nem inventar tempo acumulado.

A [evidência das questões](../artefatos/embeddings-e5-large-m8/retomada-v1/tempo_questoes.json) guarda 65 timestamps de conclusão e **64 intervalos, 67 janelas e 331,27124 segundos**. O primeiro registro apenas delimita o início: sua geração fica fora do denominador. O bloco terminou antes da suíte e da interrupção. Exclui temas, carga do modelo e processamento dos 594 reutilizados. É uma observação contígua em host compartilhado, baseada em timestamps de arquivos; não assegura representatividade de 50 mil questões. A projeção deve explicitar essa limitação e considerar os componentes Small usados pela implementação atual.

## Fonte histórica do resultado small

O pacote parcial foi gerado pela fonte original do commit `043b14e4e67ed2d8ee894c5d0a1eac25ac337687`. Sua cópia e o histórico estão em [precisao-m8-small-fontes-v1](../artefatos/precisao-m8-small-fontes-v1/registro.json). A assinatura original de `classificacao_precisao/experimento.py` é `5c29dcdb149a5a07e38acb6c1004b947d0b2b2e437b5f40d34c5491322c03a5f`.

Na comparação completa, corrigiu-se somente a leitura do diagnóstico histórico M7 das 20 referências conhecidas: o arquivo tem extensão `.jsonl`, mas contém um array JSON indentado. Essa leitura ocorre depois da seleção. A correção não altera receitas, protocolo, calibração, escolha ou publicação. Manifestos e produtos anteriores permanecem intactos. Os 17 testes direcionados da correção passaram; a suíte de 493 antecede essa alteração. Depois da correção, a [suíte final](../artefatos/checkpoints/testes_modulo8.json) passou com **496 testes em 329,929 segundos** (333,585 segundos de parede), código de saída zero e fontes preservadas.

Para conferir o pacote parcial, abra um checkout separado do commit indicado e, na pasta `etapa-complementar` desse checkout, execute:

```console
python -E -X utf8 -B -S -m classificacao_precisao verificar --small
```

A fonte atual tem outra assinatura por causa da correção do parser; a reprodução do manifesto parcial exige a versão histórica. Não substituir arquivos do checkout atual para obter essa correspondência.

## Resultado da comparação completa

A comparação e exportação concluíram em 822,052 segundos. O [pacote do experimento](../artefatos/precisao-m8-v1/manifesto.json) contém 12 arquivos: 11 produtos e seu manifesto. A [entrega](../entrega-final-v2/README.md) contém CSV de 659 linhas e previsões em TXT e JSON. A tabela das seis receitas está no [registro M8](MODULO8_PRECISAO.md).

- Seleção interna: `sinais_large`, 53/80 por ramo, 39/80 exatos e 67/80 no top 5. Seu corte de confiança ≥ 0,90 teve 14/14 acertos. `large_rrf20` com corte ≥ 0,95 também teve 14/14; `sinais_large` venceu o desempate por acerto global, 53/80 contra 50/80. O M7 acertou 54/80, mas não tinha regra elegível.
- Procedimento externo: 54/80 por ramo, 43/80 exatos e 66/80 no top 5. Blocos 1 e 2 selecionaram `baseline_m7`, sem publicação; bloco 3 selecionou `large_rrf20` e produziu quatro candidatas corretas. Esses resultados não são uma validação externa direta da receita final `sinais_large`.
- As quatro candidatas correspondem a 5% das 80 referências. Seus 4/4 acertos têm Wilson de 95% entre 51,01% e 100%. O suporte ficou abaixo dos dez casos mínimos, bloqueando a política final. Os 14/14 internos não substituem esse requisito.
- Confiança externa: Brier 0,207372 contra 0,220957 da constante; ECE 0,085172 contra 0,033977. A melhora de Brier não foi acompanhada de melhora de ECE.
- Diagnóstico das 20 já conhecidas: 13/20 por ramo, 8/20 exatos e 17/20 no top 5, após a seleção. Não é um teste independente novo.
- Saída final: 659 decisões `revisar`, incluindo as quatro candidatas externas vetadas pelo bloqueio final. As 559 sugestões usam o ranking reajustado com as 100 referências; esse reajuste não teve novo teste independente. Cobertura final: 0/559 = 0%. Precisão entre publicadas: indefinida, `null` no JSON; o zero no TXT é uma sentinela de ausência de previsão. Não há rótulos disponíveis para medir acerto nas 559.

O [benchmark da aplicação](../artefatos/checkpoints/benchmark_modulo8.json) reproduziu exatamente as 559 predições salvas: 23,471 segundos de carga, 330,730 de aplicação e 358,880 no total com verificações. A projeção linear para 50 mil questões é 8,2173 horas **somente para decidir com vetores prontos**. Não inclui preparação Small/Large, ajuste, seleção, revisão humana ou operação completa; depende de hardware e carga comparáveis.

## Reprodução e evidências

Os produtos numéricos estão em `entrega-final-v2/`. A reprodução deve usar os arquivos finais indicados no README dessa pasta. A antiga prévia `tmp/pdfs/layout-m8-provisorio.pdf` usa números fictícios, está identificada como rascunho e não integra a entrega. As imagens `tmp/pdfs/final-m8-*.png` são renderizações temporárias do PDF final com dados reais, usadas na conferência visual.

1. Reproduzir a comparação com `python -E -X utf8 -B -S scripts/entregar_precisao.py`. O comando aceita produtos existentes quando seus bytes são idênticos. Não ampliar a grade para favorecer o resultado observado nem iniciar uma execução concorrente com o benchmark.
2. Gerar o diagnóstico com `python -E -X utf8 -B -S scripts/diagnosticar_precisao.py`.
3. Com os demais processamentos encerrados, medir as 559 sugestões com `python -E -X utf8 -B -S scripts/medir_precisao.py --evidencia tmp/benchmark-m8-conferencia.json`.
4. Conferir no relatório e na defesa a receita escolhida, `sinais_large`, distinguindo-a das escolhas nos blocos externos. Distinguir componentes Small/Large, custo observado e estimativas parciais. Não apresentar o tempo da última retomada como preparação integral.
5. Conferir as quatro páginas do PDF final, incluindo nome, texto, números e layout. A defesa, o README e o registro M8 devem permanecer coerentes com os artefatos. Não chamar as 20 referências de novo teste independente nem confundir acerto global com precisão de publicação.
6. Reproduzir em cópia permitida com `python -E -X utf8 -B -S scripts/verificar_precisao.py --evidencia tmp/verificacao-m8-conferencia.json`. Isso recompõe o experimento e as três entregas sem rede, credenciais ou encoder. Destinos de evidência devem ser novos; se os exemplos em `tmp/` já existirem, escolher outros nomes. Não sobrescrever evidências oficiais em `artefatos/checkpoints/`.
7. Conferir arquivos, hashes, links e Git usando o checkpoint M8 como registro da entrega. Commit, push e envio permanecem com o usuário, salvo nova instrução explícita.

Os registros de fechamento são [benchmark M8](../artefatos/checkpoints/benchmark_modulo8.json), [reprodução M8](../artefatos/checkpoints/reproducao_modulo8.json) e [checkpoint M8](../artefatos/checkpoints/modulo8.json). Consulte nessas evidências o resultado e o escopo das verificações, sem interpretar testes de software como certificação de precisão temática.

`README_HISTORICO.md`, na raiz, preserva o README anterior. O README principal aponta à entrega atual em `etapa-complementar/entrega-final-v2/`. Não mover ou substituir CSVs/relatórios antigos, nem editar README/documentos M5 dentro da etapa: seus verificadores dependem dos arquivos e hashes congelados.

## Restrições mantidas

Nenhum LLM pode escolher, votar, julgar ou validar temas das questões avaliadas. Processamento numérico dos rótulos humanos e métricas agregadas é permitido; não expor questões com rótulos/predições para adjudicação semântica. Preparação do catálogo e embeddings ocorre antes da decisão, documentada e versionada. As 100 referências já foram reutilizadas: não há novo teste independente nem garantia de precisão populacional. Não prometer perfeição ou contratação.
