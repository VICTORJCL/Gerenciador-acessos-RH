# RH — acessos para novos colaboradores

Abre um chamado no Acelerato pedindo à TI o cadastro do Cód Zanthus dos
colaboradores recém-admitidos, põe os gestores em cópia e acompanha o status até
a conclusão.

## Como usar

```python
from rotina_de_acessos import criar_rotina_de_acessos

resultado = criar_rotina_de_acessos().executar()
```

Ou direto pelo terminal:

```bash
python main.py
```

Não há agendamento embutido — quem decide quando rodar é de fora (cron,
botManager, outro job). O esperado é uma execução por dia.

As tabelas de controle são criadas na primeira execução, se não existirem, e
coluna acrescentada depois é aplicada na execução seguinte.

## O que uma execução faz

```
1. Acompanha os chamados em aberto
     concluído               -> grava `concluido` e para de acompanhar
     lixeira/arquivado/      -> grava `nao_encontrado` e para de acompanhar
       mesclado/spam/404
     erro de API             -> mantém em acompanhamento (erro não é conclusão)

2. Busca os admitidos dos últimos 2 dias
3. Descarta quem já teve acesso pedido
4. Resolve o gestor de cada admitido
5. Abre 1 chamado com todos, gestores em cópia
6. Grava o chamado e registra os CPFs atendidos
```

O acompanhamento roda **antes** da abertura, para não consultar um chamado que
acabou de ser criado.

### Por que 2 dias

Os dados do banco são D-1 e a execução é diária, então 2 dias cobrem o dia
anterior com um dia de folga. A janela não controla duplicata — isso é feito
pelo registro por pessoa. Ela controla só o alcance para trás.

Se o programa ficar dias sem rodar, quem foi admitido fora da janela não entra
em chamado nenhum. Para recuperar:

```python
criar_rotina_de_acessos(dias_de_admissao=5).executar()
```

### Por que não duplica

Cada admitido atendido fica registrado em `cham_admitidos_acesso` com a chave
`cpf + data_admissao`. Isso cobre três situações:

- rodar duas vezes no mesmo dia;
- admissão com data futura, que permanece na janela por vários dias;
- readmissão — o CPF repete, mas a data de admissão é outra, então o acesso é
  pedido de novo, corretamente.

## De onde vêm os dados

Tudo de banco ou de API. Nenhum arquivo de dados no projeto.

| Informação | Fonte |
|---|---|
| Admitidos recentes | banco `rh`: `mov_funcao` + `cad_funcionario` + `cad_funcao` |
| Chefia ativa da loja | banco `rh`: mesmas tabelas, filtrando cargos de chefia |
| Supervisor do admitido | banco `mpcore`: `rh_solicitacaovaga.supervisor`, ligado pelo CPF do candidato em `rh_candidato` / `rh_candidatovaga` |
| E-mail do gestor | banco `mpcore`: `auth_user` do solicitante da vaga |
| E-mail do gestor (fallback) | banco `mpcore`: `acessos_perfilacesso` com escopo `LOJA` |
| `usuarioKey` do seguidor | Acelerato: `GET /usuarios?email=` |

O banco `rh` é onde o programa do Quadro de Colaboradores grava o df de
colaboradores, então ele é esse df já persistido — por isso o programa não
depende da API Webfopag nem dos anexos de e-mail que alimentam aquele job.

### Cascata do gestor

Da fonte mais específica para a mais genérica:

1. Supervisor informado na vaga, resolvido para o nome completo pela chefia da loja.
2. Supervisor informado, sem resolver — o nome que o RH digitou vale para a tabela.
3. Gerente da loja, com o e-mail de quem solicitou a vaga.
4. Gerente da loja, com o e-mail do perfil de acesso da loja.

O e-mail do próprio gestor vem antes do e-mail de quem solicitou a vaga, porque
quem abre a vaga no MPCore às vezes é o RH e não a chefia da loja. Como só o
gerente tem perfil de acesso, na prática o supervisor cai no solicitante — que
nesses casos é o gerente da loja dele.

O e-mail nunca é deduzido do nome. Deduzir pelo padrão `nome.sobrenome@` foi
testado e errou 3 em 10 — há gestores com Gmail pessoal e outros em domínio
diferente.

O campo `supervisor` do MPCore é texto livre e quase sempre traz só o primeiro
nome, em caixa variada (`Ana`, `ana`, `ANA`). Primeiro nome + loja
resolve sem ambiguidade na prática.

## Tabelas de controle

Banco `rh`, criadas automaticamente.

**`cham_admitidos`** — os chamados e seus status

| Coluna | Tipo | |
|---|---|---|
| `chamado_aceletato_id` | integer | ticketKey do Acelerato (PK) |
| `data` | date | data de criação do chamado |
| `status` | text | `aberto`, `concluido` ou `nao_encontrado` |

**`cham_admitidos_acesso`** — quem já teve acesso pedido

| Coluna | Tipo | |
|---|---|---|
| `cpf` | varchar(11) | PK composta com `data_admissao` |
| `data_admissao` | date | PK composta com `cpf` |
| `nome` | varchar(120) | o nome que foi para o chamado |
| `chamado_aceletato_id` | integer | em qual chamado entrou |
| `data` | date | quando foi pedido |

O `nome` é cópia proposital, não espelho de `cad_funcionario`: deixa a tabela
legível sem join e registra o que a TI recebeu de fato, mesmo que o cadastro
seja corrigido depois.

## Módulos

| Arquivo | Responsabilidade |
|---|---|
| `main.py` | ponto de entrada |
| `rotina_de_acessos.py` | orquestra a execução e devolve o resultado |
| `fonte_rh.py` | leitura do banco `rh` (admitidos e chefia) |
| `fonte_mpcore.py` | leitura do banco `mpcore` (vagas e perfis de acesso) |
| `gestores.py` | decide quem é o gestor — lógica pura, sem banco |
| `chamado_acessos.py` | monta o título e a tabela HTML do chamado |
| `acelerato.py` | cliente da API do Acelerato |
| `models.py` | modelos peewee das tabelas de controle |
| `repository.py` | acesso às tabelas de controle |

Cada módulo de fonte lê um banco só. As dependências entram pelo construtor, e
quem lê o `.env` é a fábrica `criar_rotina_de_acessos()` — importar qualquer
módulo não abre conexão.

## Configuração

Variáveis no `.env`, ao lado dos módulos:

Copie o `.env.example` para `.env` e preencha. O `.env` não vai para o
repositório — está no `.gitignore`.

| Variável | |
|---|---|
| `ACELERATO_URL_BASE` | instância do Acelerato |
| `EMAIL_ACELERATO` / `TOKEN_ACELERATO` | conta e token da API |
| `ACELERATO_EMAIL_SOLICITANTE` | quem aparece como solicitante |
| `ACELERATO_CATEGORIA_KEY` | categoria do chamado; tem que ser folha |
| `ACELERATO_SEGUIDORES_FIXOS` | quem entra em cópia sempre, separado por vírgula |
| `RH_FONTE_DB_*` | banco do RH |
| `MPCORE_DB_*` | banco do MPCore |

## Particularidades da API do Acelerato

Coisas descobertas na integração que não estão óbvias na documentação:

- **Seguidor entra só por `usuarioKey`.** Mandar `{"email": ...}` em `seguidores`
  devolve `HTTP 500 "Erro desconhecido"`, mesmo para usuário existente. O
  `usuarioKey` é resolvido pelo e-mail com `GET /usuarios?email=`.
- **`GET /usuarios` precisa dos campos do filtro achatados na query.** Passar
  `filtro=` é silenciosamente ignorado: devolve sempre os mesmos 10 usuários.
- **O Acelerato já adiciona a conta da API e o solicitante como seguidores.**
  Repetir qualquer um dos dois também devolve 500, então o cliente descarta
  essas chaves antes de enviar.
- **Chamado inexistente devolve `404`.** Qualquer outro erro HTTP estoura
  `ErroDoAcelerato` e o chamado continua em acompanhamento: tratar erro de
  servidor como conclusão largaria um chamado que a TI nunca atendeu.
- **Sair de circulação não é só concluir.** A TI pode mandar o chamado para a
  lixeira, arquivar, mesclar num outro ou marcar como spam — `lixeira`,
  `arquivado`, `mesclado` e `alvoDeSpam`. Todos encerram o acompanhamento.
  `suspenso` e `impedido` não encerram: o chamado continua vivo, só travado.
- **`kanbanStatus.fim`** indica etapa final e é mais confiável que comparar
  `kanbanStatusKey == 15`, porque cada quadro numera suas próprias etapas.

## Limitações conhecidas

- Unidades sem perfil de acesso no MPCore saem sem gestor em cópia: **3**
  (ADM/CD), **5** (E-commerce), **18** (Salvados Fanny), **100** e **101**
  (Administrativo), **306** (ADM/CD ES). É cadastro faltando no MPCore, não
  código — criando o perfil, passa a funcionar sozinho.
- Loja sem gerente de loja ativo no banco `rh` sai sem supervisor na tabela.
- Gestor sem conta no Acelerato aparece na tabela do chamado, mas não entra em
  cópia.
