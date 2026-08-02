async function refreshLatestRelease() {
  try {
    const response = await fetch("/api/notices", { headers: { Accept: "application/json" } });
    if (!response.ok) return;
    const payload = await response.json();
    const latest = payload.latest;
    if (!latest) return;
    const latestDownloadUrl = payload.latestDownloadUrl || latest.downloadUrl;
    document.querySelectorAll("[data-latest-version]").forEach((node) => {
      node.textContent = `v${latest.version} · 최신 버전`;
    });
    document.querySelectorAll("[data-download-link]").forEach((node) => {
      if (latestDownloadUrl) node.href = latestDownloadUrl;
    });
    const list = document.getElementById("home-notice-list");
    if (!list) return;
    list.replaceChildren();
    for (const post of (payload.posts || []).slice(0, 3)) {
      const link = document.createElement("a");
      link.className = "home-notice-card";
      link.href = `/notices?id=${encodeURIComponent(post.id)}`;
      const badge = document.createElement("span");
      badge.className = `home-notice-badge ${post.kind === "event" ? "event" : ""}`;
      badge.textContent = post.badge;
      const title = document.createElement("strong");
      title.textContent = post.title;
      const summary = document.createElement("span");
      summary.textContent = post.summary;
      link.append(badge, title, summary);
      list.append(link);
    }
  } catch (_error) {
    // Static latest-download links remain usable when the release API is unavailable.
  }
}

refreshLatestRelease();
