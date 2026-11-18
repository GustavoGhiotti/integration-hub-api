# Plano de Melhorias — API Sistema Acme

Documento de trabalho para priorizar e implementar melhorias na API, visando
**clean code**, boas práticas de Python e um **versionamento seguro** que respeite
o que já existe. Cada item é escrito como um card de backlog pronto para virar um
ticket Jira (KAN-xxx).

> **Como us ar:** revise as fases na ordem proposta. A ordem não é arbitrária — cada
> fase reduz o risco da seguinte. Marque `[x]` conforme concluir e crie o KAN
> correspondente na coluna *Ticket*.

---

## Legenda

**Prioridade**
- `P0` — Crítico / segurança. Fazer imediatamente, via `hotfix/`.
- `P1` — Alto. Estabilidade ou pré-requisito para o resto.
- `P2` — Médio. Dívida arquitetural / consolidação.
- `P3` — Baixo. Higiene e padronização incremental (contínuo).

**Esforço** (estimativa grosseira)
- `P` pequeno (< 0,5 dia) · `M` médio (1–3 dias) · `G` grande (> 3 dias, quebrar em subtarefas)

**Risco da mudança** = chance de quebrar algo em produção ao aplicar.

---

## Princípios que guiam o plano

1. **Segurança primeiro.** Segredo exposto e backdoor não esperam refactor.
2. **Rede de segurança antes de refatorar.** Sem testes, todo refactor grande é
   aposta. A Fase 1 existe para viabilizar as Fases 4–6 com segurança.
3. **Analisar antes de apagar.** Todo "código morto" listado aqui foi apontado por
   análise estática — confirme com `git log`/busca de referências antes de remover.
4. **Mudança pequena, PR pequeno, um KAN por assunto.** Facilita revisão e rollback.
5. **Boas práticas do repo já existentes** (auditoria/logging, gateway VCom, SQL
   parametrizado) viram o **padrão de referência** para o resto do código.

---

## Fase 0 — Fundações de segurança `P0`

> Branch: `hotfix/KAN-xxx-*` a partir de `main`, com merge de volta em `main` **e** `develop`.

- [ ] **SEC-1 — Remover `.env` do versionamento e rotacionar segredos** · `P0` · `M` · risco: médio
  - **Problema:** `.env` está rastreado no git e contém `DB_PASSWORD`, `JWT_SECRET`,
    `SENDGRID_API_KEY`, `INFOBIP_API_KEY`, `META_APP_SECRET`, `AD_PASS`,
    `SMTP_PASSWORD`, `BETA_BOLETO_IMAP_PASSWORD` etc. O histórico já contém os valores.
  - **Ação:**
    1. `git rm --cached .env` e adicionar `.env` ao `.gitignore`.
    2. Criar `.env.example` com as chaves (sem valores) como documentação.
    3. **Rotacionar TODOS os segredos expostos** (não basta apagar o arquivo — o
       histórico permanece). Trocar senha de banco, JWT_SECRET, API keys, secret Meta.
    4. Avaliar limpeza de histórico (`git filter-repo`) — coordenar com o time, pois
       reescreve o histórico compartilhado.
  - **Aceite:** `git ls-files | grep .env` retorna vazio; app sobe lendo do `.env` local;
    segredos antigos revogados.

- [ ] **SEC-2 — Remover backdoor de autorização do usuário DEV** · `P0` · `P` · risco: baixo
  - **Problema:** `auth_decorator.py:92` — `rota_permitida not in complementos["rotas"]
    and id_usuario != 1` concede acesso total ao usuário ID 1 em qualquer ambiente.
  - **Ação:** remover a exceção `id_usuario != 1`. Se precisar de perfil "admin",
    modelar como uma *rota/claim* explícita no token (ex.: `"*"` ou `"admin"` em `rotas`),
    não um ID hardcoded.
  - **Aceite:** nenhum ID de usuário concede bypass; admin (se necessário) autorizado por claim.

- [ ] **SEC-3 — Autenticar webhooks e a rota do EasyCollector** · `P0` · `M` · risco: médio
  - **Problema:** `/infobip/webhook`, `/sms/callback` e `/easycollector/status` não
    validam origem. O EasyCollector dispara automação de navegador e faz
    `shutil.rmtree(data)` no `finally` → acionável/DoS por qualquer um.
  - **Ação:** validar assinatura/segredo de cada provedor (Infobip signature, token
    compartilhado no EasyCollector). Espelhar o que já é feito no webhook Meta (HMAC +
    `hmac.compare_digest`).
  - **Aceite:** requisições sem assinatura válida → 401/403; webhook Meta segue de referência.

- [ ] **SEC-4 — Hash de senha e parar de expor objeto de usuário** · `P0` · `M` · risco: médio
  - **Problema:** `auth_service` compara senha em texto puro; `/api/mensagens/login`
    retorna `{**user, "token": ...}` (expõe campos internos, possível hash/senha).
  - **Ação:** adotar `argon2`/`bcrypt` (hash na criação, `verify` no login — migração
    gradual: rehash no próximo login bem-sucedido). Login retorna apenas
    `{token, nome, perfil}` — nunca o registro inteiro.
  - **Aceite:** senha nunca comparada/armazenada em claro; resposta de login sem PII/credenciais.

- [ ] **SEC-5 — Endurecer pontos menores** · `P1` · `P` · risco: baixo
  - `verify=False` nas chamadas SOAP CollectSys → habilitar TLS ou documentar exceção interna.
  - Senha de certificado em f-string no SQL (`sql_auth_token.py:11`) → parametrizar.
  - `/debug/headers` e log de lista de dívidas (PII) → remover/mascarar.
  - `/acme` usando `DB_DESENVOLVIMENTO` no caminho de auth → apontar para base correta por ambiente.

---

## Fase 1 — Rede de segurança: testes, lint e CI `P1` (enabler)

> Sem isso, as Fases 4–6 são arriscadas demais. Investir aqui **acelera** o resto.
> Branch: `chore/KAN-xxx-*`.

- [ ] **INFRA-1 — `pyproject.toml` + Ruff + formatador** · `P1` · `P` · risco: baixo
  - Adotar `ruff` (lint + format, substitui flake8/isort/black) com config em
    `pyproject.toml`. Rodar em modo *report-only* primeiro (não travar dev de imediato).
  - **Aceite:** `ruff check .` roda; regras acordadas com o time; sem reformatar tudo de uma vez.

- [ ] **INFRA-2 — Estrutura de testes com pytest** · `P1` · `M` · risco: baixo
  - Criar `tests/` + `conftest.py`. Começar pelos **utils puros e de alto risco**, que
    não dependem de I/O: `Documento`/`ValidacaoDocumento` (CPF/CNPJ), `data.py`,
    `ajusta_telefone.py`, `audit_sanitizer.py`, e o núcleo de `xml_tratamentos.py`.
  - **Aceite:** `pytest` verde; cobertura inicial mensurável nos módulos puros.

- [ ] **INFRA-3 — CI no GitHub Actions** · `P1` · `P` · risco: baixo
  - Workflow que roda `ruff check` + `pytest` em PRs para `develop`/`main`.
  - **Aceite:** PR mostra status de CI; merge bloqueado se quebrar (quando o time topar).

- [ ] **INFRA-4 — `pre-commit`** (opcional) · `P2` · `P`
  - Hooks de `ruff`/format/trailing-whitespace antes do commit local.

---

## Fase 2 — Correção de bugs em runtime `P1`

> Código que falha ou está morto por erro. Baixo risco de regressão (já não funciona).
> Branch: `bugfix/KAN-xxx-*`.

- [ ] **BUG-1 — `definir_strategy.py` (parcelamento) quebra no import** · `P1` · `P`
  - `NameError`: usa `CarteiraDefault()` sem importar → inutiliza `ParcelamentoMaximo`.
    Corrigir import ou remover a trilha se estiver morta (ver ARCH-2).
- [ ] **BUG-2 — `domain/strategies/carteiras/*` inteiro quebrado** · `P1` · `P`
  - `banco_beta_strategy` usa `Divida`/`Calcular` sem import; `RetornoCarteiraBase` é
    dataclass inválida; `retorno_carteira()` passa campos inexistentes. **Decidir:**
    corrigir ou remover (provável protótipo abandonado — ver ARCH-2).
- [ ] **BUG-3 — `users_service.time_left()` sempre lança `AttributeError`** · `P1` · `P`
  - `datetime.now(datetime.timezone.utc)` → usar `datetime.now(timezone.utc)` com import correto.
- [ ] **BUG-4 — `external/banco_beta/token.py` usa `self.token` antes de existir** · `P1` · `P`
  - Integração Banco Beta não funcional. Corrigir ordem de inicialização.
- [ ] **BUG-5 — `collectsys/providers/consulta_divida.py` chama `_post_soap` sem herdar a base** · `P1` · `P`
  - `AttributeError`. Resquício de refatoração incompleta (ver ARCH-3).
- [ ] **BUG-6 — Exceções semânticas e duplicadas** · `P2` · `P`
  - `login_user` levanta `xml.dom.NotFoundErr`; `collectsys_exception` define
    `CodigoPixException` 2× e tem typo `ParcelamentoExceptiom`.

---

## Fase 3 — Limpeza de código morto `P2`

> Baixo risco, alto ganho de legibilidade. Facilita as fases seguintes. **Confirmar
> ausência de referências antes de remover.** Branch: `chore/KAN-xxx-*`.

- [ ] **CLEAN-1 — Remover stubs/código comentado** · `P2` · `P`
  - `meta_service.py` (todo comentado), `banco_beta.py` (`BetaService: pass`),
    use_cases vazios (`formalizar_acordo_use_case`, `listar_propostas_parcelado_use_case`),
    `verificar_divida_cedente_use_case` (stub).
- [ ] **CLEAN-2 — Remover blueprints/handlers órfãos** · `P2` · `P`
  - `banco_beta_controller.py` e `chat_portalacordo.py` (nunca registrados);
    `error_http.py` (v1 duplicado, com `print`, não registrado — fica só o `error_http_v2`).
- [ ] **CLEAN-3 — Remover dead code pontual** · `P3` · `P`
  - `pesquisa_acionamento` chamando `pegar_filas()` e descartando; funções duplicadas
    com mesmo nome (`envio_boleto_whatsapp` em `digital.py`).
- [ ] **CLEAN-4 — Substituir `print()` por logger estruturado** · `P3` · `M`
  - `ad_controller`, `upload_arquivo`, `agendador`, sync Twilio, easycollector.
    Já existe `setup_logger` — usar o padrão de contexto de log que a auditoria usa.

---

## Fase 4 — Consolidação arquitetural `P2` (exige Fase 1)

> Aqui mora a maior dívida. **Só avançar com testes cobrindo o comportamento atual.**
> Branch: `feature/KAN-xxx-*`, PRs pequenos e incrementais.

- [ ] **ARCH-1 — Unificar as 3 implementações de `DadosDivida`** · `P2` · `G`
  - Existe em `obter_dividas_ativas_use_case`, `dados_divida_case` (quase idênticos) e
    `collectsys/negociacao_service`. Escolher a trilha de gateway/DTO como canônica e
    migrar o resto; remover os duplicados.
- [ ] **ARCH-2 — Consolidar o sistema de Strategy por cedente** · `P2` · `M`
  - Duplicado entre `domain/strategies/` (quebrado) e `external/collectsys/cedente_rules/`
    (o que roda). Manter **um** (recomendo `cedente_rules` como base, movendo a
    interface para o domínio se quiser respeitar a direção de dependência). Remover o outro.
- [ ] **ARCH-3 — Finalizar a migração CollectSys legado → `providers/`** · `P2` · `G`
  - Módulos legados na raiz de `collectsys/` coexistem com `collectsys/providers/`. Concluir a
    migração e **unificar o mapa cedente→usuário** (hoje duplicado e divergente entre
    `CollectSysCredentialsProvider` e `DadosUsuario` — fonte provável de bug).
- [ ] **ARCH-4 — Abstração comum acima de CollectSys × VCom** · `P2` · `G`
  - ~2.700 linhas de lógica de negociação reimplementadas por fonte. Extrair um contrato
    comum (proposta/parcelamento/tabular) acima do gateway; mesma ideia para
    Twilio × Infobip WhatsApp (mesma mecânica de template/número/controle de envio).
- [ ] **ARCH-5 — Quebrar as God classes** · `P2` · `G`
  - `NegociacaoDivida` (1.574 linhas) e `VcomNegociacaoService` (1.107) misturam
    parsing, regras por cedente, cálculo, I/O e formatação. Separar responsabilidades
    (parser / regras / cálculo / apresentação).
- [ ] **ARCH-6 — Reduzir fragilidade de `xml_tratamentos.py`** · `P2` · `G`
  - 545 linhas tratando XML por `find`/`replace` e regex sobre **mensagens de erro** do
    provedor. Isolar atrás de uma interface + parser real (`lxml`/`xml.etree`),
    blindar com testes (INFRA-2) antes de mexer.
- [ ] **ARCH-7 — Tirar regra de negócio do domínio/entidades** · `P3` · `M`
  - IDs mágicos de cedente e cálculos em `entities/contrato.py` e `entities/cedentes.py`;
    `domain/strategies/parcelamento/banco_beta_strategy` importando `infrastructure`/`application`
    (inverte a Clean Architecture). Centralizar IDs de cedente num enum/catálogo.

---

## Fase 5 — Robustez de infraestrutura `P2`

> Branch: `feature/KAN-xxx-*`.

- [ ] **INFRA-5 — Habilitar connection pooling no SQL Server** · `P2` · `M` · risco: médio
  - Hoje abre uma conexão pyodbc **por query**. Habilitar pooling (pyodbc/ODBC) ou
    reutilizar conexão por request. Medir antes/depois sob carga.
- [ ] **INFRA-6 — Dar persistência/erro à fila SMS** · `P2` · `M`
  - `config_queue.py` é `queue.Queue` em memória com `except: pass` → perde mensagens
    em crash. Avaliar persistência (tabela RAW como o consumidor SendGrid já faz) e
    tratar/logar erros em vez de engolir.
- [ ] **INFRA-7 — Externalizar IPs hardcoded** · `P3` · `P`
  - `10.0.0.x` espalhados (collectsys, `servers/`, `url_provider`). Mover para env/config.

---

## Fase 6 — Padronização e clean code contínuo `P3`

> Trabalho incremental, encaixar em cada PR que tocar a área ("regra do escoteiro").

- [ ] **STD-1 — Um mecanismo de autenticação.** Hoje: JWT, token SQL, Basic e guard
  manual convivem. Definir um padrão e migrar aos poucos.
- [ ] **STD-2 — Uma abordagem de validação.** Padronizar em marshmallow via
  `flask-smorest` (`@bp.arguments`); aposentar `validate_input` e os `.get` crus.
- [ ] **STD-3 — Códigos HTTP corretos.** Erros de negócio hoje retornam 401; usar
  400/422 para validação, 200 só para sucesso. Revisar `error_collectsys.py`.
- [ ] **STD-4 — Type hints + docstrings** nos módulos centrais; `mypy` opcional depois.
- [ ] **STD-5 — Padronizar idioma** (PT/EN misturados) e nomenclatura de módulos/DTOs.

---

## Ordem de execução recomendada

```
Fase 0 (segurança)  ──►  Fase 1 (rede de segurança)  ──►  Fase 2 (bugs)
                                                              │
                                                              ▼
        Fase 3 (limpeza)  ──►  Fase 4 (arquitetura)  ◄──  depende de testes
                                     │
                                     ▼
                          Fase 5 (infra) + Fase 6 (padronização contínua)
```

**Sprint sugerida para começar:** SEC-1, SEC-2, SEC-3, SEC-4 (Fase 0 inteira) +
INFRA-1 e INFRA-2 (começar a rede de segurança). Isso fecha o buraco de segurança e
já cria o terreno para refatorar com confiança.

---

## Convenções de versionamento (mantendo o padrão do repo)

- **Git-flow já em uso:** `main` (produção) · `develop` (integração) ·
  `feature/KAN-*` · `bugfix/KAN-*` · `chore/KAN-*` · `hotfix/KAN-*`.
- **Segurança (Fase 0):** `hotfix/` a partir de `main`, merge em `main` **e** `develop`.
- **Demais fases:** branch a partir de `develop`, PR para `develop`.
- **Commits (conventional + Jira), como já feito:**
  `KAN-XXX tipo(escopo): descrição` — ex.: `KAN-350 fix(auth): remove bypass do usuario DEV`.
- **Um KAN por card deste plano.** PRs pequenos, com critério de aceite no corpo.
- **Antes de remover código:** buscar referências (`grep`/IDE) e checar `git log` do
  arquivo — este plano aponta candidatos, a confirmação é sua.

---

## Métricas de sucesso

- Zero segredos no versionamento; segredos rotacionados.
- Nenhum bypass de auth por ID/hardcode.
- `pytest` + `ruff` rodando em CI a cada PR.
- Redução mensurável de duplicação (3×`DadosDivida` → 1; um sistema de Strategy;
  CollectSys sem módulos legados paralelos).
- Nenhum `print()` de debug em produção.
