import {
  ManagedAiError,
  RESPONSE_SCHEMA,
  buildFallbackVariants,
  buildPrompt,
  extractReservationId,
  isAllowedQuotaPayload,
  normalizeProduct,
  parseGatewayContent,
  sanitizeText,
  validateVariants,
} from "../_lib/managed-ai.mjs";

const AUTH_API_URL = String(
  process.env.AUTH_API_URL || "https://newshopping-shorts-auth.vercel.app",
).replace(/\/$/, "");
const GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions";
const PRIMARY_MODEL = process.env.PRIMARY_AI_MODEL || "xai/grok-4.3";

function sendJson(res, status, value) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(value));
}

function requestIp(req) {
  const forwarded = String(req.headers["x-forwarded-for"] || "");
  return sanitizeText(forwarded.split(",")[0], 80) || "vercel-function";
}

async function readBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  if (typeof req.body === "string") {
    try {
      return JSON.parse(req.body);
    } catch {
      throw new ManagedAiError("INVALID_REQUEST", 400, "요청 JSON 형식이 올바르지 않습니다.");
    }
  }
  let size = 0;
  const chunks = [];
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 32 * 1024) {
      throw new ManagedAiError("INVALID_REQUEST", 413, "요청 크기가 너무 큽니다.");
    }
    chunks.push(chunk);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  } catch {
    throw new ManagedAiError("INVALID_REQUEST", 400, "요청 JSON 형식이 올바르지 않습니다.");
  }
}

async function authRequest(path, token, body) {
  const response = await fetch(`${AUTH_API_URL}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(12_000),
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  return { response, payload };
}

function reservationBody(userId, token, reservationId = "", requestId = "") {
  const body = { user_id: userId, token };
  if (requestId) body.idempotency_key = requestId;
  if (reservationId) {
    body.reservation_id = reservationId;
    body.reserve_id = reservationId;
    body.work_token = reservationId;
  }
  return body;
}

async function reserveWork(userId, token, requestId) {
  const { response, payload } = await authRequest(
    "/user/work/reserve",
    token,
    reservationBody(userId, token, "", requestId),
  );
  if ([404, 405, 501].includes(response.status)) {
    throw new ManagedAiError(
      "ATOMIC_QUOTA_UNAVAILABLE",
      503,
      "안전한 작업량 예약 기능을 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
    );
  }
  if (response.status === 401) {
    throw new ManagedAiError("AUTH_REQUIRED", 401, "로그인이 만료되었습니다.");
  }
  if (response.status === 402 || response.status === 403) {
    throw new ManagedAiError(
      "SUBSCRIPTION_REQUIRED",
      403,
      sanitizeText(payload?.message, 240) || "무료 사용량 또는 이용권을 확인해주세요.",
    );
  }
  if (!response.ok) {
    throw new ManagedAiError(
      "QUOTA_RESERVATION_FAILED",
      503,
      sanitizeText(payload?.message, 240) || "작업량을 안전하게 예약하지 못했습니다.",
    );
  }
  if (payload?.code === "IDEMPOTENCY_REPLAY") {
    throw new ManagedAiError(
      "DUPLICATE_REQUEST",
      409,
      "이미 처리된 요청입니다. 새 작업으로 다시 시도해주세요.",
    );
  }
  if (!isAllowedQuotaPayload(payload)) {
    throw new ManagedAiError(
      "SUBSCRIPTION_REQUIRED",
      403,
      sanitizeText(payload?.message, 240) || "무료 사용량 또는 이용권을 확인해주세요.",
    );
  }
  const reservationId = extractReservationId(payload);
  if (!reservationId) {
    throw new ManagedAiError(
      "RESERVATION_INVALID",
      503,
      "작업량 예약 ID를 받지 못해 안전상 요청을 중단했습니다.",
    );
  }
  return reservationId;
}

async function releaseWork(userId, token, reservationId, requestId) {
  if (!reservationId) return;
  try {
    await authRequest(
      "/user/work/release",
      token,
      reservationBody(userId, token, reservationId, requestId),
    );
  } catch {
    // The authentication service owns reservation TTL recovery.
  }
}

async function gatewayCompletion(model, token, userId, prompt) {
  const response = await fetch(GATEWAY_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model,
      temperature: 0.85,
      max_tokens: 1600,
      user: String(userId),
      messages: [{ role: "user", content: prompt }],
      response_format: {
        type: "json_schema",
        json_schema: {
          name: "threads_product_variants",
          strict: true,
          schema: RESPONSE_SCHEMA,
        },
      },
    }),
    signal: AbortSignal.timeout(25_000),
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    const message = sanitizeText(payload?.error?.message ?? payload?.message, 300);
    const error = new Error(message || `AI Gateway 오류 (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return { payload, model };
}

export default async function handler(req, res) {
  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    res.end();
    return;
  }
  if (req.method !== "POST") {
    sendJson(res, 405, { success: false, code: "METHOD_NOT_ALLOWED" });
    return;
  }

  let reservationId = "";
  let userId = "";
  let loginToken = "";
  const requestId = sanitizeText(
    req.headers["idempotency-key"] || crypto.randomUUID(),
    120,
  );
  try {
    const authorization = String(req.headers.authorization || "");
    loginToken = authorization.replace(/^Bearer\s+/i, "").trim();
    if (!loginToken) {
      throw new ManagedAiError("AUTH_REQUIRED", 401, "로그인이 필요합니다.");
    }

    const body = await readBody(req);
    userId = sanitizeText(body?.user_id, 120);
    if (!userId) {
      throw new ManagedAiError("AUTH_REQUIRED", 401, "사용자 정보가 없습니다.");
    }
    const schemaVersion = Number(body?.client?.schema_version || 1);
    if (schemaVersion !== 1) {
      throw new ManagedAiError("CLIENT_UPDATE_REQUIRED", 426, "프로그램 업데이트가 필요합니다.");
    }

    const product = normalizeProduct(body?.product);
    reservationId = await reserveWork(userId, loginToken, requestId);

    const gatewayToken = process.env.AI_GATEWAY_API_KEY || process.env.VERCEL_OIDC_TOKEN;
    if (!gatewayToken) {
      throw new ManagedAiError(
        "AI_NOT_CONFIGURED",
        503,
        "AI Gateway 인증이 설정되지 않았습니다.",
      );
    }

    const prompt = buildPrompt(product);
    let model = "";
    let variants;
    let degraded = false;
    let degradedReason = "";
    try {
      const completion = await gatewayCompletion(
        PRIMARY_MODEL,
        gatewayToken,
        userId,
        prompt,
      );
      model = completion.model;
      variants = validateVariants(
        parseGatewayContent(completion.payload),
        product,
      );
    } catch (gatewayError) {
      const gatewayStatus = Number(gatewayError?.status || 0);
      const gatewayMessage = String(gatewayError?.message || "").toLowerCase();
      const creditsRequired =
        gatewayStatus === 402 ||
        (gatewayStatus === 403 && gatewayMessage.includes("credit card"));
      if (!creditsRequired) throw gatewayError;
      model = "template-fallback";
      degraded = true;
      degradedReason = "ai_credits_required";
      variants = validateVariants(buildFallbackVariants(product), product);
    }
    sendJson(res, 200, {
      success: true,
      ai_job_id: requestId,
      reservation_id: reservationId,
      quota_mode: "reservation",
      prompt_version: "threads-ko-v1",
      model,
      degraded,
      degraded_reason: degradedReason,
      variants,
      request_ip_hash_basis: requestIp(req) ? "present" : "missing",
    });
  } catch (error) {
    if (reservationId) {
      await releaseWork(userId, loginToken, reservationId, requestId);
    }
    const managed = error instanceof ManagedAiError;
    const gatewayStatus = Number(error?.status || 0);
    const gatewayMessage = String(error?.message || "").toLowerCase();
    const creditsRequired =
      !managed &&
      (gatewayStatus === 402 ||
        (gatewayStatus === 403 && gatewayMessage.includes("credit card")));
    const gatewayAuthFailed =
      !managed && !creditsRequired && [401, 403].includes(gatewayStatus);
    sendJson(res, managed ? error.status : 503, {
      success: false,
      code: managed
        ? error.code
        : creditsRequired
          ? "AI_CREDITS_REQUIRED"
          : gatewayAuthFailed
            ? "AI_GATEWAY_AUTH_FAILED"
            : "AI_TEMPORARILY_UNAVAILABLE",
      message: managed
        ? error.message
        : creditsRequired
          ? "서비스 운영자의 AI 크레딧 설정이 필요합니다."
          : gatewayAuthFailed
            ? "서비스 운영자의 AI 인증 설정을 확인해주세요."
            : "AI 서비스가 일시적으로 지연되고 있습니다.",
    });
  }
}
