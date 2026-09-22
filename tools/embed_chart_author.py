"""Refresh the shared editor embedded in the single-file native app."""
from pathlib import Path
import re

root = Path(__file__).resolve().parent.parent
path = root / 'ReaSet.html'
html = path.read_text(encoding='utf-8')
block = '<script id="chart-author-core">\n' + (root / 'tools/chart-author.js').read_text(encoding='utf-8') + '\n</script>'
if '<script id="chart-author-core">' in html:
    html = re.sub(r'<script id="chart-author-core">.*?</script>', lambda m:block, html, count=1, flags=re.S)
else:
    html = html.replace('</head>', block+'\n</head>', 1)
path.write_text(html, encoding='utf-8', newline='')
pagination = html[html.index('        function chartRowKey('):html.index('        function renderStructuredChart(')]
(root / 'tools/chart-pagination.js').write_text('// Generated from the native performance paginator by embed_chart_author.py.\nfunction transposeChordName(s,n){return s;}\n'+pagination, encoding='utf-8', newline='')
