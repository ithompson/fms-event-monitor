import asyncio
from playwright.async_api import async_playwright

FIELD_MONITOR_SCRIPT = """
console.log('Field monitor script loaded');

document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM loaded");

    function installTextStateObserver(name, node) {
        let current_text = "";
        let observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.addedNodes.length === 1) {
                    let new_text = mutation.addedNodes[0].textContent;
                    if (new_text !== current_text) {
                        current_text = new_text;
                        window.__monitorCallback({field: name, value: new_text});
                    }
                }
            });
        });
        observer.observe(node, { childList: true });
        console.log(`Observer installed for ${name}`);
    }

    installTextStateObserver("match_state", document.querySelector("#matchStateTop"));
    installTextStateObserver("match_number", document.querySelector("#MatchNumber"));
});
"""

class FieldMonitor:
    def __init__(self, event_queue: asyncio.Queue, fms_address: str):
        self._event_queue = event_queue
        self._fms_address = fms_address

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            page.on("console", self._console_callback)

            await page.expose_function("__monitorCallback", self._monitor_callback)
            await page.add_init_script(FIELD_MONITOR_SCRIPT)

            await page.goto(f"http://{self._fms_address}/FieldMonitor")
            await page.screenshot(path="example.png")
            await asyncio.sleep(1000)
            #await browser.close()

    async def _monitor_callback(self, event):
        print(f"Received event: {event}")

    async def _console_callback(self, message):
        print(f"Console message: {message}")