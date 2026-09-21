// The ONLY file that talks to our Python backend.
// Every function returns the JSON answer, or throws an Error with a readable message.

async function request(path, options = {}) {
  const response = await fetch(path, options)
  let data = null
  try {
    data = await response.json()
  } catch {
    // the answer was not JSON; that is fine, we report the status below
  }
  if (!response.ok) {
    const detail = data && (data.error || data.detail)
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `${response.status} ${response.statusText}`
    throw new Error(message)
  }
  return data
}

function post(path, body) {
  return request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export const api = {
  health: () => request("/api/health"),
  summary: () => request("/api/summary"),
  results: (params = {}) => request("/api/results?" + new URLSearchParams(params)),
  result: (emailId) => request(`/api/results/${emailId}`),
  reviews: (state = "OPEN") => request(`/api/reviews?state=${state}`),
  review: (id) => request(`/api/reviews/${id}`),
  resolve: (id, body) => post(`/api/reviews/${id}/resolve`, body),
  run: () => post("/api/run"),
  retry: (emailId) => post(`/api/emails/${emailId}/retry`),
  draft: (emailId, useAi) => post(`/api/results/${emailId}/draft?ai=${useAi}`),
}
