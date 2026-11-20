#!/usr/bin/python3
"""Build the documentation site: every page is one of the markdown files in docs/, converted to
HTML next to it with a shared navigation. No server needed; open docs/index.html, or point GitHub
Pages at the docs folder (docs/.nojekyll is written so the files are served as they are).

  build_site.py        needs the Python package "markdown"
"""
import html
import os
import re
import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
NAV = [
    ("The story", [("index", "Overview"), ("build_log", "Build log"), ("decisions", "Decisions")]),
    ("Results", [("cache_study", "Cache study"), ("layout_results", "Layout results"), ("memory_research", "Memory research")]),
    ("Reference", [("datasheet", "Datasheet"), ("verification", "Verification"), ("tapeout_checklist", "Tape-out checklist"),
                   ("analog_macros", "Analog macro spec"), ("bondout", "Bond-out")]),
]
PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - RV328</title><link rel="stylesheet" href="assets/site.css"></head>
<body><div class="wrap">
<nav><a class="name" href="index.html">RV328</a><p class="tag">A RISC-V chip in the ATmega328PB footprint</p>
{nav}
<h2>Tools</h2><a class="l" href="layout_viewer.html">Layout viewer</a>
</nav>
<main>
{body}
<footer>Generated from <code>docs/{src}.md</code> by <code>scripts/build_site.py</code>. Nothing here has been measured on silicon.</footer>
</main></div></body></html>
"""


def nav_html(current, have):
    out = []
    for group, pages in NAV:
        out.append("<h2>%s</h2>" % group)
        for name, label in pages:
            if name in have:
                out.append('<a class="l%s" href="%s.html">%s</a>' % (" on" if name == current else "", name, label))
    return "\n".join(out)


def convert(text):
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    body = re.sub(r'href="([A-Za-z0-9_]+)\.md(#[^"]*)?"', lambda m: 'href="%s.html%s"' % (m.group(1), m.group(2) or ""), body)
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    # check lists: "- [x] ..." and "- [ ] ..."
    body = re.sub(r"<li>\[x\] ", '<li class="done">', body)
    body = re.sub(r"<li>\[ \] ", '<li class="open">', body)
    body = re.sub(r"<ul>\s*(<li class=\"(?:done|open)\">)", r'<ul class="check">\1', body)
    return body


def main():
    have = {n for _, pages in NAV for n, _ in pages if os.path.exists(os.path.join(DOCS, n + ".md"))}
    for name in sorted(have):
        text = open(os.path.join(DOCS, name + ".md"), encoding="utf-8").read()
        m = re.search(r"^# (.+)$", text, re.M)
        title = html.escape(m.group(1)) if m else name
        open(os.path.join(DOCS, name + ".html"), "w", encoding="utf-8").write(
            PAGE.format(title=title, nav=nav_html(name, have), body=convert(text), src=name))
    # a page that is linked but not written yet gets a placeholder, so no link is dead
    for name, label in ((n, l) for _, pages in NAV for n, l in pages):
        if name not in have:
            open(os.path.join(DOCS, name + ".html"), "w", encoding="utf-8").write(
                PAGE.format(title=label, nav=nav_html(name, have), body="<h1>%s</h1>\n<p>In progress: this page has not been written yet.</p>" % label, src=name))
    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    print("site: %d pages in docs/ (open docs/index.html)" % len(have))


if __name__ == "__main__":
    main()
