import { isIP } from "node:net";

import {
  createPasswordResetQueueMessage,
  enqueuePasswordReset,
} from "./password-reset-queue.mjs";

const AUTH_BASE_URL = "https://newshopping-shorts-auth.vercel.app";

function parseBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  if (typeof req.body === "string" && req.body.length <= 4_096) {
    try {
      return JSON.parse(req.body);
    } catch {
      return null;
    }
  }
  return null;
}

function safeMessage(status, payload) {
  if (status === 200) {
    return payload?.message || "비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.";
  }
  if (status === 202) {
    return payload?.message || "계정이 확인되면 비밀번호 재설정 메일을 보내드립니다.";
  }
  if (status === 400) {
    return "재설정 링크가 올바르지 않거나 만료되었습니다.";
  }
  if (status === 429) {
    return "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
  }
  return "비밀번호 재설정 서비스를 잠시 사용할 수 없습니다.";
}

function canonicalIp(value) {
  const version = isIP(value);
  if (version === 4) return new URL(`http://${value}`).hostname;
  if (version === 6) return new URL(`http://[${value}]/`).hostname.slice(1, -1).toLowerCase();
  return null;
}

export async function proxyPasswordReset(
  req,
  action,
  { fetchImpl = globalThis.fetch, enqueueImpl = enqueuePasswordReset } = {},
) {
  if (req.method !== "POST") {
    return { status: 405, body: { success: false, message: "허용되지 않은 요청입니다." } };
  }
  const contentType = String(req.headers?.["content-type"] || "").toLowerCase();
  if (!contentType.startsWith("application/json")) {
    return { status: 415, body: { success: false, message: "입력값을 다시 확인해 주세요." } };
  }
  const body = parseBody(req);
  if (!body || JSON.stringify(body).length > 2_048) {
    return { status: 400, body: { success: false, message: "입력값을 다시 확인해 주세요." } };
  }
  const isRequest = action === "request";
  const validRequest =
    body &&
    typeof body.identifier === "string" &&
    /^[a-z0-9_@.+-]{3,255}$/i.test(body.identifier.trim()) &&
    body.program_type === "stmaker";
  const validConfirm =
    body &&
    typeof body.token === "string" &&
    /^[A-Za-z0-9_-]{32,256}$/.test(body.token) &&
    typeof body.password === "string" &&
    body.password.length >= 8 &&
    body.password.length <= 128;
  if ((isRequest && !validRequest) || (!isRequest && !validConfirm)) {
    return { status: 400, body: { success: false, message: "입력값을 다시 확인해 주세요." } };
  }

  const outboundBody = isRequest
    ? { identifier: body.identifier.trim().toLowerCase(), program_type: "stmaker" }
    : { token: body.token, password: body.password };
  const forwardedFor = String(req.headers?.["x-forwarded-for"] || "")
    .split(",")[0]
    .trim();
  const clientIp = canonicalIp(forwardedFor);
  const proxySecret = String(process.env.PASSWORD_RESET_PROXY_SECRET || "").trim();
  if (proxySecret.length < 32) {
    return {
      status: 503,
      body: { success: false, message: "비밀번호 재설정 서비스를 잠시 사용할 수 없습니다." },
    };
  }
  if (isRequest) {
    if (!clientIp) {
      return {
        status: 503,
        body: { success: false, message: "비밀번호 재설정 서비스를 잠시 사용할 수 없습니다." },
      };
    }
    try {
      await enqueueImpl(
        createPasswordResetQueueMessage({
          identifier: outboundBody.identifier,
          ipAddress: clientIp,
        }),
      );
      return {
        status: 202,
        body: {
          success: true,
          message: "계정이 확인되면 비밀번호 재설정 메일을 보내드립니다.",
        },
      };
    } catch {
      return {
        status: 503,
        body: { success: false, message: "비밀번호 재설정 서비스를 잠시 사용할 수 없습니다." },
      };
    }
  }

  const headers = { "Content-Type": "application/json", Accept: "application/json" };

  try {
    const upstream = await fetchImpl(`${AUTH_BASE_URL}/user/password-reset/${action}`, {
      method: "POST",
      headers,
      body: JSON.stringify(outboundBody),
      redirect: "error",
      signal: AbortSignal.timeout(12_000),
    });
    let payload = {};
    try {
      payload = await upstream.json();
    } catch {
      payload = {};
    }
    const allowedStatus = [200, 202, 400, 429, 503].includes(upstream.status)
      ? upstream.status
      : 503;
    return {
      status: allowedStatus,
      body: {
        success: Boolean(upstream.ok && payload?.success),
        message: safeMessage(allowedStatus, payload),
      },
    };
  } catch {
    return {
      status: 503,
      body: {
        success: false,
        message: "비밀번호 재설정 서비스를 잠시 사용할 수 없습니다.",
      },
    };
  }
}

export function sendPasswordResetResponse(res, result) {
  res.statusCode = result.status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  if (result.status === 405) res.setHeader("Allow", "POST");
  res.end(JSON.stringify(result.body));
}
