const state = { posts: [], filter: "all", latest: null };

function el(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text != null) node.textContent = String(options.text);
  if (options.href) node.href = options.href;
  if (options.target) node.target = options.target;
  if (options.rel) node.rel = options.rel;
  for (const [name, value] of Object.entries(options.attrs || {})) node.setAttribute(name, value);
  for (const child of Array.isArray(children) ? children : [children]) if (child) node.append(child);
  return node;
}

function cleanInlineMarkdown(value) {
  return String(value || "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`~]/g, "")
    .trim();
}

function formatDate(value) {
  const date = new Date(value || 0);
  if (Number.isNaN(date.getTime())) return "날짜 미정";
  return new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric" }).format(date);
}

function badge(post) {
  const labels = [el("span", { className: `badge ${post.kind === "event" ? "event" : ""}`, text: post.badge })];
  if (post.kind === "event" && post.eventStatus) labels.push(el("span", { className: "badge status", text: post.eventStatus }));
  return el("div", { className: "post-kind" }, labels);
}

function detailUrl(post) {
  return `/notices?id=${encodeURIComponent(post.id)}`;
}

function renderLatest(post) {
  const root = document.getElementById("latest-post");
  root.replaceChildren();
  if (!post) return;
  const copy = el("div", {}, [
    badge(post),
    el("h2", { text: post.title }),
    el("p", { text: post.summary }),
    el("a", { className: "back-link", text: "업데이트 내용 자세히 보기 →", href: detailUrl(post) }),
  ]);
  const actions = el("div", { className: "latest-actions" }, [
    el("strong", { text: `v${post.version || "최신"}` }),
    el("a", { className: "button accent", text: "Windows 다운로드", href: post.downloadUrl }),
    post.checksumUrl ? el("a", { className: "button ghost", text: "SHA-256 확인", href: post.checksumUrl }) : null,
  ]);
  root.append(el("article", { className: "latest-card" }, [copy, actions]));
}

function renderList() {
  const root = document.getElementById("post-list");
  const filtered = state.posts.filter((post) => state.filter === "all" || post.kind === state.filter);
  root.replaceChildren();
  if (!filtered.length) {
    root.append(el("div", { className: "empty", text: "이 분류에 등록된 게시글이 없습니다." }));
    return;
  }
  for (const post of filtered) {
    const copy = el("div", { className: "post-copy" }, [el("h2", { text: post.title }), el("p", { text: post.summary })]);
    const meta = el("div", { className: "post-meta", text: `${formatDate(post.publishedAt)}${post.version ? ` · v${post.version}` : ""}` });
    root.append(el("a", { className: "post-row", href: detailUrl(post) }, [badge(post), el("div", {}, [copy, meta]), el("span", { className: "post-arrow", text: "→", attrs: { "aria-hidden": "true" } })]));
  }
}

function renderBody(body) {
  const fragment = document.createDocumentFragment();
  const lines = String(body || "").split(/\r?\n/);
  let list = null;
  const flushList = () => { if (list) { fragment.append(list); list = null; } };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith("<!--")) { flushList(); continue; }
    if (/^###\s+/.test(line)) { flushList(); fragment.append(el("h3", { text: cleanInlineMarkdown(line.replace(/^###\s+/, "")) })); continue; }
    if (/^##\s+/.test(line)) { flushList(); fragment.append(el("h2", { text: cleanInlineMarkdown(line.replace(/^##\s+/, "")) })); continue; }
    if (/^[-*]\s+/.test(line)) {
      if (!list) list = el("ul");
      list.append(el("li", { text: cleanInlineMarkdown(line.replace(/^[-*]\s+/, "")) }));
      continue;
    }
    flushList();
    fragment.append(el("p", { text: cleanInlineMarkdown(line) }));
  }
  flushList();
  return fragment;
}

function renderDetail(post) {
  document.getElementById("board-list-view").hidden = true;
  document.getElementById("board-detail-view").hidden = false;
  document.title = `${post.title} · Thread Auto`;
  const header = el("header", {}, [badge(post), el("h1", { text: post.title }), el("div", { className: "article-meta", text: `${formatDate(post.publishedAt)}${post.version ? ` · v${post.version}` : ""}` })]);
  const body = el("div", { className: "article-body" });
  body.append(renderBody(post.body));
  const ctaUrl = post.kind === "release" ? post.downloadUrl : post.ctaUrl;
  const cta = ctaUrl ? el("div", { className: "article-cta" }, [
    el("div", {}, [el("strong", { text: post.kind === "release" ? "최신 버전으로 업데이트하세요." : "이벤트에 참여해 보세요." }), el("p", { text: post.kind === "release" ? "설정과 계정별 대기열은 유지됩니다." : post.summary })]),
    el("a", { className: "button accent", text: post.kind === "release" ? "Windows 다운로드" : (post.ctaLabel || "참여하기"), href: ctaUrl, target: "_blank", rel: "noopener noreferrer" }),
  ]) : null;
  const source = post.sourceUrl ? el("a", { className: "back-link", text: "GitHub 원문 보기 ↗", href: post.sourceUrl, target: "_blank", rel: "noopener noreferrer" }) : null;
  document.getElementById("post-detail").replaceChildren(el("article", { className: "article" }, [header, body, cta, source]));
}

async function loadBoard() {
  const id = new URLSearchParams(location.search).get("id");
  try {
    const response = await fetch(id ? `/api/notices?id=${encodeURIComponent(id)}` : "/api/notices", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    const latest = data.latest || null;
    if (latest?.version) document.querySelectorAll("[data-latest-version]").forEach((node) => { node.textContent = `v${latest.version}`; });
    document.querySelectorAll("[data-download-link]").forEach((node) => { if (latest?.downloadUrl) node.href = latest.downloadUrl; });
    if (id) { renderDetail(data.post); return; }
    state.latest = latest;
    state.posts = Array.isArray(data.posts) ? data.posts : [];
    const author = document.getElementById("event-author-link");
    if (author && data.eventAuthorUrl) author.href = data.eventAuthorUrl;
    renderLatest(state.latest);
    renderList();
  } catch (_error) {
    const target = id ? document.getElementById("post-detail") : document.getElementById("post-list");
    if (id) { document.getElementById("board-list-view").hidden = true; document.getElementById("board-detail-view").hidden = false; }
    target.replaceChildren(el("div", { className: "error", text: "공지사항을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요." }));
  }
}

document.querySelectorAll("[data-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    state.filter = button.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
    renderList();
  });
});

loadBoard();
