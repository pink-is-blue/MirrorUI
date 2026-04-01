from __future__ import annotations

import random
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
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
    Object.defineProperty(navigator, 'appVersion', { get: () => '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36' });
    window.chrome = window.chrome || { runtime: {}, loadTimes: () => ({}), csi: () => ({}), app: {} };

    // Hide automation from Permissions API
    const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
    if (originalQuery) {
        window.navigator.permissions.query = (parameters) => (
            parameters && parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters)
        );
    }

    // Overwrite iframe contentWindow.navigator.webdriver
    try {
        const iframe = document.createElement('iframe');
        document.body.appendChild(iframe);
        const iframeNav = Object.getOwnPropertyDescriptor(iframe.contentWindow, 'navigator');
        if (iframeNav) {
            Object.defineProperty(iframe.contentWindow, 'navigator', { ...iframeNav, configurable: true });
        }
        document.body.removeChild(iframe);
    } catch (e) {}

    // Suppress console warnings from bot-detection libraries
    const _noop = () => {};
    if (!window.__mirrorui_stealth__) {
        window.__mirrorui_stealth__ = true;
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
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
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
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": strategy.get("accept_lang", "en-US,en;q=0.9"),
                "Accept-Encoding": "gzip, deflate, br",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "Sec-Ch-Ua": '"Chromium";v="123", "Not:A-Brand";v="8"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
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
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass

        # Human-like initial pause
        try:
            await page.wait_for_timeout(800 + random.randint(200, 600))
        except Exception:
            pass

        # Attempt to dismiss cookie/consent banners with a wide selector set
        consent_texts = (
            "Accept all", "Accept All", "Accept All Cookies", "Accept cookies",
            "I agree", "Agree", "Agree & Continue", "Allow all", "Allow All",
            "OK", "Got it", "Close", "Dismiss", "Continue", "Consent",
            "Accept", "Yes, I Accept",
        )
        for text in consent_texts:
            try:
                await page.locator(
                    "button, [role='button'], a[href='#'], input[type='button'], input[type='submit']"
                ).filter(has_text=text).first.click(timeout=600)
                await page.wait_for_timeout(300)
            except Exception:
                pass

        # Human-like scroll: wander down the page to trigger lazy-load, then return to top
        try:
            last_height = 0
            for step in range(12):
                delta = random.randint(700, 1100)
                await page.mouse.wheel(0, delta)
                await page.wait_for_timeout(150 + random.randint(50, 200))
                current_height = await page.evaluate("() => document.documentElement.scrollHeight")
                if current_height == last_height and step > 4:
                    break
                last_height = current_height

            # Random mouse movement to mimic human presence
            for _ in range(4):
                x = random.randint(200, 1300)
                y = random.randint(100, 800)
                await page.mouse.move(x, y)
                await page.wait_for_timeout(random.randint(60, 150))

            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500 + random.randint(100, 400))
        except Exception:
            pass

        try:
            await page.screenshot(path=str(screenshot_path), full_page=True, timeout=25000)
        except Exception:
            try:
                await page.screenshot(path=str(screenshot_path), full_page=False, timeout=12000)
            except Exception:
                pass

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
