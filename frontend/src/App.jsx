import { useEffect, useMemo, useState } from "react";
import { approveRun, createRun, getRun, stopRun } from "./api.js";

const STAGES = ["understand", "design", "implement", "test", "docs"];
const TERMINAL = new Set(["succeeded", "failed", "stopped"]);

const SAMPLE =
  "Build a URL shortener with create, redirect, and click counts.";

export default function App() {
  const [requirement, setRequirement] = useState(SAMPLE);
  const [actor, setActor] = useState("human");
  const [note, setNote] = useState("");
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const runId = run?.id;
  const status = run?.status || "idle";
  const waiting = status === "awaiting_approval";
  const live = Boolean(runId) && !TERMINAL.has(status);

  useEffect(() => {
    if (!runId || !live) return undefined;
    const timer = setInterval(() => {
      getRun(runId)
        .then(setRun)
        .catch((err) => setError(err.message));
    }, 700);
    return () => clearInterval(timer);
  }, [runId, live]);

  const events = useMemo(() => run?.events || [], [run]);

  async function onStart(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const created = await createRun(requirement.trim());
      setRun(created);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onApprove() {
    if (!runId) return;
    setError("");
    setBusy(true);
    try {
      setRun(await approveRun(runId, actor.trim() || "human", note));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function onStop() {
    if (!runId) return;
    setError("");
    setBusy(true);
    try {
      setRun(await stopRun(runId, "operator halt from UI"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <header className="top">
        <div>
          <p className="kicker">Control plane</p>
          <h1>agentic-sdlc</h1>
        </div>
        <div className={`pill ${status}`}>
          {status.replaceAll("_", " ")}
        </div>
      </header>

      <div className="layout">
        <section className="panel">
          <h2>Requirement</h2>
          <form onSubmit={onStart}>
            <textarea
              value={requirement}
              onChange={(e) => setRequirement(e.target.value)}
              rows={7}
              placeholder="What should the agents build?"
            />
            <label>
              Actor
              <input
                value={actor}
                onChange={(e) => setActor(e.target.value)}
                maxLength={80}
              />
            </label>
            <label>
              Approval note
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="optional"
              />
            </label>
            <div className="actions">
              <button type="submit" disabled={busy || !requirement.trim()}>
                Start run
              </button>
              <button
                type="button"
                className="primary"
                onClick={onApprove}
                disabled={busy || !waiting}
              >
                Approve implement
              </button>
              <button
                type="button"
                className="danger"
                onClick={onStop}
                disabled={busy || !runId || TERMINAL.has(status)}
              >
                Stop
              </button>
            </div>
          </form>
          {error ? <p className="error">{error}</p> : null}
          {runId ? <p className="muted">run {runId}</p> : null}
        </section>

        <section className="panel">
          <h2>Stage board</h2>
          <div className="board">
            {STAGES.map((stage) => {
              const rec = run?.stages?.[stage];
              const stageStatus = rec?.status || "pending";
              return (
                <article key={stage} className={`stage ${stageStatus}`}>
                  <strong>{stage}</strong>
                  <span>{stageStatus}</span>
                  {rec?.attempts ? <em>try {rec.attempts}</em> : null}
                </article>
              );
            })}
          </div>
          <h2>Audit</h2>
          <ol className="log">
            {events.length === 0 ? (
              <li className="muted">Submit a requirement to start a run.</li>
            ) : (
              events.map((event, index) => (
                <li key={`${event.ts}-${index}`}>
                  <span className="type">{event.type}</span>
                  {event.stage ? <span className="stage-tag">{event.stage}</span> : null}
                  <span>{event.message}</span>
                </li>
              ))
            )}
          </ol>
        </section>
      </div>
    </div>
  );
}
