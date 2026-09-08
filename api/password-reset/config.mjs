import { passwordResetCaptchaConfiguration } from "../_lib/password-reset-rate-limit.mjs";
export default function handler(req, res) {
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "GET") { res.statusCode = 405; res.setHeader("Allow", "GET"); res.end('{}'); return; }
  try {
    const { siteKey } = passwordResetCaptchaConfiguration();
    res.statusCode = 200;
    res.end(JSON.stringify({ siteKey }));
  } catch { res.statusCode = 503; res.end(JSON.stringify({ message: "복구 서비스를 준비 중입니다. 잠시 후 다시 시도해 주세요." })); }
}
