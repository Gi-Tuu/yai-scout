import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8020";

const headers = { "Content-Type": "application/json" };
const replayBase = {
  answer:
    "YAI Agent Core 当前版本是 0.24.0。" +
    "来源：https://github.com/Gi-Tuu/yai-agent-core/releases/tag/v0.24.0",
  max_claims: 3,
  mode: "replay",
};

function post(path, payload, expected) {
  const response = http.post(BASE + path, JSON.stringify(payload), {
    headers,
    tags: { endpoint: path, expected },
  });
  check(response, {
    "status 200": (r) => r.status === 200,
    "allowed status": (r) => {
      if (r.status !== 200) return false;
      const body = r.json();
      return body && body.verdicts && body.verdicts[0].status === expected;
    },
  });
  return response;
}

export const options = {
  scenarios: {
    replay_fresh: {
      executor: "constant-vus",
      vus: 2,
      duration: "30s",
      exec: "replayFresh",
    },
    replay_stale: {
      executor: "constant-vus",
      vus: 2,
      duration: "30s",
      exec: "replayStale",
    },
    live_stable: {
      executor: "constant-vus",
      vus: 1,
      duration: "30s",
      exec: "liveStable",
    },
    health: {
      executor: "constant-vus",
      vus: 1,
      duration: "30s",
      exec: "health",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000", "p(99)<2000"],
  },
};

export function replayFresh() {
  post(
    "/freshness/verify",
    { ...replayBase, as_of: "2026-10-28" },
    "fresh",
  );
  sleep(0.05);
}

export function replayStale() {
  post(
    "/freshness/verify",
    { ...replayBase, as_of: "2026-11-01" },
    "stale",
  );
  sleep(0.05);
}

export function liveStable() {
  post(
    "/freshness/verify",
    {
      answer: "Python 3.12 于 2023 年发布。",
      as_of: "2026-11-01",
      max_claims: 3,
      mode: "live",
    },
    "fresh",
  );
  sleep(0.05);
}

export function health() {
  const response = http.get(BASE + "/api/healthz", { tags: { endpoint: "/api/healthz" } });
  check(response, { "health 200": (r) => r.status === 200 });
  sleep(0.2);
}
