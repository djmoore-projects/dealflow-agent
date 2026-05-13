# DealFlow Agent

**Multi-agent AI system for commercial real estate investment analysis.**
Upload a deal PDF. Get a structured investment memo in under 60 seconds.

![Tests](https://img.shields.io/badge/tests-22%20passed-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Demo

> **[Loom walkthrough coming — record after first cloud deploy]**

---

## What It Does

You're looking at a 300-page offering memorandum that landed in your inbox at 4pm on a Friday. Normally that means a junior analyst spends the weekend reading it, pulling numbers into a spreadsheet, writing a draft memo, and flagging the obvious risks — before anyone with authority even glances at it.

DealFlow Agent does that work in under a minute.

Upload the PDF. The system reads the document, researches current market conditions for that submarket, scores the deal across five risk dimensions, and produces a formal investment committee memo — with every claim cited back to either the deal document or the market data source.

The output is the same structured memo your IC expects: executive summary, property overview, financial analysis, market context, risk scores, and a final recommendation with conditions. The difference is it takes 45 seconds instead of four hours.

---

## Architecture

```mermaid
graph TD
    Browser["Browser\nReact + Vite\nUpload · Progress · Memo viewer"]
    API["FastAPI\nPOST /analyze\nGET /status · GET /result"]
    Supervisor["LangGraph Supervisor\npure Python router"]
    DA["DocumentAnalystAgent\nClaude Sonnet 4\ntool_use forced schema"]
    MR["MarketResearchAgent\nClaude Sonnet 4 + Tavily\nweb search + synthesis"]
    RA["RiskAnalystAgent\nClaude Sonnet 4\ntool_use forced schema"]
    MW["MemoWriterAgent\nClaude Sonnet 4\ntool_use forced schema"]
    PG["pgvector\nPostgreSQL 16\ndeal document chunks"]
    MCP["FastMCP Server\nquery_deal_knowledge_base\ncallable from Claude Desktop"]
    LS["LangSmith\nper-agent latency · tokens\nfull prompt trace"]
    ECS["AWS ECS Fargate\nprivate subnet\nALB + HTTPS"]

    Browser -->|"PDF bytes\nHTTP multipart"| API
    API -->|"BackgroundTask\nainvoke(AgentState)"| Supervisor
    Supervisor -->|"deal_metrics is None\nroutes to"| DA
    Supervisor -->|"market_data is None\nroutes to"| MR
    Supervisor -->|"risk_scores is None\nroutes to"| RA
    Supervisor -->|"memo_draft is None\nroutes to"| MW
    DA & MR & RA & MW -->|"state dict\nmerged by reducer"| Supervisor
    MR -->|"similarity search\ntop-k chunks"| MCP
    MCP -->|"embedding lookup\ncosine distance"| PG
    Supervisor -.->|"@traceable\nRunnableConfig run_id"| LS
    API -.->|"Docker image\nECR push + deploy"| ECS
```

---

## Agent Design

| Agent | Role | Tools Used | Output Schema |
|-------|------|------------|---------------|
| **DocumentAnalyst** | Extracts structured financial metrics from the deal document | Claude `tool_use` (forced) | `deal_metrics`: property name, type, market, purchase price, NOI, cap rate, DSCR, LTV, vacancy, loan terms |
| **MarketResearch** | Researches current submarket conditions via web search | Tavily search API + Claude synthesis | `market_data`: vacancy rate, rent growth, absorption, comparable sales, macro narrative |
| **RiskAnalyst** | Scores deal risk across five dimensions | Claude `tool_use` (forced) | `risk_scores`: overall score 1–5, per-dimension scores, key flags, mitigants |
| **MemoWriter** | Synthesizes all prior outputs into a formal IC memo | Claude `tool_use` (forced) | `memo_draft`: executive summary, property overview, financial summary, market context, risk assessment, recommendation, citations |

**Why four agents instead of one big prompt?**

**DocumentAnalyst** exists as a separate agent because document extraction is a different cognitive task from writing prose. Giving it sole focus — with a strictly typed output schema — means downstream agents receive clean, validated data rather than having to parse a blob of text for numbers.

**MarketResearch** is separate because it needs to leave the document and talk to the outside world. It calls Tavily for live web search, then synthesizes the results with Claude. Mixing that I/O pattern into a single prompt would make the system non-deterministic and harder to debug when market data is unavailable.

**RiskAnalyst** is separate because risk scoring requires deliberate reasoning over the financial metrics *and* market context together — but should not have write access to the memo draft. Isolating it forces a clean interface: it reads two inputs, writes one output, and the supervisor can validate the score is within range before proceeding.

**MemoWriter** is last in the chain and has read access to all three prior outputs. It exists as a separate agent because memo writing is a synthesis task, not a data extraction task. Separating it means you can swap the memo template or model without touching any upstream logic.

---

## MCP Server

The RAG pipeline is exposed as an [MCP](https://modelcontextprotocol.io) tool, making the deal knowledge base callable directly from Claude Desktop.

**Tool exposed:** `query_deal_knowledge_base(query: str, k: int = 5)`  
Returns the top-k most relevant chunks from any ingested deal document, ranked by cosine similarity.

**Start the server locally:**

```bash
DATABASE_URL=postgresql+psycopg://dealflow:dealflow@localhost:5432/dealflow \
OPENAI_API_KEY=sk-... \
python -m src.mcp.server
```

**Connect to Claude Desktop** — add to `~/.config/claude/claude_desktop_config.json`:

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

Once connected, Claude Desktop can answer questions like *"What was the DSCR on the Riverside Commons deal?"* by retrieving grounded passages from the ingested document.

---

## Evaluation

RAGAS evals run against a 10-question golden dataset based on the fictional Riverside Commons 240-unit multifamily deal. No live database or external API calls required — contexts are pre-written.

| Metric | Score | Threshold | Status |
|--------|-------|-----------|--------|
| Faithfulness | 0.76 | ≥ 0.75 | ✅ Pass |
| Context Recall | 0.90 | — | ✅ |
| Context Precision | 1.00 | — | ✅ |

> Scores produced by CI against the golden dataset (golden mode, no live retrieval). Run `python -m src.evals.ragas_suite` locally to reproduce.

```bash
# Run evals locally (no database required)
python -m src.evals.ragas_suite

# Live mode (requires running postgres + ingested documents)
python -m src.evals.ragas_suite --live
```

---

## Quick Start

**Prerequisites:** Docker Desktop, API keys (see `.env.example`)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/dealflow-agent.git
cd dealflow-agent

# 2. Configure environment
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and OPENAI_API_KEY at minimum

# 3. Start all services (postgres + API + frontend)
docker compose up --build

# 4. Open the app
open http://localhost:3050
```

The UI is at **http://localhost:3050**. Drag in a deal PDF and watch the agents run.

**Run tests without Docker:**

```bash
pip install -e ".[dev]"
pytest tests/ -v   # 22 tests, all mocked — no API keys needed
```

---

## Deploy to AWS

Full walkthrough in [`infra/README.md`](infra/README.md). The short version:

```bash
cd infra
terraform init
terraform apply -var-file=prod.tfvars   # provisions VPC, ECS, RDS, ALB
# Then add AWS_ROLE_ARN to GitHub repo secrets
# Push to main — GitHub Actions builds, pushes, and deploys automatically
```

---

## Design Decisions

- **LangGraph over CrewAI** — LangGraph gives you explicit control over the state machine. The routing logic is a Python function you can read, test, and trace. CrewAI's agent-to-agent delegation is opaque — when it misroutes, you're debugging a black box. For a pipeline where every step needs to be auditable by an investment committee, transparent routing is non-negotiable.

- **pgvector over Pinecone** — pgvector runs in the same PostgreSQL instance the app already uses, so there's no second cloud service to provision, pay for, or lose data in during an outage. For the document volumes a CRE firm processes, the performance difference is immaterial. Pinecone makes sense when you're at tens of millions of vectors; pgvector is the right default until you have evidence you need something more.

- **RAGAS evals in CI** — Evals that live outside CI get run once and then forgotten. Putting them in CI with a hard threshold (faithfulness ≥ 0.75) means a prompt change or model update that degrades output quality fails the build before it reaches production. It's the same reason you write unit tests for business logic — you want the system to tell you when you broke something.

- **MCP server as a separate process** — The FastAPI app handles synchronous request/response; the MCP server handles long-lived tool connections from Claude Desktop. They have different concurrency models, different lifecycles, and different failure modes. Merging them would mean a crashed Claude Desktop connection could take down the API, or vice versa. Separation keeps the blast radius small.

- **ECS Fargate over Lambda** — The agent pipeline regularly runs for 30–60 seconds and uses up to 1GB of memory for model context. Lambda's 15-minute limit isn't the problem — the cold start latency, the 10GB memory ceiling with a per-invocation pricing model, and the difficulty of running long-lived async tasks cleanly are. Fargate gives you a persistent container with predictable cost, no cold starts, and straightforward autoscaling.

---

## Roadmap

- **Streaming via SSE** — stream agent progress events to the frontend token-by-token rather than polling. Eliminates the progress bar hack and makes the system feel real-time.
- **Multi-document deal rooms** — ingest multiple documents per deal (OM, rent roll, T12, inspection report) into a shared namespace so the agents can cross-reference across sources.
- **Slack bot via MCP** — expose the full pipeline as an MCP tool callable from a Slack integration, so deal teams can run `@dealflow analyze [PDF link]` directly in their deal channel.
- **Fine-tuned reranker** — replace the cosine similarity retrieval step with a reranker fine-tuned on CRE document Q&A pairs, improving context precision for financial metric extraction.

---

## License

MIT
