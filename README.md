# DealFlow Agent

Production-grade multi-agent AI system for commercial real estate investment analysis. Upload a deal PDF, get a structured investment memo with citations, risk scores, and full LangSmith observability.

---

## Architecture

```mermaid
graph TD
    Browser["Browser\n(React + Vite)"]
    API["FastAPI\nPOST /analyze\nGET /status/:id\nGET /result/:id"]
    Supervisor["LangGraph Supervisor\npure Python router"]
    DA["DocumentAnalystAgent\nClaude tool_use\nextracts deal metrics"]
    MR["MarketResearchAgent\nTavily web search\nmarket comps"]
    RA["RiskAnalystAgent\nClaude tool_use\n5-dimension scoring"]
    MW["MemoWriterAgent\nClaude tool_use\nfull IC memo"]
    MCP["FastMCP Server\nquery_deal_knowledge_base"]
    PG["PostgreSQL 16\npgvector"]
    LS["LangSmith\ntracing + latency"]

    Browser -->|"PDF upload\npoll status\nfetch result"| API
    API -->|"BackgroundTask\nainvoke()"| Supervisor
    Supervisor -->|"deal_metrics is None"| DA
    Supervisor -->|"market_data is None"| MR
    Supervisor -->|"risk_scores is None"| RA
    Supervisor -->|"memo_draft is None"| MW
    DA & MR & RA & MW -->|"state update"| Supervisor
    MR -->|"similarity search"| MCP
    MCP --> PG
    Supervisor -.->|"@traceable\nRunnableConfig"| LS
```

### LangGraph State Machine

```mermaid
stateDiagram-v2
    [*] --> supervisor
    supervisor --> document_analyst : deal_metrics is None
    supervisor --> market_research : market_data is None
    supervisor --> risk_analyst : risk_scores is None
    supervisor --> memo_writer : memo_draft is None
    supervisor --> [*] : all fields populated OR error set
    document_analyst --> supervisor
    market_research --> supervisor
    risk_analyst --> supervisor
    memo_writer --> supervisor
```

---

## Agent Design

| Agent | Model | Technique | Output | Tokens (typical) |
|-------|-------|-----------|--------|-----------------|
| **DocumentAnalyst** | Claude Sonnet 4 | `tool_choice: {type: "tool"}` forced JSON | `deal_metrics` dict (NOI, cap rate, DSCR, LTV, vacancy, …) | ~1 200 |
| **MarketResearch** | Claude Sonnet 4 + Tavily | Web search → Claude synthesis | `market_data` dict (vacancy, rent growth, comps, macro) | ~2 500 |
| **RiskAnalyst** | Claude Sonnet 4 | `tool_choice: {type: "tool"}` forced JSON | `risk_scores` dict (5 dimensions, 1–5 scale, flags) | ~1 800 |
| **MemoWriter** | Claude Sonnet 4 | `tool_choice: {type: "tool"}` forced JSON | Full IC memo (executive summary, property overview, financial summary, market context, risk assessment, recommendation, citations) | ~3 200 |

Token totals accumulate via LangGraph's `Annotated[int, operator.add]` reducer — each agent returns `{"total_tokens_used": N}` and the graph sums them automatically.

---

## Quick Start

### Prerequisites

- Docker + Docker Compose
- API keys (see `.env.example`)

### 1. Configure environment

```bash
cp .env.example .env
# Required: ANTHROPIC_API_KEY, OPENAI_API_KEY
# Recommended: LANGCHAIN_API_KEY (LangSmith tracing)
# Optional: TAVILY_API_KEY (web search in MarketResearchAgent)
```

### 2. Start all services

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| React frontend | http://localhost:3000 |
| FastAPI (docs) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

### 3. Analyze a deal

**Via the UI:** open http://localhost:3000, drag-drop or select a PDF, watch the agent progress bar, then browse the structured memo.

**Via the API:**

```bash
# 1. Upload
JOB_ID=$(curl -s -X POST http://localhost:8000/analyze \
  -F "file=@your_deal.pdf" | jq -r .job_id)

# 2. Poll until complete
while true; do
  STATUS=$(curl -s "http://localhost:8000/status/${JOB_ID}" | jq -r .status)
  echo "Status: $STATUS"
  [ "$STATUS" = "complete" ] || [ "$STATUS" = "failed" ] && break
  sleep 3
done

# 3. Get the memo
curl "http://localhost:8000/result/${JOB_ID}" | jq .
```

### 4. Run tests

```bash
pip install -e ".[dev]"
pytest tests/ -v              # 22 tests, all mocked — no API keys needed
```

### 5. Run RAGAS evals

```bash
# Golden mode — no database required, uses pre-written contexts
python -m src.evals.ragas_suite

# Live mode — requires running postgres + ingested documents
python -m src.evals.ragas_suite --live
```

---

## API Reference

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| `POST` | `/analyze` | `202` | Upload PDF → `{job_id, status: "queued"}` |
| `GET` | `/status/{job_id}` | `200` | `{status, current_agent, progress_pct}` |
| `GET` | `/result/{job_id}` | `200` / `202` | Full memo JSON when complete; `202` while running |
| `GET` | `/health` | `200` | `{status: "ok"}` liveness probe |

Interactive docs: http://localhost:8000/docs

### Result payload (abbreviated)

```jsonc
{
  "job_id": "abc-123",
  "status": "complete",
  "deal_metrics": { "property_name": "Riverside Commons", "cap_rate_pct": 5.2, … },
  "market_data": { "market_summary": "Austin multifamily rents +4.1% YoY…", … },
  "risk_scores": { "overall_risk_score": 2.1, "dimensions": { … } },
  "memo": {
    "executive_summary": "Riverside Commons is a 240-unit…",
    "recommendation": "Proceed — conditioned on Phase I ESA",
    "data_citations": [ { "claim": "Cap rate 5.2%", "source": "deal document p. 4" } ],
    …
  },
  "latency_ms": 34200,
  "total_tokens": 8700,
  "langsmith_trace_url": "https://smith.langchain.com/public/…"
}
```

---

## LangSmith Observability

When `LANGCHAIN_API_KEY` is set, every pipeline run is traced automatically:

- **Per-agent latency** — wall time for each Claude call
- **Token counts** — input + output per agent
- **Full prompt/response** — every message sent to Claude
- **Graph execution DAG** — node traversal order in LangGraph

The `GET /result/{job_id}` response includes a `langsmith_trace_url` field.
The frontend ObservabilityPanel renders it as a clickable link.

Tracing is opt-in and gracefully degrades — the pipeline runs identically without `LANGCHAIN_API_KEY`.

---

## MCP Server

The RAG pipeline is exposed as an MCP tool callable from Claude Desktop.

### Run the server

```bash
DATABASE_URL=postgresql+psycopg://dealflow:dealflow@localhost:5432/dealflow \
OPENAI_API_KEY=sk-... \
python -m src.mcp.server
```

### Connect to Claude Desktop

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dealflow-rag": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/path/to/dealflow-agent",
      "env": {
        "DATABASE_URL": "postgresql+psycopg://dealflow:dealflow@localhost:5432/dealflow",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Once connected, Claude Desktop can call `query_deal_knowledge_base(query, k)` to retrieve relevant passages from any ingested deal document.

---

## Eval Results (Golden Dataset — Riverside Commons)

| Metric | Score | Threshold | Status |
|--------|-------|-----------|--------|
| faithfulness | — | ≥ 0.75 | run `python -m src.evals.ragas_suite` |
| answer_relevancy | — | — | |
| context_recall | — | — | |
| context_precision | — | — | |

The golden dataset (`src/evals/golden_dataset.py`) contains 10 Q&A pairs for the fictional Riverside Commons 240-unit multifamily deal, covering financial metrics, market comps, and risk factors. No live database or external API calls are required.

---

## AWS Deployment

See [`infra/README.md`](infra/README.md) for the full guide. Summary:

```bash
cd infra

# 1. Create prod.tfvars (never commit — contains secrets)
#    Required vars: acm_certificate_arn, github_repo, anthropic_api_key,
#    openai_api_key, tavily_api_key, langchain_api_key, rds_password

terraform init
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars

# 2. Add AWS_ROLE_ARN to GitHub repo secrets
terraform output -raw github_deploy_role_arn

# 3. Push to main — GitHub Actions builds, pushes, and deploys automatically
git push origin main
```

### Infrastructure overview

- **Networking:** VPC with 2 public + 2 private subnets across 2 AZs, NAT Gateway, IGW
- **ALB:** HTTPS only (ACM cert), HTTP→HTTPS redirect, TLS 1.3 policy
- **ECS Fargate:** private subnets, no public IP, pulls images via NAT
- **RDS PostgreSQL 16:** pgvector built-in, encrypted gp3 storage, 7-day backups, private subnet group
- **Secrets Manager:** all API keys injected at task start via `secrets:` in task definition — never in plaintext env
- **OIDC:** GitHub Actions authenticates via OIDC (no long-lived credentials); role scoped to `repo:org/repo:ref:refs/heads/main`

---

## Project Structure

```
dealflow-agent/
├── src/
│   ├── agents/
│   │   ├── supervisor.py        # AgentState schema + LangGraph graph builder
│   │   ├── document_analyst.py  # PDF metric extraction via Claude tool_use
│   │   ├── market_research.py   # Tavily web search + market synthesis
│   │   ├── risk_analyst.py      # 5-dimension risk scoring via Claude tool_use
│   │   └── memo_writer.py       # Full IC memo synthesis via Claude tool_use
│   ├── api/
│   │   ├── main.py              # FastAPI app + lifespan (logging, tracing init)
│   │   ├── models.py            # Pydantic request/response models
│   │   └── routes/analyze.py    # /analyze, /status, /result endpoints + job store
│   ├── mcp/
│   │   └── server.py            # FastMCP server: query_deal_knowledge_base tool
│   ├── rag/
│   │   ├── ingestion.py         # PDF chunking + embedding + pgvector upsert
│   │   └── retrieval.py         # Similarity search with typed results
│   ├── evals/
│   │   ├── golden_dataset.py    # 10 Q&A pairs for Riverside Commons deal
│   │   └── ragas_suite.py       # RAGAS faithfulness/relevancy/recall/precision
│   └── utils/
│       ├── logging.py           # Structured JSON logging via structlog stdlib
│       └── tracing.py           # TracingConfig: LangSmith enable + run URL resolve
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Phase state machine (idle→uploading→polling→complete)
│   │   ├── api/                 # Typed fetch wrappers, ApiError class
│   │   └── components/          # UploadPanel, JobStatus, MemoViewer, ObservabilityPanel
│   ├── Dockerfile.frontend      # Multi-stage: node build → nginx static serve
│   └── vite.config.ts           # Dev proxy: /analyze /status /result → :8000
├── tests/
│   ├── test_agents.py           # Agent unit tests (mocked AsyncAnthropic)
│   ├── test_api.py              # FastAPI integration tests (httpx ASGITransport)
│   └── test_rag.py              # RAG unit tests (mocked pgvector store)
├── infra/
│   ├── main.tf                  # Terraform + AWS provider + locals
│   ├── networking.tf            # VPC, subnets, IGW, NAT, security groups, ALB
│   ├── ecr.tf                   # ECR repo + lifecycle policy
│   ├── iam.tf                   # ECS exec role + GitHub Actions OIDC role
│   ├── secrets.tf               # Secrets Manager entries for all API keys
│   ├── rds.tf                   # RDS PostgreSQL 16 + pgvector
│   ├── ecs.tf                   # ECS cluster + task definition + Fargate service
│   ├── outputs.tf               # ECR URL, ALB DNS, deploy role ARN, RDS endpoint
│   ├── variables.tf             # All input variables with descriptions + defaults
│   └── README.md                # First-deploy walkthrough + update + destroy
├── .github/workflows/
│   └── deploy.yml               # OIDC push→ECR → ECS update → health check verify
├── docker-compose.yml           # postgres/pgvector + FastAPI app + React frontend
├── Dockerfile                   # Multi-stage Python build
└── pyproject.toml
```

---

## Design Decisions

**Supervisor is pure Python, not an LLM.** Routing is mechanical: check which state fields are populated, advance to the next agent. An LLM supervisor adds ~1s of latency, token cost, and non-determinism for a decision that requires zero reasoning.

**Forced `tool_choice` for structured output.** Each agent calls Claude with `tool_choice: {type: "tool", name: "..."}`, which guarantees a tool call response. The failure mode is a clear exception caught in the agent — not silently malformed JSON that corrupts downstream agents.

**All agents are `async def`.** FastAPI is async. Running blocking LLM calls in a thread pool adds overhead and obscures backpressure. `anthropic.AsyncAnthropic()` + `graph.ainvoke()` keeps the call stack fully async.

**Token accumulation via LangGraph reducer.** `Annotated[int, operator.add]` means each agent can simply return `{"total_tokens_used": N}` without reading or modifying any shared counter. LangGraph sums the values automatically when merging state.

**Deferred imports for optional heavy dependencies.** `langchain_postgres`, `langchain_openai`, and `datasets` are imported inside functions, not at module top-level. This allows `pytest` to collect tests without a full dep installation, which unblocks CI on a minimal environment.

**LangSmith tracing is fully opt-in.** `TracingConfig.enable()` sets `LANGCHAIN_TRACING_V2=true` programmatically only when `LANGCHAIN_API_KEY` is present. The pipeline runs identically — same code path — with tracing off.

**Pre-generated `run_id`.** A `uuid.uuid4()` is generated before `ainvoke()`. This ID is passed to LangGraph via `RunnableConfig` and used post-invocation to resolve the LangSmith trace URL with a single `client.read_run()` call, avoiding polling.
