"""Render WRITEUP.md into app/static/writeup.html (served at /writeup, printable to PDF).

    uv run --with markdown python tools/render_writeup.py
"""

import os

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "WRITEUP.md"), encoding="utf-8") as f:
    body = markdown.markdown(f.read(), extensions=["tables"])

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Event Lead Cockpit: Write-up</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root { --bg: #ffffff; --ink: #1b1c1f; --muted: #5d6169; --line: #e5e5e1; --accent: #2f4fd8; }
@media (prefers-color-scheme: dark) { :root { --bg: #131416; --ink: #ececee; --muted: #a0a4ab; --line: #2c2e33; --accent: #7d95ff; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.55 Inter, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 780px; margin: 0 auto; padding: 40px 20px 60px; }
h1 { font-size: 24px; letter-spacing: -.02em; margin: 0 0 4px; }
h1 + p { color: var(--muted); margin-top: 0; }
h2 { font-size: 17px; margin: 28px 0 8px; padding-top: 14px; border-top: 1px solid var(--line); }
p, li { margin: 6px 0; }
ul, ol { padding-left: 20px; }
a { color: var(--accent); }
table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin: 10px 0 14px; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }
td:nth-child(2), td:nth-child(3) { white-space: nowrap; }
em { color: var(--muted); }
@media print {
  :root { --bg: #fff; --ink: #000; --muted: #444; --line: #ccc; }
  body { font-size: 10.3px; line-height: 1.5; } main { padding: 0; max-width: none; }
  h1 { font-size: 17px; } h2 { font-size: 12.5px; margin: 10px 0 4px; padding-top: 6px; }
  p, li { margin: 3px 0; } ul, ol { margin: 3px 0; padding-left: 16px; }
  table { font-size: 9px; margin: 6px 0 8px; } th, td { padding: 2px 6px; }
  @page { size: A4; margin: 13mm 14mm; }
}
</style></head><body><main>
""" + body + "\n</main></body></html>\n"

with open(os.path.join(ROOT, "app", "static", "writeup.html"), "w", encoding="utf-8") as f:
    f.write(PAGE)
print("wrote app/static/writeup.html")
