const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const test = require("node:test");
const { runInNewContext } = require("node:vm");

test("a starting Minecraft server can be stopped once systemd marks it active", async () => {
    const scriptPath = resolve(__dirname, "../../src/apps/core/static/core/js/minecraft.js");
    const elements = { button: {}, '[role="status"]': {}, '[role="alert"]': {} };
    const { button, '[role="status"]': status } = elements;
    const statuses = [
        { state: "starting", active: false },
        { state: "starting", active: true },
        { state: "stopping", active: false },
    ];
    const submissions = [];
    const confirmations = [];
    let confirmStop = false;
    let submit;
    let poll;
    let delay;
    const form = {
        action: "/services/minecraft/power/",
        querySelector: (selector) => elements[selector],
        addEventListener(type, handler) {
            assert.equal(type, "submit");
            submit = () => handler({ preventDefault() {} });
        },
    };

    runInNewContext(readFileSync(scriptPath, "utf8"), {
        AbortController,
        URLSearchParams,
        FormData: class extends URLSearchParams {
            constructor() {
                super({ csrfmiddlewaretoken: "token" });
            }
        },
        document: { querySelector: () => form },
        window: {
            setTimeout(callback, timeout) {
                poll = callback;
                delay = timeout;
            },
            clearTimeout() {},
            confirm(message) {
                confirmations.push(message);
                return confirmStop;
            },
        },
        async fetch(url, { method, body }) {
            assert.equal(url, form.action);
            if (method === "POST") {
                submissions.push(Object.fromEntries(body));
                return { ok: true, json: async () => ({ state: "stopping" }) };
            }
            return { ok: true, json: async () => statuses.shift() };
        },
    });
    await new Promise(setImmediate);

    assert.equal(status.textContent, "Startet…");
    assert.equal(button.disabled, true);
    assert.equal(delay, 2500);

    await poll();
    assert.equal(status.textContent, "Startet…");
    assert.equal(button.textContent, "Stoppen");
    assert.equal(button.disabled, false);
    assert.equal(delay, 2500);

    await submit();
    const prompt = "Minecraft stoppen? Wer gerade spielt, fliegt raus.";
    assert.deepEqual(confirmations, [prompt]);
    assert.deepEqual(submissions, []);

    confirmStop = true;
    await submit();
    assert.deepEqual(confirmations, [prompt, prompt]);
    assert.deepEqual(submissions, [{ csrfmiddlewaretoken: "token", action: "stop" }]);
    assert.equal(button.disabled, true);

    await poll();
    assert.equal(status.textContent, "Stoppt…");
    assert.equal(button.disabled, true);
    assert.equal(delay, 2500);
});
