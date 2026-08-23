import { FormEvent, useState } from "react";

type WorkItem = { id: string; title: string; owner: string };
type FactoryRun = {
  project_id: string;
  requirements: { product_name: string; acceptance_criteria: string[] };
  architecture: { summary: string; backend: string; frontend: string; database: string };
  plan: { items: WorkItem[] };
  execution: {
    workspace: string;
    files_written: string[];
    commands: { command: string; return_code: number }[];
  };
  review: { approved: boolean; summary: string; risks: string[] };
};

const defaultRequest =
  "Build an employee leave-management application where employees submit leave, managers approve or reject requests, and HR can view reports.";

export default function App() {
  const [request, setRequest] = useState(defaultRequest);
  const [result, setResult] = useState<FactoryRun | null>(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8080";
      const response = await fetch(`${baseUrl}/api/v1/projects/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request }),
      });
      if (!response.ok) throw new Error(await response.text());
      setResult(await response.json());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Factory run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="shell">
      <header>
        <span className="eyebrow">Agentic AI Software Factory</span>
        <h1>Control Center</h1>
        <p>Submit a product request and inspect the governed delivery trace.</p>
      </header>

      <form onSubmit={submit} className="request-card">
        <label htmlFor="request">Product request</label>
        <textarea
          id="request"
          value={request}
          onChange={(event) => setRequest(event.target.value)}
          rows={6}
        />
        <button disabled={running || request.trim().length < 20}>
          {running ? "Running workflow…" : "Run software factory"}
        </button>
      </form>

      {error && <section className="error">{error}</section>}
      {result && (
        <section className="results">
          <div className="status-row">
            <div>
              <span className="eyebrow">{result.requirements.product_name}</span>
              <h2>{result.review.approved ? "Release candidate approved" : "Quality gate failed"}</h2>
            </div>
            <span className={`pill ${result.review.approved ? "pass" : "fail"}`}>
              {result.review.approved ? "PASS" : "FAIL"}
            </span>
          </div>

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
              <h3>Quality gates</h3>
              {result.execution.commands.map((item) => (
                <div className="gate" key={item.command}>
                  <span>{item.command}</span><strong>{item.return_code === 0 ? "passed" : "failed"}</strong>
                </div>
              ))}
              <small>{result.review.summary}</small>
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
            <h3>Workspace</h3>
            <code>{result.execution.workspace}</code>
            <p>{result.execution.files_written.length} files materialized</p>
          </article>
        </section>
      )}
    </main>
  );
}
