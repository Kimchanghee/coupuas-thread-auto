import { initializePasswordReset } from "./password-reset-controller.mjs";
initializePasswordReset({ window, document, fetch: window.fetch.bind(window) });
