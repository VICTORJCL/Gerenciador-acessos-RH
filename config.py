from pathlib import Path

from dotenv import load_dotenv

PASTA_DO_PACOTE = Path(__file__).resolve().parent

# Ao lado do executar.py vem antes do .env do próprio pacote: assim o mesmo
# pacote serve instalado dentro de outro projeto e sozinho, clonado do GitHub.
CANDIDATOS = (PASTA_DO_PACOTE.parent / ".env", PASTA_DO_PACOTE / ".env")

_carregado = False


def carregar_ambiente(arquivo: Path | str | None = None) -> Path:
    """Carrega o .env uma vez e devolve o arquivo usado.

    Caminhos são resolvidos a partir do pacote, nunca do diretório de trabalho:
    o destino não pode mudar conforme de onde o programa é chamado.
    """
    global _carregado
    if arquivo is not None:
        escolhido = Path(arquivo).resolve()
        if not escolhido.is_file():
            raise FileNotFoundError(f"Arquivo de ambiente não encontrado: {escolhido}")
    else:
        escolhido = next((c for c in CANDIDATOS if c.is_file()), None)
        if escolhido is None:
            procurados = " ou ".join(str(c) for c in CANDIDATOS)
            raise FileNotFoundError(f"Nenhum .env encontrado em {procurados}")

    if not _carregado or arquivo is not None:
        load_dotenv(escolhido)
        _carregado = True
    return escolhido


def ler_banco(prefixo: str, alternativo: str = "") -> dict:
    """Parâmetros de conexão a partir do prefixo das variáveis.

    `alternativo` existe porque o rh_db nomeia o banco do RH como DB_*, e o
    pacote precisa funcionar tanto encaixado nele quanto sozinho.
    """
    import os

    def valor(campo: str) -> str | None:
        return os.getenv(f"{prefixo}_{campo}") or (
            os.getenv(f"{alternativo}_{campo}") if alternativo else None
        )

    faltando = [c for c in ("NAME", "USER", "PASSWORD", "HOST", "PORT") if not valor(c)]
    if faltando:
        nomes = ", ".join(f"{prefixo}_{c}" for c in faltando)
        raise RuntimeError(f"Variáveis ausentes no .env: {nomes}")

    return {
        "database": valor("NAME"),
        "user": valor("USER"),
        "password": valor("PASSWORD"),
        "host": valor("HOST"),
        "port": int(valor("PORT")),
    }
