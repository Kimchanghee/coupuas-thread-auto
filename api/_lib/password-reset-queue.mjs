import {
  createCipheriv,
  createDecipheriv,
  createHash,
  createHmac,
  randomBytes,
  randomUUID,
} from "node:crypto";

import { QueueClient, send } from "@vercel/queue";


export const PASSWORD_RESET_TOPIC = "thread-pilot-password-reset";
const AUTH_PROCESS_URL =
  "https://newshopping-shorts-auth.vercel.app/user/password-reset/process";

export class PermanentPasswordResetQueueError extends Error {}

function workerSignature(timestamp, message, secret) {
  return createHmac("sha256", secret)
    .update(
      [
        timestamp,
        "password-reset-process",
        message.request_id,
        message.identifier,
        message.program_type,
        message.ip_address,
      ].join("\n"),
    )
    .digest("hex");
}

function queueKey(secret) {
  return createHash("sha256").update(`password-reset-queue:${secret}`).digest();
}

export function createPasswordResetQueueMessage(
  { identifier, ipAddress },
  { requestId = randomUUID(), randomBytesImpl = randomBytes } = {},
) {
  const secret = String(process.env.PASSWORD_RESET_PROXY_SECRET || "").trim();
  if (secret.length < 32) throw new Error("password reset queue is not configured");
  const payload = {
    request_id: requestId,
    identifier,
    program_type: "stmaker",
    ip_address: ipAddress,
  };
  const iv = randomBytesImpl(12);
  const cipher = createCipheriv("aes-256-gcm", queueKey(secret), iv);
  const ciphertext = Buffer.concat([
    cipher.update(JSON.stringify(payload), "utf8"),
    cipher.final(),
  ]);
  return {
    v: 1,
    request_id: requestId,
    iv: iv.toString("base64url"),
    tag: cipher.getAuthTag().toString("base64url"),
    ciphertext: ciphertext.toString("base64url"),
  };
}

function decryptPasswordResetQueueMessage(envelope, secret) {
  if (
    !envelope ||
    envelope.v !== 1 ||
    typeof envelope.request_id !== "string" ||
    typeof envelope.iv !== "string" ||
    typeof envelope.tag !== "string" ||
    typeof envelope.ciphertext !== "string"
  ) {
    throw new Error("invalid password reset queue envelope");
  }
  const decipher = createDecipheriv(
    "aes-256-gcm",
    queueKey(secret),
    Buffer.from(envelope.iv, "base64url"),
  );
  decipher.setAuthTag(Buffer.from(envelope.tag, "base64url"));
  const plaintext = Buffer.concat([
    decipher.update(Buffer.from(envelope.ciphertext, "base64url")),
    decipher.final(),
  ]).toString("utf8");
  const message = JSON.parse(plaintext);
  if (message.request_id !== envelope.request_id) {
    throw new Error("password reset queue envelope mismatch");
  }
  return message;
}

export async function enqueuePasswordReset(message) {
  return send(PASSWORD_RESET_TOPIC, message, {
    idempotencyKey: message.request_id,
    retentionSeconds: 86_400,
  });
}

export async function processPasswordResetQueueMessage(
  envelope,
  { fetchImpl = globalThis.fetch, nowImpl = Date.now } = {},
) {
  const secret = String(process.env.PASSWORD_RESET_PROXY_SECRET || "").trim();
  if (secret.length < 32) throw new Error("password reset worker is not configured");
  const message = decryptPasswordResetQueueMessage(envelope, secret);
  if (
    !message ||
    typeof message.request_id !== "string" ||
    typeof message.identifier !== "string" ||
    message.program_type !== "stmaker" ||
    typeof message.ip_address !== "string"
  ) {
    throw new Error("invalid password reset queue message");
  }

  const timestamp = String(Math.floor(nowImpl() / 1000));
  const response = await fetchImpl(AUTH_PROCESS_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      "X-Reset-Worker-Timestamp": timestamp,
      "X-Reset-Worker-Signature": workerSignature(timestamp, message, secret),
    },
    body: JSON.stringify(message),
    redirect: "error",
    signal: AbortSignal.timeout(15_000),
  });
  if (!response.ok) {
    if (response.status >= 400 && response.status < 500 && ![408, 409, 429].includes(response.status)) {
      throw new PermanentPasswordResetQueueError("password reset worker rejected the message");
    }
    throw new Error("password reset delivery worker failed");
  }
}

export function passwordResetRetryDirective(error, metadata) {
  if (error instanceof PermanentPasswordResetQueueError) return { acknowledge: true };
  return {
    afterSeconds: Math.min(300, 5 * 2 ** Math.min(metadata.deliveryCount, 6)),
  };
}

const queue = new QueueClient({ region: process.env.VERCEL_REGION || "iad1" });

export const passwordResetQueueHandler = queue.handleNodeCallback(
  async (message) => processPasswordResetQueueMessage(message),
  {
    visibilityTimeoutSeconds: 60,
    retry: passwordResetRetryDirective,
  },
);
