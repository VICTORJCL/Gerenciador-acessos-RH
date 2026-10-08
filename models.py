from contextlib import contextmanager
from datetime import date

from peewee import (
    CharField,
    CompositeKey,
    DateField,
    IntegerField,
    Model,
    PostgresqlDatabase,
    TextField,
)

from .config import carregar_ambiente, ler_banco

carregar_ambiente()

db = PostgresqlDatabase(**ler_banco("RH_FONTE_DB", alternativo="DB"))

@contextmanager
def db_session():
    try:
        if db.is_closed():
            db.connect()
        yield db
    except Exception as e:
        print("Erro de conectar ao banco de dados :\n", e)
    finally:
        if not db.is_closed():
            db.close()





class BaseModel(Model):
    class Meta:
        database = db


class  TableChamado (BaseModel):
    chamado_aceletato_id = IntegerField(primary_key=True)
    data = DateField(default=date.today)
    status = TextField()
    # Admissão e rescisão dividem esta tabela porque o acompanhamento é o mesmo.
    tipo = CharField(max_length=20, default="admissao")

    class Meta:
        table_name =  'cham_admitidos'


class TableAcessoSolicitado(BaseModel):
    """Quem já teve acesso pedido, para não pedir duas vezes."""

    cpf = CharField(max_length=11)
    data_admissao = DateField()
    nome = CharField(max_length=120)
    chamado_aceletato_id = IntegerField()
    data = DateField(default=date.today)

    class Meta:
        table_name = "cham_admitidos_acesso"
        primary_key = CompositeKey("cpf", "data_admissao")


class TableRescisaoSolicitada(BaseModel):
    """Quem já teve inativação pedida, para não pedir duas vezes."""

    cpf = CharField(max_length=11)
    data_rescisao = DateField()
    nome = CharField(max_length=120)
    chamado_aceletato_id = IntegerField()
    data = DateField(default=date.today)

    class Meta:
        table_name = "cham_rescindidos_acesso"
        primary_key = CompositeKey("cpf", "data_rescisao")





def conectar_mpcore() -> PostgresqlDatabase:
    banco = PostgresqlDatabase(**ler_banco("MPCORE_DB"))
    banco.connect()
    return banco
