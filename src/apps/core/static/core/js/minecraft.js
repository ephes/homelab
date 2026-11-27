(() => {
    const form = document.querySelector("#minecraft-power");
    const button = form.querySelector("button");
    const status = form.querySelector('[role="status"]');
    const error = form.querySelector('[role="alert"]');
    const labels = {
        off: "Aus",
        starting: "Startet…",
        running: "Läuft",
        stopping: "Stoppt…",
        unknown: "Unbekannt",
    };
    let timer;
    let statusRequest;

    function render(state, active = false) {
        const canStop = active && state !== "stopping";
        status.textContent = labels[state] ?? labels.unknown;
        button.value = canStop || state === "stopping" ? "stop" : "start";
        button.textContent = button.value === "stop" ? "Stoppen" : "Starten";
        button.disabled = state !== "off" && !canStop;
    }

    async function refresh() {
        statusRequest = new AbortController();
        const { signal } = statusRequest;
        let state = "unknown";
        let active = false;
        try {
            const response = await fetch(form.action, { signal });
            if (response.ok) {
                ({ state, active } = await response.json());
            }
        } catch {
            // A failed status request is shown as unknown and retried later.
        }

        if (!signal.aborted) {
            render(state, active);
            const transitioning = state === "starting" || state === "stopping";
            timer = window.setTimeout(refresh, transitioning ? 2500 : 30000);
        }
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (button.disabled) return;

        const action = button.value;
        if (action === "stop" && !window.confirm("Minecraft stoppen? Wer gerade spielt, fliegt raus.")) return;

        window.clearTimeout(timer);
        statusRequest.abort();
        render(action === "start" ? "starting" : "stopping");
        error.textContent = "";

        const body = new URLSearchParams(new FormData(form));
        body.set("action", action);
        let state = "unknown";
        let message = "Minecraft-Befehl fehlgeschlagen.";
        try {
            const response = await fetch(form.action, { method: "POST", body });
            const data = await response.json();
            if (response.ok) {
                state = data.state;
                message = "";
            } else {
                message = data.error ?? message;
            }
        } catch {
            // Keep the fallback message for network and non-JSON responses.
        }
        render(state);
        error.textContent = message;
        timer = window.setTimeout(refresh, 2500);
    });

    refresh();
})();
