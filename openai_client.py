import json
from html.parser import HTMLParser


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._tag_stack = []
        self._in_a = False
        self._curr_href = ""
        self.headings = []
        self.paragraphs = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        if tag == "a":
            self._in_a = True
            self._curr_href = dict(attrs).get("href", "")

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
        if tag == "a":
            self._in_a = False
            self._curr_href = ""

    def handle_data(self, data):
        text = " ".join(data.split()).strip()
        if not text:
            return

        current_tag = self._tag_stack[-1] if self._tag_stack else ""
        if current_tag in {"h1", "h2", "h3"} and len(self.headings) < 24:
            self.headings.append(text[:120])
        elif current_tag in {"p", "li"} and len(self.paragraphs) < 48:
            self.paragraphs.append(text[:220])

        if self._in_a and text and len(self.links) < 24:
            self.links.append({"label": text[:60], "href": self._curr_href or "#"})


def _dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else item
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _to_js_array(items):
    return json.dumps(items, ensure_ascii=True, indent=2)


def gpt_generate(html: str, image_b64: str) -> str:
    # `image_b64` is intentionally unused in free mode.
    extractor = _Extractor()
    extractor.feed(html)

    headings = _dedupe_keep_order(extractor.headings)
    paragraphs = _dedupe_keep_order(extractor.paragraphs)
    links = _dedupe_keep_order(extractor.links)

    hero_title = headings[0] if headings else "Generated Mirror"
    hero_subtitle = paragraphs[0] if paragraphs else "This layout was generated locally from captured HTML."

    nav_items = links[:6] if links else [{"label": "Home", "href": "#"}, {"label": "About", "href": "#"}, {"label": "Contact", "href": "#"}]

    cards = []
    for idx, title in enumerate(headings[1:7]):
        body = paragraphs[idx] if idx < len(paragraphs) else "Content extracted from the source page."
        cards.append({"title": title, "body": body})
    if not cards:
        cards = [
            {"title": "Section One", "body": "MirrorUI created this section from the page structure."},
            {"title": "Section Two", "body": "Run generation on another URL to produce different content."},
            {"title": "Section Three", "body": "Export to zip when you are happy with the output."},
        ]

    app_body = f"""import React from 'react'
import SectionList from './SectionList'

const navItems = {_to_js_array(nav_items)}
const cards = {_to_js_array(cards)}

export default function AppBody() {{
  return (
    <div className=\"min-h-screen bg-slate-50 text-slate-900\">
      <header className=\"border-b border-slate-200 bg-white\">
        <div className=\"mx-auto max-w-6xl px-6 py-5\">
          <div className=\"flex flex-wrap items-center justify-between gap-3\">
            <strong className=\"text-lg\">MirrorUI Local</strong>
            <nav className=\"flex flex-wrap items-center gap-2\">
              {{navItems.map((item) => (
                <a
                  key={{item.label + item.href}}
                  href={{item.href || '#'}}
                  className=\"rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100\"
                >
                  {{item.label}}
                </a>
              ))}}
            </nav>
          </div>
        </div>
      </header>

      <main className=\"mx-auto max-w-6xl px-6 py-10\">
        <section className=\"mb-10 rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200\">
          <h1 className=\"text-3xl font-semibold tracking-tight\">{hero_title}</h1>
          <p className=\"mt-3 max-w-3xl text-slate-600\">{hero_subtitle}</p>
        </section>

        <SectionList cards={{cards}} />
      </main>
    </div>
  )
}}
"""

    section_list = """import React from 'react'

export default function SectionList({ cards }) {
  return (
    <section className=\"grid gap-5 sm:grid-cols-2 lg:grid-cols-3\">
      {cards.map((card) => (
        <article
          key={card.title}
          className=\"rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200\"
        >
          <h2 className=\"text-lg font-semibold\">{card.title}</h2>
          <p className=\"mt-2 text-sm leading-6 text-slate-600\">{card.body}</p>
        </article>
      ))}
    </section>
  )
}
"""

    return (
        "[FILE: src/components/generated/AppBody.jsx]\n"
        + app_body
        + "\n[FILE: src/components/generated/SectionList.jsx]\n"
        + section_list
    )
