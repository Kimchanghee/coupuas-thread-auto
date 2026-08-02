import assert from "node:assert/strict";
import test from "node:test";

import handler from "../api/not-found.mjs";

test("unknown routes return an index-safe 404 page", () => {
  const headers = {};
  let body = "";
  const response = {
    statusCode: 200,
    setHeader(name, value) { headers[name] = value; },
    end(value) { body = value; },
  };

  handler({}, response);

  assert.equal(response.statusCode, 404);
  assert.match(headers["Content-Type"], /text\/html/);
  assert.match(body, /noindex,follow/);
});
