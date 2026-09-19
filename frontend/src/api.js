async function parse(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export function createRun(requirement) {
  return fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement }),
  }).then(parse);
}

export function getRun(id) {
  return fetch(`/api/runs/${id}`).then(parse);
}

export function approveRun(id, actor = "human", note = "") {
  return fetch(`/api/runs/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor, note }),
  }).then(parse);
}

export function stopRun(id, reason = "human safe-stop") {
  return fetch(`/api/runs/${id}/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  }).then(parse);
}
