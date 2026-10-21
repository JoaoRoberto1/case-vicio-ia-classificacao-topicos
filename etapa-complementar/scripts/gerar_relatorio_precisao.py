"""Relatório final M8 de quatro páginas, incluindo memo, sem alterar decisões."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "entrega-final-v2"


def ler(nome):
    return json.loads((RAIZ / nome).read_text(encoding="utf-8"))


def numero(valor, casas=2):
    return f"{valor:.{casas}f}".replace(".", ",")


def percentual(valor):
    return "indefinida" if valor is None else numero(valor * 100) + "%"


def construir_markdown():
    m = ler("artefatos/precisao-m8-v1/metricas.json")
    r = ler("artefatos/precisao-m8-v1/diagnostico_reserva_conhecida.json")
    p = ler("entrega-final-v2/previsao.json")
    d = ler("artefatos/entrega-m8-v1/diagnostico.json")["resultados"]
    b = ler("artefatos/checkpoints/benchmark_modulo8.json")
    antigo = ler("artefatos/entrega-m5-v1/diagnostico.json")
    large = ler("artefatos/embeddings-e5-large-m8/execucao.json")
    receita = m["receita_selecionada"]
    nomes = {"baseline_m7": "M7 preservado", "sinais_small": "Small + sinais",
             "sinais_small_hierarquico": "Small + sinais + hierarquia", "large_rrf20": "Large + fusão RRF",
             "sinais_large": "Large + sinais", "sinais_large_hierarquico": "Large + sinais + hierarquia"}
    escolhido = m["metricas_receitas"][receita]
    externa = m["selecao_aninhada"]
    grupo = externa["publicacao"]
    pub = p["publicadas"]
    desempenho = (f"A política candidata publica {pub}/559 questões ({percentual(p['cobertura_prevista'])}). "
                  f"A precisão prevista é {percentual(p['precisao_prevista'])}, extrapolada de uma avaliação exploratória, sem garantia populacional."
                  if pub else "As 559 questões seguem para revisão. A meta de precisão de 95% com cobertura não foi atingida; sem publicações, a precisão é indefinida.")
    ranking = ("Fusão das posições lexical e semântica por RRF, k=20, pesos iguais; não aprende pesos com os100 rótulos."
               if receita == "large_rrf20" else
               "Ranking supervisionado por pares, com regularização e peso igual por questão. Aprende com centrais e extras humanos; o escore não é probabilidade.")
    ajuste = ("O ranking RRF é fixo: os80 rótulos orientam seleção e calibração; os20 conhecidos entram apenas no diagnóstico."
              if receita == "large_rrf20" else
              "O ranking final é reajustado nas100 referências; a confiança usa apenas as previsões fora do treino das80. Esse reajuste não recebeu teste independente novo.")
    tabela = "\n".join(f"| {nomes[n]}{' (escolhida)' if n == receita else ''} | {x['acertos']['ramo']}/80 | {x['acertos']['exato']} / {x['acertos_top_k_ramo']} |"
                         for n, x in m["metricas_receitas"].items())
    diagnostico = d["selecao_aninhada80"]
    rel = diagnostico["relacoes"]
    comparacao = (f"A publicação externa teve {grupo['k']}/{grupo['n']} acertos ({percentual(grupo['precision'])}); "
                  "essa taxa de grupo informa a previsão, sob hipótese de comparabilidade."
                  if grupo["n"] else "Não houve publicações na avaliação externa; ela não oferece uma estimativa de precisão entre publicadas.")
    confianca = externa["calibracao"]
    constante = externa["calibracao_constante"]
    inferencia = b["tempos_segundos"]["inferencia_559"]
    horas = b["estimativa_linear_50000"]["segundos_so_inferencia"] / 3600
    revisao_horas = (50000 * (1 - p["cobertura_prevista"]) * 2) / 60
    usa_large = "large" in receita
    prep = ({"segundos_observados": large["segundos"], "registros_observados": large["registros"]}
            if usa_large else antigo["contas_50_mil"]["preparacao_m3"])
    prep_horas = 50000 * prep["segundos_observados"] / prep["registros_observados"] / 3600
    status_memo = (f"A política separou {pub} das559 questões para publicação candidata; as demais seguem para revisão. "
                   "A estimativa é exploratória e precisa de confirmação em questões novas antes de uma ampliação em produção."
                   if pub else "A entrega encaminha todas as559 questões à revisão. Ainda não há evidência suficiente para publicação automática com95% de precisão.")
    texto = f"""**João Roberto de Oliveira Felix**

# Classificação de tópicos da Vício

Etapa complementar | Relatório final M8 | 21 de outubro de 2026

**Resultado:** {nomes[receita]} foi a receita escolhida. Acertou {escolhido['acertos']['ramo']}/80 sugestões por ramo no desenvolvimento e {r['geral']['acertos']['ramo']}/20 no diagnóstico já conhecido. {desempenho}

## Sistema construído

O programa recebe659 questões, a árvore e100 referências humanas. Limpa HTML e normaliza campos, preservando IDs e hashes. Disciplina e assunto de origem não entram como verdade nem atributo. Só concorrem371 temas ativos abaixo das raízes. A decisão final usa código numérico próprio e caches: nenhuma chamada a modelo de linguagem ou encoder.

| Componente | Função e procedência |
|---|---|
| Catálogo | Descrições e termos para371 temas, com fontes e ambiguidades;88 âncoras de leis/artigos para87 temas. Preparação por LLM somente sobre taxonomia e fontes, sem consultar classificações de questões. |
| Representação | TF-IDF do catálogo; E5-small FP32 de384 dimensões e alternativa E5-large INT8 de1024, preparados localmente. Texto longo é dividido em janelas, sem corte silencioso. Versões e hashes estão nos manifestos. |
| Ordenação escolhida | {ranking} Variantes com sinais usam normas, artigos, termos e títulos. A relação com uma lei é evidência textual, não validação jurídica. |
| Confiança e publicação | Logística regularizada com nove atributos, ajustada em previsões fora do treino. Dezoito regras por receita com suporte mínimo10 e precisão observada mínima95%; validação externa antes de habilitar a política. |

A variante hierárquica recua ao ancestral comum mais específico dos três primeiros candidatos, quando ativo, não raiz e não genérico. Níveis e recuos são registrados. Não há classificação manual das questões, reutilização de rótulos de IA anteriores ou uso das respostas do concorrente. Não houve revisão jurídica humana dos descritores.

Fontes: [catálogo](../config/modulo7/preparacao_catalogo.json), [âncoras](../config/modulo8/ancoras_normativas.json), [protocolo](../config/modulo8/protocolo.json), [encoder maior](../config/modulo8/embeddings_large.json). E5-large: revisão 3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3, licença MIT. INT8 oficial executado em AVX2; não se presume equivalência ao FP32.

<!-- pagina -->

# Avaliação, escolha e previsão

As100 referências têm92 questões dentro da árvore, oito fora,61 temas centrais e39 questões com extras. Todas vêm do banco anterior; não há referência recente disponível. O acerto aceita central, extra ou ancestral/descendente de um deles; irmãos contam como erro.

## Comparação registrada antes da medição M8

| Receita | Acerto por ramo | Exato / top5 |
|---|---:|---:|
| Híbrido original M3 | 37/80 | 24 /54 |
{tabela}

O M6 já havia testado oito variações sem superar o M3. Enriquecer o catálogo no M7 elevou o acerto a54/80. O M8 compara esse resultado preservado, seis sinais específicos e o encoder maior, mantendo a grade fixada. O maior modelo não recebe preferência por tamanho: a regra prioriza cobertura elegível, precisão, acerto global e desempates fixos.

Em três blocos externos das80 referências, o treino é subdividido para escolher receita e regra e ajustar a confiança. Rótulos externos ficam fora de todos esses ajustes. O procedimento completo teve {externa['geral']['acertos']['ramo']}/80 acertos por ramo e {externa['geral']['acertos_top_k_ramo']}/80 no top5. {comparacao}

Na confiança externa, Brier={numero(confianca['brier'],4)} e log-loss={numero(confianca['logloss'],4)}, contra Brier={numero(constante['brier'],4)} da constante ajustada no treino; menor é melhor. ECE={numero(confianca['ece'],4)}, em cinco faixas fixas. Esses diagnósticos não certificam probabilidades individuais.

## Limites da evidência e entrega

As80 referências orientaram módulos anteriores, e as20 inicialmente reservadas já eram conhecidas. O resultado permanece exploratório: a validação aninhada controla a seleção desta grade, sem apagar a adaptação histórica. O cross-fit interno da confiança compartilha treinos dos rankers; não é um teste independente. As20 foram consultadas somente depois da escolha: {r['geral']['acertos']['ramo']}/20 por ramo e {r['geral']['acertos_top_k_ramo']}/20 no top5.

O CSV reúne80 predições externas aninhadas,20 do diagnóstico e559 da execução final. {ajuste} A previsão exclui as100 referências: cobertura={pub}/559. A precisão real das559 é desconhecida; intervalo de Wilson exploratório não cobre adaptação ou mudança de distribuição. Se não há publicadas, TXT usa zero como sentinela e JSON registra null.

Fontes: [métricas](../artefatos/precisao-m8-v1/metricas.json), [diagnóstico das20](../artefatos/precisao-m8-v1/diagnostico_reserva_conhecida.json), [previsão](previsao.json). Não são resultados de um novo teste independente.

<!-- pagina -->

# Diagnóstico e operação

## O que ainda atrapalha

A árvore original tem337 descrições de parentesco,20 vazias e oito grupos de títulos repetidos. O enriquecimento melhora a representação, mas não estabelece a convenção editorial da equipe. Recortes ambíguos como Parte1/2 continuam sem fronteiras inventadas. Os100 exemplos cobrem apenas61 centrais, o que limita o aprendizado de distinções finas.

Na seleção externa das80, a comparação estrutural encontrou {rel.get('outra_disciplina_erro',0)} erros em outra disciplina, {rel.get('outro_ramo_mesma_disciplina_erro',0)} em outro ramo da mesma disciplina, {rel.get('irmao_erro',0)} em tema irmão e {rel.get('referencia_fora',0)} referências fora. Em {diagnostico['erros_ordenacao_com_aceito_top5']} erros havia destino aceito no top5; em {diagnostico['sem_aceito_top5_incluindo_fora']} casos não havia, incluindo fora. São relações da árvore, não causas jurídicas demonstradas por IA.

As intervenções propostas são critérios de inclusão/exclusão para temas próximos, exemplos humanos por recorte e avaliação temporal recente. Baixa confiança encaminha à revisão; não prova que a questão é fora da taxonomia. Extras não são automatizados sem avaliação própria.

## Cenário de50 mil questões por semana

As medidas locais usam Windows e CPU. Uma execução em ambiente compartilhado não é teste de carga de produção. A projeção abaixo é linear, com textos e catálogo semelhantes, sem paralelismo; vetores já existentes não precisam ser preparados novamente.

| Fase | Medida local | Projeção para50 mil |
|---|---|---|
| Preparação selecionada | {numero(prep['segundos_observados'],1)}s /{prep['registros_observados']} registros, misturando questões e temas | {numero(prep_horas)} horas; aproximação com custo fixo e composição diferente |
| Decisão com vetores prontos | {numero(inferencia,1)}s para559; carga separada:{numero(b['tempos_segundos']['carga_e_verificacao_inicial'],1)}s | {numero(horas)} horas só de inferência |
| Revisão humana | Hipótese:2min por questão revisada; cobertura mantida | {numero(revisao_horas,1)} horas de revisão |

Não houve custo de API. Computador, energia e revisão têm custo: a conta é horas-máquina vezes sua tarifa mais horas de revisão vezes o custo do especialista. O tempo humano acima é hipótese de cenário, não duração medida. O gargalo operacional depende da cobertura validada, não apenas da velocidade do código.

Cada correção deve registrar central, extras ou fora, justificativa, revisor e versões da árvore e do sistema. Avaliar candidatos semanalmente, com novas correções e teste temporal separado; promover só com precisão e cobertura sustentadas, preservando a versão anterior. Essa operação é proposta, não serviço implantado.

Para regenerar CSV e previsão, na pasta etapa-complementar: `python -E -X utf8 -B -S scripts/entregar_precisao.py`. O README separa esse comando da reconstrução dos embeddings e do PDF. A verificação em cópia bloqueia rede, credenciais, encoders e pesos.

Fontes: [benchmark](../artefatos/checkpoints/benchmark_modulo8.json), [diagnóstico estrutural](../artefatos/entrega-m8-v1/diagnostico.json), [preparação large](../artefatos/embeddings-e5-large-m8/execucao.json). Projeções não são garantias de capacidade.

<!-- pagina -->

# Memo para o professor

**Para:** equipe responsável pelos temas e pela revisão de questões  
**De:** João Roberto de Oliveira Felix  
**Assunto:** critérios dos temas, revisão e próxima validação

## O que encontramos

Melhorar as descrições do catálogo ajudou o sistema a encontrar destinos mais coerentes com as classificações da equipe. Na rodada final, a avaliação do procedimento em80 referências acertou {externa['geral']['acertos']['ramo']} primeiras sugestões; em {externa['geral']['acertos_top_k_ramo']} havia um destino aceito entre as cinco opções. Esses exemplos já foram usados em desenvolvimento, portanto os números não garantem o mesmo resultado em questões novas.

{status_memo} A sugestão pode ajudar na triagem, mas a confiança estimada não substitui sua decisão em um caso incerto.

## O que recomendamos mudar nos temas

Começar pelos títulos repetidos, descrições sem definição temática e recortes como Parte1/2. Para cada destino, escrever o que entra, o que não entra e como se distingue dos temas próximos. Incluir exemplos e contraexemplos revisados pela equipe. Informar se um nó aceita questões diretamente ou apenas organiza subtemas.

Não recomendamos juntar temas automaticamente porque seus nomes são parecidos. Quando forem o mesmo destino de estudo, a equipe pode estabelecer um nome principal e redirecionamentos. Quando forem recortes diferentes, a fronteira precisa ser explícita. Toda alteração deve ter versão e mapa dos IDs, preservando o histórico das questões.

As descrições e referências de leis preparadas nesta entrega são insumos para o sistema, sem revisão jurídica humana. Elas não resolvem sozinhas a convenção editorial. Uma citação de lei ou artigo também não determina, por si, o assunto central de uma questão.

## Apoio necessário da equipe

Priorizar uma amostra de questões recentes, sem usar todas imediatamente para corrigir o sistema. Guardar parte para uma avaliação futura separada. Incluir temas com poucos exemplos, fronteiras entre temas próximos e situações em que nenhum destino serve. Em parte da amostra, dois revisores podem classificar independentemente e resolver divergências.

Registrar o tema central, os temas adicionais aceitos, o motivo da correção e eventual lacuna da árvore. Distinguir erro da sugestão, informação ausente, ambiguidade da convenção e ausência de tema. Nas100 referências,39 possuem assuntos adicionais; uma regra comum para central e extras ajudará tanto o treinamento quanto a revisão.

**Recomendação:** limitar o piloto à capacidade da equipe e ampliar a automação somente após confirmar precisão de pelo menos95% em uma avaliação humana recente, com quantidade de casos e cobertura explicitadas. O principal próximo ganho deve ser demonstrado na redução de revisão sem aumentar publicações erradas.
"""
    # Espaçamento editorial; links, código e revisão do encoder são preservados.
    import re
    trechos = re.split(r"(`[^`]*`|\[[^\]]*\]\([^)]+\)|[0-9a-f]{40})", texto)
    for i in range(0, len(trechos), 2):
        trechos[i] = re.sub(r"(?<=[a-záéíóúãõçêô])(?=\d)", " ", trechos[i])
        trechos[i] = re.sub(r"(?<=\d)(?=(?:questões|temas|rótulos|referências|âncoras|centrais|min\b|s\b))", " ", trechos[i])
        trechos[i] = re.sub(r"(?<=[;:])(?=\S)", " ", trechos[i])
    return "".join(trechos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true")
    args = parser.parse_args()
    markdown = construir_markdown()
    spec = importlib.util.spec_from_file_location("render_relatorio_m5", RAIZ / "scripts/gerar_relatorio.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    pdf = modulo.gerar(markdown)
    for nome, dados in (("relatorio.md", markdown.encode("utf-8")), ("relatorio.pdf", pdf)):
        destino = DESTINO / nome
        if args.verificar:
            if destino.read_bytes() != dados:
                raise ValueError("Relatório divergente: " + nome)
        else:
            DESTINO.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(dados)
    print(json.dumps({"paginas": 4, "bytes": len(pdf), "sha256": hashlib.sha256(pdf).hexdigest(),
                      "verificado": args.verificar}))


if __name__ == "__main__":
    main()
