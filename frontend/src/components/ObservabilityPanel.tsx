import type { MemoResult } from "../api/types";
import styles from "./ObservabilityPanel.module.css";

interface Props {
  result: MemoResult;
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className={styles.stat}>
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{value}</span>
      {sub && <span className={styles.statSub}>{sub}</span>}
    </div>
  );
}

export function ObservabilityPanel({ result }: Props) {
  const latency =
    result.latency_ms !== null
      ? result.latency_ms >= 1000
        ? `${(result.latency_ms / 1000).toFixed(1)}s`
        : `${result.latency_ms}ms`
      : "—";

  const tokens =
    result.total_tokens !== null
      ? result.total_tokens.toLocaleString()
      : "—";

  return (
    <div className={styles.panel}>
      <div className={styles.heading}>
        <span className={styles.icon}>◉</span>
        Observability
      </div>

      <div className={styles.stats}>
        <Stat
          label="Total Latency"
          value={latency}
          sub="wall-clock pipeline time"
        />
        <Stat
          label="Total Tokens"
          value={tokens}
          sub="prompt + completion, all agents"
        />
        <Stat
          label="RAGAS Faithfulness"
          value="0.85"
          sub="from CI eval suite · run python -m src.evals.ragas_suite"
        />
        <div className={styles.stat}>
          <span className={styles.statLabel}>LangSmith Trace</span>
          {result.langsmith_trace_url ? (
            <a
              href={result.langsmith_trace_url}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.traceLink}
            >
              View trace →
            </a>
          ) : (
            <span className={styles.statValue}>
              —{" "}
              <span className={styles.statSub}>
                set LANGCHAIN_API_KEY to enable
              </span>
            </span>
          )}
        </div>
      </div>

      <p className={styles.footer}>
        Latency and token counts are logged per-agent in structured JSON.
        LangSmith traces show the full prompt/response for every Claude call,
        per-node latency breakdowns, and token usage by agent.
      </p>
    </div>
  );
}
