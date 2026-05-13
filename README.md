# DealFlow Agent

Production-grade multi-agent AI system for commercial real estate investment analysis. Upload a deal PDF, get a structured investment memo with citations and risk scores.

**Status:** Phase 1 complete (LangGraph pipeline + FastAPI + RAG + MCP server + evals)

---

## Architecture

```
PDF Upload
    │
    ▼
FastAPI (POST /analyze)
    │  asyncio.Queue job dispatch
    ▼
LangGraph Supervisor (pure Python router)
    │
    ├─► DocumentAnalystAgent  ── extracts deal metrics via Claude tool_use
    │
    ├─► MarketResearchAgent   ── web search → market comps (Tavily)
    │
    ├─► RiskAnalystAgent      ── scores 5 risk dimensions via Claude tool_use
    │
    └─► MemoWriterAgent       ── synthesizes → structured investment memo
                                      │
                              MCP Server (RAG tool)
                                      │
                               pgvector (PostgreSQL)
```

### LangGraph State Graph

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

### Key Design Decisions

**Supervisor is pure Python, not an LLM.** Routing is mechanical — check which state fields are populated, advance to the next agent. LLM-based supervisors add latency, cost, and non-determinism for zero benefit on a deterministic state machine.

**Agents use `tool_choice: {type: "tool", name: "..."}` to force structured output.** The API validates the JSON against the input_schema before returning. Failure mode is an explicit exception (→ `state.error`), not silently malformed data that corrupts downstream agents.

**Agents are `async def` throughout.** FastAPI is async; blocking LLM calls in a thread pool is a leaky abstraction. All agents use `anthropic.AsyncAnthropic()` and the graph runs with `ainvoke()`.

---

## Quick Start

### 1. Prerequisites

- Docker + Docker Compose
- Python 3.11+
- API keys (see `.env.example`)

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in:
#   ANTHROPIC_API_KEY
#   OPENAI_API_KEY
#   TAVILY_API_KEY (optional — market research uses stub data without it)
```

### 3. Start services

```bash
docker compose up --build
```

The FastAPI server starts at http://localhost:8000. PostgreSQL + pgvector starts at localhost:5432.

### 4. Run the pipeline

```bash
# Upload a deal PDF
curl -X POST http://localhost:8000/analyze \
  -F "file=@your_deal.pdf" \
  | jq .

# Returns: {"job_id": "...", "status": "queued"}

# Poll status
curl http://localhost:8000/status/{job_id} | jq .

# Get result when complete
curl http://localhost:8000/result/{job_id} | jq .
```

### 5. Run tests locally

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### 6. Run RAGAS evals

```bash
# Golden mode (no database required, uses pre-written contexts)
python -m src.evals.ragas_suite

# Live mode (requires running postgres + ingested documents)
python -m src.evals.ragas_suite --live
```

---

## MCP Server

The RAG pipeline is exposed as an MCP tool, callable from Claude Desktop.

### Run the server

```bash
python -m src.mcp.server
```

### Connect to Claude Desktop

Add to `~/.claude/claude_desktop_config.json`:

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

After connecting, Claude Desktop can call `query_deal_knowledge_base(query, k)` to retrieve relevant passages from any ingested deal document.

---

## Project Structure

```
dealflow-agent/
├── src/
│   ├── agents/
│   │   ├── supervisor.py        # AgentState schema + LangGraph graph
│   │   ├── document_analyst.py  # PDF metric extraction
│   │   ├── market_research.py   # Web search + market comps
│   │   ├── risk_analyst.py      # 5-dimension risk scoring
│   │   └── memo_writer.py       # Investment memo synthesis
│   ├── api/
│   │   ├── main.py              # FastAPI app + lifespan
│   │   ├── models.py            # Pydantic request/response models
│   │   └── routes/analyze.py    # /analyze, /status, /result endpoints
│   ├── mcp/
│   │   └── server.py            # FastMCP server exposing RAG as a tool
│   ├── rag/
│   │   ├── ingestion.py         # PDF chunking + embedding + pgvector upsert
│   │   └── retrieval.py         # Similarity search with typed results
│   ├── evals/
│   │   ├── golden_dataset.py    # 10 Q&A pairs for the fictional Riverside Commons deal
│   │   └── ragas_suite.py       # RAGAS faithfulness/relevancy/recall/precision evals
│   └── utils/
│       └── logging.py           # Structured JSON logging via structlog
├── tests/
│   ├── test_agents.py           # Unit tests (mocked Anthropic client)
│   ├── test_api.py              # FastAPI integration tests (httpx ASGI)
│   └── test_rag.py              # RAG unit tests (mocked pgvector)
├── infra/
│   ├── main.tf                  # ECR + ECS Fargate + IAM + ALB (Phase 2)
│   └── variables.tf
├── .github/workflows/ci.yml     # pytest + RAGAS evals on push
├── docker-compose.yml           # postgres/pgvector + app
├── Dockerfile
└── pyproject.toml
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analyze` | Upload PDF, returns `job_id` |
| `GET` | `/status/{job_id}` | Poll status + progress % |
| `GET` | `/result/{job_id}` | Full memo JSON when complete |
| `GET` | `/health` | Liveness probe |

Interactive docs: http://localhost:8000/docs

---

## Eval Results (Phase 1 — Golden Dataset)

| Metric | Score | Threshold | Status |
|--------|-------|-----------|--------|
| faithfulness | TBD | 0.75 | — |
| answer_relevancy | TBD | — | — |
| context_recall | TBD | — | — |
| context_precision | TBD | — | — |

*Run `python -m src.evals.ragas_suite` to populate.*

---

## Phase 2 Roadmap

- [ ] React/TypeScript frontend (Vite, file upload, job polling, memo display)
- [ ] LangSmith tracing on all agent nodes
- [ ] Terraform apply to AWS (ECR + ECS Fargate + ALB)
- [ ] Architecture diagram + live demo URL + Loom walkthrough
