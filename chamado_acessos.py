from dataclasses import replace
from html import escape
from typing import Mapping, Sequence

from .acelerato import AceleratoAPI
from .fonte_rh import Admitido
from .gestores import Gestor

COLUNAS_DA_TABELA = ("Filial", "Nome", "CPF", "Função", "Data Admissão", "Supervisor")
ABERTURA = "Bom dia"
PEDIDO = "Segue os colaboradores abaixo para cadastro do Cód Zanthus."
AVISO_DE_COPIA = "Enviar para os gerentes que estão em cópia."
PEDIDO_DE_CONFERENCIA = (
    "Favor conferir os gestores em cópia e acrescentar quem estiver faltando."
)


def montar_titulo(admitidos: Sequence[Admitido]) -> str:
    return f"Cadastro de Cód Zanthus — {len(admitidos)} admitido(s)"


def montar_descricao(admitidos: Sequence[Admitido]) -> str:
    # O campo descricao do Acelerato é renderizado como HTML.
    if not admitidos:
        raise ValueError("Chamado de acessos sem nenhum admitido")

    cabecalho = "".join(f"<th>{escape(coluna)}</th>" for coluna in COLUNAS_DA_TABELA)
    linhas = "".join(
        "<tr>" + "".join(f"<td>{escape(celula)}</td>" for celula in admitido.celulas) + "</tr>"
        for admitido in admitidos
    )
    return (
        f"<p>{ABERTURA}</p>"
        f"<p>{PEDIDO}</p>"
        f"<p>{AVISO_DE_COPIA}</p>"
        f"<p>{PEDIDO_DE_CONFERENCIA}</p>"
        f'<table border="1" cellpadding="4" cellspacing="0">'
        f"<thead><tr>{cabecalho}</tr></thead>"
        f"<tbody>{linhas}</tbody>"
        f"</table>"
    )


def aplicar_gestores(
    admitidos: Sequence[Admitido],
    gestores_por_cpf: Mapping[str, Gestor],
) -> tuple[list[Admitido], list[int]]:
    # Gestor sem conta no Acelerato aparece na tabela, não entra como seguidor.
    preenchidos, chaves = [], []
    for admitido in admitidos:
        gestor = gestores_por_cpf.get(admitido.cpf)
        if gestor is None:
            preenchidos.append(admitido)
            continue
        preenchidos.append(replace(admitido, supervisor=gestor.nome))
        if gestor.chave_no_acelerato and gestor.chave_no_acelerato not in chaves:
            chaves.append(gestor.chave_no_acelerato)
    return preenchidos, chaves


def abrir_chamado_de_acessos(
    acelerato: AceleratoAPI,
    admitidos: Sequence[Admitido],
    chaves_dos_supervisores: Sequence[int] = (),
) -> int:
    return acelerato.abrir_chamado(
        titulo=montar_titulo(admitidos),
        descricao=montar_descricao(admitidos),
        chaves_dos_seguidores=chaves_dos_supervisores,
    )
