# Diagnóstico da cobertura da versão 1

As 359 questões têm decisão no CSV congelado: 78 `publicar`, 277 `revisar` e quatro `fora`. A cobertura observada é **78/359 = 21,73%**. Ela mede a fração liberada automaticamente para o aluno. A precisão mede a correção dos temas centrais entre as publicadas e é objeto de outra avaliação.

O diagnóstico abaixo conta os sinais da [trilha congelada](../artefatos/decisoes-v1/trilha_decisoes.jsonl). Não reclassifica questões, não ajusta a política e não mede o mérito jurídico das 277 revisões.

## Por que 277 questões ficaram para revisão

| Sinal presente na decisão final | Questões |
| --- | ---: |
| Há temas alternativos | 232 |
| Confiança abaixo de 0,95 | 218 |
| Revisão solicitada | 193 |
| Tema central na lista de ambiguidades da árvore | 60 |
| Mais de um tema extra | 32 |
| Tema encontrado na revisão de um candidato a `fora` | 4 |

**Os grupos se sobrepõem.** Uma mesma questão pode ter baixa confiança, temas alternativos e revisão solicitada. Somar as linhas não representa o número de questões. A solicitação de revisão também inclui as quatro correções de `fora`, produzidas pelo revisor de IA, cuja origem permanece explícita na trilha.

Há 49 questões com apenas um sinal:

| Único sinal | Questões |
| --- | ---: |
| Temas alternativos | 41 |
| Confiança abaixo do limiar | 7 |
| Tema central na lista de ambiguidades | 1 |

As outras **228 questões acumulam dois ou mais sinais**. Os grupos e IDs completos estão no [diagnóstico reproduzível](../artefatos/analises/cobertura-v1.json).

## Implicações para uma próxima versão

Reduzir apenas o limiar de confiança não resolve o principal gargalo: somente sete questões estão retidas exclusivamente por esse critério. Mesmo nesses sete casos, mudar a regra não demonstraria que seus temas estão corretos.

As 41 questões retidas exclusivamente por temas alternativos são um grupo delimitado para investigar desambiguação. Isso exige examinar o conteúdo, a hierarquia e o escopo dos candidatos, distinguindo concorrência real de um conceito apenas incidental. Um candidato semanticamente defensável deve ser demonstrado; a ausência dos demais sinais não equivale a validação jurídica.

Uma eventual versão 2 deve registrar previamente sua intervenção, preservar a versão 1 e avaliar os novos publicados. Reutilizar referências já vistas para corrigir o sistema caracteriza desenvolvimento; não constitui nova avaliação independente. A decisão de ampliar a publicação precisa considerar os resultados da auditoria e a incerteza da referência, além da cobertura.

Nenhuma dessas mudanças foi aplicada neste diagnóstico. As 277 decisões continuam `revisar` e as quatro decisões `fora` permanecem separadas.

## Reprodução

Na raiz do repositório, sem chave ou rede:

```powershell
python -B -m classificacao_topicos.diagnostico_cobertura --decisoes artefatos/decisoes-v1 --saida artefatos/analises/cobertura-v1.json
```

O programa confere o hash da trilha e suas contagens contra o manifesto de decisões. Conta cada ID uma vez, expõe sinais sobrepostos e combinações exclusivas e preserva um diagnóstico existente se a nova execução divergir. O JSON inclui hashes das fontes; a repetição com as mesmas entradas é idêntica. Os testes cobrem dupla contagem, sobreposição, correções de `fora`, adulteração da trilha e preservação da saída.
