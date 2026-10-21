# Módulo 6 Refinamento do classificador

Nenhuma das sete receitas novas superou o classificador anterior na comparação das 80 referências: a baseline manteve 37 acertos por ramo, contra 34 da melhor alternativa. Por isso, ela continua selecionada. O resultado desta rodada é negativo para as hipóteses testadas; não houve aumento de cobertura nem demonstração da meta de 95% de precisão entre publicadas.

CSV, previsão, PDF, calibração e política de publicação dos módulos 1 a 5 permanecem com os bytes anteriores. Os resultados completos das oito receitas e as sugestões experimentais ficam em um pacote separado.

## Resultados e decisão

As contagens abaixo usam as mesmas 80 referências e partições. São métricas de desenvolvimento usadas na própria seleção, sem interpretação de teste independente. A [tabela estruturada](../artefatos/refinamento-v1/metricas_desenvolvimento.json) conserva todos os resultados, inclusive os negativos.

| Receita | Acertos por ramo | Acertos exatos | Acertos no top 5 | Sugestões em folhas ativas |
| --- | ---: | ---: | ---: | ---: |
| Baseline M3 | **37/80** | **24/80** | 54/80 | 66/80 |
| Palavras por campos e E5, k=20 | 33/80 | 22/80 | 52/80 | 66/80 |
| Palavras e caracteres por campos e E5, k=20 | 30/80 | 20/80 | 51/80 | 64/80 |
| Palavras por campos e E5, k=5 | 32/80 | 22/80 | 55/80 | 68/80 |
| Palavras e caracteres por campos e E5, k=5 | 33/80 | 20/80 | 50/80 | 63/80 |
| Palavras e caracteres por campos, somente lexical | 34/80 | 19/80 | **56/80** | 67/80 |
| Palavras e caracteres, E5 e prior de disciplina, k=5 | 33/80 | 20/80 | 50/80 | 63/80 |
| Palavras e caracteres, E5 e prior de disciplina, k=20 | 30/80 | 20/80 | 51/80 | 64/80 |

A alternativa somente lexical teve saldo de dois acertos a mais no top 5, mas perdeu três acertos na primeira sugestão e cinco acertos exatos. Esse pequeno ganho de recuperação na mesma amostra de seleção não justifica promover a receita. O prior de disciplina não aumentou o total de acertos em nenhuma das duas ablações: com k=20 não mudou a primeira sugestão; com k=5 mudou duas, mantendo as contagens de acerto.

A avaliação aninhada do **procedimento de selecionar uma receita** resultou em **33/80 acertos por ramo (41,25%)**, 21/80 exatos e 54/80 no top 5. A baseline foi escolhida nos dois primeiros cortes externos, com 13/27 acertos em cada um; a variante somente lexical venceu a seleção interna do terceiro corte, mas obteve 7/26 acertos externos. Comparando as mesmas questões com a baseline fixa, o procedimento aninhado melhorou uma sugestão e piorou cinco: saldo de quatro acertos a menos. A receita mais bem colocada no treino não se manteve superior fora dele.

O diagnóstico nas 20 referências conhecidas permaneceu em **6/20 acertos por ramo**, 3/20 exatos e 12/20 no top 5. A baseline vencedora, reajustada nas 100 referências, produziu as mesmas primeiras sugestões, escores e margens anteriores nas **559 questões**. Não houve edição manual de classificações. A política anterior continua encaminhando todas à revisão; a precisão entre publicadas permanece indefinida.

Para a defesa técnica, a decisão central é: a rodada testou sete alternativas sem alterar a régua depois de observar os resultados. A maior complexidade não trouxe ganho no objetivo principal, e a avaliação aninhada expôs a instabilidade da escolha. A entrega conserva o classificador anterior e torna os experimentos descartados reproduzíveis. Isso demonstra controle da evolução do sistema, mas não resolve a qualidade insuficiente para publicação automática.

## O que mudou

O classificador anterior reunia enunciado, comando e alternativas em um único texto lexical. As receitas novas representam o corpo da questão e as alternativas separadamente, dando pesos de 75% e 25% aos respectivos cossenos. Quando um campo não tem vetor representável, seu peso é redistribuído ao outro. Cada campo passa a ter peso explícito após sua própria normalização.

Uma ablação acrescenta sequências de três a cinco caracteres dentro de cada palavra para reconhecer flexões e grafias próximas. A mistura usa 70% de similaridade por palavras e 30% por caracteres. Cada espaço TF-IDF é ajustado somente no catálogo e nos textos de treino do corte; nenhum texto de validação ajusta vocabulário ou IDF. O catálogo conserva os pesos anteriores: título 3, caminho 1 e descrição 1.

As variantes híbridas combinam esse ranking lexical com os embeddings E5 já preparados e versionados. Elas comparam duas constantes de RRF, 20 e 5, mantendo peso de 50% para cada ranking. O valor menor dá mais peso às primeiras posições. A ablação lexical dispensa a similaridade E5 na pontuação.

Duas receitas acrescentam um sinal suave de disciplina. Para cada disciplina, calcula-se o centróide dos vetores das questões humanas de treino cujo tema central pertence àquela disciplina. Sem exemplos, usa-se o centróide dos temas do catálogo. Um softmax dos cossenos, com temperatura 0,05, fornece pesos que participam em 15% do escore. Esses pesos **não são probabilidades calibradas de disciplina ou de acerto**. Nenhum tema é eliminado por esse sinal; disciplina e assunto da classificação de origem continuam fora dos atributos.

A implementação valida e copia os vetores na criação do motor, e reutiliza as similaridades de cada consulta entre as receitas. A decisão continua usando somente operações numéricas locais, sem carregar encoder, chamar API ou pedir a um LLM que escolha ou avalie temas.

## Como interpretar a avaliação

A [grade de oito receitas](../config/modulo6/protocolo.json) foi fixada antes da primeira medição desta rodada, com SHA-256 `7f8bcafa1c823215ba76598722e985011880e3f65d99ae1772708f9a8e36d26f`. Isso não constitui um pré-registro independente: os resultados históricos dos módulos anteriores já eram conhecidos.

1. **Seleção nas 80 referências:** cada receita recebe previsões fora da amostra nas três partições originais. A escolha usa acertos por ramo, depois acertos exatos e, em empate, prioridade fixa e nome. O desempenho da receita escolhida nessa mesma comparação está sujeito a otimismo de seleção.
2. **Avaliação aninhada nas 80:** dentro de cada treino externo, três novas partições comparam as oito receitas. Somente a vencedora daquele treino classifica a validação externa. Isso mede o procedimento de seleção, que pode escolher receitas diferentes em cada corte. As novas partições internas são determinísticas, preservam os grupos de duplicatas e são montadas sem consultar rótulos. Os cortes externos são os já fixados no módulo 2, originalmente estratificados com os rótulos no módulo 1. As 80 referências já foram reutilizadas no desenvolvimento anterior; esta medida também permanece exploratória.
3. **Diagnóstico nas 20 conhecidas:** depois da seleção global nas 80, aplica-se a receita às 20 referências antes reservadas. Elas já foram avaliadas no módulo 4. O resultado não define a receita e não constitui um novo teste independente.
4. **Sugestões para as 559 sem rótulo:** a receita escolhida é reajustada nas 100 referências humanas e gera cinco candidatos por questão. Esse reajuste não recebeu teste independente; seus escores não autorizam publicação automática.

O acerto por ramo usa a mesma regra estrutural dos módulos anteriores: igualdade ou ancestralidade com o tema central ou um extra aceito. O acerto exato exige igualdade com uma dessas referências. Irmãos não contam como acerto apenas por compartilharem o pai. A comparação também registra acerto imediato, top 5, profundidade e sugestões em folhas, para tornar visíveis os ganhos obtidos por generalização excessiva.

## Consulta externa

O [repositório público indicado pelo autor](https://github.com/edcastanha/case-vicio-ia-poc/tree/b89f1632697e60b3abcb360a8cc50e277ecd5677) foi consultado em 21/10/2026. Naquela revisão, o README descrevia a primeira etapa, com votação por modelos, e anunciava a construção futura da etapa complementar. Por isso, seus resultados não entram na comparação desta rodada. Nenhum código, classificação, voto ou rótulo daquele projeto foi incorporado. As receitas deste módulo foram implementadas sobre os componentes locais e a folha-verdade oficial.

## Reprodução e arquivos

Na pasta `etapa-complementar`, usando somente a biblioteca padrão do Python:

```console
python -E -X utf8 -B -S -m classificacao_refinamento verificar
python -E -X utf8 -B -S scripts/verificar_refinamento.py
```

O primeiro comando reconstrói a rodada e compara os dez arquivos do pacote com os bytes versionados. O segundo faz essa reconstrução em uma cópia temporária por lista permitida, com ambiente sem credenciais e bloqueios de rede, `.env`, pesos e dependências do encoder. Ele produz uma nova evidência em `tmp/` sem sobrescrever evidências anteriores. A cópia reutiliza o interpretador instalado e os vetores versionados: não é clone Git, máquina virtual ou regeneração dos embeddings.

O comando `python -E -X utf8 -B -S -m classificacao_refinamento executar` materializa o pacote quando ainda não existe e recusa sobrescrever resultados divergentes. Uma nova hipótese exige nova versão de protocolo e saída; editar a grade atual invalida seus hashes.

Os dez arquivos em [refinamento-v1](../artefatos/refinamento-v1/) contêm métricas, 640 previsões de seleção, 80 previsões aninhadas, partições, receita escolhida, diagnóstico e 20 previsões da reserva conhecida, 559 sugestões, receita e insumos necessários para reconstruir o modelo final, e manifesto. O estado do modelo é reconstruído a partir dos IDs de treino, parâmetros, fontes e vetores assinados, sem duplicar o TF-IDF em outro arquivo.

A execução inicial levou **610,677 segundos** neste Windows com CPython 3.14.7. O tempo inclui todas as receitas, avaliação aninhada, diagnóstico e geração das 559 sugestões; parte da execução concorreu com testes. Não é tempo exclusivo de classificação nem benchmark de produção. Não houve chamadas de API de inferência nem nova preparação de embeddings.

**Validação concluída:** a suíte completa de 270 testes passou em 60,274 segundos; os seis testes do verificador, acrescentados em seguida, passaram em 2,511 segundos. Foram 276 testes aprovados, dos quais 38 são novos nesta rodada. Os testes novos cobrem isolamento das partições, grupos de duplicatas, invariância a metadados, integridade dos vetores, ressubstituição, preservação de fontes e bloqueio de operações na reprodução.

A [reprodução em cópia temporária](../artefatos/checkpoints/reproducao_modulo6.json) copiou 118 arquivos, totalizando 37.373.850 bytes, e reconstruiu os **dez arquivos M6 com bytes idênticos** em 536,856 segundos. As fontes originais e a cópia permaneceram intactas durante a verificação. O [checkpoint do módulo](../artefatos/checkpoints/modulo6.json) reúne resultados, testes, hashes e o ponto de retomada.

## Próxima hipótese com maior prioridade

Os novos pesos e representações lexicais não resolveram a limitação observada. O diagnóstico anterior mostrou que 337 descrições de temas contêm apenas metadados de hierarquia e outras 20 estão vazias. A próxima hipótese é enriquecer o catálogo com definições e termos distintivos, versionados antes da classificação e produzidos sem acesso às questões avaliadas. O uso de LLM nessa preparação é permitido pelo case; escolher ou validar temas de questões por LLM continua excluído.

Qualquer nova versão deve repetir a comparação, avaliar o efeito sobre sugestões genéricas e receber uma calibração própria. Novas referências humanas, especialmente das questões recentes, são necessárias para uma avaliação independente. A rodada atual termina em um ponto de revisão e commit, preservando integralmente o pacote de entrega anterior.

Mensagem de commit sugerida: `Compara receitas de refinamento e mantém o classificador anterior`. Código, protocolo, resultados e verificador desta rodada podem ser revisados como um único módulo. Commit, push e envio à recrutadora não foram executados.
