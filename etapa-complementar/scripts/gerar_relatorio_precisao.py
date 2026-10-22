"""Relatório final M8 de quatro páginas, incluindo memo, sem alterar decisões."""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "entrega-final-v2"


def ler(nome):
    return json.loads((RAIZ / nome).read_text(encoding="utf-8"))


def numero(valor, casas=2):
    return f"{valor:.{casas}f}".replace(".", ",")


def percentual(valor):
    return "indefinida" if valor is None else numero(valor * 100) + "%"


def linhas_preparacao(receita, small, large, tempo_questoes=None):
    """Separa encoders e não trata checkpoints reutilizados como trabalho medido."""
    horas_small = 50000 * small["segundos_observados"] / small["registros_observados"] / 3600
    linhas = [f"| Preparação Small | {numero(small['segundos_observados'],1)}s /{small['registros_observados']} registros | {numero(horas_small)} horas; aproximação com questões e temas misturados |"]
    nota = "A preparação Small inclui carga fixa e uma composição diferente da semana projetada."
    if "large" in receita:
        total = large["registros"]
        reutilizados = large["registros_reutilizados_checkpoint"]
        if (type(total) is not int or type(reutilizados) is not int
                or not 0 <= reutilizados <= total or total <= 0):
            raise ValueError("Contagens de preparação Large inválidas.")
        if not isinstance(tempo_questoes, dict):
            raise ValueError("Projeção Large exige evidência dos intervalos de questões.")
        n = tempo_questoes["registros_medidos"]
        intervalos = tempo_questoes["intervalos_ns"]
        registros = tempo_questoes["registros"]
        derivados = [b["concluido_mtime_ns"] - a["concluido_mtime_ns"]
                     for a, b in zip(registros, registros[1:])]
        if (type(n) is not int or n <= 0 or len(registros) != n + 1
                or len(intervalos) != n or derivados != intervalos
                or any(type(x) is not int or x <= 0 for x in intervalos)
                or tempo_questoes["temas_incluidos"] is not False
                or tempo_questoes["carga_encoder_ou_594_reutilizados_incluidos"] is not False
                or not math.isclose(sum(intervalos) / 1e9, tempo_questoes["segundos"], abs_tol=1e-9)):
            raise ValueError("Evidência temporal Large inconsistente.")
        horas_large = 50000 * tempo_questoes["segundos"] / n / 3600
        linhas.append(f"| Preparação Large adicional | {numero(tempo_questoes['segundos'],1)}s /{n} questões ({tempo_questoes['janelas_medidas']} janelas) | {numero(horas_large)} horas adicionais; extrapolação linear condicional |")
        nota = (f"Large também exige Small: cenário somado de{numero(horas_small + horas_large)} horas. "
                f"Large usa{n} questões contíguas não aleatórias, por timestamps de arquivos em host compartilhado; "
                "não garante representatividade e exclui carga inicial e reaproveitamento de cache. "
                "A duração integral desde zero permanece desconhecida.")
    return "\n".join(linhas), nota


def construir_markdown():
    m = ler("artefatos/precisao-m8-v1/metricas.json")
    r = ler("artefatos/precisao-m8-v1/diagnostico_reserva_conhecida.json")
    p = ler("entrega-final-v2/previsao.json")
    d = ler("artefatos/entrega-m8-v1/diagnostico.json")["resultados"]
    b = ler("artefatos/checkpoints/benchmark_modulo8.json")
    antigo = ler("artefatos/entrega-m5-v1/diagnostico.json")
    large = ler("artefatos/embeddings-e5-large-m8/execucao.json")
    receita = m["receita_selecionada"]
    tempo_questoes = (ler("artefatos/embeddings-e5-large-m8/retomada-v1/tempo_questoes.json")
                     if "large" in receita else None)
    nomes = {"baseline_m7": "M7 preservado", "sinais_small": "Small + sinais",
             "sinais_small_hierarquico": "Small + sinais + hierarquia", "large_rrf20": "Large + fusão RRF",
             "sinais_large": "Large + sinais", "sinais_large_hierarquico": "Large + sinais + hierarquia"}
    escolhido = m["metricas_receitas"][receita]
    interna = m["politica_selecionada_dev"]
    externa = m["selecao_aninhada"]
    grupo = externa["publicacao"]
    pub = p["publicadas"]
    desempenho = (f"A política candidata publica {pub}/559 questões ({percentual(p['cobertura_prevista'])}). "
                  f"A precisão prevista é {percentual(p['precisao_prevista'])}, extrapolada de uma avaliação exploratória, sem garantia populacional."
                  if pub else "As 559 questões seguem para revisão. A meta de precisão de 95% com cobertura não foi atingida; sem publicações, a precisão é indefinida.")
    ranking = ("Fusão das posições lexical e semântica por RRF, k=20, pesos iguais; não aprende pesos com os100 rótulos. Sinais específicos informam confiança e política, sem mudar o ranking RRF."
               if receita == "large_rrf20" else
               "Ranking supervisionado por pares, com regularização e peso igual por questão. Aprende com centrais e extras humanos; o escore não é probabilidade. Variantes com sinais usam normas, artigos, termos e títulos.")
    ajuste = ("O ranking RRF é fixo: os80 rótulos orientam seleção e calibração; os20 conhecidos entram apenas no diagnóstico."
              if receita == "large_rrf20" else
              "O ranking final é reajustado nas100 referências; a confiança usa apenas as previsões fora do treino das80. Esse reajuste não recebeu teste independente novo.")
    tabela = "\n".join(f"| {nomes[n]}{' (escolhida)' if n == receita else ''} | {x['acertos']['ramo']}/80 | {x['acertos']['exato']} / {x['acertos_top_k_ramo']} |"
                         for n, x in m["metricas_receitas"].items())
    diagnostico = d["selecao_aninhada80"]
    rel = diagnostico["relacoes"]
    comparacao = (f"As regras candidatas aceitaram {grupo['n']}/80 ({percentual(grupo['coverage'])}), "
                  f"com {grupo['k']}/{grupo['n']} acertos e Wilson95% de{percentual(grupo['wilson95']['inferior'])} "
                  f"a{percentual(grupo['wilson95']['superior'])}. "
                  f"São menos de10 aceitos: a política final ficou desabilitada."
                  if grupo["n"] else "As regras candidatas não aceitaram questões na avaliação externa; não há estimativa de precisão entre aceitas.")
    origem_aceites = "; ".join(
        f"bloco{x['particao']}: {nomes[x['politica']['receita']]} aceitou{x['resultado_externo']['n']}"
        for x in externa["particoes"])
    confianca = externa["calibracao"]
    constante = externa["calibracao_constante"]
    inferencia = b["tempos_segundos"]["inferencia_559"]
    horas = b["estimativa_linear_50000"]["segundos_so_inferencia"] / 3600
    revisao_horas = (50000 * (1 - p["cobertura_prevista"]) * 2) / 60
    preparo_linhas, preparo_nota = linhas_preparacao(
        receita, antigo["contas_50_mil"]["preparacao_m3"], large, tempo_questoes)
    status_memo = (f"A política separou {pub} das559 questões para publicação candidata; as demais seguem para revisão. "
                   "A estimativa é exploratória e precisa de confirmação em questões novas antes de uma ampliação em produção."
                   if pub else "A entrega encaminha todas as559 questões à revisão. Ainda não há evidência suficiente para publicação automática com95% de precisão.")
    texto = f"""**João Roberto de Oliveira Felix**

# Classificação de tópicos da Vício

Etapa complementar | Relatório final M8 | 22 de outubro de 2026

**Resultado:** {nomes[receita]} foi a receita escolhida. Acertou {escolhido['acertos']['ramo']}/80 sugestões por ramo no desenvolvimento e {r['geral']['acertos']['ramo']}/20 no diagnóstico já conhecido. {desempenho}

## Sistema construído

O programa recebe659 questões, a árvore e100 referências humanas. Limpa HTML e normaliza campos, preservando IDs e hashes. Disciplina e assunto de origem não entram como verdade nem atributo. Só concorrem371 temas ativos abaixo das raízes. A decisão final usa código numérico próprio e caches: nenhuma chamada a modelo de linguagem ou encoder.

| Componente | Função e procedência |
|---|---|
| Catálogo | Descrições e termos para371 temas, com fontes e ambiguidades;88 âncoras de leis/artigos para87 temas. Preparação por LLM somente sobre taxonomia e fontes, sem consultar classificações de questões. |
| Representação | TF-IDF do catálogo; E5-small FP32 de384 dimensões e alternativa E5-large INT8 de1024, preparados localmente. As receitas Large também requerem vetores Small. Texto longo usa janelas, sem corte silencioso. Versões e hashes estão nos manifestos. |
| Ordenação escolhida | {ranking} Uma referência legal é evidência textual, não validação jurídica. |
| Confiança e publicação | Logística regularizada com nove atributos, ajustada em previsões fora do treino. Dezoito regras por receita com suporte mínimo10 e precisão observada mínima95%; validação externa antes de habilitar a política. |

A variante hierárquica recua ao ancestral comum mais específico dos três primeiros candidatos, quando ativo, não raiz e não genérico. Níveis e recuos são registrados. As referências de classificação são exclusivamente as100 fornecidas pela equipe, sem rótulos artificiais ou classificação manual das questões. Não houve revisão jurídica humana dos descritores.

Fontes: [catálogo](../config/modulo7/preparacao_catalogo.json), [âncoras](../config/modulo8/ancoras_normativas.json), [protocolo](../config/modulo8/protocolo.json), [encoder maior](../config/modulo8/embeddings_large.json). E5-large: revisão 3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3, licença MIT. INT8 oficial executado em AVX2; não se presume equivalência ao FP32.

<!-- pagina -->

# Avaliação, escolha e previsão

As100 referências têm92 questões dentro da árvore, oito fora, 61 temas centrais e39 questões com extras. Todas vêm do banco anterior; não há referência recente disponível. O acerto aceita central, extra ou ancestral/descendente de um deles; irmãos contam como erro.

## Grade fixada antes da medição M8

| Receita | Acerto por ramo | Exato / top5 |
|---|---:|---:|
| Híbrido original M3 | 37/80 | 24 /54 |
{tabela}

A regra fixada prioriza cobertura elegível, precisão e depois acerto global. Na seleção interna, {nomes[receita]} com confiança mínima{numero(interna['corte'])} teve{interna['k']}/{interna['n']} aceitas corretas ({percentual(interna['n']/80)} das80). RRF também teve14/14, mas perdeu no desempate:50/80 contra{escolhido['acertos']['ramo']}/80. M7 tinha54/80, sem grupo elegível. Portanto, a escolhida não melhorou o acerto global: perdeu um acerto frente ao M7.

Em três blocos externos, receita, regra e confiança são ajustadas apenas no treino. O procedimento teve {externa['geral']['acertos']['ramo']}/80 acertos por ramo, {externa['geral']['acertos']['exato']} exatos e {externa['geral']['acertos_top_k_ramo']} no top5. {comparacao} Origem: {origem_aceites}. Os4/4 vieram do RRF; não validam diretamente a receita final nem repetem o resultado interno de14/14.

Na confiança externa, Brier={numero(confianca['brier'],4)} contra{numero(constante['brier'],4)} da constante ajustada no treino; ECE={numero(confianca['ece'],4)} contra{numero(constante['ece'],4)}, em cinco faixas. Menor é melhor em ambos: o Brier melhorou, o ECE piorou. O resultado misto não certifica probabilidades individuais.

## Limites da evidência e entrega

As80 referências orientaram módulos anteriores; as20 reservadas já eram conhecidas. A validação aninhada separa esta seleção, sem apagar a adaptação histórica. O cross-fit interno compartilha treinos dos rankers. O diagnóstico das20 veio depois da escolha: {r['geral']['acertos']['ramo']}/20 por ramo e {r['geral']['acertos_top_k_ramo']}/20 no top5; não é um teste independente novo.

O CSV reúne80 predições externas aninhadas,20 do diagnóstico e559 da execução final. {ajuste} A previsão exclui as100 referências: cobertura={pub}/559. A precisão real das559 é desconhecida; intervalo de Wilson exploratório não cobre adaptação ou mudança de distribuição. Se não há publicadas, TXT usa zero como sentinela e JSON registra null.

Fontes: [métricas](../artefatos/precisao-m8-v1/metricas.json), [diagnóstico das 20](../artefatos/precisao-m8-v1/diagnostico_reserva_conhecida.json), [previsão](previsao.json). Não são resultados de um novo teste independente.

<!-- pagina -->

# Diagnóstico e operação

## O que ainda atrapalha

A árvore original tem337 descrições de parentesco, 20 vazias e oito grupos de títulos repetidos. O enriquecimento melhora a representação, mas não estabelece a convenção editorial da equipe. Recortes ambíguos como Parte1/2 continuam sem fronteiras inventadas. Os100 exemplos cobrem apenas61 centrais, o que limita o aprendizado de distinções finas.

Na seleção externa das80, a comparação estrutural encontrou {rel.get('outra_disciplina_erro',0)} erros em outra disciplina, {rel.get('outro_ramo_mesma_disciplina_erro',0)} em outro ramo da mesma disciplina, {rel.get('irmao_erro',0)} em tema irmão e {rel.get('referencia_fora',0)} referências fora. Em {diagnostico['erros_ordenacao_com_aceito_top5']} erros havia destino aceito no top5; em {diagnostico['sem_aceito_top5_incluindo_fora']} casos não havia, incluindo fora. São relações da árvore, não causas jurídicas demonstradas por IA.

As intervenções propostas são critérios de inclusão/exclusão para temas próximos, exemplos humanos por recorte e avaliação temporal recente. Baixa confiança encaminha à revisão; não prova que a questão é fora da taxonomia. Extras não são automatizados sem avaliação própria.

## Cenário de50 mil questões por semana

As medidas locais usam Windows e CPU. Uma execução em ambiente compartilhado não é teste de carga de produção. A projeção abaixo é linear, com textos e catálogo semelhantes, sem paralelismo; vetores já existentes não precisam ser preparados novamente.

| Fase | Medida local | Projeção para50 mil |
|---|---|---|
{preparo_linhas}
| Decisão com vetores prontos | {numero(inferencia,1)}s para559; carga separada:{numero(b['tempos_segundos']['carga_e_verificacao_inicial'],1)}s | {numero(horas)} horas só de inferência |
| Revisão humana | Hipótese:2min por questão revisada; cobertura mantida | {numero(revisao_horas,1)} horas de revisão |

{preparo_nota} Não houve custo de API. Computador, energia e revisão têm custo: horas-máquina vezes tarifa mais horas de revisão vezes custo do especialista. O tempo humano é hipótese, não duração medida.

Em produção, processar em lotes e liberar caches de consultas para limitar RAM. Cada correção registra central, extras ou fora, justificativa, revisor e versões. Avaliar candidatos semanalmente com novas correções e teste temporal separado; promover só com precisão e cobertura sustentadas, preservando a versão anterior. Essa operação é proposta, não serviço implantado.

Para regenerar CSV e previsão, na pasta etapa-complementar: `python -E -X utf8 -B -S scripts/entregar_precisao.py`. O README separa esse comando da reconstrução dos embeddings e do PDF. A verificação em cópia bloqueia rede, credenciais, encoders e pesos.

Fontes: [benchmark](../artefatos/checkpoints/benchmark_modulo8.json), [diagnóstico estrutural](../artefatos/entrega-m8-v1/diagnostico.json), [preparação Small](../artefatos/entrega-m5-v1/diagnostico.json), [execução Large](../artefatos/embeddings-e5-large-m8/execucao.json), [intervalos Large](../artefatos/embeddings-e5-large-m8/retomada-v1/tempo_questoes.json). Projeções não garantem capacidade.

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


def gerar_pdf(markdown):
    from reportlab.pdfgen import canvas
    from unittest.mock import patch

    spec = importlib.util.spec_from_file_location("render_relatorio_m5", RAIZ / "scripts/gerar_relatorio.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    rodapes_atualizados = 0

    class CanvasRelatorio(canvas.Canvas):
        def drawString(self, x, y, text, *args, **kwargs):
            nonlocal rodapes_atualizados
            if text == "Vício | Etapa complementar | 21 out 2026":
                text = "Vício | Etapa complementar | 22 out 2026"
                rodapes_atualizados += 1
            return super().drawString(x, y, text, *args, **kwargs)

    # Reutiliza o layout M5 sem alterar sua fonte congelada por hashes.
    with patch.object(canvas, "Canvas", CanvasRelatorio):
        pdf = modulo.gerar(markdown)
    if rodapes_atualizados != 4:
        raise ValueError("Os quatro rodapés devem usar a data da entrega M8.")
    return pdf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verificar", action="store_true")
    args = parser.parse_args()
    markdown = construir_markdown()
    pdf = gerar_pdf(markdown)
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
