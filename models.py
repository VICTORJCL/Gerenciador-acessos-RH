import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from peewee import (
    CharField,
    CompositeKey,
    DateField,
    IntegerField,
    Model,
    PostgresqlDatabase,
    TextField,
)



# Caminho fixo: `load_dotenv()` sem argumento procura a partir do diretório de
# trabalho, e com isso o banco mudava conforme de onde o programa fosse chamado.
ARQUIVO_DE_AMBIENTE = Path(__file__).parent / ".env"

load_dotenv(ARQUIVO_DE_AMBIENTE)

db = PostgresqlDatabase(
    database=os.getenv("RH_FONTE_DB_NAME"),
    user=os.getenv("RH_FONTE_DB_USER"),
    password=os.getenv("RH_FONTE_DB_PASSWORD"),
    host=os.getenv("RH_FONTE_DB_HOST"),
    port=int(os.getenv("RH_FONTE_DB_PORT")),
)

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
        




def conectar_mpcore() -> PostgresqlDatabase:
    banco = PostgresqlDatabase(
        database=os.getenv("MPCORE_DB_NAME"),
        user=os.getenv("MPCORE_DB_USER"),
        password=os.getenv("MPCORE_DB_PASSWORD"),
        host=os.getenv("MPCORE_DB_HOST"),
        port=int(os.getenv("MPCORE_DB_PORT")),
    )
    banco.connect()
    return banco
