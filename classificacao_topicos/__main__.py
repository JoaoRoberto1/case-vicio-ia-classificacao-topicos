"""Interface de linha de comando do projeto."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from .preparacao import executar_preparacao


def _registrar_verificacao_api(registro: dict) -> None:
    raiz = Path(__file__).resolve().parents[1]
    destino = raiz / "artefatos" / "execucoes" / "verificacoes_api.jsonl"
    if destino.is_symlink() or not destino.resolve().is_relative_to(raiz):
        raise ValueError("Destino do registro da API inválido.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    registro = {"instante_utc": datetime.now(timezone.utc).isoformat(), **registro}
    with destino.open("a", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Case Vício: preparação e classificação de tópicos.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    preparar = comandos.add_parser("preparar", help="Preparar dados e conferir a árvore sem chamar modelos.")
    preparar.add_argument("--entrada", type=Path, default=Path("."), help="Pasta dos materiais originais.")
    preparar.add_argument("--saida", type=Path, default=Path("artefatos/preparacao"), help="Pasta dos produtos derivados.")
    piloto = comandos.add_parser("preparar-piloto", help="Selecionar casos e montar prompts sem chamar a API.")
    piloto.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    piloto.add_argument("--saida", type=Path, default=Path("artefatos/piloto"))
    piloto.add_argument("--tamanho", type=int, default=20)
    piloto.add_argument("--semente", type=int, default=20261014)
    piloto.add_argument("--prompt", type=Path, default=None, help="Template alternativo para um novo experimento.")
    piloto.add_argument("--versao-prompt", default="classificacao-v1")
    lote = comandos.add_parser("preparar-lote", help="Preparar todas as questões, preservando a lista de desenvolvimento.")
    lote.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    lote.add_argument("--piloto-desenvolvimento", type=Path, required=True)
    lote.add_argument("--saida", type=Path, required=True)
    lote.add_argument("--prompt", type=Path, required=True)
    lote.add_argument("--versao-prompt", required=True)
    verificar = comandos.add_parser("verificar-api", help="Fazer uma chamada sintética curta para conferir a integração.")
    verificar.add_argument("--env", type=Path, default=None, help="Arquivo de configuração local; padrão .env.")
    executar = comandos.add_parser("executar-piloto", help="Executar até o limite informado, reaproveitando respostas salvas.")
    executar.add_argument("--piloto", type=Path, default=Path("artefatos/piloto"))
    executar.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    executar.add_argument("--saida", type=Path, default=Path("artefatos/execucoes/piloto-v1"))
    executar.add_argument("--env", type=Path, default=None)
    executar.add_argument("--limite", type=int, default=1, help="Máximo de novas chamadas nesta execução; padrão 1.")
    executar.add_argument("--intervalo-segundos", type=float, default=10.0)
    executar_lote_parser = comandos.add_parser("executar-lote", help="Executar um lote completo com limite explícito e retomada.")
    executar_lote_parser.add_argument("--lote", type=Path, required=True)
    executar_lote_parser.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    executar_lote_parser.add_argument("--saida", type=Path, required=True)
    executar_lote_parser.add_argument("--env", type=Path, default=None)
    executar_lote_parser.add_argument("--limite", type=int, default=1)
    executar_lote_parser.add_argument("--intervalo-segundos", type=float, default=10.0)
    executar_lote_parser.add_argument("--continuar-erros-validacao", action="store_true",
                                      help="Salvar respostas inválidas e avançar; falhas da API ainda interrompem.")
    executar_lote_parser.add_argument("--ids-arquivo", type=Path, default=None,
                                      help="JSON com lista não vazia de IDs únicos do lote; mantém a ordem do manifesto.")
    revalidar = comandos.add_parser("revalidar-recibo", help="Revalidar offline a primeira tentativa tecnicamente válida, preservando o recibo.")
    revalidar.add_argument("--lote", type=Path, required=True)
    revalidar.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    revalidar.add_argument("--execucao", type=Path, required=True)
    revalidar.add_argument("--id", required=True)
    analisar = comandos.add_parser("analisar-piloto", help="Comparar sugestões e revisões provisórias, sem chamadas externas.")
    analisar.add_argument("--piloto", type=Path, default=Path("artefatos/piloto"))
    analisar.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    analisar.add_argument("--execucao", type=Path, required=True)
    analisar.add_argument("--revisoes", type=Path, default=Path("artefatos/revisao_piloto"))
    analisar.add_argument("--saida", type=Path, required=True)
    decisoes = comandos.add_parser("preparar-decisoes", help="Aplicar a política aos recibos e gerar o CSV quando não houver pendências, sem API.")
    decisoes.add_argument("--lote", type=Path, required=True)
    decisoes.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    decisoes.add_argument("--execucao", type=Path, required=True)
    decisoes.add_argument("--politica", type=Path, default=Path("config/politica_v1.json"))
    decisoes.add_argument("--confirmacoes-fora", type=Path, default=None,
                          help="JSONL com as revisões separadas dos candidatos fora.")
    decisoes.add_argument("--saida", type=Path, required=True)
    auditoria = comandos.add_parser("preparar-auditoria", help="Sortear a amostra e preparar entradas cegas a partir das decisões congeladas, sem API.")
    auditoria.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    auditoria.add_argument("--lote", type=Path, required=True)
    auditoria.add_argument("--decisoes", type=Path, required=True,
                           help="Pasta das decisões ou caminho do CSV completo.")
    auditoria.add_argument("--politica", type=Path, default=Path("config/politica_v1.json"))
    auditoria.add_argument("--saida", type=Path, required=True, help="Nova pasta vazia para a seleção congelada.")
    avaliacao = comandos.add_parser("avaliar-auditoria", help="Comparar a amostra com referências provisórias de IA, sem API.")
    avaliacao.add_argument("--preparacao", type=Path, default=Path("artefatos/preparacao"))
    avaliacao.add_argument("--auditoria", type=Path, required=True)
    avaliacao.add_argument("--decisoes", type=Path, required=True,
                           help="Pasta das decisões ou caminho do CSV congelado.")
    avaliacao.add_argument("--revisoes", type=Path, required=True,
                           help="Arquivo JSONL ou pasta de referências provisórias.")
    avaliacao.add_argument("--saida", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.comando == "preparar":
            diagnostico = executar_preparacao(args.entrada, args.saida)
            resultado = {"questoes": diagnostico["questoes"]["total"],
                         "temas": diagnostico["taxonomia"]["total"], "saida": str(args.saida)}
        elif args.comando == "preparar-piloto":
            from .piloto import preparar_piloto
            manifesto = preparar_piloto(args.preparacao, args.saida, args.tamanho, args.semente,
                                       prompt_path=args.prompt, prompt_version=args.versao_prompt)
            resultado = {"questoes_piloto": len(manifesto["ids"]), "saida": str(args.saida), "chamadas_api": 0}
        elif args.comando == "preparar-lote":
            from .lote import preparar_lote
            manifesto = preparar_lote(args.preparacao, args.piloto_desenvolvimento, args.saida,
                                      prompt_path=args.prompt, prompt_version=args.versao_prompt)
            resultado = {"questoes_lote": len(manifesto["ids"]), "desenvolvimento": len(manifesto["desenvolvimento_ids"]),
                         "saida": str(args.saida), "chamadas_api": 0}
        elif args.comando == "verificar-api":
            from .gemini import ErroGemini, carregar_configuracao, gerar_json
            config = carregar_configuracao(args.env)
            try:
                recibo = gerar_json(
                    'Responda somente com um objeto JSON contendo o campo ok com valor true.',
                    {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
                    api_key=config["api_key"], model=config["model"], thinking_level="LOW",
                )
            except ErroGemini as erro:
                _registrar_verificacao_api({"status": "erro", "modelo": config["model"],
                                            "erro": str(erro), "resposta": erro.resposta,
                                            "duracao_segundos": erro.duracao_segundos})
                raise
            resposta_valida = (set(recibo["resultado"]) == {"ok"}
                              and recibo["resultado"]["ok"] is True)
            _registrar_verificacao_api({"status": "sucesso" if resposta_valida else "resposta_inesperada",
                                        "modelo": config["model"], "resposta": recibo["resposta"],
                                        "duracao_segundos": recibo["duracao_segundos"]})
            if not resposta_valida:
                raise ValueError("A resposta sintética não correspondeu ao contrato esperado.")
            resultado = {"ok": True, "modelo_solicitado": config["model"],
                         "modelo_retornado": recibo["resposta"].get("modelVersion"),
                         "uso": recibo["resposta"].get("usageMetadata"),
                         "duracao_segundos": recibo["duracao_segundos"]}
        elif args.comando == "revalidar-recibo":
            from .execucao import _validar_entradas, _validar_cache, _ler, _json, _hash_bytes, _canonico
            from .piloto import esquema_resposta
            from .revalidacao import revalidar_recibo
            entradas, temas, questoes, hash_preparacao, _ = _validar_entradas(
                args.lote, args.preparacao, procedimento_esperado="lote-v1")
            entrada = next((e for e in entradas if e["id"] == args.id), None)
            if entrada is None:
                raise ValueError("O ID solicitado não pertence ao lote.")
            caminho = args.execucao / (args.id + ".json")
            registro = _json(_ler(caminho))
            if not isinstance(registro, dict) or not isinstance(registro.get("model"), str):
                raise ValueError("Recibo sem modelo válido.")
            modelo = registro["model"]
            hash_schema = _hash_bytes(_canonico(esquema_resposta()))
            registro = _validar_cache(caminho, entrada, modelo, hash_schema, hash_preparacao, temas, questoes[args.id])
            revisao = revalidar_recibo(caminho, registro, entrada, modelo, hash_schema,
                                       hash_preparacao, temas, questoes[args.id])
            resultado = {"id": args.id, "status": "sucesso_revalidado", "chamadas_api": 0,
                         "numero_tentativa_selecionada": revisao["numero_tentativa_selecionada"]}
        elif args.comando in {"executar-piloto", "executar-lote"}:
            from .execucao import executar_lote, executar_piloto
            funcao = executar_piloto if args.comando == "executar-piloto" else executar_lote
            entrada = args.piloto if args.comando == "executar-piloto" else args.lote
            opcoes_lote = ({"continuar_erros_validacao": args.continuar_erros_validacao}
                          if args.comando == "executar-lote" else {})
            if args.comando == "executar-lote" and args.ids_arquivo is not None:
                from .execucao import _json, _ler
                ids = _json(_ler(args.ids_arquivo))
                if not isinstance(ids, list):
                    raise ValueError("O arquivo de IDs deve conter uma lista JSON de strings.")
                opcoes_lote["ids_selecionados"] = ids
            resultado = funcao(entrada, args.preparacao, args.saida, env_path=args.env,
                              limite=args.limite, intervalo_segundos=args.intervalo_segundos, **opcoes_lote)
        elif args.comando == "preparar-decisoes":
            from .decisoes import preparar_decisoes
            resumo = preparar_decisoes(args.lote, args.preparacao, args.execucao, args.politica,
                                       args.saida, confirmacoes_fora=args.confirmacoes_fora)
            resultado = {"questoes": resumo["total_questoes"], "completo": resumo["completo"],
                         "decisoes": resumo["decisoes"], "pendentes_fora": resumo["pendentes_fora"],
                         "revisoes_fora": resumo["revisoes_fora"],
                         "ids_pendentes": resumo["ids_pendentes"], "saida": str(args.saida),
                         "chamadas_api": 0}
        elif args.comando == "preparar-auditoria":
            from .auditoria import preparar_auditoria
            manifesto = preparar_auditoria(args.preparacao, args.lote, args.decisoes, args.politica, args.saida)
            resultado = {"questoes": manifesto["total_questoes"], "publicadas": manifesto["total_publicadas"],
                         "selecionadas": len(manifesto["ids"]), "semente": manifesto["semente"],
                         "estratos": {nome: {campo: estrato[campo] for campo in ("N", "n", "metodo")}
                                      for nome, estrato in manifesto["estratos"].items()},
                         "referencia_tipo": manifesto["referencia_tipo"],
                         "saida": str(args.saida), "chamadas_api": 0}
        elif args.comando == "avaliar-auditoria":
            from .avaliacao import avaliar_auditoria
            relatorio = avaliar_auditoria(args.preparacao, args.auditoria, args.decisoes,
                                          args.revisoes, args.saida)
            resultado = {"questoes": relatorio["total_questoes"], "publicadas": relatorio["total_publicadas"],
                         "revisadas": relatorio["total_revisadas"], "tipo_referencia": relatorio["tipo_referencia"],
                         "comparacao_central": relatorio["comparacao_central"],
                         "precisao_condicional": relatorio["precisao_condicional"], "cobertura": relatorio["cobertura"],
                         "saida": str(args.saida), "chamadas_api": 0}
        else:
            from .analise_piloto import analisar_piloto
            resumo = analisar_piloto(args.piloto, args.preparacao, args.execucao,
                                     args.revisoes, args.saida)
            resultado = {"questoes": resumo["total_questoes"], "status_tecnico": resumo["status_tecnico"],
                         "comparacao_central": resumo["comparacao_central"], "saida": str(args.saida)}
    except (ValueError, OSError) as erro:
        parser.exit(2, f"Erro: {erro}\n")
    except RuntimeError as erro:
        # Erros do cliente REST usam mensagens sanitizadas, sem chave/headers.
        parser.exit(2, f"Erro: {erro}\n")
    print(json.dumps(resultado, ensure_ascii=False))
    return 1 if (resultado.get("parou_em_erro") or resultado.get("concluido_com_falhas")
                 or resultado.get("completo") is False) else 0


if __name__ == "__main__":
    raise SystemExit(main())
