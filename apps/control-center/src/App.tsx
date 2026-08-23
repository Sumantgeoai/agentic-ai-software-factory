import { FormEvent, useState } from "react";

type TargetProfile = "lightweight-python" | "enterprise-dotnet-react";
type WorkItem = { id: string; title: string; owner: string };
type CommandEvidence = { command: string; return_code: number };
type SecurityFinding = { severity: string; rule: string; file: string; message: string };
type AuditEvent = {
  id: number;
  actor: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
};
type FactoryRun = {
  project_id: string;
  requirements: { product_name: string; acceptance_criteria: string[] };
  architecture: { summary: string; backend: string; frontend: string; database: string };
  plan: { items: WorkItem[] };
  execution: { files_written: string[]; commands: CommandEvidence[] };
  quality: { passed: boolean; summary: string; failures: string[] };
  security: { passed: boolean; findings: SecurityFinding[] };
  review: { approved: boolean; summary: string; risks: string[] };
  release: { sha256: string; file_count: number } | null;
  repair_attempts: number;
};
type StoredRun = {
  project_id: string;
  status: "running" | "completed" | "failed";
  error: string | null;
  updated_at: string;
};

const defaultRequest =
  "Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports.";
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";

function newCorrelationId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `factory-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function requestHeaders(apiKey: string, correlationId: string, json = false) {
  const headers: Record<string, string> = { "X-Correlation-ID": correlationId };
  if (apiKey) headers["X-API-Key"] = apiKey;
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Preserve the status-only message when the response is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export default function App() {
  const [request, setRequest] = useState(defaultRequest);
  const [targetProfile, setTargetProfile] = useState<TargetProfile>("enterprise-dotnet-react");
  const [apiKey, setApiKey] = useState("");
  const [result, setResult] = useState<FactoryRun | null>(null);
  const [storedRun, setStoredRun] = useState<StoredRun | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [correlationId, setCorrelationId] = useState("");
  const [error, setError] = useState("");
  const [traceError, setTraceError] = useState("");
  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  async function loadTrace(projectId: string, correlation: string) {
    const headers = requestHeaders(apiKey, correlation);
    const [runState, events] = await Promise.all([
      fetchJson<StoredRun>(`${baseUrl}/api/v1/runs/${projectId}`, { headers }),
      fetchJson<AuditEvent[]>(`${baseUrl}/api/v1/runs/${projectId}/audit`, { headers }),
    ]);
    setStoredRun(runState);
    setAudit(events);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setRunning(true);
    setError("");
    setTraceError("");
    setResult(null);
    setStoredRun(null);
    setAudit([]);
    const correlation = newCorrelationId();
    setCorrelationId(correlation);
    try {
      const factoryRun = await fetchJson<FactoryRun>(`${baseUrl}/api/v1/projects/run`, {
        method: "POST",
        headers: requestHeaders(apiKey, correlation, true),
        body: JSON.stringify({ request, target_profile: targetProfile }),
      });
      setResult(factoryRun);
      try {
        await loadTrace(factoryRun.project_id, correlation);
      } catch (reason) {
        setTraceError(reason instanceof Error ? reason.message : "Trace retrieval failed");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Factory run failed");
    } finally {
      setRunning(false);
    }
  }

  async function refreshTrace() {
    if (!result || !correlationId) return;
    setRefreshing(true);
    setTraceError("");
    try {
      await loadTrace(result.project_id, correlationId);
    } catch (reason) {
      setTraceError(reason instanceof Error ? reason.message : "Trace retrieval failed");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <main className="shell">
      <header>
        <span className="eyebrow">Agentic AI Software Factory</span>
        <h1>Control Center</h1>
        <p>Submit a product request and inspect the governed delivery evidence end to end.</p>
      </header>

      <form onSubmit={submit} className="request-card">
        <div className="field-row">
          <div>
            <label htmlFor="api-key">API key</label>
            <input
              id="api-key"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              autoComplete="off"
              placeholder="Leave blank when API authentication is disabled"
            />
            <small>Held in memory for this tab only; it is not persisted by the UI.</small>
          </div>
          <div className="endpoint">
            <span className="eyebrow">API endpoint</span>
            <code>{baseUrl}</code>
          </div>
        </div>

        <label htmlFor="target-profile">Generation profile</label>
        <select
          id="target-profile"
          value={targetProfile}
          onChange={(event) => setTargetProfile(event.target.value as TargetProfile)}
        >
          <option value="enterprise-dotnet-react">Enterprise · ASP.NET Core + React + PostgreSQL</option>
          <option value="lightweight-python">Lightweight · Python/FastAPI</option>
        </select>
        <small>Profile selection is sent as a typed factory input; agents must honor the selected stack.</small>

        <label htmlFor="request">Product request</label>
        <textarea
          id="request"
          value={request}
          onChange={(event) => setRequest(event.target.value)}
          rows={6}
        />
        <button disabled={running || request.trim().length < 20}>
          {running ? "Running governed workflow…" : "Run software factory"}
        </button>
      </form>

      {error && <section className="error">{error}</section>}
      {running && (
        <section className="progress-card" aria-live="polite">
          <span className="pulse" />
          <div>
            <strong>Factory run in progress</strong>
            <p>Agents can reason, but filesystem and command side effects remain behind policy gates.</p>
          </div>
        </section>
      )}

      {result && (
        <section className="results">
          <div className="status-row">
            <div>
              <span className="eyebrow">{result.requirements.product_name} · {targetProfile}</span>
              <h2>{result.review.approved ? "Release candidate approved" : "Release blocked"}</h2>
            </div>
            <span className={`pill ${result.review.approved ? "pass" : "fail"}`}>
              {result.review.approved ? "APPROVED" : "BLOCKED"}
            </span>
          </div>

          <div className="summary-strip">
            <div><span>Persisted status</span><strong>{storedRun?.status ?? "loading"}</strong></div>
            <div><span>Security</span><strong>{result.security.passed ? "passed" : "blocked"}</strong></div>
            <div><span>Quality</span><strong>{result.quality.passed ? "passed" : "failed"}</strong></div>
            <div><span>Repairs</span><strong>{result.repair_attempts}</strong></div>
          </div>

          <article className="identity-card">
            <div>
              <span className="eyebrow">Project ID</span>
              <code>{result.project_id}</code>
            </div>
            <div>
              <span className="eyebrow">Correlation ID</span>
              <code>{correlationId}</code>
            </div>
          </article>

          <div className="grid">
            <article>
              <h3>Architecture</h3>
              <p>{result.architecture.summary}</p>
              <dl>
                <dt>Backend</dt><dd>{result.architecture.backend}</dd>
                <dt>Frontend</dt><dd>{result.architecture.frontend}</dd>
                <dt>Data</dt><dd>{result.architecture.database}</dd>
              </dl>
            </article>
            <article>
              <h3>Validation evidence</h3>
              {result.execution.commands.map((item) => (
                <div className="gate" key={item.command}>
                  <span>{item.command}</span>
                  <strong>{item.return_code === 0 ? "passed" : "failed"}</strong>
                </div>
              ))}
              <small>{result.review.summary}</small>
            </article>
          </div>

          <div className="grid">
            <article>
              <h3>Security gate</h3>
              <div className={`security-state ${result.security.passed ? "pass" : "fail"}`}>
                {result.security.passed
                  ? "No blocking deterministic findings"
                  : `${result.security.findings.length} finding(s) blocked execution or release`}
              </div>
              {result.security.findings.map((finding) => (
                <div className="finding" key={`${finding.rule}-${finding.file}`}>
                  <strong>{finding.severity.toUpperCase()} · {finding.rule}</strong>
                  <span>{finding.file}</span>
                  <small>{finding.message}</small>
                </div>
              ))}
            </article>
            <article>
              <h3>Release package</h3>
              {result.release ? (
                <>
                  <div className="release-stat">
                    <strong>{result.release.file_count}</strong>
                    <span>governed files packaged</span>
                  </div>
                  <span className="eyebrow">SHA-256</span>
                  <code>{result.release.sha256}</code>
                  <p>The release ZIP includes a deterministic file manifest and content hashes.</p>
                </>
              ) : (
                <p>No release artifact was created because approval gates did not pass.</p>
              )}
            </article>
          </div>

          <article>
            <h3>Task plan</h3>
            <div className="tasks">
              {result.plan.items.map((item) => (
                <div className="task" key={item.id}>
                  <span>{item.id}</span><strong>{item.title}</strong><small>{item.owner}</small>
                </div>
              ))}
            </div>
          </article>

          <article>
            <div className="trace-heading">
              <div>
                <h3>Audit trace</h3>
                <p>Persisted lifecycle evidence, ordered by event ID.</p>
              </div>
              <button type="button" className="secondary" onClick={refreshTrace} disabled={refreshing}>
                {refreshing ? "Refreshing…" : "Refresh trace"}
              </button>
            </div>
            {traceError && <div className="inline-error">{traceError}</div>}
            <div className="timeline">
              {audit.map((event) => (
                <div className="event" key={event.id}>
                  <span className="event-index">{event.id}</span>
                  <div>
                    <strong>{event.event_type}</strong>
                    <small>{event.actor} · {new Date(event.created_at).toLocaleString()}</small>
                    <code>{JSON.stringify(event.payload)}</code>
                  </div>
                </div>
              ))}
              {!audit.length && !traceError && <p>Loading persisted audit evidence…</p>}
            </div>
          </article>

          <article className="files-card">
            <h3>Governed output</h3>
            <p>{result.execution.files_written.length} files materialized through the tool registry.</p>
            <div className="file-list">
              {result.execution.files_written.map((path) => <code key={path}>{path}</code>)}
            </div>
          </article>
        </section>
      )}
    </main>
  );
}