
from playwright.async_api import async_playwright

async def capture(url: str, screenshot_path: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await page.goto(url, wait_until="networkidle", timeout=60000)
        for _ in range(10):
            await page.mouse.wheel(0, 1000); await page.wait_for_timeout(150)
        await page.screenshot(path=screenshot_path, full_page=True)
        html = await page.content()
        title = await page.title()
        await browser.close()
    return html, screenshot_path, title
