import type { StatusResponse } from "../api/types";
import styles from "./JobStatus.module.css";

interface Props {
  status: StatusResponse;
}

const AGENT_LABELS: Record<string, string> = {
  document_analyst: "Document Analyst",
  market_research: "Market Research",
  risk_analyst: "Risk Analyst",
  memo_writer: "Memo Writer",
  supervisor: "Supervisor",
  __end__: "Complete",
};

const AGENT_DESCRIPTIONS: Record<string, string> = {
  document_analyst: "Extracting deal metrics and financial data from the document…",
  market_research: "Researching comparable market data, cap rates, and vacancy trends…",
  risk_analyst: "Scoring risk across five dimensions: market, financial, property, liquidity, and execution…",
  memo_writer: "Synthesizing findings into a structured investment committee memo…",
  supervisor: "Initializing pipeline…",
  __end__: "Pipeline complete.",
};

export function JobStatus({ status }: Props) {
  const agentKey = status.current_agent ?? "supervisor";
  const label = AGENT_LABELS[agentKey] ?? agentKey;
  const description = AGENT_DESCRIPTIONS[agentKey] ?? "Processing…";
  const isFailed = status.status === "failed";

  return (
    <div className={`${styles.container} ${isFailed ? styles.failed : ""}`}>
      <div className={styles.header}>
        <div className={styles.statusBadge}>
          {isFailed ? (
            <span className={styles.failedBadge}>Failed</span>
          ) : (
            <span className={styles.runningBadge}>
              <span className={styles.pulse} />
              Running
            </span>
          )}
        </div>
        <span className={styles.jobId}>Job {status.job_id.slice(0, 8)}…</span>
      </div>

      {!isFailed && (
        <>
          <div className={styles.agentName}>{label} Agent</div>
          <p className={styles.description}>{description}</p>

          <div className={styles.progressWrapper}>
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{ width: `${status.progress_pct}%` }}
              />
            </div>
            <span className={styles.progressLabel}>{status.progress_pct}%</span>
          </div>

          <div className={styles.steps}>
            {(["document_analyst", "market_research", "risk_analyst", "memo_writer"] as const).map(
              (agent) => {
                const pct = { document_analyst: 25, market_research: 50, risk_analyst: 75, memo_writer: 100 }[agent];
                const done = status.progress_pct >= pct;
                const active = agentKey === agent;
                return (
                  <div
                    key={agent}
                    className={`${styles.step} ${done ? styles.stepDone : ""} ${active ? styles.stepActive : ""}`}
                  >
                    <span className={styles.stepDot} />
                    <span className={styles.stepLabel}>{AGENT_LABELS[agent]}</span>
                  </div>
                );
              }
            )}
          </div>
        </>
      )}

      {isFailed && status.error && (
        <div className={styles.errorBox}>
          <strong>Error:</strong> {status.error}
        </div>
      )}
    </div>
  );
}
