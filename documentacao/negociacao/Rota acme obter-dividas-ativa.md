# Rota `/acme/obter-dividas-ativa`

Documento especifico da rota que consulta as dividas ativas de um cliente e retorna os cedentes, contratos/acordos e dados basicos do cliente.

## Resumo

- Metodo: `GET`
- Endpoint: `/acme/obter-dividas-ativa`
- Controller: `src/presentation/controllers/collectsys.py`
- Funcao: `obter_dividas_ativa`
- Autenticacao: JWT Bearer via `@token_require("/acme")`
- Entrada: header `cpfCnpj`
- Retorno de sucesso: JSON com `status`, `cliente` e `dividas`

## Arquivos envolvidos

```text
src/presentation/controllers/collectsys.py
src/presentation/schemas/collectsys.py
src/domain/entities/documento.py
src/infrastructure/security/auth_decorator.py
src/infrastructure/repositories/sql_collectsys_repository.py
src/application/services/collectsys/negociacao_service.py
src/application/services/collectsys/cliente_service.py
src/infrastructure/external/collectsys/providers/obter_dividas.py
src/infrastructure/external/collectsys/providers/consultar_cliente.py
src/infrastructure/external/collectsys/providers/dados_usuario.py
src/domain/entities/contrato.py
src/shared/utils/xml_tratamentos.py
src/presentation/error/error_domain.py
src/presentation/error/error_collectsys.py
```

## Assinatura da rota

No arquivo `src/presentation/controllers/collectsys.py`:

```python
@bp.get("/obter-dividas-ativa")
@bp.arguments(ObterDividaAtivaSchema, location="headers")
@bp.response(200, ObterDividasResponse, description="Retorno das dividas do cliente")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def obter_dividas_ativa(body: ObterDividaAtivaSchema):
    log.info("obter_dividas_ativa iniciado cpfCnpj=%s", body.cpfCnpj)

    dividas: list[dict] = asyncio.run(DadosDivida.obter_cedentes(body.cpfCnpj))
    cliente = asyncio.run(ClienteService.dados_cliente(dividas))

    log.info("obter_dividas_ativa concluido idCliente=%s totalCedentes=%s", dividas, len(dividas))
    return jsonify({"status": True, "cliente": cliente, "dividas": dividas})
```

## Headers esperados

### `Authorization`

Token JWT no formato:

```text
Authorization: Bearer <token>
```

Esse token e validado pelo decorator `token_require("/acme")`.

### `cpfCnpj`

Documento do cliente.

Exemplo:

```text
cpfCnpj: 12345678909
```

Pode vir com pontuacao, porque o schema remove caracteres nao numericos antes de validar.

## Validacao do `cpfCnpj`

A validacao acontece em `ObterDividaAtivaSchema`, no arquivo `src/presentation/schemas/collectsys.py`.

Regra:

1. O campo `cpfCnpj` e obrigatorio.
2. O valor passa por `ValidacaoDocumento`.
3. Caracteres nao numericos sao removidos por `remove_caracteres`.
4. Se o documento ficar vazio, dispara `CpfCnpjInvalidoException("CPF/CNPJ e obrigatorio")`.
5. Se nao for CPF nem CNPJ valido, dispara `CpfCnpjInvalidoException("Documento invalido")`.
6. Se estiver valido, o schema retorna um `SimpleNamespace`, permitindo acesso como `body.cpfCnpj`.

Classe usada:

```text
src/domain/entities/documento.py -> ValidacaoDocumento
```

A validacao de CPF/CNPJ calcula os digitos verificadores e tambem rejeita sequencias repetidas.

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
3. Executa `verify_jwt_in_request()`.
4. Pega o id do usuario com `get_jwt_identity()`.
5. Pega os claims do token com `get_jwt()`.
6. Atualiza o contexto de log com usuario, rota, metodo e IP.
7. Verifica se `"/acme"` esta dentro de `rotas` no JWT.
8. Se a rota nao estiver permitida e o usuario nao for `id_usuario == 1`, dispara `TokenInvalido("Acesso negado a esta rota")`.
9. Como a rota permitida e `"/acme"`, busca as credenciais CollectSys do usuario.
10. Salva as credenciais no contexto Flask:

```python
g.collectsys = UsuarioCollectSys(resultado["USUARIO"], resultado["SENHA"])
```

Consulta usada para obter usuario CollectSys:

```text
src/infrastructure/repositories/sql_collectsys_repository.py
SqlCollectSysRepository(DB_66, "DB_DESENVOLVIMENTO").obter_usuario_collectsys(id_usuario)
```

Essas credenciais sao usadas depois nas chamadas SOAP para a CollectSys/EasyCollector.

## Fluxo principal

```text
Cliente HTTP
  |
  | GET /acme/obter-dividas-ativa
  | Headers: Authorization, cpfCnpj
  v
Flask / Blueprint Acme
  |
  v
ObterDividaAtivaSchema
  |
  | valida CPF/CNPJ
  v
token_require("/acme")
  |
  | valida JWT
  | valida permissao da rota
  | carrega g.collectsys
  v
obter_dividas_ativa()
  |
  | DadosDivida.obter_cedentes(cpfCnpj)
  v
Consulta CollectSys em paralelo
  |
  | ObterDivida("Cobrancas").consultar_por_cpf(cpfCnpj)
  | ObterDivida("Vega").consultar_por_cpf(cpfCnpj)
  v
Monta lista de cedentes, contratos e acordos
  |
  | ClienteService.dados_cliente(dividas)
  v
Consulta dados do cliente em paralelo
  |
  | ConsultarCliente("Cobrancas", id_cliente_cobranca)
  | ConsultarCliente("Vega", id_cliente_vega)
  v
JSON final
```

## Etapa 1: buscar cedentes e dividas

Metodo chamado:

```text
DadosDivida.obter_cedentes(cpf_cnpj)
```

Arquivo:

```text
src/application/services/collectsys/negociacao_service.py
```

### Consultas executadas

O metodo consulta dois servidores em paralelo usando `asyncio.gather` e `asyncio.to_thread`:

```python
divida_cobranca, divida_vega = await asyncio.gather(
    asyncio.to_thread(lambda: ObterDivida("Cobrancas").consultar_por_cpf(cpf_cnpj)),
    asyncio.to_thread(lambda: ObterDivida("Vega").consultar_por_cpf(cpf_cnpj))
)
```

Ou seja, a mesma consulta de divida ativa por CPF/CNPJ e feita em:

- servidor de cobranca;
- servidor da Vega.

### Provider usado

Arquivo:

```text
src/infrastructure/external/collectsys/providers/obter_dividas.py
```

Classe:

```python
class ObterDivida(DadosUsuario)
```

Metodo:

```python
consultar_por_cpf(cpf)
```

Esse metodo monta um envelope SOAP para a operacao:

```text
ObterDividaAtivaPorCPF
```

Campos enviados no SOAP:

- `logonUsuario`: usuario vindo de `g.collectsys`;
- `senhaUsuario`: senha vinda de `g.collectsys`;
- `cpfCnpj`: documento recebido no header.

### URL usada

A URL vem de `DadosUsuario.gerar_url_servidor()`.

Arquivo:

```text
src/infrastructure/external/collectsys/providers/dados_usuario.py
```

Regras:

- se o servidor for `vega` ou `vega financeira`, usa:

```text
http://10.0.0.18/easycollectorws/easycollectorWs.asmx?op=
```

- caso contrario, usa:

```text
http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op=
```

Depois o provider concatena a operacao SOAP no final da URL.

### Credenciais usadas na CollectSys

`DadosUsuario.usuario_cedente()` define o usuario e senha.

Para esta rota, como `ObterDivida("Cobrancas")` e `ObterDivida("Vega")` nao recebem `id_cedente`, a credencial usada normalmente vem de:

```python
g.collectsys
```

Esse `g.collectsys` foi carregado antes pelo decorator `token_require("/acme")`.

## Etapa 2: tratar ausencia de dividas

Depois das duas consultas, o metodo verifica as mensagens:

```text
Nenhum cliente localizado com este CPFCNPJ.
O cliente nao possui divida ativa.
```

Regra:

- se as duas respostas, cobranca e vega, indicarem uma dessas mensagens, a API dispara:

```python
NenhumaDividaException(
    "No momento, nao constam dividas ativas do cliente em nossa assessoria."
)
```

Tratamento:

```text
src/presentation/error/error_domain.py
```

Resposta retornada:

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

## Etapa 3: montar lista de cedentes

Se houver dividas em pelo menos uma das consultas, o codigo concatena os XMLs:

```python
dividas = divida_vega + divida_cobranca
```

Depois percorre cada bloco:

```text
<DividaAtiva>...</DividaAtiva>
```

Para cada bloco, extrai:

- `<NmCedente>` -> nome do cedente;
- `<IdCedente>` -> id do cedente;
- `<IdCliente>` -> id do cliente;
- `<TipoDivida>` -> indica se e divida normal ou acordo.

Utilitarios usados:

```text
src/shared/utils/xml_tratamentos.py
extrair_tag()
extrair_array()
```

### Agrupamento por cedente

A lista final e agrupada por `idCedente`.

Se ainda nao existir item para o cedente, cria:

```python
{
    "cedente": nome_cedente,
    "idCedente": id_cedente,
    "idCliente": id_cliente
}
```

Depois adiciona contratos ou acordos dentro desse mesmo item.

## Etapa 4: tratar acordos

Se `<TipoDivida>` contem `acordo`, a rota trata como acordo.

Regra:

1. Extrai `<IdAcordo>`.
2. Garante que a chave `"Acordos"` existe no cedente.
3. Evita duplicidade pelo `idAcordo`.
4. Consulta as faturas do acordo:

```python
DadosAcordo(nome_cedente, id_cliente, id_acordo).obter_faturas()
```

5. Monta um objeto de acordo usando:

```python
Contrato(resultado, nome_cedente, id_cedente, id_cliente).acordo(1)
```

6. Adiciona no cedente:

```python
{
    "grupo": contrato.nome_cedente,
    "idAcordo": contrato.id_acordo,
    "valor": contrato.valor,
    "dataPagamento": contrato.vencimento_boleto
}
```

Observacao:

- Nesta rota, para acordo, a funcao usa a parcela `1` ao chamar `acordo(1)`.
- A classe `Contrato.acordo()` extrai dados de `<Fatura>`, como valor da parcela, data de vencimento e situacao.

## Etapa 5: tratar contratos/dividas normais

Se `<TipoDivida>` nao contem `acordo`, a rota trata como divida normal.

Regra:

1. Cria um objeto `Divida` com:

```python
Contrato(divida, nome_cedente, id_cedente, id_cliente).divida()
```

2. Garante que a chave `"Contratos"` existe no cedente.
3. Evita duplicidade pelo `idContrato`.
4. Adiciona:

```python
{
    "idContrato": contrato.id_contrato,
    "grupo": contrato.nome_cedente
}
```

### Regras internas da classe `Contrato.divida()`

Arquivo:

```text
src/domain/entities/contrato.py
```

Ela extrai:

- `<IdContrato>`;
- `<NumeroPrestacao>`;
- `<Atraso>`.

Regras especificas:

- Se `id_cedente == 3`, ajusta o nome do grupo usando `Mu.grupo(self.xml)`.
- Se `id_cedente` for `65` ou `73`, ajusta XML com `Delta.selecionar_contratos(self.xml)`.
- Se houver valor e cedente for `81` ou `104`, mantem o valor.
- Se houver valor para outros cedentes, multiplica por `0.12`.
- Se nao houver valor, usa `0.0`.
- Encapsula o XML em `<ArrayOfDividaAtiva>...</ArrayOfDividaAtiva>`.

Nesta rota, o valor nao e passado no construtor `Contrato(...)`, entao normalmente a entidade `Divida` e criada com valor `0.0`. A rota usa essa entidade principalmente para extrair e normalizar identificadores de contrato/grupo.

## Etapa 6: consultar dados basicos do cliente

Depois de montar `dividas`, o controller chama:

```python
cliente = asyncio.run(ClienteService.dados_cliente(dividas))
```

Arquivo:

```text
src/application/services/collectsys/cliente_service.py
```

### Separacao entre Vega e cobranca

O service separa ids de cliente por origem:

- `ids_vega`: cedentes cujo nome contem `VEGA`;
- `ids_cobranca`: cedentes cujo nome nao contem `VEGA`.

Depois pega um id de cada conjunto:

```python
id_cliente_vega = next(iter(ids_vega), None)
id_cliente_cobranca = next(iter(ids_cobranca), None)
```

### Consulta do cliente

Executa em paralelo:

```python
cliente_cobranca, cliente_vega = await asyncio.gather(
    asyncio.to_thread(lambda: ConsultarCliente("Cobrancas", id_cliente_cobranca).consultar()),
    asyncio.to_thread(lambda: ConsultarCliente("Vega", id_cliente_vega).consultar())
)
```

Provider:

```text
src/infrastructure/external/collectsys/providers/consultar_cliente.py
```

Operacao SOAP:

```text
ConsultarCliente
```

Campos enviados:

- `logonUsuario`;
- `senhaUsuario`;
- `idCliente`.

### Escolha da resposta usada

Regra:

```python
dados = cliente_cobranca if id_cliente_cobranca else cliente_vega
```

Ou seja:

- se existir cliente de cobranca, ele e usado como fonte principal;
- se nao existir, usa o cliente da Vega.

### Cliente nao encontrado

Se `dados` estiver vazio, dispara:

```python
ClienteNaoEncontrado(mensagem="Cliente nao localizado.")
```

Essa exception herda de `CollectSysException`, entao e tratada por:

```text
src/presentation/error/error_collectsys.py
```

Resposta:

```json
{
  "status": false,
  "erro": "Cliente nao localizado."
}
```

Status HTTP:

```text
401
```

### Divergencia entre Vega e cobranca

Se houver cliente tanto em cobranca quanto em Vega:

1. Extrai o primeiro nome de cada XML:

```python
nome_cobranca = extrair_tag(cliente_cobranca, "<Nome>", "</Nome>").split()[0]
nome_vega = extrair_tag(cliente_vega, "<Nome>", "</Nome>").split()[0]
```

2. Normaliza os nomes com `normalizar_nome`.
3. Se os nomes forem diferentes, dispara:

```python
ClienteNaoEncontrado(mensagem="Divergencia de dados")
```

### Dados retornados do cliente

O service extrai:

- `<Nome>`: usa somente o primeiro nome;
- `<DataNascimento>`: remove `T00:00:00` e converte de `YYYY-MM-DD` para `DD/MM/YYYY`.

Retorno:

```python
{
    "nome": nome,
    "dataNascimento": data_nascimento
}
```

## Resposta de sucesso

Formato retornado pelo controller:

```json
{
  "status": true,
  "cliente": {
    "nome": "JOAO",
    "dataNascimento": "01/01/1980"
  },
  "dividas": [
    {
      "cedente": "NOME DO CEDENTE",
      "idCedente": 10,
      "idCliente": 123456,
      "Contratos": [
        {
          "idContrato": 999,
          "grupo": "NOME DO GRUPO"
        }
      ],
      "Acordos": [
        {
          "grupo": "NOME DO GRUPO",
          "idAcordo": 888,
          "valor": 100.0,
          "dataPagamento": "2026-05-20"
        }
      ]
    }
  ]
}
```

Observacoes:

- Um cedente pode ter apenas `Contratos`, apenas `Acordos`, ou ambos.
- `Contratos` e `Acordos` so aparecem quando existem itens daquele tipo.
- A lista e agrupada por `idCedente`.
- Contratos duplicados sao ignorados.
- Acordos duplicados sao ignorados.

## Erros e respostas tratadas

### CPF/CNPJ ausente ou invalido

Origem:

```text
ObterDividaAtivaSchema.validar_documento()
```

Exception:

```text
CpfCnpjInvalidoException
```

Resposta:

```json
{
  "status": false,
  "erro": "Documento invalido"
}
```

Status HTTP:

```text
401
```

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

### Nenhuma divida encontrada

Origem:

```text
DadosDivida.obter_cedentes()
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

### Cliente nao localizado ou divergente

Origem:

```text
ClienteService.dados_cliente()
```

Exception:

```text
ClienteNaoEncontrado
```

Resposta:

```json
{
  "status": false,
  "erro": "Cliente nao localizado."
}
```

ou:

```json
{
  "status": false,
  "erro": "Divergencia de dados"
}
```

Status HTTP:

```text
401
```

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
curl -X GET "http://localhost:8030/acme/obter-dividas-ativa" \
  -H "Authorization: Bearer <token>" \
  -H "cpfCnpj: 12345678909"
```

## Regras importantes da rota

- A rota consulta Cobrancas e Vega em paralelo.
- A rota considera que nao ha divida somente quando as duas origens retornam mensagem de cliente/divida inexistente.
- As credenciais da CollectSys nao vem diretamente da requisicao; elas sao carregadas a partir do usuario do JWT.
- O retorno de dividas e agrupado por cedente.
- A resposta nao detalha valores de todos os contratos. Ela lista os contratos e acordos encontrados por cedente.
- Dados detalhados de contrato ficam para outra rota: `/acme/verifica-divida-cedente`.
- O cliente retornado usa o primeiro nome e data de nascimento formatada.
- Quando ha dados em Vega e Cobrancas, o primeiro nome precisa bater apos normalizacao; caso contrario a API considera divergencia.

## Dependencias externas

- SQL Server:
  - busca credenciais CollectSys do usuario autenticado.
- CollectSys/EasyCollector SOAP:
  - `ObterDividaAtivaPorCPF`;
  - `ConsultarCliente`;
  - em caso de acordo, tambem consulta faturas do acordo via `DadosAcordo.obter_faturas()`.

## Observacao sobre performance

A rota usa `asyncio.gather` com `asyncio.to_thread` para paralelizar chamadas bloqueantes:

- consulta de dividas em Cobrancas e Vega;
- consulta de dados do cliente em Cobrancas e Vega.

Isso reduz o tempo total quando os dois servidores respondem em velocidades diferentes, mas as chamadas SOAP continuam sendo bloqueantes internamente porque usam `requests.post`.
