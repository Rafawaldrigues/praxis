# PRAXIS

Sistema de gestão processual para escritórios de advocacia — clientes, processos, agenda de prazos, avisos automáticos de movimentação e relatórios gerenciais.

## Stack

- **Backend/API**: Python, FastAPI, psycopg (PostgreSQL)
- **Front-end**: HTML/CSS/JS puro (sem framework, sem build step), Chart.js para os gráficos de relatório
- **Banco de dados**: PostgreSQL
- **Protótipo local**: Streamlit (`app.py`) — versão inicial, não é mais o que está em produção

## Estrutura

```
api/            → API FastAPI (main.py expõe os endpoints REST)
models/         → Classes de domínio (Cliente, Processo, Usuario, etc.)
repositories/   → Acesso ao banco (um repository por entidade)
database/       → Conexão com o Postgres
servicos/       → Integração com a API DataJud (CNJ) e detecção automática de tribunal
frontend/       → praxis_app.html — front-end completo, consome a API
DOCUMENTOS BANCO/ → Migrações SQL (rodar em ordem: schema base → v2 → v3)
app.py          → Protótipo Streamlit (legado, uso local)
```

## Rodando localmente

1. Copie `.env.example` para `.env` e preencha com as credenciais do seu banco.
2. Instale as dependências: `pip install -r requirements-api.txt --break-system-packages`
3. Rode as migrações em `DOCUMENTOS BANCO/` na ordem: `migracao_v1_schema_base.sql` → `migracao_v2.sql` → `migracao_v3.sql`
4. Suba a API: `uvicorn api.main:app --reload --port 8000`
5. Abra `frontend/praxis_app.html` no navegador (ou sirva com `python -m http.server`)

## Deploy

Roda em container Docker (`Dockerfile` na raiz), atrás de Traefik. Ver `docker-compose-trecho-owlex.yml` como referência do formato usado em produção — os nomes de serviço/domínio na VPS ainda usam o codinome técnico antigo (`owlex`) e serão migrados para `praxis` numa próxima etapa.
