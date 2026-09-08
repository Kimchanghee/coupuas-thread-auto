(() => {
  const page = document.body.dataset.recoveryPage;
  const form = document.querySelector("#recovery-form");
  const button = document.querySelector("#submit-button");
  const status = document.querySelector("#status");
  let resetToken = "";
  let captchaToken = "";
  let captchaWidget;
  if (page === "request") {
    button.disabled = true;
    window.recoveryCaptchaReady = async () => {
      try {
        const response = await fetch("/api/password-reset/config", { cache: "no-store", credentials: "omit" });
        if (!response.ok) throw new Error("계정 복구를 준비할 수 없습니다. 잠시 후 다시 시도해 주세요.");
        const config = await response.json();
        captchaWidget = window.turnstile.render("#recovery-captcha", {
          sitekey: config.siteKey, action: "password_reset",
          callback: token => { captchaToken = token; button.disabled = false; },
          "expired-callback": () => { captchaToken = ""; button.disabled = true; },
          "error-callback": () => { captchaToken = ""; button.disabled = true; showStatus("보안 확인을 다시 시도해 주세요.", "error"); },
        });
      } catch (error) { showStatus(error.message, "error"); }
    };
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=recoveryCaptchaReady&render=explicit";
    script.onerror = () => showStatus("보안 확인을 불러올 수 없습니다. 새로고침해 주세요.", "error");
    document.head.appendChild(script);
  }

  const showStatus = (message, kind) => {
    status.textContent = message;
    status.dataset.kind = kind;
  };

  const postJson = async (url, payload) => {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "omit",
      cache: "no-store",
      body: JSON.stringify(payload),
    });
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    return { response, data };
  };

  if (page === "confirm") {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    resetToken = fragment.get("token") || "";
    history.replaceState(null, "", window.location.pathname);
    if (!/^[A-Za-z0-9_-]{32,256}$/.test(resetToken)) {
      form.hidden = true;
      showStatus("재설정 링크가 올바르지 않거나 만료되었습니다. 새 링크를 요청해 주세요.", "error");
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    button.disabled = true;
    showStatus("안전하게 확인하고 있습니다…", "info");

    try {
      if (page === "request") {
        if (!captchaToken) throw new Error("보안 확인을 완료해 주세요.");
        const identifier = document.querySelector("#identifier").value.trim();
        const { response, data } = await postJson("/api/password-reset/request", {
          identifier,
          program_type: "stmaker",
          captcha_token: captchaToken,
        });
        if (!response.ok && response.status !== 202) {
          throw new Error(data.message || "지금은 재설정 메일을 보낼 수 없습니다. 잠시 후 다시 시도해 주세요.");
        }
        form.hidden = true;
        showStatus(
          data.message || "계정이 확인되면 비밀번호 재설정 메일을 보내드립니다.",
          "success",
        );
      } else {
        const password = document.querySelector("#password").value;
        const confirmation = document.querySelector("#password-confirm").value;
        if (password.length < 15 || password.length > 128) {
          throw new Error("새 비밀번호는 15~128자로 입력해주세요.");
        }
        if (password !== confirmation) {
          throw new Error("새 비밀번호가 서로 일치하지 않습니다.");
        }
        const { response, data } = await postJson("/api/password-reset/confirm", {
          token: resetToken,
          password,
        });
        if (!response.ok) {
          throw new Error(data.message || "재설정 링크가 올바르지 않거나 만료되었습니다.");
        }
        resetToken = "";
        form.reset();
        form.hidden = true;
        showStatus(data.message || "비밀번호가 변경되었습니다. 앱에서 다시 로그인해 주세요.", "success");
      }
    } catch (error) {
      showStatus(error?.message || "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.", "error");
      if (page === "request") {
        captchaToken = "";
        button.disabled = true;
        if (captchaWidget !== undefined) window.turnstile.reset(captchaWidget);
      } else button.disabled = false;
    }
  });
})();
