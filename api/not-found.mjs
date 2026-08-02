const PAGE = `<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <meta name="robots" content="noindex,follow" />
    <title>페이지를 찾을 수 없습니다 · Thread Auto</title>
    <style>
      :root{font-family:Pretendard,"Noto Sans KR",system-ui,sans-serif;color:#1d1c1a;background:#f7f4ee}
      body{min-height:100vh;display:grid;place-items:center;margin:0;padding:24px;text-align:center}
      main{max-width:620px;padding:48px;border:1px solid #d9d3ca;border-radius:22px;background:#fffdf9}
      strong{display:block;color:#a43821;font-size:14px;letter-spacing:.12em}h1{font-size:clamp(36px,7vw,60px);letter-spacing:-.05em}
      p{color:#666159;line-height:1.7}a{display:inline-flex;min-height:48px;align-items:center;padding:0 20px;border-radius:12px;background:#1d1c1a;color:white;font-weight:800;text-decoration:none}
    </style>
  </head>
  <body><main><strong>404 · NOT FOUND</strong><h1>이 페이지는 없어요.</h1><p>주소가 바뀌었거나 삭제된 페이지입니다. 홈에서 최신 다운로드와 공지사항을 확인해 주세요.</p><a href="/">Thread Auto 홈으로</a></main></body>
</html>`;

export default function handler(req, res) {
  res.statusCode = 404;
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=0, s-maxage=60");
  res.end(PAGE);
}
