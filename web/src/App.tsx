import { FormEvent, useMemo, useState } from "react";

type Investigation = {
  diagnosis: string;
  tools_used: string[];
  model_turns: number;
  tokens: { input: number; output: number; total: number };
  stop_reason: string;
};

type RequestState = "idle" | "loading" | "success" | "error";

const checks = [
  { tool: "get_service_health", service: "Amazon ECS", detail: "Inspect orders-worker task health", command: "get_service_health" },
  { tool: "get_queue_status", service: "Amazon SQS", detail: "Measure the orders queue backlog", command: "get_queue_status" },
  { tool: "search_logs", service: "CloudWatch", detail: "Find recent worker errors", command: "search_logs" },
] as const;

function ArrowIcon() {
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 10h13M12 6l4 4-4 4" /></svg>;
}

function Diagnosis({ text }: { text: string }) {
  const lines = text.split("\n").filter((line) => line.trim());
  return (
    <div className="diagnosis-copy">
      {lines.map((line, index) => {
        const clean = line.replaceAll("**", "").trim();
        const isHeading = line.includes("**") && clean.endsWith(":");
        return isHeading
          ? <h3 key={`${clean}-${index}`}>{clean.slice(0, -1)}</h3>
          : <p key={`${clean}-${index}`}>{clean}</p>;
      })}
    </div>
  );
}

function App() {
  const [question, setQuestion] = useState("Why are orders delayed?");
  const [state, setState] = useState<RequestState>("idle");
  const [result, setResult] = useState<Investigation | null>(null);
  const [error, setError] = useState("");
  const completedTools = useMemo(() => new Set(result?.tools_used ?? []), [result]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || state === "loading") return;
    setState("loading");
    setResult(null);
    setError("");
    try {
      const response = await fetch("/api/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "The investigation could not complete.");
      setResult(body as Investigation);
      setState("success");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The investigation could not complete.");
      setState("error");
    }
  }

  const stateLabel = state === "loading" ? "Running" : state === "success" ? "Complete" : state === "error" ? "Stopped" : "Ready";

  return (
    <div className="site-shell">
      <div className="announcement"><span>●</span> Alexa+ MCP incident investigation · Read-only AWS evidence <span aria-hidden="true">→</span></div>

      <header className="topbar">
        <a className="brand" href="#overview" aria-label="CloudForge home">
          <span className="brand-glyph">CF</span>
          <span className="brand-name">CLOUDFORGE <small>for Alexa+</small></span>
        </a>
        <nav aria-label="Primary navigation">
          <a className="active" href="#investigate">Investigate</a>
          <a href="#evidence">Evidence</a>
          <a href="#diagnosis">Diagnosis</a>
        </nav>
        <div className="stack-badge"><span>Alexa+</span><span>MCP</span></div>
      </header>

      <div className="docs-layout">
        <main className="content" id="overview">
          <div className="breadcrumb">CloudForge / Alexa+ MCP demo</div>
          <section className="intro">
            <h1>Investigate order delays</h1>
            <p>CloudForge is an Alexa+ MCP incident investigator. Ask it to trace a failure across ECS, SQS, and CloudWatch before explaining the most likely root cause.</p>
          </section>

          <div className="callout"><strong>Read-only by design.</strong><span>The agent can inspect your demo infrastructure, but it cannot change it.</span></div>

          <section className="section" id="investigate">
            <div className="section-number">01</div>
            <div className="section-heading"><span>ASK THE AGENT</span><h2>What is happening?</h2></div>
            <form className="question-console" onSubmit={submit}>
              <div className="console-bar">
                <div className="window-dots" aria-hidden="true"><span /><span /><span /></div>
                <span>incident_query.txt</span>
                <span className={`run-state ${state}`}>{stateLabel}</span>
              </div>
              <div className="question-row">
                <label htmlFor="incident-question" aria-label="Incident question">$</label>
                <input id="incident-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Why are orders delayed?" maxLength={500} disabled={state === "loading"} />
                <button type="submit" disabled={!question.trim() || state === "loading"}>
                  {state === "loading" ? <><span className="button-spinner" /> Running</> : <>Investigate <ArrowIcon /></>}
                </button>
              </div>
            </form>
          </section>

          <section className="section" id="evidence" aria-live="polite">
            <div className="section-number">02</div>
            <div className="section-heading evidence-heading">
              <div><span>INVESTIGATION TRACE</span><h2>Gather evidence</h2></div>
              <span className={`state-tag ${state}`}>{stateLabel}</span>
            </div>
            <div className="checks-list">
              {checks.map((check, index) => {
                const complete = completedTools.has(check.tool);
                return (
                  <div className={`check-row ${complete ? "complete" : ""}`} key={check.tool}>
                    <span className="check-index">0{index + 1}</span>
                    <div className="check-copy"><strong>{check.service}</strong><span>{check.detail}</span></div>
                    <code>{check.command}()</code>
                    <div className={`check-status ${state === "loading" ? "checking" : ""}`}>{complete ? "PASS" : state === "loading" ? "..." : "WAIT"}</div>
                  </div>
                );
              })}
            </div>
            {state === "idle" && <div className="empty-state"><span className="prompt-caret">▋</span><p>Run an investigation to populate the evidence trace.</p></div>}
            {state === "loading" && <div className="loading-state"><span className="terminal-loader">[···]</span><p>The Strands agent is querying the three MCP tools.</p></div>}
            {state === "error" && <div className="error-state"><strong>Investigation stopped</strong><p>{error}</p></div>}
          </section>

          <section className="section diagnosis-section" id="diagnosis">
            <div className="section-number">03</div>
            <div className="section-heading"><span>AGENT OUTPUT</span><h2>Diagnosis</h2></div>
            {state === "success" && result ? (
              <article className="diagnosis-card">
                <div className="diagnosis-bar"><span><span className="status-dot" /> Root-cause analysis</span><span>cloudforge-agent</span></div>
                <Diagnosis text={result.diagnosis} />
                <div className="run-metadata"><span>turns: {result.model_turns}</span><span>tokens: {result.tokens.total.toLocaleString()}</span><span>stop: {result.stop_reason.replaceAll("_", " ")}</span></div>
              </article>
            ) : <div className="diagnosis-placeholder"><span>//</span>The evidence-backed diagnosis will appear here.</div>}
          </section>
        </main>

      </div>

      <footer><span>CloudForge / Alexa+ hackathon MVP</span><span>Strands Agents + Amazon Bedrock</span></footer>
    </div>
  );
}

export default App;
