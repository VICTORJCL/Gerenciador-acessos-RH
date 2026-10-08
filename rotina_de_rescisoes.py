from dataclasses import dataclass, field
from typing import Sequence

from .acelerato import AceleratoAPI, ErroDoAcelerato, StatusChamado
from .chamado_rescisoes import abrir_chamado_de_rescisao, montar_titulo
from .fonte_rh import RepositorioDeRescindidos
from .repository import RepositorioDeChamados

TIPO = "rescisao"


@dataclass
class ResultadoDaRescisao:
    chamado_aberto: int | None = None
    rescindidos: int = 0
    ja_tinham_rescisao_pedida: int = 0
    seguidores: int = 0
    falhas: list[str] = field(default_factory=list)
    titulo: str = ""
    linhas: list[tuple[str, ...]] = field(default_factory=list)

    @property
    def abriu_chamado(self) -> bool:
        return self.chamado_aberto is not None


class RotinaDeRescisoes:
    def __init__(
        self,
        acelerato: AceleratoAPI,
        chamados: RepositorioDeChamados,
        rescindidos: RepositorioDeRescindidos,
        seguidores_fixos: Sequence[int] = (),
        categoria_key: int | None = None,
        dias_de_rescisao: int = 2,
        simular: bool = False,
    ):
        self._acelerato = acelerato
        self._chamados = chamados
        self._rescindidos = rescindidos
        self._seguidores_fixos = list(seguidores_fixos)
        self._categoria_key = categoria_key
        self._dias_de_rescisao = dias_de_rescisao
        self._simular = simular

    def executar(self) -> ResultadoDaRescisao:
        # Sem laço de acompanhamento: a RotinaDeAcessos já acompanha todos os
        # chamados da cham_admitidos, inclusive os de rescisão.
        resultado = ResultadoDaRescisao()

        encontrados = self._rescindidos.buscar_recentes(self._dias_de_rescisao)
        rescindidos = self._chamados.filtrar_sem_rescisao_pedida(encontrados)
        resultado.rescindidos = len(rescindidos)
        resultado.ja_tinham_rescisao_pedida = len(encontrados) - len(rescindidos)
        if not rescindidos:
            return resultado

        resultado.seguidores = len(self._seguidores_fixos)
        resultado.titulo = montar_titulo(rescindidos)
        resultado.linhas = [rescindido.celulas for rescindido in rescindidos]

        if self._simular:
            return resultado

        try:
            chamado_id = abrir_chamado_de_rescisao(
                self._acelerato,
                rescindidos,
                self._seguidores_fixos,
                self._categoria_key,
            )
        except ErroDoAcelerato as erro:
            resultado.falhas.append(f"Abertura do chamado de rescisão falhou: {erro}")
            return resultado

        self._chamados.salvar(chamado_id, StatusChamado.ABERTO, tipo=TIPO)
        self._chamados.registrar_rescisao_pedida(rescindidos, chamado_id)
        resultado.chamado_aberto = chamado_id
        return resultado


def criar_rotina_de_rescisoes(
    dias_de_rescisao: int = 2, simular: bool = False
) -> RotinaDeRescisoes:
    # `simular=True` faz tudo menos abrir chamado e gravar.
    from .acelerato import criar_cliente_acelerato
    from .models import db
    from .rotina_de_acessos import _chaves_dos_seguidores_fixos

    if db.is_closed():
        db.connect()

    acelerato = criar_cliente_acelerato()
    chamados = RepositorioDeChamados(db)
    chamados.garantir_tabelas()

    return RotinaDeRescisoes(
        acelerato=acelerato,
        chamados=chamados,
        rescindidos=RepositorioDeRescindidos(db),
        seguidores_fixos=_chaves_dos_seguidores_fixos(acelerato),
        categoria_key=acelerato.categoria_key_rescisao,
        dias_de_rescisao=dias_de_rescisao,
        simular=simular,
    )
