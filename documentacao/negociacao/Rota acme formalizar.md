# Rota `/acme/formalizar`

Documento especifico da rota que formaliza um acordo na CollectSys/EasyCollector a partir de uma proposta informada pelo cliente.

## Resumo

- Metodo: `POST`
- Endpoint: `/acme/formalizar`
- Controller: `src/presentation/controllers/collectsys.py`
- Funcao: `formalizar`
- Autenticacao: JWT Bearer via `@token_require("/acme")`
- Entrada: JSON com dados da proposta
- Regra principal:
  - `NegociacaoDivida.proposta_cliente(..., gerar_acordo=True)`
  - `Formalizar.gerar(idCliente, xml_acordo, id_cedente)`
- Retorno de sucesso: JSON com `status` e `idAcordo`

## Arquivos envolvidos

```text
src/presentation/controllers/collectsys.py
src/presentation/schemas/collectsys.py
src/infrastructure/security/auth_decorator.py
src/infrastructure/repositories/sql_collectsys_repository.py
src/application/services/collectsys/negociacao_service.py
src/application/services/collectsys/formalizar_service.py
src/application/services/collectsys/valores_dividas_service.py
src/domain/entities/contrato.py
src/domain/entities/divida.py
src/domain/entities/cedentes.py
src/infrastructure/external/collectsys/providers/obter_dividas.py
src/infrastructure/external/collectsys/providers/calcular.py
src/infrastructure/external/collectsys/providers/confirmar_acordo.py
src/infrastructure/external/collectsys/providers/consulta_contrato_detalhe.py
src/shared/utils/xml_tratamentos.py
src/presentation/error/error_domain.py
src/presentation/error/error_collectsys.py
```

## Assinatura da rota

No arquivo `src/presentation/controllers/collectsys.py`:

```python
@bp.post("/formalizar")
@bp.arguments(PropostaDividaSchema, location="json")
@bp.response(200, FormalizarAcordoResponseSchema, description="Acordo formalizado com sucesso")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def formalizar(body: PropostaDividaSchema):
    log.info(
        "formalizar iniciado idCliente=%s idContrato=%s parcelamento=%s",
        body.idCliente,
        body.idContrato,
        body.parcelamento,
    )

    xml_acordo, id_cedente = asyncio.run(
        NegociacaoDivida.proposta_cliente(
            body.idCliente,
            body.idContrato,
            body.valorEntrada,
            body.parcelamento,
            body.dataPagamento,
            True,
        )
    )

    acordo = Formalizar.gerar(body.idCliente, xml_acordo, id_cedente)
    log.info("formalizar concluido idCliente=%s idAcordo=%s", body.idCliente, acordo)

    return jsonify({"status": True, "idAcordo": acordo}), 200
```

## Body esperado

Formato JSON:

```json
{
  "idCliente": 123456,
  "idContrato": 999999,
  "dataPagamento": "2026-05-20",
  "valorEntrada": 100.0,
  "parcelamento": 3
}
```

Campos:

- `idCliente`: id do cliente na CollectSys/EasyCollector.
- `idContrato`: id do contrato que sera negociado.
- `dataPagamento`: data da entrada/primeiro pagamento.
- `valorEntrada`: valor de entrada informado.
- `parcelamento`: quantidade de parcelas/plano.

## Validacao de entrada

A rota usa:

```text
src/presentation/schemas/collectsys.py -> PropostaDividaSchema
```

Existe uma observacao importante no arquivo atual: `PropostaDividaSchema` aparece definido duas vezes.

Primeira definicao:

```python
class PropostaDividaSchema(Schema):
    idCliente = fields.Integer(required=True)
    idContrato = fields.Integer(required=True)
    dataPagamento = fields.Date(required=True)
    valorEntrada = fields.Float(required=True)
    parcelamento = fields.Integer(required=True)
```

Segunda definicao, mais abaixo no mesmo arquivo:

```python
class PropostaDividaSchema(Schema):
    idCliente = fields.Integer()
    idContrato = fields.Integer()
    valorEntrada = fields.Float()
    parcelamento = fields.Integer()
    dataPagamento = fields.Date()
```

Em Python, a segunda definicao sobrescreve a primeira. Entao, no estado atual do arquivo, a rota usa a segunda classe. Na pratica:

- os campos existem no schema;
- mas nao aparecem como `required=True` na classe que fica valendo;
- se algum campo faltar, o controller pode quebrar ao acessar `body.idCliente`, `body.idContrato`, `body.valorEntrada`, `body.parcelamento` ou `body.dataPagamento`.

## Autenticacao e permissao

A rota usa:

```python
@token_require("/acme")
```

Arquivo:

```text
src/infrastructure/security/auth_decorator.py
```

Fluxo:

1. Busca o header `Authorization`.
2. Se nao existir, dispara `TokenInvalido("Token de autorizacao ausente")`.
3. Valida o JWT com `verify_jwt_in_request()`.
4. Le o id do usuario com `get_jwt_identity()`.
5. Le os claims com `get_jwt()`.
6. Atualiza o contexto de log.
7. Verifica se `"/acme"` esta no claim `rotas`.
8. Se nao estiver e o usuario nao for `id_usuario == 1`, dispara `TokenInvalido("Acesso negado a esta rota")`.
9. Busca credenciais CollectSys do usuario:

```text
SqlCollectSysRepository(DB_66, "DB_DESENVOLVIMENTO").obter_usuario_collectsys(id_usuario)
```

10. Salva no contexto Flask:

```python
g.collectsys = UsuarioCollectSys(resultado["USUARIO"], resultado["SENHA"])
```

Essas credenciais sao usadas nas chamadas SOAP de calculo e confirmacao do acordo.

## Fluxo principal

```text
Cliente HTTP
  |
  | POST /acme/formalizar
  | Authorization + JSON da proposta
  v
Flask / Blueprint Acme
  |
  v
PropostaDividaSchema
  |
  | valida/converte campos do JSON
  v
token_require("/acme")
  |
  | valida JWT
  | valida permissao
  | carrega g.collectsys
  v
formalizar()
  |
  | NegociacaoDivida.proposta_cliente(..., gerar_acordo=True)
  v
ObterDivida("COBRANCA").consultar_por_id(idCliente)
  |
  | localiza o idContrato e monta xml_divida
  v
Contrato(...).divida()
  |
  | aplica regras por cedente
  v
CalcularAcordo ou CalcularAcordoComDetalhe
  |
  | retorna XML com <Acordo>
  v
Formalizar.gerar(idCliente, xml_acordo, id_cedente)
  |
  | ConfirmarAcordo SOAP
  v
Retorna idAcordo
```

## Etapa 1: gerar o XML do acordo

O controller chama:

```python
xml_acordo, id_cedente = asyncio.run(
    NegociacaoDivida.proposta_cliente(
        body.idCliente,
        body.idContrato,
        body.valorEntrada,
        body.parcelamento,
        body.dataPagamento,
        True,
    )
)
```

Arquivo:

```text
src/application/services/collectsys/negociacao_service.py
```

O ultimo parametro e `gerar_acordo=True`. Essa e a diferenca principal entre `/formalizar` e `/proposta-divida`.

- Em `/proposta-divida`, `gerar_acordo=False`, a funcao retorna uma proposta formatada.
- Em `/formalizar`, `gerar_acordo=True`, a funcao retorna o XML `<Acordo>...</Acordo>` e o `id_cedente`.

## Etapa 2: consultar divida ativa por cliente

Dentro de `proposta_cliente`, a primeira chamada e:

```python
dividas = ObterDivida("COBRANCA").consultar_por_id(id_cliente)
```

Provider:

```text
src/infrastructure/external/collectsys/providers/obter_dividas.py
```

Operacao SOAP:

```text
ObterDividaAtiva
```

Campos enviados:

- `logonUsuario`: usuario carregado em `g.collectsys`;
- `senhaUsuario`: senha carregada em `g.collectsys`;
- `idCliente`: valor recebido no JSON.

Mensagens tratadas como ausencia de divida:

```text
Nenhum cliente localizado com este CPFCNPJ.
O cliente nao possui divida ativa.
Cliente nao localizado.
```

Se alguma aparecer, dispara:

```python
NenhumaDividaException(
    "No momento, nao constam dividas ativas do cliente em nossa assessoria."
)
```

## Etapa 3: localizar o contrato

Depois da consulta, o codigo extrai:

- `<NmCedente>` -> `nome_cedente`;
- `<IdCedente>` -> `id_cedente`.

Em seguida monta `xml_divida`.

### Cedentes `60` e `71`

Se `id_cedente in (60, 71)`, usa diretamente:

```text
<ArrayOfDividaAtiva>...</ArrayOfDividaAtiva>
```

### Demais cedentes

Percorre cada bloco:

```text
<DividaAtiva>...</DividaAtiva>
```

Para cada bloco:

1. Extrai `<IdContrato>`.
2. Compara com `idContrato` recebido no JSON.
3. Se for diferente, ignora.
4. Para cedentes `73`, `65`, `71` e `70`, verifica `<Atraso>`.
5. Se o atraso for menor que `0`, ignora o bloco.
6. Se passar nas regras, concatena o bloco em `xml_divida`.

Se `xml_divida` continuar vazio:

```python
raise NenhumaDividaException(
    "No momento, nao constam dividas ativas do cliente em nossa assessoria."
)
```

## Etapa 4: definir valor base

Regra:

```python
if id_cedente in (65, 73):
    valor_str = extrair_tag(xml_divida, "<ValorDividaIntegral>", "</ValorDividaIntegral>")
else:
    valor_str = "0.0"
```

Se `valor_str` estiver vazio, dispara `NenhumaDividaException`.

Depois:

```python
valor = float(valor_str)
```

## Etapa 5: criar entidade `Divida`

O contrato e criado assim:

```python
contrato = Contrato(xml_divida, nome_cedente, id_cedente, id_cliente, valor).divida()
```

Arquivo:

```text
src/domain/entities/contrato.py
```

Regras internas:

- Extrai `<IdContrato>`, `<NumeroPrestacao>` e `<Atraso>`.
- Cedente `3`: ajusta o grupo por `Mu.grupo(xml)`.
- Cedentes `65` e `73`: substitui `<Marcado>false</Marcado>` por `<Marcado>true</Marcado>`.
- Cedentes `81` e `104`: mantem o valor recebido.
- Outros cedentes com valor: aplica `round(valor * 0.12, 2)`.
- Sem valor: usa `0.0`.
- Encapsula o XML em `<ArrayOfDividaAtiva>...</ArrayOfDividaAtiva>`.

## Etapa 6: regras antes do calculo

Depois de criar `contrato`, a rota aplica regras por cedente.

### Cedentes `65` e `73`

Para esses cedentes:

```python
contrato.atualizar_valores(contrato.valor, 0, 0, plano)
```

Ou seja:

- usa o valor do contrato;
- zera `valor_parcelas`;
- zera `parcelamento_max`;
- usa `plano` igual ao `parcelamento` recebido no JSON.

### Banco Beta: cedentes `81` e `104`

Fluxo especifico:

1. Consulta nome do produto:

```python
nm_produto = ConsultaContratoDetalhe(id_cliente, id_contrato).consultar_nm_produto()
```

Provider:

```text
src/infrastructure/external/collectsys/providers/consulta_contrato_detalhe.py
```

Operacao SOAP:

```text
ConsultarContratoDetalhes
```

2. Extrai atraso:

```python
atraso = int(extrair_tag(xml_divida, "<Atraso>", "</Atraso>"))
```

3. Se for produto de cartao e atraso ate 35 dias:

```python
cartao_35 = "SIM"
```

Produto de cartao e definido por `BancoBeta.eh_produto_cartao(nome_produto)`:

- contem `CARTAO`;
- nao contem `RENEG`;
- nao contem `EMPRESTIMO`.

4. Cria `Calcular`.
5. Se for cartao ate 35 dias, exige plano entre 4 e 5 para formalizacao parcelada:

```python
if not 4 <= plano <= 5:
    raise NenhumaDividaException(
        "Plano nao disponivel para parcelamento de cartao. Plano minimo e de 4 e o maximo e 5"
    )
```

Observacao:

- A regra especial de proposta a vista original para cartao ate 35 dias so roda quando `gerar_acordo == False and plano == 1`.
- Como `/formalizar` chama `gerar_acordo=True`, esse atalho de boleto original nao e usado nesta rota.

6. Chama:

```python
calcular_acordo_com_detalhes(
    parcelado="VALOR ENTRADA PD",
    cartao_35=cartao_35,
)
```

7. O retorno esperado e uma tupla:

```text
(valor_min, valor_max, parcela_min, parcela_max, cartao_35)
```

8. Valida se o plano esta entre `parcela_min` e `parcela_max`.
9. Define o valor de entrada:

- se `valorEntrada` for `None` ou `0`, calcula com `BancoBeta.valor_entrada(...)`;
- se `cartao_35 == "SIM"`, soma `10.0` ao valor calculado;
- se o usuario informou valor, valida se esta entre `valor_min` e `valor_max`;
- se estiver fora, dispara `NenhumaDividaException`.

10. Atualiza:

```python
contrato.atualizar_valores(valor_entrada_tratado, 0, 0, plano)
```

### Demais cedentes

Para os demais:

```python
contrato.atualizar_valores(valor_entrada, 0, 0, plano)
```

Depois, para todos os fluxos:

```python
contrato.atualizar_data(data_vencimento)
```

## Etapa 7: calcular acordo

Depois das regras por cedente, escolhe a chamada de calculo.

### Cedentes sem calculo por detalhe

Se o cedente nao esta em `CEDENTES_CALCULO_DETALHE`, chama:

```python
Calcular(...).calcular_acordo()
```

Operacao SOAP:

```text
CalcularAcordo
```

Regras importantes:

- Cedente `3`: desconto `199`.
- Demais: desconto `100`.
- Se nao houver vencimento, usa hoje + 7 dias.
- Ajusta vencimento para dia util.
- Tenta tratar erros de data, desconto maximo e valor.
- Tenta ate 5 vezes.

### Cedentes com calculo por detalhe

Se o cedente esta em:

```text
(60, 65, 51, 73, 64, 70, 71, 83, 90, 81, 77, 103, 104)
```

chama:

```python
Calcular(...).calcular_acordo_com_detalhes(cartao_35=cartao_35)
```

Operacao SOAP:

```text
CalcularAcordoComDetalhe
```

Regras importantes:

- Usa `get_cedente_rule(id_cedente)` para montar o XML de detalhe.
- Monta um `CalculoContext` com plano, valor de entrada, data, XML da divida, detalhes e flags como `cartao_35`.
- Tenta ate 5 vezes.
- Pode recalcular conforme a regra especifica do cedente.
- Pode retornar erro tratado por `CollectSysException`, `RetornoTratadoBeta` ou `ErroFormalizarAcordo`.

## Etapa 8: validar retorno do calculo

Depois do calculo:

```python
if "<RetornoErro>" in resultado:
    if id_cedente in (81, 104) and BancoBeta.eh_erro_sem_parcelamento(resultado):
        raise NenhumaDividaException(BancoBeta.mensagem_parcelamento_indisponivel())
    raise CollectSysException(mensagem=resultado)
```

Regras adicionais:

- Se resultado contem `falha ao calcular divida` e cedente e Banco Beta, dispara `CollectSysException`.
- Se Banco Beta retorna erro reconhecido como sem parcelamento, dispara `NenhumaDividaException("Proposta nao disponivel para esse contrato")`.

## Etapa 9: extrair XML do acordo

Como `/formalizar` chama `gerar_acordo=True`, o final da funcao e:

```python
xml_acordo = extrair_array(resultado, "<Acordo>", "</Acordo>")
return xml_acordo, id_cedente
```

Ou seja, a primeira parte da rota nao confirma o acordo. Ela apenas calcula uma proposta e extrai o XML `<Acordo>...</Acordo>` que sera enviado para confirmacao.

Observacao tecnica:

- Se o retorno nao tiver `<Acordo>`, `xml_acordo` pode ficar `None`.
- A validacao explicita de `xml_acordo is None` nao aparece antes de chamar `Formalizar.gerar`.

## Etapa 10: confirmar/formalizar acordo

Depois que `proposta_cliente` retorna `xml_acordo` e `id_cedente`, o controller chama:

```python
acordo = Formalizar.gerar(body.idCliente, xml_acordo, id_cedente)
```

Arquivo:

```text
src/application/services/collectsys/formalizar_service.py
```

Implementacao:

```python
id_acordo = ConfirmarAcordo(id_cedente, id_cliente, xml).formalizar()
id_acordo = int(extrair_tag(id_acordo, "<ConfirmarAcordoResult>", "</ConfirmarAcordoResult>"))
return id_acordo
```

## Etapa 11: chamada SOAP `ConfirmarAcordo`

Provider:

```text
src/infrastructure/external/collectsys/providers/confirmar_acordo.py
```

Classe:

```python
ConfirmarAcordo(DadosUsuario)
```

Construtor:

```python
ConfirmarAcordo(id_cedente, id_cliente, xml_acordo)
```

Detalhe importante:

- `ConfirmarAcordo` chama `DadosUsuario("", id_cedente)`.
- Como passa `id_cedente`, `DadosUsuario.usuario_cedente()` pode trocar as credenciais para alguns cedentes especificos, como `73`, `65`, `71` e `70`.
- Para outros cedentes, usa `g.collectsys`.

Operacao SOAP:

```text
ConfirmarAcordo
```

Campos enviados:

- `logonUsuario`;
- `senhaUsuario`;
- `idCliente`;
- `acordoXml` dentro de `CDATA`.

Headers:

```text
content-type: application/soap+xml; charset=utf-8
```

Se o retorno contiver `<RetornoErro>`:

```python
raise ErroFormalizarAcordo(mensagem=resultado)
```

Se der certo, retorna o XML de resposta. `Formalizar.gerar()` extrai:

```text
<ConfirmarAcordoResult>...</ConfirmarAcordoResult>
```

e converte para inteiro.

## Resposta de sucesso

Formato:

```json
{
  "status": true,
  "idAcordo": 123456
}
```

Status HTTP:

```text
200
```

## Erros e respostas tratadas

### Body ausente ou campos ausentes

Origem:

```text
PropostaDividaSchema / controller
```

No estado atual, por existir duplicidade de `PropostaDividaSchema`, a classe efetiva nao marca os campos como obrigatorios. Se algum campo faltar, pode ocorrer erro no controller ao acessar os atributos do `body`.

### Token ausente, invalido ou sem permissao

Origem:

```text
token_require("/acme")
```

Exception:

```text
TokenInvalido
```

Resposta:

```json
{
  "status": false,
  "erro": "Acesso negado a esta rota"
}
```

Status HTTP:

```text
401
```

### Cliente, contrato ou divida nao encontrados

Origem:

```text
NegociacaoDivida.proposta_cliente()
```

Exception:

```text
NenhumaDividaException
```

Resposta:

```json
{
  "status": true,
  "msg": "No momento, nao constam dividas ativas do cliente em nossa assessoria."
}
```

Status HTTP:

```text
200
```

### Plano indisponivel para Banco Beta cartao

Origem:

```text
NegociacaoDivida.proposta_cliente()
```

Exemplo de mensagem:

```text
Plano nao disponivel para parcelamento de cartao. Plano minimo e de 4 e o maximo e 5
```

Como usa `NenhumaDividaException`, o handler retorna HTTP `200` com `status: true` e `msg`.

### Valor de entrada fora da faixa Banco Beta

Origem:

```text
NegociacaoDivida.proposta_cliente()
```

Mensagem:

```text
Valor de entrada deve ser entre X e Y
```

Tambem usa `NenhumaDividaException`, retornando HTTP `200` com `status: true` e `msg`.

### Erro no calculo CollectSys

Origem:

```text
Calcular.calcular_acordo()
Calcular.calcular_acordo_com_detalhes()
```

Exception:

```text
CollectSysException
```

Resposta:

```json
{
  "status": false,
  "erro": "mensagem tratada"
}
```

Status HTTP:

```text
401
```

### Erro ao confirmar acordo

Origem:

```text
ConfirmarAcordo.formalizar()
```

Exception:

```text
ErroFormalizarAcordo
```

Resposta:

```json
{
  "status": false,
  "erro": "mensagem"
}
```

Status HTTP:

```text
401
```

Observacao:

- O handler atual de `ErroFormalizarAcordo` retorna `str(e)`, nao `e.erro()`.

### Erro nao tratado

Qualquer exception nao mapeada cai no handler generico:

```text
src/presentation/error/error_http_v2.py
```

Resposta:

```json
{
  "error": "Erro interno no servidor",
  "code": 500
}
```

Status HTTP:

```text
500
```

## Exemplo de chamada

```bash
curl -X POST "http://localhost:8030/acme/formalizar" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{\"idCliente\":123456,\"idContrato\":999999,\"dataPagamento\":\"2026-05-20\",\"valorEntrada\":100.0,\"parcelamento\":3}"
```

## Regras importantes da rota

- A rota sempre consulta `ObterDivida("COBRANCA")`.
- O contrato e localizado por `idContrato`.
- Para cedentes `60` e `71`, o XML de divida e tratado pelo bloco `<ArrayOfDividaAtiva>`.
- Para cedentes `73`, `65`, `71` e `70`, parcelas com atraso menor que `0` sao ignoradas.
- Cedentes `65` e `73` usam `<ValorDividaIntegral>` como valor base.
- Cedentes `65` e `73` tambem marcam parcelas no XML trocando `<Marcado>false</Marcado>` por `<Marcado>true</Marcado>`.
- Cedentes em `CEDENTES_CALCULO_DETALHE` usam `CalcularAcordoComDetalhe`.
- Demais cedentes usam `CalcularAcordo`.
- Banco Beta (`81`, `104`) tem regra propria de produto, faixa de entrada e limite de parcelas.
- Banco Beta cartao ate 35 dias exige plano de 4 a 5 parcelas para formalizacao parcelada.
- A rota primeiro calcula um XML `<Acordo>` e depois confirma esse XML com `ConfirmarAcordo`.
- O id retornado ao cliente vem de `<ConfirmarAcordoResult>`.

## Dependencias externas

- SQL Server:
  - busca credenciais CollectSys do usuario autenticado;
  - pode buscar credenciais especificas por cedente em `DadosUsuario.usuario_cedente()`.
- CollectSys/EasyCollector SOAP:
  - `ObterDividaAtiva`;
  - `ConsultarContratoDetalhes`, para Banco Beta;
  - `CalcularAcordo`;
  - `CalcularAcordoComDetalhe`;
  - `ConfirmarAcordo`.

## Observacao sobre consistencia

A rota `/formalizar` depende diretamente da mesma regra usada por `/proposta-divida`. Para evitar divergencia entre a proposta exibida ao usuario e a formalizacao, o ideal e que os campos enviados para `/formalizar` sejam exatamente os escolhidos a partir da proposta retornada antes.
