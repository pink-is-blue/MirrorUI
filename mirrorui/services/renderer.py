from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from playwright.async_api import async_playwright

from mirrorui.schemas import CapturePayload, DOMNode

# Capture at most 700 meaningful visible elements.
# We skip tiny / invisible elements early in JS to keep the evaluate() call fast.
_CAPTURE_SCRIPT = """
() => {
  const MAX_NODES = 700;

  const directText = (el) => {
    let t = '';
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        const v = (node.textContent || '').replace(/\\s+/g, ' ').trim();
        if (v) t += (t ? ' ' : '') + v;
      }
    }
    return t.slice(0, 200);
  };

  // First pass: assign IDs to all elements.
  const all = Array.from(document.querySelectorAll('*'));
  const idMap = new Map();
  all.forEach((el, idx) => idMap.set(el, `n_${idx}`));

  const nodes = [];

  for (let idx = 0; idx < all.length && nodes.length < MAX_NODES; idx++) {
    const el = all[idx];
    const tag = el.tagName.toLowerCase();

    // Skip script / style / meta / noscript nodes entirely.
    if (['script','style','meta','link','noscript','head','br','wbr'].includes(tag)) continue;

    const rect = el.getBoundingClientRect();
    // Skip truly invisible or zero-size elements (fast path, no computed style).
    if (rect.width < 2 && rect.height < 2) continue;

    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') <= 0) continue;

    const attrs = {};
    for (const a of el.attributes) {
      if (['id','href','src','alt','type','placeholder','aria-label','role','data-id'].includes(a.name))
        attrs[a.name] = a.value;
    }

    const children = Array.from(el.children).map(c => idMap.get(c)).filter(Boolean);
    const parentId = el.parentElement ? idMap.get(el.parentElement) : null;

    nodes.push({
      node_id: `n_${idx}`,
      tag,
      text: directText(el),
      classes: Array.from(el.classList).slice(0, 20),
      attrs,
      styles: {
        display: style.display,
        position: style.position,
        flexDirection: style.flexDirection,
        flexWrap: style.flexWrap,
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
        fontFamily: style.fontFamily.split(',')[0].trim(),
        color: style.color,
        backgroundColor: style.backgroundColor,
        backgroundImage: style.backgroundImage.length < 200 ? style.backgroundImage : 'none',
        backgroundSize: style.backgroundSize,
        marginTop: style.marginTop,
        marginBottom: style.marginBottom,
        marginLeft: style.marginLeft,
        marginRight: style.marginRight,
        width: style.width,
        height: style.height,
        maxWidth: style.maxWidth,
        paddingTop: style.paddingTop,
        paddingBottom: style.paddingBottom,
        paddingLeft: style.paddingLeft,
        paddingRight: style.paddingRight,
        gap: style.gap,
        justifyContent: style.justifyContent,
        alignItems: style.alignItems,
        gridTemplateColumns: style.gridTemplateColumns,
        borderRadius: style.borderRadius,
        borderWidth: style.borderWidth,
        borderStyle: style.borderStyle,
        borderColor: style.borderColor,
        boxShadow: style.boxShadow.length < 100 ? style.boxShadow : 'none',
        lineHeight: style.lineHeight,
        textAlign: style.textAlign,
        textDecoration: style.textDecoration,
        textTransform: style.textTransform,
        opacity: style.opacity,
        overflow: style.overflow,
        objectFit: style.objectFit,
        left: style.left,
        top: style.top,
        zIndex: style.zIndex,
      },
      box: {
        x: Math.round(rect.x + window.scrollX),
        y: Math.round(rect.y + window.scrollY),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
      children,
      parent_id: parentId,
      visible: true,
    });
  }

  return nodes;
}
"""


class PlaywrightRenderer:
    async def capture(self, url: str, screenshot_path: Path) -> CapturePayload:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page(viewport={"width": 1440, "height": 900})

            # Block heavy assets to speed up load — we only need DOM and layout.
            await page.route(
                "**/*.{mp4,webm,ogg,mp3,wav,pdf,zip,woff,woff2,ttf,eot}",
                lambda route: route.abort(),
            )

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass  # Even a partial load is enough for DOM capture.

            # Short networkidle wait — don't block long.
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            # Scroll to trigger lazy-loaded images.
            try:
                for _ in range(6):
                    await page.mouse.wheel(0, 900)
                    await page.wait_for_timeout(150)
                await page.evaluate("window.scrollTo(0,0)")
                await page.wait_for_timeout(300)
            except Exception:
                pass

            try:
                await page.screenshot(path=str(screenshot_path), full_page=True, timeout=20000)
            except Exception:
                await page.screenshot(path=str(screenshot_path), full_page=False, timeout=10000)

            title = await page.title()

            try:
                html = await page.content()
            except Exception:
                html = ""

            try:
                dom_raw: list = await page.evaluate(_CAPTURE_SCRIPT)
            except Exception:
                dom_raw = []

            await browser.close()

        nodes = []
        for node in dom_raw:
            try:
                nodes.append(DOMNode(**node))
            except Exception:
                pass

        return CapturePayload(
            url=url,
            title=title,
            screenshot_path=str(screenshot_path),
            viewport={"width": 1440, "height": 900},
            html=html,
            dom_nodes=nodes,
        )
