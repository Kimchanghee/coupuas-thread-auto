import {
  proxyPasswordReset,
  sendPasswordResetResponse,
} from "../_lib/password-reset-proxy.mjs";

export default async function handler(req, res) {
  sendPasswordResetResponse(res, await proxyPasswordReset(req, "request"));
}
