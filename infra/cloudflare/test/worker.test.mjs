import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { describe, it } from "node:test";

import gateway, {
  MAX_BODY_BYTES,
  MAX_ORIGIN_RESPONSE_BYTES,
  ORIGIN_TIMEOUT_MS,
  REQUEST_TIMEOUT_MS,
  canonicalMessage,
  hmacSha256Hex,
  parseAllowedIps,
  validateEnvelope,
} from "../src/index.mjs";

describe("Cloudflare webhook gateway helpers", () => {
  it("parses an explicit source allowlist", () => {
    const ips = parseAllowedIps("52.89.214.238, 34.212.75.30,");
    assert.equal(ips.size, 2);
    assert.equal(ips.has("34.212.75.30"), true);
  });

  it("fails closed when the allowlist is absent", () => {
    assert.equal(parseAllowedIps(undefined).size, 0);
  });

  it("requires a complete webhook envelope", () => {
    const valid = {
      strategy: "MOMENTUM_ATR",
      action: "BUY",
      order_type: "MARKET",
      ticker: "PETR4",
      close_price: 30.5,
      quantity: 10,
      timestamp: 1_788_480_000,
      nonce: "nonce-1",
      reason: "MOMENTUM_ENTRY",
      idempotency_key: "PETR4-1D-1788480000-BUY",
    };
    assert.equal(validateEnvelope(valid), true);
    delete valid.ticker;
    assert.equal(validateEnvelope(valid), false);
  });

  it("creates a stable SHA-256 HMAC", async () => {
    const message = canonicalMessage('{"ok":true}');
    const signature = await hmacSha256Hex("x".repeat(32), message);
    assert.match(signature, /^[0-9a-f]{64}$/);
    assert.equal(
      signature,
      await hmacSha256Hex("x".repeat(32), message),
    );
  });
});

const ENV = {
  INGRESS_ROUTE_SECRET: "test-ingress-" + "a".repeat(43),
  ORIGIN_HMAC_SECRET: "test-hmac-" + "b".repeat(43),
  ORIGIN_URL: "https://paper-origin.example.com/webhook/tradingview",
  TRADINGVIEW_IPS: "52.89.214.238,34.212.75.30",
};
const PAYLOAD = {
  strategy: "MOMENTUM_ATR", action: "BUY", order_type: "MARKET", ticker: "PETR4",
  close_price: 30.5, quantity: 10, timestamp: 1_788_480_000, nonce: "nonce-12345678",
  reason: "MOMENTUM_ENTRY", idempotency_key: "PETR4-1D-1788480000-BUY",
};

function request({ body = JSON.stringify(PAYLOAD), path = `/webhook/tradingview/${ENV.INGRESS_ROUTE_SECRET}`, headers = {}, method = "POST" } = {}) {
  return new Request(`https://gateway.example.com${path}`, {
    method, body: method === "GET" ? undefined : body, duplex: "half",
    headers: { "content-type": "application/json", "cf-connecting-ip": "52.89.214.238", ...headers },
  });
}

function mockOrigin(t, handler = async () => Response.json({ status: "accepted", mode: "paper" })) {
  t.mock.method(console, "log", () => {});
  t.mock.method(console, "warn", () => {});
  return t.mock.method(globalThis, "fetch", handler);
}

async function expectRejected(t, input, status, code, env = ENV) {
  const origin = mockOrigin(t);
  const response = await gateway.fetch(input, env);
  assert.equal(response.status, status);
  assert.equal((await response.json()).code, code);
  assert.equal(origin.mock.callCount(), 0);
}

describe("Gateway HTTP handler", { concurrency: false }, () => {
  it("forwards exact Unicode/whitespace bytes with independently verified raw-body HMAC", async (t) => {
    const raw = new TextEncoder().encode("  " + JSON.stringify({ ...PAYLOAD, metadata: { exchange: "açãо" } }, null, 2) + "\n");
    const origin = mockOrigin(t, async (url, options) => {
      assert.equal(String(url), ENV.ORIGIN_URL);
      assert.equal(options.method, "POST");
      assert.equal(options.redirect, "manual");
      assert.deepEqual(options.body, raw);
      const signature = createHmac("sha256", ENV.ORIGIN_HMAC_SECRET).update(raw).digest("hex");
      assert.equal(options.headers["x-webhook-signature"], `sha256=${signature}`);
      assert.equal(options.headers.authorization, undefined);
      assert.equal(options.headers.cookie, undefined);
      assert.equal(options.headers["x-webhook-timestamp"], undefined);
      assert.equal(JSON.stringify(options.headers).includes(ENV.INGRESS_ROUTE_SECRET), false);
      return Response.json({ detail: "risk limit reached" }, { status: 409 });
    });
    const response = await gateway.fetch(request({ body: raw, headers: { authorization: "Bearer unwanted", cookie: "session=unwanted" } }), ENV);
    assert.equal(origin.mock.callCount(), 1);
    assert.equal(response.status, 409);
    assert.deepEqual(await response.json(), { detail: "risk limit reached" });
    assert.equal(response.headers.get("cache-control"), "no-store");
  });

  for (const path of ["/webhook/tradingview", "/webhook/tradingview/wrong", `/webhook/tradingview/${ENV.INGRESS_ROUTE_SECRET}?extra=yes`]) {
    it(`rejects an unauthorized ingress route (${path.length} characters)`, async (t) => {
      await expectRejected(t, request({ path }), 404, "not_found");
    });
  }
  it("rejects GET", async (t) => expectRejected(t, request({ method: "GET" }), 404, "not_found"));
  it("requires independent ingress and origin credentials", async (t) => {
    await expectRejected(t, request(), 503, "gateway_not_configured", { ...ENV, ORIGIN_HMAC_SECRET: ENV.INGRESS_ROUTE_SECRET });
  });
  it("requires a configured ingress credential", async (t) => {
    await expectRejected(t, request(), 503, "gateway_not_configured", { ...ENV, INGRESS_ROUTE_SECRET: undefined });
  });
  it("requires a strong ingress credential", async (t) => {
    await expectRejected(t, request(), 503, "gateway_not_configured", { ...ENV, INGRESS_ROUTE_SECRET: "short" });
  });
  it("rejects absent source allowlist", async (t) => {
    await expectRejected(t, request(), 403, "source_not_allowed", { ...ENV, TRADINGVIEW_IPS: "" });
  });
  it("rejects a source outside TradingView even with a valid route", async (t) => {
    await expectRejected(t, request({ headers: { "cf-connecting-ip": "192.0.2.1" } }), 403, "source_not_allowed");
  });
  for (const contentType of ["application/json-patch", "text/plain", "text/json"]) {
    it(`rejects content type ${contentType}`, async (t) => {
      await expectRejected(t, request({ headers: { "content-type": contentType } }), 415, "json_required");
    });
  }
  it("accepts JSON media type with charset", async (t) => {
    mockOrigin(t);
    assert.equal((await gateway.fetch(request({ headers: { "content-type": "Application/JSON; charset=utf-8" } }), ENV)).status, 200);
  });
  it("rejects encoded bodies", async (t) => {
    await expectRejected(t, request({ headers: { "content-encoding": "gzip" } }), 415, "json_required");
  });
  it("rejects invalid UTF-8 before signing it", async (t) => {
    await expectRejected(t, request({ body: new Uint8Array([0xff, 0xfe]) }), 422, "invalid_json");
  });
  it("rejects malformed and incomplete payloads", async (t) => {
    await expectRejected(t, request({ body: "{\"ticker\":\"PETR4\"}" }), 422, "invalid_payload");
  });
  it("rejects advertised oversized bodies before reading them", async (t) => {
    let reads = 0;
    const body = new ReadableStream({ pull() { reads++; } }, { highWaterMark: 0 });
    await expectRejected(t, request({ body, headers: { "content-length": String(MAX_BODY_BYTES + 1) } }), 413, "payload_too_large");
    assert.equal(reads, 0);
  });
  it("stops a chunked body above its limit even when Content-Length lies", async (t) => {
    let reads = 0;
    let cancelled = false;
    const body = new ReadableStream({
      pull(controller) { reads++; controller.enqueue(new Uint8Array(8192)); },
      cancel() { cancelled = true; },
    }, { highWaterMark: 0 });
    await expectRejected(t, request({ body, headers: { "content-length": "10" } }), 413, "payload_too_large");
    assert.equal(reads, 3);
    assert.equal(cancelled, true);
  });
  for (const originUrl of ["not-a-url", "http://remote.example.com/webhook/tradingview", "ftp://127.0.0.1/webhook/tradingview", "https://name:password@origin.example.com/webhook/tradingview", "https://origin.example.com/webhook/tradingview?secret=abc", "https://origin.example.com/other"]) {
    it(`fails closed for unsafe origin configuration ${originUrl.split(":")[0]}`, async (t) => {
      const origin = mockOrigin(t);
      assert.equal((await gateway.fetch(request(), { ...ENV, ORIGIN_URL: originUrl })).status, 503);
      assert.equal(origin.mock.callCount(), 0);
    });
  }
  it("rejects origin redirects instead of forwarding credentials or reporting success", async (t) => {
    const origin = mockOrigin(t, async () => new Response(null, { status: 302, headers: { location: "https://attacker.example" } }));
    const response = await gateway.fetch(request(), ENV);
    assert.equal(response.status, 502);
    assert.equal((await response.json()).code, "origin_redirect_rejected");
    assert.equal(origin.mock.callCount(), 1);
    assert.equal(response.headers.get("location"), null);
  });
  it("preserves origin server errors and does not convert them to acceptance", async (t) => {
    mockOrigin(t, async () => Response.json({ detail: "database unavailable" }, { status: 503 }));
    const response = await gateway.fetch(request(), ENV);
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { detail: "database unavailable" });
  });
  it("rejects non-JSON origin content", async (t) => {
    mockOrigin(t, async () => new Response("<html>login</html>", { headers: { "content-type": "text/html" } }));
    const response = await gateway.fetch(request(), ENV);
    assert.equal(response.status, 502);
    assert.equal((await response.json()).code, "invalid_origin_response");
  });
  it("bounds the origin acknowledgment body", async (t) => {
    mockOrigin(t, async () => new Response(new Uint8Array(MAX_ORIGIN_RESPONSE_BYTES + 1), { headers: { "content-type": "application/json" } }));
    const response = await gateway.fetch(request(), ENV);
    assert.equal(response.status, 502);
    assert.equal((await response.json()).code, "origin_response_too_large");
  });
  it("does not log either credential, URLs, body, or thrown exception messages", async (t) => {
    mockOrigin(t, async () => { throw new Error(ENV.ORIGIN_HMAC_SECRET + ENV.INGRESS_ROUTE_SECRET + ENV.ORIGIN_URL); });
    const response = await gateway.fetch(request(), ENV);
    const output = JSON.stringify(console.warn.mock.calls.map((call) => call.arguments));
    assert.equal(response.status, 502);
    for (const forbidden of [ENV.ORIGIN_HMAC_SECRET, ENV.INGRESS_ROUTE_SECRET, ENV.ORIGIN_URL, "PETR4"]) {
      assert.equal(output.includes(forbidden), false);
    }
  });
  it("aborts an unresponsive origin within the delivery budget", async (t) => {
    let aborted = false;
    mockOrigin(t, async (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => { aborted = true; reject(options.signal.reason); }, { once: true });
    }));
    const start = performance.now();
    const response = await gateway.fetch(request(), ENV);
    assert.equal(response.status, 504);
    assert.equal((await response.json()).code, "origin_timeout");
    assert.equal(aborted, true);
    assert.ok(performance.now() - start < REQUEST_TIMEOUT_MS + 400);
    assert.ok(ORIGIN_TIMEOUT_MS < 3_000);
  });
  it("times out a stalled response after headers instead of acknowledging it", async (t) => {
    let cancelled = false;
    mockOrigin(t, async () => new Response(new ReadableStream({ cancel() { cancelled = true; } }), { headers: { "content-type": "application/json" } }));
    const response = await gateway.fetch(request(), ENV);
    assert.equal(response.status, 504);
    assert.equal((await response.json()).code, "origin_timeout");
    assert.equal(cancelled, true);
  });
  it("cancels an incoming body that never finishes", async (t) => {
    let cancelled = false;
    const body = new ReadableStream({ cancel() { cancelled = true; } });
    await expectRejected(t, request({ body }), 408, "request_timeout");
    assert.equal(cancelled, true);
  });
});
