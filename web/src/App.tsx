import { FormEvent, useMemo, useState } from "react";

type Investigation = {
  diagnosis: string;
  tools_used: string[];
  model_turns: number;
  tokens: {
    input: number;
    output: number;
    total: number;
  };
  stop_reason: string;
};

type RequestState = "idle" | "loading" | "success" | "error";

const checks = [
  {
    tool: "get_service_health",
    service: "Amazon ECS",
    detail: "Worker health",
    icon: "ECS",
  },
  {
    tool: "get_queue_status",
    service: "Amazon SQS",
    detail: "Queue backlog",
    icon: "SQS",
  },
  {
    tool: "search_logs",
    service: "CloudWatch",
    detail: "Failure logs",
    icon: "CW",
  },
] as const;

function CloudMark() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path d="M15.4 35.5h20.1a8.5 8.5 0 0 0 .5-17 12.3 12.3 0 0 0-23.4 3.7A6.8 6.8 0 0 0 15.4 35.5Z" />
      <path d="m20.2 29.2 4.8-10.4 2.6 7.1h5.2" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M4 10h11M11 6l4 4-4 4" />
    </svg>
  );
}

function Diagnosis({ text }: { text: string }) {
  const lines = text.split("\n").filter((line) => line.trim());

  return (
    <div className="diagnosis-copy">
      {lines.map((line, index) => {
        const clean = line.replaceAll("**", "").trim();
        const isHeading = line.includes("**") && clean.endsWith(":");
        if (isHeading) {
          return <h3 key={`${clean}-${index}`}>{clean.slice(0, -1)}</h3>;
        }
        return <p key={`${clean}-${index}`}>{clean}</p>;
      })}
    </div>
  );
}

function App() {
  const [question, setQuestion] = useState("Why are orders delayed?");
  const [state, setState] = useState<RequestState>("idle");
  const [result, setResult] = useState<Investigation | null>(null);
  const [error, setError] = useState("");

  const completedTools = useMemo(
    () => new Set(result?.tools_used ?? []),
    [result],
  );

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
      if (!response.ok) {
        throw new Error(body.detail ?? "The investigation could not complete.");
      }
      setResult(body as Investigation);
      setState("success");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The investigation could not complete.",
      );
      setState("error");
    }
  }

  return (
    <main className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="topbar">
        <a className="brand" href="#top" aria-label="CloudForge home">
          <span className="brand-mark"><CloudMark /></span>
          <span>CloudForge</span>
        </a>
        <div className="read-only-badge">
          <span className="pulse-dot" />
          Read-only investigation
        </div>
      </header>

      <section className="hero" id="top">
        <div className="eyebrow"><span /> AWS incident intelligence</div>
        <h1>Find the signal.<br /><em>Fix with confidence.</em></h1>
        <p className="hero-copy">
          CloudForge connects the dots across your AWS services and turns live
          operational evidence into a clear incident diagnosis.
        </p>

        <form className="question-card" onSubmit={submit}>
          <label htmlFor="incident-question">Ask about your incident</label>
          <div className="question-row">
            <input
              id="incident-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Why are orders delayed?"
              maxLength={500}
              disabled={state === "loading"}
            />
            <button type="submit" disabled={!question.trim() || state === "loading"}>
              {state === "loading" ? (
                <><span className="button-spinner" /> Investigating</>
              ) : (
                <>Investigate <ArrowIcon /></>
              )}
            </button>
          </div>
          <div className="form-footnote">
            <span className="shield">✓</span>
            Evidence only · CloudForge cannot change your infrastructure
          </div>
        </form>
      </section>

      <section className="investigation-panel" aria-live="polite">
        <div className="panel-heading">
          <div>
            <span className="section-kicker">Investigation path</span>
            <h2>{state === "loading" ? "Gathering live evidence" : "Three signals. One diagnosis."}</h2>
          </div>
          <span className={`state-pill ${state}`}>
            {state === "loading" ? "In progress" : state === "success" ? "Complete" : state === "error" ? "Needs attention" : "Ready"}
          </span>
        </div>

        <div className="checks-grid">
          {checks.map((check, index) => {
            const complete = completedTools.has(check.tool);
            return (
              <div className={`check-card ${complete ? "complete" : ""}`} key={check.tool}>
                <div className="service-icon">{check.icon}</div>
                <div className="service-copy">
                  <strong>{check.service}</strong>
                  <span>{check.detail}</span>
                </div>
                <div className={`check-state ${state === "loading" ? "checking" : ""}`}>
                  {complete ? "✓" : state === "loading" ? <span className="mini-spinner" /> : index + 1}
                </div>
              </div>
            );
          })}
        </div>

        {state === "idle" && (
          <div className="empty-state">
            <div className="radar"><span /></div>
            <p>Your evidence trail will appear here.</p>
          </div>
        )}

        {state === "loading" && (
          <div className="loading-state">
            <div className="scan-line" />
            <p>The agent is checking ECS, SQS, and CloudWatch through read-only MCP tools.</p>
          </div>
        )}

        {state === "error" && (
          <div className="error-state">
            <strong>Investigation stopped</strong>
            <p>{error}</p>
          </div>
        )}

        {state === "success" && result && (
          <article className="diagnosis-card">
            <div className="diagnosis-header">
              <div className="diagnosis-icon">CF</div>
              <div>
                <span className="section-kicker">CloudForge diagnosis</span>
                <h2>Orders worker incident</h2>
              </div>
            </div>
            <Diagnosis text={result.diagnosis} />
            <div className="run-metadata">
              <span>{result.model_turns} model turns</span>
              <span>{result.tokens.total.toLocaleString()} tokens</span>
              <span>{result.stop_reason.replaceAll("_", " ")}</span>
            </div>
          </article>
        )}
      </section>

      <footer>
        <span>CloudForge</span>
        <span>Powered by Strands Agents + Amazon Bedrock</span>
      </footer>
    </main>
  );
}

export default App;
