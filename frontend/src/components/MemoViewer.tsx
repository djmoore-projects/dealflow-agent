import type { MemoContent, RiskDimension, RiskScores } from "../api/types";
import styles from "./MemoViewer.module.css";

interface Props {
  memo: MemoContent;
  riskScores: RiskScores | null;
}

function riskColor(score: number): string {
  if (score <= 2) return "#16a34a";
  if (score === 3) return "#d97706";
  return "#dc2626";
}

function riskBg(score: number): string {
  if (score <= 2) return "#dcfce7";
  if (score === 3) return "#fef3c7";
  return "#fee2e2";
}

function RiskScore({ score }: { score: number }) {
  return (
    <span
      className={styles.scoreBadge}
      style={{ color: riskColor(score), background: riskBg(score) }}
    >
      {score}/5
    </span>
  );
}

function RiskDimensionRow({ label, dim }: { label: string; dim: RiskDimension }) {
  return (
    <div className={styles.dimRow}>
      <div className={styles.dimHeader}>
        <span className={styles.dimLabel}>{label}</span>
        <RiskScore score={dim.score} />
      </div>
      <p className={styles.dimRationale}>{dim.rationale}</p>
      {dim.evidence.length > 0 && (
        <ul className={styles.evidenceList}>
          {dim.evidence.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}
    </div>
  );
}

function formatCurrency(n: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function formatPct(n: number): string {
  // Values from backend are already decimals (0.055 = 5.5%)
  return `${(n * 100).toFixed(2)}%`;
}

function formatMultiple(n: number): string {
  return `${n.toFixed(2)}x`;
}

const RECOMMENDATION_LABEL: Record<string, string> = {
  strong_pass: "Strong Pass",
  pass: "Pass",
  conditional_pass: "Conditional Pass",
  decline: "Decline",
  strong_decline: "Strong Decline",
};

const RECOMMENDATION_COLOR: Record<string, string> = {
  strong_pass: "#16a34a",
  pass: "#16a34a",
  conditional_pass: "#d97706",
  decline: "#dc2626",
  strong_decline: "#dc2626",
};

export function MemoViewer({ memo, riskScores }: Props) {
  const rec = riskScores?.investment_recommendation ?? "";

  return (
    <div className={styles.viewer}>

      {/* Executive Summary */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Executive Summary</h3>
        <p className={styles.summaryText}>{memo.executive_summary}</p>
      </section>

      {/* Property Overview */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Property Overview</h3>
        <div className={styles.grid}>
          <div className={styles.kv}><span className={styles.kvLabel}>Name</span><span>{memo.property_overview.name}</span></div>
          <div className={styles.kv}><span className={styles.kvLabel}>Type</span><span className={styles.capitalize}>{memo.property_overview.type}</span></div>
          <div className={styles.kv}><span className={styles.kvLabel}>Market</span><span>{memo.property_overview.market}</span></div>
          <div className={styles.kv}><span className={styles.kvLabel}>Purchase Price</span><span>{formatCurrency(memo.property_overview.purchase_price_usd)}</span></div>
        </div>
        <p className={styles.description}>{memo.property_overview.description}</p>
      </section>

      {/* Financial Summary */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Financial Metrics</h3>
        <div className={styles.metricsGrid}>
          {memo.financial_summary.noi_usd !== null && (
            <div className={styles.metric}>
              <span className={styles.metricLabel}>NOI</span>
              <span className={styles.metricValue}>{formatCurrency(memo.financial_summary.noi_usd)}</span>
            </div>
          )}
          {memo.financial_summary.cap_rate_pct !== null && (
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Cap Rate</span>
              <span className={styles.metricValue}>{formatPct(memo.financial_summary.cap_rate_pct)}</span>
            </div>
          )}
          {memo.financial_summary.dscr !== null && (
            <div className={styles.metric}>
              <span className={styles.metricLabel}>DSCR</span>
              <span className={styles.metricValue}>{formatMultiple(memo.financial_summary.dscr)}</span>
            </div>
          )}
          {memo.financial_summary.ltv_pct !== null && (
            <div className={styles.metric}>
              <span className={styles.metricLabel}>LTV</span>
              <span className={styles.metricValue}>{formatPct(memo.financial_summary.ltv_pct)}</span>
            </div>
          )}
          {memo.financial_summary.vacancy_pct !== null && (
            <div className={styles.metric}>
              <span className={styles.metricLabel}>Vacancy</span>
              <span className={styles.metricValue}>{formatPct(memo.financial_summary.vacancy_pct)}</span>
            </div>
          )}
        </div>
        <p className={styles.analysisText}>{memo.financial_summary.analysis}</p>
      </section>

      {/* Market Context */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Market Context</h3>
        <p className={styles.bodyText}>{memo.market_context}</p>
      </section>

      {/* Risk Assessment */}
      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Risk Assessment</h3>

        {riskScores && (
          <>
            <div className={styles.overallRisk}>
              <div>
                <div className={styles.overallScore}>
                  Overall Risk Score
                  <span
                    className={styles.bigScore}
                    style={{ color: riskColor(Math.round(riskScores.overall_risk_score)) }}
                  >
                    {riskScores.overall_risk_score.toFixed(1)} / 5
                  </span>
                </div>
              </div>
              {rec && (
                <span
                  className={styles.recBadge}
                  style={{ color: RECOMMENDATION_COLOR[rec] ?? "#64748b", background: riskBg(rec === "strong_pass" || rec === "pass" ? 1 : rec === "conditional_pass" ? 3 : 5) }}
                >
                  {RECOMMENDATION_LABEL[rec] ?? rec}
                </span>
              )}
            </div>

            <div className={styles.dimensions}>
              <RiskDimensionRow label="Market Risk" dim={riskScores.market_risk} />
              <RiskDimensionRow label="Financial Risk" dim={riskScores.financial_risk} />
              <RiskDimensionRow label="Property Risk" dim={riskScores.property_risk} />
              <RiskDimensionRow label="Liquidity Risk" dim={riskScores.liquidity_risk} />
              <RiskDimensionRow label="Execution Risk" dim={riskScores.execution_risk} />
            </div>

            {riskScores.key_risks.length > 0 && (
              <div className={styles.keyRisks}>
                <h4 className={styles.subTitle}>Key Risks</h4>
                <ul className={styles.riskList}>
                  {riskScores.key_risks.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            )}
          </>
        )}

        <p className={styles.bodyText}>{memo.risk_assessment.dimension_summary}</p>
      </section>

      {/* Recommendation */}
      <section className={`${styles.section} ${styles.recSection}`}>
        <h3 className={styles.sectionTitle}>Recommendation</h3>
        <p className={styles.bodyText}>{memo.recommendation}</p>
      </section>

      {/* Citations */}
      {memo.data_citations.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Data Citations</h3>
          <div className={styles.citations}>
            {memo.data_citations.map((c, i) => (
              <div key={i} className={styles.citation}>
                <span className={styles.citationClaim}>"{c.claim}"</span>
                <span className={styles.citationSource}>— {c.source}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
