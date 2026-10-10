(() => {
  const measurementId = "G-TQ30XL5VX0";
  const consentKey = "thread-auto-analytics-consent-v1";
  const cookieSuffix = measurementId.replace(/^G-/, "").replaceAll("-", "_");
  let lastPageView = "";

  // Password recovery URLs can contain account tokens, so never send those pages to Analytics.
  if (/^\/(?:forgot-password|reset-password)(?:\/|$)/i.test(window.location.pathname)) return;

  const getChoice = () => {
    try {
      return window.localStorage.getItem(consentKey);
    } catch (_error) {
      return "denied";
    }
  };

  const cleanUrl = (value) => {
    if (!value) return "";
    try {
      const url = new URL(value, window.location.origin);
      url.search = "";
      url.hash = "";
      return url.toString();
    } catch (_error) {
      return "";
    }
  };

  const sendPageView = () => {
    if (typeof window.gtag !== "function") return;
    const pageLocation = cleanUrl(window.location.href);
    if (!pageLocation || pageLocation === lastPageView) return;
    window.gtag("event", "page_view", {
      page_location: pageLocation,
      page_referrer: cleanUrl(document.referrer),
    });
    lastPageView = pageLocation;
  };

  const loadAnalytics = () => {
    if (window.__threadAutoAnalyticsLoaded) return;
    window.__threadAutoAnalyticsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
      window.dataLayer.push(arguments);
    };
    window.gtag("consent", "default", {
      analytics_storage: "granted",
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
    });
    window.gtag("js", new Date());
    window.gtag("config", measurementId, {
      page_location: cleanUrl(window.location.href),
      page_referrer: cleanUrl(document.referrer),
      send_page_view: false,
      cookie_expires: 60 * 60 * 24 * 60,
      cookie_update: false,
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
    });

    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(measurementId)}`;
    script.referrerPolicy = "no-referrer";
    document.head.appendChild(script);
    sendPageView();
  };

  const clearAnalyticsCookies = () => {
    const cookieNames = ["_ga", `_ga_${cookieSuffix}`];
    const host = window.location.hostname;
    const domains = ["", `; domain=${host}`, `; domain=.${host}`];
    for (const name of cookieNames) {
      for (const domain of domains) {
        document.cookie = `${name}=; Max-Age=0; path=/${domain}; SameSite=Lax; Secure`;
      }
    }
  };

  const makeButton = (label, choice, onClick) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (choice) button.dataset.consent = choice;
    button.addEventListener("click", onClick);
    return button;
  };

  const setChoice = (choice) => {
    try {
      window.localStorage.setItem(consentKey, choice);
    } catch (_error) {
      // If the choice cannot be saved, keep Analytics disabled for this visit.
      if (choice === "granted") return;
    }
    if (choice === "granted") {
      loadAnalytics();
      if (typeof window.gtag === "function") {
        window.gtag("consent", "update", {
          analytics_storage: "granted",
          ad_storage: "denied",
          ad_user_data: "denied",
          ad_personalization: "denied",
        });
      }
      sendPageView();
    } else {
      if (typeof window.gtag === "function") {
        window.gtag("consent", "update", {
          analytics_storage: "denied",
          ad_storage: "denied",
          ad_user_data: "denied",
          ad_personalization: "denied",
        });
      }
      lastPageView = "";
      clearAnalyticsCookies();
    }
  };

  const showBanner = () => {
    document.getElementById("analytics-consent-banner")?.remove();
    const banner = document.createElement("aside");
    banner.id = "analytics-consent-banner";
    banner.className = "analytics-consent-banner";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-label", "쿠키 및 분석 설정");

    const copy = document.createElement("p");
    copy.className = "analytics-consent-copy";
    copy.append(
      document.createTextNode(
        "방문 통계를 위해 페이지 조회, 브라우저·기기 정보와 대략적인 위치를 Google Analytics로 전송합니다. 분석 쿠키는 동의한 경우에만 사용합니다. "
      )
    );
    const privacy = document.createElement("a");
    privacy.href = "/privacy";
    privacy.textContent = "개인정보처리방침";
    copy.append(privacy);

    const actions = document.createElement("div");
    actions.className = "analytics-consent-actions";
    actions.append(
      makeButton("거부", "denied", () => {
        setChoice("denied");
        banner.remove();
        showManageButton();
      }),
      makeButton("분석 허용", "granted", () => {
        setChoice("granted");
        banner.remove();
        showManageButton();
      })
    );
    banner.append(copy, actions);
    document.body.append(banner);
  };

  const showManageButton = () => {
    if (document.getElementById("analytics-consent-manage")) return;
    const button = document.createElement("button");
    button.id = "analytics-consent-manage";
    button.className = "analytics-consent-manage";
    button.type = "button";
    button.textContent = "쿠키 설정";
    button.addEventListener("click", showBanner);
    document.body.append(button);
  };

  if (getChoice() === "granted") loadAnalytics();
  showManageButton();
  if (getChoice() !== "granted" && getChoice() !== "denied") showBanner();

  document.querySelectorAll("[data-analytics]").forEach((node) => {
    node.addEventListener("click", () => {
      if (getChoice() !== "granted" || typeof window.gtag !== "function") return;
      window.gtag("event", node.dataset.analytics, { transport_type: "beacon" });
    });
  });
})();
