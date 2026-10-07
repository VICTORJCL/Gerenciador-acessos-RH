from dataclasses import dataclass, field
from typing import Sequence

from .acelerato import AceleratoAPI, ErroDoAcelerato, StatusChamado
from .fonte_mpcore import RepositorioDeEmailsDaLoja, RepositorioDeVagas
from .chamado_acessos import abrir_chamado_de_acessos, aplicar_gestores, montar_titulo
from .fonte_rh import RepositorioDeAdmitidos, RepositorioDeChefia
from .gestores import resolver_gestor
from .repository import RepositorioDeChamados


@dataclass
class ResultadoDaRotina:
    chamado_aberto: int | None = None
    admitidos: int = 0
    ja_tinham_acesso_pedido: int = 0
    seguidores: int = 0
    gestores_sem_acesso_ao_acelerato: list[str] = field(default_factory=list)
    chamados_acompanhados: int = 0
    chamados_concluidos: list[int] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    titulo: str = ""
    linhas: list[tuple[str, ...]] = field(default_factory=list)

    @property
    def abriu_chamado(self) -> bool:
        return self.chamado_aberto is not None


class RotinaDeAcessos:
    def __init__(
        self,
        acelerato: AceleratoAPI,
        chamados: RepositorioDeChamados,
        admitidos: RepositorioDeAdmitidos,
        chefia: RepositorioDeChefia,
        vagas: "RepositorioDeVagas",
        emails_da_loja: RepositorioDeEmailsDaLoja,
        seguidores_fixos: Sequence[int] = (),
        dias_de_admissao: int = 2,
        simular: bool = False,
    ):
        self._acelerato = acelerato
        self._chamados = chamados
        self._admitidos = admitidos
        self._chefia = chefia
        self._vagas = vagas
        self._emails_da_loja = emails_da_loja
        self._seguidores_fixos = list(seguidores_fixos)
        self._simular = simular
        self._dias_de_admissao = dias_de_admissao

    def executar(self) -> ResultadoDaRotina:
        resultado = ResultadoDaRotina()
        self._acompanhar_chamados_abertos(resultado)
        self._abrir_chamado_dos_admitidos(resultado)
        return resultado

    def _abrir_chamado_dos_admitidos(self, resultado: ResultadoDaRotina) -> None:
        encontrados = self._admitidos.buscar_recentes(self._dias_de_admissao)
        admitidos = self._chamados.filtrar_sem_acesso_pedido(encontrados)
        resultado.admitidos = len(admitidos)
        resultado.ja_tinham_acesso_pedido = len(encontrados) - len(admitidos)
        if not admitidos:
            return

        gestores = self._resolver_gestores(admitidos)
        admitidos, chaves = aplicar_gestores(admitidos, gestores)
        # O RH acompanha todo chamado, independente de quem são os gestores.
        chaves = chaves + [c for c in self._seguidores_fixos if c not in chaves]
        resultado.seguidores = len(chaves)
        resultado.gestores_sem_acesso_ao_acelerato = sorted(
            {g.nome for g in gestores.values() if not g.chave_no_acelerato}
        )

        resultado.titulo = montar_titulo(admitidos)
        resultado.linhas = [admitido.celulas for admitido in admitidos]

        if self._simular:
            return

        try:
            chamado_id = abrir_chamado_de_acessos(self._acelerato, admitidos, chaves)
        except ErroDoAcelerato as erro:
            resultado.falhas.append(f"Abertura do chamado falhou: {erro}")
            return

        self._chamados.salvar(chamado_id, StatusChamado.ABERTO)
        self._chamados.registrar_acesso_pedido(admitidos, chamado_id)
        resultado.chamado_aberto = chamado_id

    def _resolver_gestores(self, admitidos) -> dict:
        lojas = [a.loja for a in admitidos]
        vagas = self._vagas.buscar_por_cpf([a.cpf for a in admitidos])
        chefia = self._chefia.buscar_por_loja(lojas)
        emails = self._emails_da_loja.buscar_por_loja(lojas)

        gestores = {}
        for admitido in admitidos:
            gestor = resolver_gestor(
                admitido.loja,
                vagas.get(admitido.cpf),
                chefia.get(admitido.loja, []),
                emails.get(admitido.loja, []),
                self._acelerato.buscar_chave_do_usuario,
            )
            if gestor is not None:
                gestores[admitido.cpf] = gestor
        return gestores

    def _acompanhar_chamados_abertos(self, resultado: ResultadoDaRotina) -> None:
        if self._simular:
            resultado.chamados_acompanhados = len(self._chamados.listar_em_acompanhamento())
            return

        for chamado_id in self._chamados.listar_em_acompanhamento():
            resultado.chamados_acompanhados += 1
            try:
                chamado = self._acelerato.consultar_chamado(chamado_id)
            except ErroDoAcelerato as erro:
                # Segue em acompanhamento: erro de API não é conclusão.
                resultado.falhas.append(f"Consulta do chamado {chamado_id} falhou: {erro}")
                continue

            if not chamado.acompanhamento_encerrado:
                continue

            self._chamados.atualizar_status(chamado_id, chamado.status)
            resultado.chamados_concluidos.append(chamado_id)


def criar_rotina_de_acessos(dias_de_admissao: int = 2, simular: bool = False) -> RotinaDeAcessos:
    # `simular=True` faz tudo menos abrir chamado e gravar.
    from .acelerato import criar_cliente_acelerato
    from .models import conectar_mpcore, db

    if db.is_closed():
        db.connect()

    acelerato = criar_cliente_acelerato()
    chamados = RepositorioDeChamados(db)
    chamados.garantir_tabelas()
    mpcore = conectar_mpcore()

    return RotinaDeAcessos(
        acelerato=acelerato,
        chamados=chamados,
        admitidos=RepositorioDeAdmitidos(db),
        chefia=RepositorioDeChefia(db),
        vagas=RepositorioDeVagas(mpcore),
        emails_da_loja=RepositorioDeEmailsDaLoja(mpcore),
        seguidores_fixos=_chaves_dos_seguidores_fixos(acelerato),
        simular=simular,
        dias_de_admissao=dias_de_admissao,
    )


def _chaves_dos_seguidores_fixos(acelerato) -> list[int]:
    # Quem não tem conta no Acelerato é descartado, senão a API recusa o chamado.
    import os

    brutos = os.getenv("ACELERATO_SEGUIDORES_FIXOS", "")
    emails = [parte.strip() for parte in brutos.split(",") if parte.strip()]
    chaves = [acelerato.buscar_chave_do_usuario(email) for email in emails]
    return [chave for chave in chaves if chave]
