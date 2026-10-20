"""Download explícito de pesos públicos fixados; fora da classificação."""

import hashlib
from pathlib import Path
import urllib.request


def baixar_modelo(raiz: Path, config: dict) -> dict:
    pasta = raiz.resolve() / ".cache-modelos/e5-small"
    if pasta.is_symlink() or not pasta.resolve().is_relative_to(raiz.resolve()):
        raise ValueError("Pasta de pesos fora do projeto.")
    pasta.mkdir(parents=True, exist_ok=True)
    resultado = {}
    for nome, registro in config["arquivos"].items():
        if nome not in {"modelo.onnx", "tokenizer.json"}:
            raise ValueError("Nome de arquivo de pesos inesperado.")
        destino = pasta / nome
        if destino.is_symlink():
            raise ValueError("Arquivo de pesos não pode ser link.")
        if not destino.exists():
            temporario = pasta / (nome + ".download")
            url = (f"https://huggingface.co/{config['modelo']}/resolve/"
                   f"{config['revisao']}/{registro['caminho_remoto']}")
            if temporario.exists():
                raise ValueError("Download incompleto existente; preserve e investigue antes de retomar.")
            assinatura = hashlib.sha256()
            total = 0
            # Nenhum texto do case, credencial ou rótulo é enviado. Apenas GET
            # de arquivos públicos na revisão explicitamente fixada.
            with urllib.request.urlopen(url, timeout=60) as resposta, temporario.open("xb") as arquivo:
                while bloco := resposta.read(1024 * 1024):
                    assinatura.update(bloco)
                    total += len(bloco)
                    arquivo.write(bloco)
            if total != registro["bytes"] or assinatura.hexdigest() != registro["sha256"]:
                raise ValueError("Pesos baixados não correspondem ao hash/tamanho fixado.")
            temporario.rename(destino)
        with destino.open("rb") as arquivo:
            assinatura = hashlib.file_digest(arquivo, "sha256").hexdigest()
        if destino.stat().st_size != registro["bytes"] or assinatura != registro["sha256"]:
            raise ValueError("Pesos locais divergentes do modelo fixado.")
        resultado[nome] = {"bytes": destino.stat().st_size, "sha256": assinatura}
        print(f"Arquivo público verificado: {nome}", flush=True)
    return resultado
