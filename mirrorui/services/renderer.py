from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from playwright.async_api import async_playwright

from mirrorui.schemas import CapturePayload, DOMNode

STEALTH_INIT_SCRIPT = """
() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
    Object.defineProperty(navigator, 'language', { get: () => 'en-US' });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4] });
    window.chrome = window.chrome || { runtime: {} };

    const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
    if (originalQuery) {
        window.navigator.permissions.query = (parameters) => (
            parameters && parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters)
        );
    }
}
"""

_CAPTURE_SCRIPT = """
() => {
    const MAX_NODES = 1100;
    const interactiveTags = new Set(['a', 'button', 'input', 'select', 'textarea', 'label', 'summary']);
    const challengeHints = [
        'access denied',
        'captcha',
        'verify you are human',
        'checking your browser',
        'press and hold',
        'bot detection',
        'cloudflare',
        'attention required',
    ];

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

    const roleHint = (el) => {
        const tag = el.tagName.toLowerCase();
        if (tag === 'img') return 'image';
        if (interactiveTags.has(tag)) return 'interactive';
        if (tag.match(/^h[1-6]$/)) return 'heading';
        if (tag === 'nav' || el.getAttribute('role') === 'navigation') return 'navigation';
        if (tag === 'header') return 'header';
        if (tag === 'footer') return 'footer';
        if (tag === 'main' || el.getAttribute('role') === 'main') return 'main';
        if (tag === 'section' || tag === 'article') return 'section';
        return '';
    };

    const isInteractive = (el, style) => {
        const tag = el.tagName.toLowerCase();
        const role = (el.getAttribute('role') || '').toLowerCase();
        const tabIndex = Number(el.getAttribute('tabindex') || '-1');
        return interactiveTags.has(tag)
            || ['button', 'link', 'textbox', 'menuitem', 'option', 'tab'].includes(role)
            || tabIndex >= 0
            || style.cursor === 'pointer';
    };

    const depthOf = (el) => {
        let depth = 0;
        let cur = el.parentElement;
        while (cur) {
            depth += 1;
            cur = cur.parentElement;
        }
        return depth;
    };

    const challengeDetected = challengeHints.some((hint) => document.body.innerText.toLowerCase().includes(hint));

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
        const area = rect.width * rect.height;
        const text = directText(el);
        const important = text || children.length || attrs.src || attrs.href || tag === 'img' || interactiveTags.has(tag);
        if (!important && area < 2500) continue;

    nodes.push({
      node_id: `n_${idx}`,
      tag,
            text,
      classes: Array.from(el.classList).slice(0, 20),
      attrs,
      styles: {
        display: style.display,
        position: style.position,
                visibility: style.visibility,
                pointerEvents: style.pointerEvents,
        flexDirection: style.flexDirection,
        flexWrap: style.flexWrap,
                flexGrow: style.flexGrow,
                flexShrink: style.flexShrink,
                flexBasis: style.flexBasis,
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
        fontFamily: style.fontFamily.split(',')[0].trim(),
        color: style.color,
        backgroundColor: style.backgroundColor,
        backgroundImage: style.backgroundImage.length < 200 ? style.backgroundImage : 'none',
                backgroundPosition: style.backgroundPosition,
        backgroundSize: style.backgroundSize,
                backgroundRepeat: style.backgroundRepeat,
        marginTop: style.marginTop,
        marginBottom: style.marginBottom,
        marginLeft: style.marginLeft,
        marginRight: style.marginRight,
        width: style.width,
        height: style.height,
                minWidth: style.minWidth,
                minHeight: style.minHeight,
        maxWidth: style.maxWidth,
                maxHeight: style.maxHeight,
        paddingTop: style.paddingTop,
        paddingBottom: style.paddingBottom,
        paddingLeft: style.paddingLeft,
        paddingRight: style.paddingRight,
        gap: style.gap,
                rowGap: style.rowGap,
                columnGap: style.columnGap,
        justifyContent: style.justifyContent,
        alignItems: style.alignItems,
                alignSelf: style.alignSelf,
        gridTemplateColumns: style.gridTemplateColumns,
                gridTemplateRows: style.gridTemplateRows,
                gridColumn: style.gridColumn,
                gridRow: style.gridRow,
        borderRadius: style.borderRadius,
        borderWidth: style.borderWidth,
        borderStyle: style.borderStyle,
        borderColor: style.borderColor,
        boxShadow: style.boxShadow.length < 100 ? style.boxShadow : 'none',
        lineHeight: style.lineHeight,
                letterSpacing: style.letterSpacing,
        textAlign: style.textAlign,
        textDecoration: style.textDecoration,
        textTransform: style.textTransform,
        opacity: style.opacity,
        overflow: style.overflow,
                overflowX: style.overflowX,
                overflowY: style.overflowY,
        objectFit: style.objectFit,
        left: style.left,
        top: style.top,
                right: style.right,
                bottom: style.bottom,
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
            depth: depthOf(el),
            order: idx,
            interactive: isInteractive(el, style),
            role_hint: roleHint(el),
    });
  }

    return {
        challengeDetected,
        challengeReason: challengeDetected ? 'Page content matched challenge/captcha heuristics.' : '',
        nodes,
    };
}
"""


class PlaywrightRenderer:
    async def capture(self, url: str, screenshot_path: Path) -> CapturePayload:
        capture_results: List[CapturePayload] = []
        strategies = [
            {
                "browser": "chromium",
                "wait_idle": True,
                "accept_lang": "en-US,en;q=0.9",
            },
            {
                "browser": "chromium",
                "wait_idle": False,
                "accept_lang": "en-GB,en;q=0.8",
            },
            {
                "browser": "webkit",
                "wait_idle": False,
                "accept_lang": "en-US,en;q=0.9",
            },
        ]

        async with async_playwright() as p:
            for strategy in strategies:
                try:
                    result = await self._capture_once(p, url, screenshot_path, strategy)
                    capture_results.append(result)

                    if result.dom_nodes and not result.challenge_detected and len(result.dom_nodes) >= 80:
                        return result
                except Exception:
                    continue

        if not capture_results:
            return CapturePayload(
                url=url,
                title="",
                screenshot_path=str(screenshot_path),
                viewport={"width": 1512, "height": 982},
                html="",
                dom_nodes=[],
                challenge_detected=True,
                challenge_reason="All browser capture strategies failed.",
            )

        # Choose the best attempt by most extracted nodes and no challenge hint.
        capture_results.sort(
            key=lambda c: (
                0 if c.challenge_detected else 1,
                len(c.dom_nodes),
            ),
            reverse=True,
        )
        return capture_results[0]

    async def _capture_once(self, playwright, url: str, screenshot_path: Path, strategy: Dict[str, Any]) -> CapturePayload:
        browser_name = strategy.get("browser", "chromium")
        browser_type = getattr(playwright, browser_name)
        browser = await browser_type.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1512, "height": 982},
            locale="en-US",
            timezone_id="America/New_York",
            device_scale_factor=1,
            color_scheme="light",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": strategy.get("accept_lang", "en-US,en;q=0.9"),
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "no-cache",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            },
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        page = await context.new_page()

        await page.route(
            "**/*.{mp4,webm,ogg,mp3,wav,pdf,zip}",
            lambda route: route.abort(),
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass

        if strategy.get("wait_idle", True):
            try:
                await page.wait_for_load_state("networkidle", timeout=7000)
            except Exception:
                pass

        try:
            await page.wait_for_timeout(1400)
        except Exception:
            pass

        # Trigger lazy content and then return to top for stable screenshot.
        try:
            last_height = 0
            for step in range(10):
                await page.mouse.wheel(0, 950)
                await page.wait_for_timeout(230)
                current_height = await page.evaluate("() => document.documentElement.scrollHeight")
                if current_height == last_height and step > 3:
                    break
                last_height = current_height
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(700)
        except Exception:
            pass

        for text in ("Accept", "I agree", "Agree", "OK", "Allow all"):
            try:
                await page.locator("button, [role='button']").filter(has_text=text).first.click(timeout=700)
            except Exception:
                pass

        try:
            await page.screenshot(path=str(screenshot_path), full_page=True, timeout=20000)
        except Exception:
            await page.screenshot(path=str(screenshot_path), full_page=False, timeout=10000)

        try:
            title = await page.title()
        except Exception:
            title = ""

        try:
            html = await page.content()
        except Exception:
            html = ""

        try:
            capture_raw: Dict[str, Any] = await page.evaluate(_CAPTURE_SCRIPT)
        except Exception:
            capture_raw = {"nodes": [], "challengeDetected": False, "challengeReason": ""}

        await context.close()
        await browser.close()

        nodes: List[DOMNode] = []
        for node in capture_raw.get("nodes", []):
            try:
                nodes.append(DOMNode(**node))
            except Exception:
                pass

        challenge_detected = bool(capture_raw.get("challengeDetected", False))
        challenge_reason = str(capture_raw.get("challengeReason", ""))
        if len(nodes) < 25 and not challenge_detected:
            challenge_detected = True
            challenge_reason = "Very low extracted node count; likely challenge/interstitial page."

        return CapturePayload(
            url=url,
            title=title,
            screenshot_path=str(screenshot_path),
            viewport={"width": 1512, "height": 982},
            html=html,
            dom_nodes=nodes,
            challenge_detected=challenge_detected,
            challenge_reason=challenge_reason,
        )
