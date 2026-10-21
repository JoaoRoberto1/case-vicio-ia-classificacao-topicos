# Defesa técnica da etapa complementar

**João Roberto de Oliveira Felix**

Roteiro para uma apresentação de aproximadamente seis minutos, seguida de perguntas técnicas. O resultado central precisa aparecer logo: o sistema executa a classificação localmente e preserva a avaliação, mas **não atingiu a meta de publicação automática**. Acertou 6/20 sugestões no teste reservado e encaminhou as 559 questões da avaliação oficial para revisão.

## Roteiro de apresentação

### Objetivo e resultado em 45 segundos

“O problema é colocar a questão no tópico correto sem prejudicar o estudo do aluno. A meta combina pelo menos 95% de precisão entre as publicadas com a maior cobertura possível. Construí um classificador local, comparei alternativas e congelei a política antes de avaliar a reserva. O teste teve seis acertos em vinte sugestões pelo critério do case. A calibração não sustentou a publicação automática, então a entrega tem cobertura zero. Eu não apresentaria esse sistema como pronto para publicar para alunos.”

Abra o [relatório](../relatorio.pdf). Use o resultado para distinguir a implementação concluída do objetivo de qualidade ainda não alcançado.

### Dados e prevenção de vazamento em um minuto

“São 659 questões e 100 referências humanas fornecidas pela equipe. Separei 80 referências para desenvolvimento e preservei 20 para o teste final. As 559 questões restantes não têm referência conhecida e são o denominador da cobertura oficial. As 300 recentes estão nesse grupo; não tenho uma medição de acerto nelas.”

“No desenvolvimento, cada referência recebeu a sugestão de um ajuste que não a incluía no treino. O calibrador também foi medido fora do próprio ajuste. Essas mesmas 80 referências orientaram a escolha das receitas, portanto os resultados de desenvolvimento são exploratórios. A reserva só foi avaliada depois do congelamento do código, das configurações, do calibrador e da política.”

Mostre o [protocolo](PROTOCOLO_AVALIACAO.md) e, se solicitado, o [registro de congelamento](../artefatos/calibracao-v1/congelamento.json). Não apresente a repetição técnica desse teste como uma nova avaliação independente.

### Classificador e alternativas em um minuto

“Comecei com recuperação lexical por TF-IDF e comparei sinais de leis, exemplos humanos e embeddings. A receita escolhida combina a posição de cada tema nos rankings lexical e semântico, com pesos iguais. Ela não pede a um modelo que escolha o tema. O codificador E5 só gerou vetores antes da decisão; a classificação lê os vetores versionados e usa operações numéricas locais.”

“No desenvolvimento, o lexical inicial acertou 31/80; o híbrido selecionado, 37/80. O catálogo lexical sem exemplos já acertava 34/80. Embeddings sozinhos tiveram 21/80, o pior resultado. Portanto, não atribuo todo o ganho à semântica nem afirmo que um modelo mais complexo foi melhor em geral. O top5 da receita escolhida caiu de 57/80 do lexical inicial para 54/80.”

A seleção priorizou o primeiro tema, com desempate fixado antes da medição. O modelo escolhido não usa os rótulos dos vizinhos no escore; os textos de treino participam do vocabulário e do IDF, e as referências humanas orientam a avaliação e a seleção.

### Calibração e decisão em um minuto

“Similaridade não é chance de acerto. Na validação, um escore de pelo menos 0,95 ainda produziu apenas 17 acertos em 23 sugestões. Comparei três calibradores: constante, logística do escore e logística do escore com margem. A constante teve o menor Brier fora da amostra.”

“O ajuste final dessa constante é aproximadamente 46,3%. Ele estima uma taxa global e não distingue questões fáceis e difíceis. Não substituí essa saída por uma confiança alta para gerar cobertura. Nenhum dos três calibradores chegou ao limiar mínimo de 0,95. A política ficou sem publicação automática antes de abrir a reserva e foi mantida depois do teste.”

Os filtros também impedem publicar disciplinas, temas com descendentes ativos e determinados títulos genéricos. Esses filtros não explicam sozinhos a cobertura zero: as probabilidades já eram insuficientes. Confiança baixa leva a revisão, não à conclusão de que nenhum tema serve.

### Teste e significado da entrega em um minuto

| Medida | Desenvolvimento | Reserva |
|---|---:|---:|
| Primeiro tema correto pelo critério de ramo | 37/80 | 6/20 |
| Primeiro tema exato | 24/80 | 3/20 |
| Tema aceitável entre cinco candidatos | 54/80 | 12/20 |
| Publicações automáticas | 0 | 0 |

“O resultado reservado é 30% de acerto das sugestões, não precisão das publicações. Sem publicações, essa precisão é indefinida. O JSON usa `null`; o TXT usa zero somente como sentinela para manter o campo numérico, com a explicação no próprio arquivo. O intervalo de zero a um também não é um intervalo estatístico estimado.”

“O CSV contém 659 linhas e preserva três procedências: 80 sugestões fora da amostra, 20 do teste congelado e 559 do reajuste final. Esse reajuste usa os textos das 100 referências, mas mantém o calibrador das 80. Ele não recebeu outro teste independente. Na avaliação oficial, são zero publicações e 559 revisões.”

### Operação e próximos investimentos em 45 segundos

“A regeneração usa um comando, o cache versionado e a biblioteca padrão do Python. A CLI bloqueia rede Python, `.env`, pesos e importação do codificador durante a decisão. A geração registrada no módulo 4 levou cerca de cinco minutos neste ambiente; isso não é um benchmark para 50 mil questões semanais.”

“Antes de ampliar, eu investiria em referências humanas para temas pouco cobertos e concursos recentes, com uma nova reserva independente. Mediria separadamente a recuperação de candidatos, a ordenação e a calibração. Para operar em volume, separaria a preparação de embeddings por lote da decisão local, reutilizaria o cache por hash de texto e mediria custo e latência com carga representativa. Hoje, encaminhar tudo à revisão não resolve a necessidade de escala.”

## Demonstração pelo terminal

Não há interface obrigatória no case. O relatório, os artefatos e uma demonstração da CLI permitem inspecionar o sistema entregue. Uma tela de revisão poderia ser uma evolução, mas sua utilidade teria de ser avaliada com especialistas; não faz parte desta entrega.

A partir da raiz do repositório:

```console
cd etapa-complementar
python -B -S scripts/verificar_entrega.py
python -B -m classificacao_decisao regenerar
python -B -m classificacao_decisao verificar
```

O primeiro comando reproduz M1 e M4 em uma cópia temporária criada a partir de uma lista permitida, usando o Python instalado e os caches numéricos versionados. A cópia não herda credenciais, ambientes virtuais ou pesos. Não é um clone Git nem uma máquina virtual; a prova também não avalia o PDF ou o conteúdo remoto e não refaz os experimentos M2/M3.

Reserve alguns minutos para a regeneração e para a reprodução, mantendo uma execução já registrada disponível. `Regenerar` refaz a entrega na pasta atual; `verificar` reconstrói os produtos e compara bytes. Ambos recusam divergências, em vez de sobrescrever experimentos. Execute um processo por diretório.

Mostre [previsao.txt](../previsao.txt), o [resumo estruturado](../artefatos/decisoes-v1/previsao.json) e o [checkpoint do módulo 4](../artefatos/checkpoints/modulo4.json). Explique o esquema do [CSV](../publicacao.csv) e a procedência das linhas sem improvisar uma validação jurídica de questões individuais.

O experimento de decisão não exige instalar dependências de IA nem baixar pesos. Reconstruir os embeddings é uma etapa separada, documentada no [módulo 3](MODULO3_EXPERIMENTOS.md). Questões novas precisam passar por essa preparação explícita; o classificador não chama o codificador como fallback.

## Perguntas difíceis e respostas sustentadas pela entrega

**Vocês cumpriram a meta do case?**

Não. Cumprimos a implementação e a reprodução do procedimento, mas não demonstramos 95% de precisão com cobertura útil. A ausência de publicações não comprova precisão alta. Ela explicita que a política não encontrou suporte para automatizar.

**Por que não reduzir o limiar e entregar alguma cobertura?**

Isso mudaria a exigência depois de observar o resultado. Os calibradores não sustentaram a região de 95%. Reduzir o limiar para produzir um número maior de publicações exigiria assumir uma qualidade inferior; não seria cumprimento da meta.

**Se o calibrador é constante, ele serve para quê?**

Ele oferece uma estimativa global que venceu as alternativas pelo Brier de desenvolvimento. Sua escolha mostra que os atributos testados não produziram probabilidades melhores nessa comparação. Ele não discrimina risco individual e, portanto, não oferece uma política seletiva útil. ECE muito baixo no desenvolvimento também não resolve esse problema: na reserva, a previsão média de 46,3% ficou acima dos 30% observados.

**Por que não usar validação cruzada nas 100 referências?**

Usei validação interna nas 80 para desenvolver e preservei 20 para medir a receita completa depois da seleção. A reserva é pequena: o intervalo de Wilson de 95% para os 6/20 acertos das sugestões vai aproximadamente de 14,5% a 51,9%. Ele não é um intervalo de precisão de publicação. A escolha protege uma avaliação final, mas limita a quantidade de dados disponível para ajuste e a força estatística do teste.

**O que significam os 12/20 no top5?**

Em doze referências reservadas, algum dos cinco candidatos era aceitável pelo critério de ramo. Isso sugere investigar recuperação e ordenação separadamente. Não significa 60% de precisão do primeiro tema, nem demonstra que um especialista revisaria mais rápido usando a lista.

**Por que a confiança não aumentou ao usar todas as referências no final?**

O classificador final reajusta a representação lexical com os textos das 100 referências; o calibrador foi preservado das 80. Os rótulos dos vinte casos reservados não foram usados para recalibrar nem escolher outra política. O efeito do reajuste não foi testado independentemente, e os escores novos não autorizam afirmar qualidade maior.

**O que acontece com questões fora da árvore e com múltiplos temas?**

`Fora` não é automatizado: havia apenas seis exemplos de desenvolvimento e dois de reserva nessa condição. No teste, a chamada `fora` teve recall zero e precisão indefinida porque não houve chamadas. Os extras previstos permanecem vazios. Os extras humanos participam da avaliação do primeiro tema; predizer vários temas exigiria um procedimento próprio avaliado.

**Os temas genéricos poderiam melhorar o número de acertos?**

O critério admite parentesco no mesmo ramo, mas não promovi sugestões a ancestrais para explorar essa tolerância. A política de publicação exige folha ativa e bloqueia títulos genéricos predefinidos. O resultado exato é mostrado junto do resultado por ramo para deixar clara essa diferença.

**Qual foi o papel da IA no desenvolvimento?**

Houve assistência de IA na implementação, nos testes e na documentação. Nesta etapa complementar, o codificador E5 participou apenas da preparação dos vetores. Não usei rótulos, votos ou julgamentos de IA da primeira entrega para treinar ou avaliar esta etapa, nem um LLM para escolher, votar ou validar os temas das questões. A avaliação compara a saída do código com as referências humanas fornecidas.

**O projeto já suporta 50 mil questões por semana?**

Não foi medido nessa escala. Uma extrapolação linear dos tempos locais daria cerca de 7,6 horas para classificar 50 mil questões e 14,8 horas para a preparação, usando a execução adicional de vinte questões. São contas indicativas com overhead incluído, não medições de capacidade nessa carga. Há uma separação que permite preparar representações em lote e executar decisões sem modelo, mas faltam teste de carga, orçamento de infraestrutura, metas de latência e capacidade de revisão. O gargalo de qualidade atual permanece mesmo que o código fique mais rápido.

**O que faria com mais prazo?**

Primeiro obteria novas referências humanas, incluindo concursos recentes e temas com pouco suporte, mantendo um novo teste fechado. Depois investigaria descrições e recuperação de candidatos, classificadores supervisionados hierárquicos e sinais para `fora`, com comparações controladas. Reutilizar os vinte casos já observados seria desenvolvimento exploratório. Um resultado melhor sobre eles não substituiria o novo teste.

## Referências para aprofundar durante a entrevista

- [Relatório](../relatorio.md): síntese da entrega e plano de operação.
- [Experimentos do módulo 3](MODULO3_EXPERIMENTOS.md): sete receitas, fórmulas e ablações.
- [Calibração e decisões](MODULO4_CALIBRACAO_DECISOES.md): grade, política, congelamento e limitações.
- [Guia de entrega](ENTREGA.md): arquivos finais e revisão antes do envio.
