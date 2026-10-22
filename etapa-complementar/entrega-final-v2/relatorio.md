**João Roberto de Oliveira Felix**

# Classificação de tópicos da Vício

Etapa complementar | Relatório final M8 | 22 de outubro de 2026

**Resultado: ** Large + sinais foi a receita escolhida. Acertou 53/80 sugestões por ramo no desenvolvimento e 13/20 no diagnóstico já conhecido. As 559 questões seguem para revisão. A meta de precisão de 95% com cobertura não foi atingida; sem publicações, a precisão é indefinida.

## Sistema construído

O programa recebe 659 questões, a árvore e 100 referências humanas. Limpa HTML e normaliza campos, preservando IDs e hashes. Disciplina e assunto de origem não entram como verdade nem atributo. Só concorrem 371 temas ativos abaixo das raízes. A decisão final usa código numérico próprio e caches: nenhuma chamada a modelo de linguagem ou encoder.

| Componente | Função e procedência |
|---|---|
| Catálogo | Descrições e termos para 371 temas, com fontes e ambiguidades; 88 âncoras de leis/artigos para 87 temas. Preparação por LLM somente sobre taxonomia e fontes, sem consultar classificações de questões. |
| Representação | TF-IDF do catálogo; E5-small FP32 de 384 dimensões e alternativa E5-large INT8 de 1024, preparados localmente. As receitas Large também requerem vetores Small. Texto longo usa janelas, sem corte silencioso. Versões e hashes estão nos manifestos. |
| Ordenação escolhida | Ranking supervisionado por pares, com regularização e peso igual por questão. Aprende com centrais e extras humanos; o escore não é probabilidade. Variantes com sinais usam normas, artigos, termos e títulos. Uma referência legal é evidência textual, não validação jurídica. |
| Confiança e publicação | Logística regularizada com nove atributos, ajustada em previsões fora do treino. Dezoito regras por receita com suporte mínimo 10 e precisão observada mínima 95%; validação externa antes de habilitar a política. |

A variante hierárquica recua ao ancestral comum mais específico dos três primeiros candidatos, quando ativo, não raiz e não genérico. Níveis e recuos são registrados. As referências de classificação são exclusivamente as 100 fornecidas pela equipe, sem rótulos artificiais ou classificação manual das questões. Não houve revisão jurídica humana dos descritores.

Fontes: [catálogo](../config/modulo7/preparacao_catalogo.json), [âncoras](../config/modulo8/ancoras_normativas.json), [protocolo](../config/modulo8/protocolo.json), [encoder maior](../config/modulo8/embeddings_large.json). E5-large: revisão 3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3, licença MIT. INT8 oficial executado em AVX2; não se presume equivalência ao FP32.

<!-- pagina -->

# Avaliação, escolha e previsão

As 100 referências têm 92 questões dentro da árvore, oito fora, 61 temas centrais e 39 questões com extras. Todas vêm do banco anterior; não há referência recente disponível. O acerto aceita central, extra ou ancestral/descendente de um deles; irmãos contam como erro.

## Grade fixada antes da medição M8

| Receita | Acerto por ramo | Exato / top 5 |
|---|---: |---: |
| Híbrido original M3 | 37/80 | 24 /54 |
| M7 preservado | 54/80 | 42 / 66 |
| Large + fusão RRF | 50/80 | 35 / 68 |
| Large + sinais (escolhida) | 53/80 | 39 / 67 |
| Large + sinais + hierarquia | 54/80 | 38 / 67 |
| Small + sinais | 53/80 | 38 / 66 |
| Small + sinais + hierarquia | 54/80 | 38 / 66 |

A regra fixada prioriza cobertura elegível, precisão e depois acerto global. Na seleção interna, Large + sinais com confiança mínima 0,90 teve 14/14 aceitas corretas (17,50% das 80). RRF também teve 14/14, mas perdeu no desempate: 50/80 contra 53/80. M7 tinha 54/80, sem grupo elegível. Portanto, a escolhida não melhorou o acerto global: perdeu um acerto frente ao M7.

Em três blocos externos, receita, regra e confiança são ajustadas apenas no treino. O procedimento teve 54/80 acertos por ramo, 43 exatos e 66 no top 5. As regras candidatas aceitaram 4/80 (5,00%), com 4/4 acertos e Wilson 95% de 51,01% a 100,00%. São menos de 10 aceitos: a política final ficou desabilitada. Origem: bloco 1: M7 preservado aceitou 0; bloco 2: M7 preservado aceitou 0; bloco 3: Large + fusão RRF aceitou 4. Os 4/4 vieram do RRF; não validam diretamente a receita final nem repetem o resultado interno de 14/14.

Na confiança externa, Brier=0,2074 contra 0,2210 da constante ajustada no treino; ECE=0,0852 contra 0,0340, em cinco faixas. Menor é melhor em ambos: o Brier melhorou, o ECE piorou. O resultado misto não certifica probabilidades individuais.

## Limites da evidência e entrega

As 80 referências orientaram módulos anteriores; as 20 reservadas já eram conhecidas. A validação aninhada separa esta seleção, sem apagar a adaptação histórica. O cross-fit interno compartilha treinos dos rankers. O diagnóstico das 20 veio depois da escolha: 13/20 por ramo e 17/20 no top 5; não é um teste independente novo.

O CSV reúne 80 predições externas aninhadas,20 do diagnóstico e 559 da execução final. O ranking final é reajustado nas 100 referências; a confiança usa apenas as previsões fora do treino das 80. Esse reajuste não recebeu teste independente novo. A previsão exclui as 100 referências: cobertura=0/559. A precisão real das 559 é desconhecida; intervalo de Wilson exploratório não cobre adaptação ou mudança de distribuição. Se não há publicadas, TXT usa zero como sentinela e JSON registra null.

Fontes: [métricas](../artefatos/precisao-m8-v1/metricas.json), [diagnóstico das 20](../artefatos/precisao-m8-v1/diagnostico_reserva_conhecida.json), [previsão](previsao.json). Não são resultados de um novo teste independente.

<!-- pagina -->

# Diagnóstico e operação

## O que ainda atrapalha

A árvore original tem 337 descrições de parentesco, 20 vazias e oito grupos de títulos repetidos. O enriquecimento melhora a representação, mas não estabelece a convenção editorial da equipe. Recortes ambíguos como Parte 1/2 continuam sem fronteiras inventadas. Os 100 exemplos cobrem apenas 61 centrais, o que limita o aprendizado de distinções finas.

Na seleção externa das 80, a comparação estrutural encontrou 6 erros em outra disciplina, 11 em outro ramo da mesma disciplina, 3 em tema irmão e 6 referências fora. Em 12 erros havia destino aceito no top 5; em 14 casos não havia, incluindo fora. São relações da árvore, não causas jurídicas demonstradas por IA.

As intervenções propostas são critérios de inclusão/exclusão para temas próximos, exemplos humanos por recorte e avaliação temporal recente. Baixa confiança encaminha à revisão; não prova que a questão é fora da taxonomia. Extras não são automatizados sem avaliação própria.

## Cenário de 50 mil questões por semana

As medidas locais usam Windows e CPU. Uma execução em ambiente compartilhado não é teste de carga de produção. A projeção abaixo é linear, com textos e catálogo semelhantes, sem paralelismo; vetores já existentes não precisam ser preparados novamente.

| Fase | Medida local | Projeção para 50 mil |
|---|---|---|
| Preparação Small | 316,5 s /1010 registros | 4,35 horas; aproximação com questões e temas misturados |
| Preparação Large adicional | 331,3 s /64 questões (67 janelas) | 71,89 horas adicionais; extrapolação linear condicional |
| Decisão com vetores prontos | 330,7 s para 559; carga separada: 23,5 s | 8,22 horas só de inferência |
| Revisão humana | Hipótese: 2 min por questão revisada; cobertura mantida | 1666,7 horas de revisão |

Large também exige Small: cenário somado de 76,24 horas. Large usa 64 questões contíguas não aleatórias, por timestamps de arquivos em host compartilhado; não garante representatividade e exclui carga inicial e reaproveitamento de cache. A duração integral desde zero permanece desconhecida. Não houve custo de API. Computador, energia e revisão têm custo: horas-máquina vezes tarifa mais horas de revisão vezes custo do especialista. O tempo humano é hipótese, não duração medida.

Em produção, processar em lotes e liberar caches de consultas para limitar RAM. Cada correção registra central, extras ou fora, justificativa, revisor e versões. Avaliar candidatos semanalmente com novas correções e teste temporal separado; promover só com precisão e cobertura sustentadas, preservando a versão anterior. Essa operação é proposta, não serviço implantado.

Para regenerar CSV e previsão, na pasta etapa-complementar: `python -E -X utf8 -B -S scripts/entregar_precisao.py`. O README separa esse comando da reconstrução dos embeddings e do PDF. A verificação em cópia bloqueia rede, credenciais, encoders e pesos.

Fontes: [benchmark](../artefatos/checkpoints/benchmark_modulo8.json), [diagnóstico estrutural](../artefatos/entrega-m8-v1/diagnostico.json), [preparação Small](../artefatos/entrega-m5-v1/diagnostico.json), [execução Large](../artefatos/embeddings-e5-large-m8/execucao.json), [intervalos Large](../artefatos/embeddings-e5-large-m8/retomada-v1/tempo_questoes.json). Projeções não garantem capacidade.

<!-- pagina -->

# Memo para o professor

**Para: ** equipe responsável pelos temas e pela revisão de questões  
**De: ** João Roberto de Oliveira Felix  
**Assunto: ** critérios dos temas, revisão e próxima validação

## O que encontramos

Melhorar as descrições do catálogo ajudou o sistema a encontrar destinos mais coerentes com as classificações da equipe. Na rodada final, a avaliação do procedimento em 80 referências acertou 54 primeiras sugestões; em 66 havia um destino aceito entre as cinco opções. Esses exemplos já foram usados em desenvolvimento, portanto os números não garantem o mesmo resultado em questões novas.

A entrega encaminha todas as 559 questões à revisão. Ainda não há evidência suficiente para publicação automática com 95% de precisão. A sugestão pode ajudar na triagem, mas a confiança estimada não substitui sua decisão em um caso incerto.

## O que recomendamos mudar nos temas

Começar pelos títulos repetidos, descrições sem definição temática e recortes como Parte 1/2. Para cada destino, escrever o que entra, o que não entra e como se distingue dos temas próximos. Incluir exemplos e contraexemplos revisados pela equipe. Informar se um nó aceita questões diretamente ou apenas organiza subtemas.

Não recomendamos juntar temas automaticamente porque seus nomes são parecidos. Quando forem o mesmo destino de estudo, a equipe pode estabelecer um nome principal e redirecionamentos. Quando forem recortes diferentes, a fronteira precisa ser explícita. Toda alteração deve ter versão e mapa dos IDs, preservando o histórico das questões.

As descrições e referências de leis preparadas nesta entrega são insumos para o sistema, sem revisão jurídica humana. Elas não resolvem sozinhas a convenção editorial. Uma citação de lei ou artigo também não determina, por si, o assunto central de uma questão.

## Apoio necessário da equipe

Priorizar uma amostra de questões recentes, sem usar todas imediatamente para corrigir o sistema. Guardar parte para uma avaliação futura separada. Incluir temas com poucos exemplos, fronteiras entre temas próximos e situações em que nenhum destino serve. Em parte da amostra, dois revisores podem classificar independentemente e resolver divergências.

Registrar o tema central, os temas adicionais aceitos, o motivo da correção e eventual lacuna da árvore. Distinguir erro da sugestão, informação ausente, ambiguidade da convenção e ausência de tema. Nas 100 referências,39 possuem assuntos adicionais; uma regra comum para central e extras ajudará tanto o treinamento quanto a revisão.

**Recomendação: ** limitar o piloto à capacidade da equipe e ampliar a automação somente após confirmar precisão de pelo menos 95% em uma avaliação humana recente, com quantidade de casos e cobertura explicitadas. O principal próximo ganho deve ser demonstrado na redução de revisão sem aumentar publicações erradas.
