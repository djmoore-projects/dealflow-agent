// TypeScript interfaces mirroring backend Pydantic models exactly.
// Keep in sync with src/api/models.py and src/agents/memo_writer.py tool schema.

export type JobStatus = "queued" | "running" | "complete" | "failed";

export interface AnalyzeResponse {
  job_id: string;
  status: JobStatus;
  message: string;
}

export interface StatusResponse {
  job_id: string;
  status: JobStatus;
  current_agent: string | null;
  progress_pct: number;
  error: string | null;
}

// ── Memo sub-shapes (from MemoWriter tool schema) ──────────────────────────

export interface PropertyOverview {
  name: string;
  type: string;
  market: string;
  purchase_price_usd: number;
  description: string;
}

export interface FinancialSummary {
  noi_usd: number | null;
  cap_rate_pct: number | null;
  dscr: number | null;
  ltv_pct: number | null;
  vacancy_pct: number | null;
  analysis: string;
}

export interface RiskAssessmentSection {
  overall_score: number;
  recommendation: string;
  dimension_summary: string;
  key_risks: string[];
  mitigants?: string[];
}

export interface DataCitation {
  claim: string;
  source: string;
}

export interface MemoContent {
  executive_summary: string;
  property_overview: PropertyOverview;
  financial_summary: FinancialSummary;
  market_context: string;
  risk_assessment: RiskAssessmentSection;
  recommendation: string;
  data_citations: DataCitation[];
}

// ── Risk scores (from RiskAnalystAgent tool schema) ────────────────────────

export interface RiskDimension {
  score: number; // 1–5
  rationale: string;
  evidence: string[];
}

export interface RiskScores {
  market_risk: RiskDimension;
  financial_risk: RiskDimension;
  property_risk: RiskDimension;
  liquidity_risk: RiskDimension;
  execution_risk: RiskDimension;
  overall_risk_score: number;
  investment_recommendation: string;
  key_risks: string[];
}

// ── Full result (from GET /result/{job_id}) ────────────────────────────────

export interface MemoResult {
  job_id: string;
  status: JobStatus;
  deal_metrics: Record<string, unknown> | null;
  market_data: Record<string, unknown> | null;
  risk_scores: RiskScores | null;
  memo: MemoContent | null;
  error: string | null;
  latency_ms: number | null;
  total_tokens: number | null;
  langsmith_trace_url: string | null;
}

// ── Typed API error ────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
