from datetime import date

from typing import Iterable, Sequence

from .acelerato import StatusChamado
from .fonte_rh import Admitido, Rescindido
from .models import (
    TableAcessoSolicitado,
    TableChamado,
    TableRescisaoSolicitada,
)


class RepositorioDeChamados:
    def __init__(self, banco):
        self._banco = banco

    def garantir_tabelas(self) -> None:
        # `CREATE TABLE IF NOT EXISTS` não mexe em tabela que já existe, por
        # isso as colunas são conferidas à parte.
        modelos = [TableChamado, TableAcessoSolicitado, TableRescisaoSolicitada]
        self._banco.create_tables(modelos, safe=True)
        for modelo in modelos:
            self._acrescentar_colunas_faltantes(modelo)

    def _acrescentar_colunas_faltantes(self, modelo) -> None:
        tabela = modelo._meta.table_name
        existentes = {coluna.name for coluna in self._banco.get_columns(tabela)}
        for nome, campo in modelo._meta.fields.items():
            if campo.column_name in existentes:
                continue
            tipo = campo.ddl_datatype(self._banco.get_sql_context()).sql
            self._banco.execute_sql(
                f'ALTER TABLE "{tabela}" ADD COLUMN "{campo.column_name}" {tipo}'
            )
            # O default do peewee é da aplicação, não do banco: sem isto as
            # linhas que já existiam ficariam nulas na coluna nova.
            if campo.default is not None and not callable(campo.default):
                self._banco.execute_sql(
                    f'UPDATE "{tabela}" SET "{campo.column_name}" = %s '
                    f'WHERE "{campo.column_name}" IS NULL',
                    (campo.default,),
                )

    def salvar(
        self,
        chamado_id: int,
        status: StatusChamado,
        data: date | None = None,
        tipo: str = "admissao",
    ) -> None:
        TableChamado.insert(
            chamado_aceletato_id=chamado_id,
            data=data or date.today(),
            status=status.value,
            tipo=tipo,
        ).on_conflict(
            conflict_target=[TableChamado.chamado_aceletato_id],
            update={TableChamado.status: status.value},
        ).execute()

    def listar_em_acompanhamento(self) -> list[int]:
        registros = TableChamado.select(TableChamado.chamado_aceletato_id).where(
            TableChamado.status == StatusChamado.ABERTO.value
        )
        return [registro.chamado_aceletato_id for registro in registros]

    def atualizar_status(self, chamado_id: int, status: StatusChamado) -> None:
        TableChamado.update(status=status.value).where(
            TableChamado.chamado_aceletato_id == chamado_id
        ).execute()

    def filtrar_sem_acesso_pedido(self, admitidos: Sequence[Admitido]) -> list[Admitido]:
        # A dupla cpf + data_admissao, e não a data do chamado, é o que cobre
        # rodar duas vezes no dia, pular um dia e admissão com data futura.
        if not admitidos:
            return []

        chaves = {(admitido.cpf, admitido.data_admissao) for admitido in admitidos}
        ja_pedidos = {
            (registro.cpf, registro.data_admissao)
            for registro in TableAcessoSolicitado.select().where(
                TableAcessoSolicitado.cpf.in_([cpf for cpf, _ in chaves])
            )
        }
        return [
            admitido
            for admitido in admitidos
            if (admitido.cpf, admitido.data_admissao) not in ja_pedidos
        ]

    def registrar_acesso_pedido(
        self, admitidos: Iterable[Admitido], chamado_id: int
    ) -> None:
        TableAcessoSolicitado.insert_many(
            [
                {
                    "cpf": admitido.cpf,
                    "data_admissao": admitido.data_admissao,
                    "nome": admitido.nome.title(),
                    "chamado_aceletato_id": chamado_id,
                }
                for admitido in admitidos
            ]
        ).on_conflict_ignore().execute()

    def filtrar_sem_rescisao_pedida(
        self, rescindidos: Sequence[Rescindido]
    ) -> list[Rescindido]:
        if not rescindidos:
            return []

        chaves = {(r.cpf, r.data_rescisao) for r in rescindidos}
        ja_pedidos = {
            (registro.cpf, registro.data_rescisao)
            for registro in TableRescisaoSolicitada.select().where(
                TableRescisaoSolicitada.cpf.in_([cpf for cpf, _ in chaves])
            )
        }
        return [
            rescindido
            for rescindido in rescindidos
            if (rescindido.cpf, rescindido.data_rescisao) not in ja_pedidos
        ]

    def registrar_rescisao_pedida(
        self, rescindidos: Iterable[Rescindido], chamado_id: int
    ) -> None:
        TableRescisaoSolicitada.insert_many(
            [
                {
                    "cpf": rescindido.cpf,
                    "data_rescisao": rescindido.data_rescisao,
                    "nome": rescindido.nome.title(),
                    "chamado_aceletato_id": chamado_id,
                }
                for rescindido in rescindidos
            ]
        ).on_conflict_ignore().execute()
