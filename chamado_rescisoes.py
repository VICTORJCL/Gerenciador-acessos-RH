from html import escape
from typing import Sequence

from .acelerato import AceleratoAPI
from .fonte_rh import Rescindido

COLUNAS_DA_TABELA = ("Filial", "Nome", "CPF", "Função", "Data Rescisão")
TITULO = "Inativar acessos"
ABERTURA = "Bom dia"
PEDIDO = "Poderiam inativar os acessos abaixo."


def montar_titulo(rescindidos: Sequence[Rescindido]) -> str:
    return TITULO


def montar_descricao(rescindidos: Sequence[Rescindido]) -> str:
    # O campo descricao do Acelerato é renderizado como HTML.
    if not rescindidos:
        raise ValueError("Chamado de rescisão sem nenhum rescindido")

    cabecalho = "".join(f"<th>{escape(coluna)}</th>" for coluna in COLUNAS_DA_TABELA)
    linhas = "".join(
        "<tr>" + "".join(f"<td>{escape(celula)}</td>" for celula in rescindido.celulas) + "</tr>"
        for rescindido in rescindidos
    )
    return (
        f"<p>{ABERTURA}</p>"
        f"<p>{PEDIDO}</p>"
        f'<table border="1" cellpadding="4" cellspacing="0">'
        f"<thead><tr>{cabecalho}</tr></thead>"
        f"<tbody>{linhas}</tbody>"
        f"</table>"
    )


def abrir_chamado_de_rescisao(
    acelerato: AceleratoAPI,
    rescindidos: Sequence[Rescindido],
    chaves_dos_seguidores: Sequence[int] = (),
    categoria_key: int | None = None,
) -> int:
    return acelerato.abrir_chamado(
        titulo=montar_titulo(rescindidos),
        descricao=montar_descricao(rescindidos),
        chaves_dos_seguidores=chaves_dos_seguidores,
        categoria_key=categoria_key,
    )
