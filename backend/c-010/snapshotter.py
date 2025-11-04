from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright


class Snapshotter:
    def capture(
        self,
        url: str,
        out_path: str,
        width: int = 1366,
        height: int = 768,
        full_page: bool = True,
        selector: Optional[str] = None,
        wait_until: str = "networkidle",
        timeout_ms: int = 30000,
        delay_ms: int = 0,
        device_scale_factor: float = 1.0,
        emulate_media: Optional[str] = None,
    ) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=device_scale_factor,
            )
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(url, wait_until=wait_until)

            if emulate_media:
                try:
                    page.emulate_media(media=emulate_media)
                except Exception:
                    pass

            if selector:
                page.wait_for_selector(selector)

            if delay_ms and delay_ms > 0:
                page.wait_for_timeout(delay_ms)

            if selector:
                locator = page.locator(selector)
                locator.screenshot(path=out_path)
            else:
                page.screenshot(path=out_path, full_page=full_page)

            meta = {
                "url": url,
                "viewport": {"width": width, "height": height},
                "full_page": full_page,
                "selector": selector,
                "wait_until": wait_until,
                "timeout_ms": timeout_ms,
                "delay_ms": delay_ms,
                "device_scale_factor": device_scale_factor,
                "emulate_media": emulate_media,
                "browser": "chromium",
            }

            context.close()
            browser.close()
        return meta

