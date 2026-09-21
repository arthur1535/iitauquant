import { timingSafeEqual } from "node:crypto";

export const MAX_BODY_BYTES = 16 * 1024;
export const MAX_ORIGIN_RESPONSE_BYTES = 64 * 1024;
export const ORIGIN_TIMEOUT_MS = 2_000;
export const REQUEST_TIMEOUT_MS = 2_500;
const ROUTE_PREFIX = "/webhook/tradingview/";
const REQUIRED_FIELDS = [
  "strategy", "action", "order_type", "ticker", "close_price", "quantity",
  "timestamp", "nonce", "reason", "idempotency_key",
];

class GatewayError extends Error {
  constructor(status, code) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

function jsonResponse(status, code, requestId) {
  return Response.json(
    { status: "error", code, request_id: requestId },
    { status, headers: {
      "cache-control": "no-store", "x-content-type-options": "nosniff",
      "x-request-id": requestId,
    } },
  );
}

export function parseAllowedIps(value) {
  return new Set(String(value ?? "").split(",").map((ip) => ip.trim()).filter(Boolean));
}

export function validateEnvelope(payload) {
  return payload !== null && typeof payload === "object" && !Array.isArray(payload)
    && REQUIRED_FIELDS.every((field) => Object.hasOwn(payload, field));
}

// FastAPI verifies raw HTTP body bytes, without JSON reserialization or a prefix.
export function canonicalMessage(rawBody) {
  return rawBody;
}

export async function hmacSha256Hex(secret, message) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const bytes = typeof message === "string" ? encoder.encode(message) : message;
  const signature = await crypto.subtle.sign("HMAC", key, bytes);
  return Array.from(new Uint8Array(signature), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function matchesRouteSecret(provided, expected) {
  const encoder = new TextEncoder();
  const hashes = await Promise.all([provided, expected].map((value) =>
    crypto.subtle.digest("SHA-256", encoder.encode(value))));
  return timingSafeEqual(new Uint8Array(hashes[0]), new Uint8Array(hashes[1]));
}

function isJsonContentType(value) {
  return (value ?? "").split(";", 1)[0].trim().toLowerCase() === "application/json";
}

function readConfiguration(env) {
  const ingressSecret = env.INGRESS_ROUTE_SECRET;
  const hmacSecret = env.ORIGIN_HMAC_SECRET;
  if (typeof ingressSecret !== "string" || !/^[A-Za-z0-9_-]{43,128}$/.test(ingressSecret)
      || typeof hmacSecret !== "string" || new TextEncoder().encode(hmacSecret).length < 32
      || ingressSecret === hmacSecret) {
    throw new GatewayError(503, "gateway_not_configured");
  }
  let originUrl;
  try { originUrl = new URL(env.ORIGIN_URL); }
  catch { throw new GatewayError(503, "gateway_not_configured"); }
  const localHttp = originUrl.protocol === "http:" && originUrl.hostname === "127.0.0.1";
  if ((originUrl.protocol !== "https:" && !localHttp)
      || originUrl.username || originUrl.password || originUrl.search || originUrl.hash
      || originUrl.pathname !== "/webhook/tradingview") {
    throw new GatewayError(503, "invalid_origin_configuration");
  }
  return { ingressSecret, hmacSecret, originUrl };
}

async function readBoundedBytes(body, limit, signal, oversizeCode) {
  if (!body) return new Uint8Array();
  const reader = body.getReader();
  const chunks = [];
  let size = 0;
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener("abort", cancel, { once: true });
  try {
    while (true) {
      signal.throwIfAborted();
      const { done, value } = await reader.read();
      signal.throwIfAborted();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new GatewayError(oversizeCode === "payload_too_large" ? 413 : 502, oversizeCode);
      }
      chunks.push(value);
    }
  } finally {
    signal.removeEventListener("abort", cancel);
    reader.releaseLock();
  }
  const result = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
  return result;
}

async function readBoundedJson(request, signal) {
  const length = request.headers.get("content-length");
  if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_BODY_BYTES)) {
    throw new GatewayError(413, "payload_too_large");
  }
  const bytes = await readBoundedBytes(request.body, MAX_BODY_BYTES, signal, "payload_too_large");
  if (!bytes.byteLength) throw new GatewayError(422, "empty_payload");
  let payload;
  try { payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new GatewayError(422, "invalid_json"); }
  if (!validateEnvelope(payload)) throw new GatewayError(422, "invalid_payload");
  return bytes;
}

export default {
  async fetch(request, env) {
    const requestId = crypto.randomUUID();
    const controller = new AbortController();
    const requestTimer = setTimeout(() => controller.abort(new GatewayError(408, "request_timeout")), REQUEST_TIMEOUT_MS);
    let originTimer;
    try {
      const url = new URL(request.url);
      if (request.method !== "POST" || !url.pathname.startsWith(ROUTE_PREFIX) || url.search) {
        throw new GatewayError(404, "not_found");
      }
      const { ingressSecret, hmacSecret, originUrl } = readConfiguration(env);
      const suppliedSecret = url.pathname.slice(ROUTE_PREFIX.length);
      if (!await matchesRouteSecret(suppliedSecret, ingressSecret)) throw new GatewayError(404, "not_found");

      // Cloudflare supplies this header at the edge. Direct Node development is not an authenticated ingress.
      const allowedIps = parseAllowedIps(env.TRADINGVIEW_IPS);
      if (!allowedIps.size || !allowedIps.has(request.headers.get("cf-connecting-ip") ?? "")) {
        throw new GatewayError(403, "source_not_allowed");
      }
      if (!isJsonContentType(request.headers.get("content-type")) || request.headers.has("content-encoding")) {
        throw new GatewayError(415, "json_required");
      }
      const rawBytes = await readBoundedJson(request, controller.signal);
      const signature = await hmacSha256Hex(hmacSecret, canonicalMessage(rawBytes));
      controller.signal.throwIfAborted();
      originTimer = setTimeout(() => controller.abort(new GatewayError(504, "origin_timeout")), ORIGIN_TIMEOUT_MS);
      let originResponse;
      try {
        originResponse = await fetch(originUrl, {
          method: "POST", redirect: "manual", signal: controller.signal,
          headers: {
            "content-type": "application/json", "user-agent": "momentum-atr-cloudflare-gateway/1.1",
            "x-webhook-signature": `sha256=${signature}`, "x-request-id": requestId,
          },
          body: rawBytes,
        });
      } catch {
        controller.signal.throwIfAborted();
        throw new GatewayError(502, "origin_unavailable");
      }
      if (originResponse.status >= 300 && originResponse.status < 400) {
        await originResponse.body?.cancel();
        throw new GatewayError(502, "origin_redirect_rejected");
      }
      if (!isJsonContentType(originResponse.headers.get("content-type"))) {
        await originResponse.body?.cancel();
        throw new GatewayError(502, "invalid_origin_response");
      }
      // Bound the full acknowledgment too: receiving headers alone is not successful delivery.
      const responseBytes = await readBoundedBytes(
        originResponse.body, MAX_ORIGIN_RESPONSE_BYTES, controller.signal, "origin_response_too_large",
      );
      console.log(JSON.stringify({ event: "webhook_forwarded", request_id: requestId, origin_status: originResponse.status }));
      return new Response(responseBytes, {
        status: originResponse.status,
        headers: {
          "content-type": "application/json", "cache-control": "no-store",
          "x-content-type-options": "nosniff", "x-request-id": requestId,
        },
      });
    } catch (error) {
      // Never log URLs, body, secret values, exception messages, or inbound headers.
      const failure = error instanceof GatewayError ? error : new GatewayError(502, "gateway_failure");
      console.warn(JSON.stringify({ event: "webhook_rejected", request_id: requestId, code: failure.code }));
      return jsonResponse(failure.status, failure.code, requestId);
    } finally {
      clearTimeout(requestTimer);
      clearTimeout(originTimer);
    }
  },
};
