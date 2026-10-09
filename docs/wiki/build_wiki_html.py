#!/usr/bin/env python3
"""Build interactive single-file Wiki HTML viewer for Aiccountant007."""

import json
import os

WIKI_DIR = "/root/1projects/Aiccountant007/docs/wiki"
OUTPUT_HTML = os.path.join(WIKI_DIR, "index.html")

ARTICLE_METADATA = [
    {"id": "Home", "title": "🏠 Главная / Обзор", "icon": "🏠"},
    {"id": "01-System-Architecture", "title": "🏗️ 01. Архитектура системы", "icon": "🏗️"},
    {"id": "02-Cardano-Masumi-Escrow", "title": "⛓️ 02. Cardano & Masumi Escrow", "icon": "⛓️"},
    {"id": "03-MIP-003-and-MIP-004-Protocols", "title": "📜 03. Протоколы MIP-003 & MIP-004", "icon": "📜"},
    {"id": "04-Deterministic-Auditor-and-Czech-Tax", "title": "🔍 04. Детерминированный верификатор", "icon": "🔍"},
    {"id": "05-Wallet-Policy-and-Security", "title": "🛡️ 05. Политика кошелька и Безопасность", "icon": "🛡️"},
    {"id": "06-Bayesian-Reputation-Engine", "title": "📊 06. Байесовская репутация", "icon": "📊"},
    {"id": "07-End-to-End-Demo-and-Scenarios", "title": "🎬 07. Сценарий демо и кейсы", "icon": "🎬"},
    {"id": "08-Operator-Runbook-and-CLI", "title": "🛠️ 08. Runbook оператора и CLI", "icon": "🛠️"},
]

articles_data = {}
for item in ARTICLE_METADATA:
    path = os.path.join(WIKI_DIR, f"{item['id']}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            articles_data[item["id"]] = {
                "title": item["title"],
                "content": f.read()
            }

html_template = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aiccountant007 — Interactive Wiki & Knowledge Base</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/github-markdown-css@5.5.1/github-markdown-dark.min.css">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
  <style>
    :root {
      --bg-dark: #090d16;
      --sidebar-bg: #0d1322;
      --card-bg: #131c31;
      --border-color: #1e293b;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --success: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg-dark);
      color: var(--text-main);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      height: 100vh;
      overflow: hidden;
    }
    /* Sidebar */
    #sidebar {
      width: 320px;
      min-width: 280px;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      height: 100%;
    }
    .sidebar-header {
      padding: 20px 18px 14px;
      border-bottom: 1px solid var(--border-color);
    }
    .brand {
      font-size: 18px;
      font-weight: 700;
      color: var(--accent);
      display: flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
    }
    .brand-sub {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .search-box {
      margin-top: 12px;
      position: relative;
    }
    .search-input {
      width: 100%;
      background: #090d16;
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
      transition: border-color 0.2s;
    }
    .search-input:focus {
      border-color: var(--accent);
    }
    .nav-list {
      list-style: none;
      overflow-y: auto;
      flex: 1;
      padding: 12px 10px;
    }
    .nav-item {
      margin-bottom: 4px;
    }
    .nav-link {
      display: flex;
      align-items: center;
      padding: 9px 12px;
      border-radius: 6px;
      color: #cbd5e1;
      text-decoration: none;
      font-size: 13.5px;
      font-weight: 500;
      transition: all 0.15s ease;
      cursor: pointer;
    }
    .nav-link:hover {
      background: rgba(56, 189, 248, 0.08);
      color: var(--accent);
    }
    .nav-link.active {
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
      font-weight: 600;
      border-left: 3px solid var(--accent);
    }
    .sidebar-footer {
      padding: 14px 18px;
      border-top: 1px solid var(--border-color);
      font-size: 12px;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .badge-status {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: rgba(16, 185, 129, 0.15);
      color: #34d399;
      padding: 3px 8px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
    }
    .status-dot {
      width: 6px;
      height: 6px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10b981;
    }

    /* Main Content Area */
    #main-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--bg-dark);
    }
    .top-bar {
      height: 56px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 28px;
      background: rgba(13, 19, 34, 0.6);
      backdrop-filter: blur(8px);
    }
    .breadcrumbs {
      font-size: 13px;
      color: var(--text-muted);
    }
    .breadcrumbs span {
      color: var(--accent);
      font-weight: 600;
    }
    .top-actions {
      display: flex;
      gap: 10px;
    }
    .action-btn {
      background: #1e293b;
      border: 1px solid #334155;
      color: #f1f5f9;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
    }
    .action-btn:hover {
      background: #334155;
      border-color: var(--accent);
      color: var(--accent);
    }
    .content-scroll {
      flex: 1;
      overflow-y: auto;
      padding: 36px 48px;
    }
    .markdown-body {
      max-width: 960px;
      margin: 0 auto;
      background: transparent !important;
      font-size: 15px;
      line-height: 1.7;
    }
    .markdown-body pre {
      background: #0f172a !important;
      border: 1px solid #1e293b;
      border-radius: 8px;
    }
    .markdown-body code {
      color: #38bdf8;
    }
    .markdown-body table {
      width: 100%;
      background: #0d1322;
      border-radius: 8px;
      overflow: hidden;
    }
    .markdown-body blockquote {
      border-left-color: var(--accent);
      background: rgba(56, 189, 248, 0.05);
      border-radius: 0 6px 6px 0;
      padding: 10px 16px;
    }
    .mermaid {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 16px;
      margin: 20px 0;
      display: flex;
      justify-content: center;
    }
  </style>
</head>
<body>

  <aside id="sidebar">
    <div class="sidebar-header">
      <a href="#" class="brand" onclick="loadArticle('Home')">
        🛡️ Aiccountant007
      </a>
      <div class="brand-sub">Masumi Escrow & Agentic Accounting</div>
      <div class="search-box">
        <input type="text" id="searchInput" class="search-input" placeholder="Поиск по документации..." oninput="filterNav()">
      </div>
    </div>
    
    <ul class="nav-list" id="navList">
      <!-- Generated via JS -->
    </ul>

    <div class="sidebar-footer">
      <span>Preprod Cardano</span>
      <div class="badge-status">
        <span class="status-dot"></span>
        <span>Online</span>
      </div>
    </div>
  </aside>

  <main id="main-content">
    <div class="top-bar">
      <div class="breadcrumbs">
        Aiccountant007 Wiki / <span id="currentTitle">Главная</span>
      </div>
      <div class="top-actions">
        <a href="../presentation/index.html" class="action-btn">📊 Pitch Deck</a>
        <a href="../video/Aiccountant007_Demo_90s.mp4" class="action-btn">🎬 Demo Video</a>
        <a href="https://github.com/chotamode/Aiccountant007" target="_blank" class="action-btn">🐙 GitHub</a>
      </div>
    </div>

    <div class="content-scroll" id="contentScroll">
      <article class="markdown-body" id="articleContent">
        <!-- Rendered Markdown goes here -->
      </article>
    </div>
  </main>

  <script id="wiki-dataset" type="application/json">
""" + json.dumps(articles_data, ensure_ascii=False) + """
  </script>

  <script>
    mermaid.initialize({ startOnLoad: false, theme: 'dark', securityLevel: 'loose' });

    const dataset = JSON.parse(document.getElementById('wiki-dataset').textContent);
    let activeId = 'Home';

    const articlesMeta = """ + json.dumps(ARTICLE_METADATA, ensure_ascii=False) + """;

    function renderNav() {
      const navList = document.getElementById('navList');
      navList.innerHTML = '';
      articlesMeta.forEach(meta => {
        const li = document.createElement('li');
        li.className = 'nav-item';
        li.dataset.title = meta.title.toLowerCase();
        li.innerHTML = `
          <a class="nav-link ${meta.id === activeId ? 'active' : ''}" onclick="loadArticle('${meta.id}')">
            ${meta.title}
          </a>
        `;
        navList.appendChild(li);
      });
    }

    function filterNav() {
      const query = document.getElementById('searchInput').value.toLowerCase();
      document.querySelectorAll('#navList .nav-item').forEach(item => {
        if (item.dataset.title.includes(query)) {
          item.style.display = 'block';
        } else {
          item.style.display = 'none';
        }
      });
    }

    function loadArticle(id) {
      if (!dataset[id]) id = 'Home';
      activeId = id;

      const art = dataset[id];
      document.getElementById('currentTitle').textContent = art.title;

      renderNav();

      // Parse markdown
      const html = marked.parse(art.content);
      const articleEl = document.getElementById('articleContent');
      articleEl.innerHTML = html;

      // Transform mermaid codeblocks
      articleEl.querySelectorAll('pre code.language-mermaid').forEach(block => {
        const pre = block.parentElement;
        const div = document.createElement('div');
        div.className = 'mermaid';
        div.textContent = block.textContent;
        pre.replaceWith(div);
      });

      // Render mermaid
      mermaid.run({
        nodes: document.querySelectorAll('.mermaid')
      });

      // Handle internal wiki link clicks
      articleEl.querySelectorAll('a').forEach(link => {
        const href = link.getAttribute('href');
        if (href && !href.startsWith('http') && !href.startsWith('#') && !href.includes('/')) {
          const targetId = href.replace('.md', '');
          if (dataset[targetId]) {
            link.onclick = (e) => {
              e.preventDefault();
              loadArticle(targetId);
            };
          }
        }
      });

      document.getElementById('contentScroll').scrollTop = 0;
    }

    // Init
    window.onload = () => {
      loadArticle('Home');
    };
  </script>
</body>
</html>
"""

with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
    f.write(html_template)

print(f"Successfully generated {OUTPUT_HTML} (size: {len(html_template)} bytes)")
