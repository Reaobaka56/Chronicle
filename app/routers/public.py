"""Public changelog pages."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import Repo, Release

router = APIRouter(tags=["public"])


CHANGELOG_PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Changelog — {repo_name}</title>
    <style>
        :root {{ --bg: #0d1117; --surface: #161b22; --border: #30363d; --text: #c9d1d9; --text-secondary: #8b949e; --accent: #58a6ff; --accent-hover: #79c0ff; }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
        .container {{ max-width: 860px; margin: 0 auto; padding: 40px 24px; }}
        header {{ margin-bottom: 48px; padding-bottom: 24px; border-bottom: 1px solid var(--border); }}
        h1 {{ font-size: 32px; font-weight: 600; margin-bottom: 8px; }}
        .subtitle {{ color: var(--text-secondary); font-size: 16px; }}
        .release {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 28px; margin-bottom: 24px; }}
        .release-header {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
        .tag {{ font-size: 20px; font-weight: 600; color: var(--accent); text-decoration: none; }}
        .tag:hover {{ color: var(--accent-hover); }}
        .date {{ color: var(--text-secondary); font-size: 14px; }}
        .badge {{ font-size: 11px; padding: 2px 8px; border-radius: 12px; background: #238636; color: white; font-weight: 500; }}
        .badge-draft {{ background: #6e7681; }}
        .changelog-body {{ color: var(--text); font-size: 15px; line-height: 1.7; }}
        .changelog-body h2 {{ font-size: 20px; margin: 24px 0 12px; color: var(--text); }}
        .changelog-body h3 {{ font-size: 16px; margin: 16px 0 8px; }}
        .changelog-body ul {{ margin: 8px 0 8px 20px; }}
        .changelog-body li {{ margin: 4px 0; }}
        .changelog-body code {{ background: rgba(110,118,129,0.2); padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
        .changelog-body a {{ color: var(--accent); }}
        .changelog-body a:hover {{ text-decoration: underline; }}
        .subscribe {{ margin-top: 48px; padding: 24px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; text-align: center; }}
        .subscribe h3 {{ margin-bottom: 12px; }}
        .subscribe-form {{ display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }}
        .subscribe input {{ padding: 10px 16px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font-size: 14px; min-width: 260px; }}
        .subscribe button {{ padding: 10px 20px; border: none; border-radius: 6px; background: var(--accent); color: white; font-size: 14px; font-weight: 500; cursor: pointer; }}
        .subscribe button:hover {{ background: var(--accent-hover); }}
        footer {{ margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--border); text-align: center; color: var(--text-secondary); font-size: 13px; }}
        @media (max-width: 600px) {{ .container {{ padding: 20px 16px; }} .release {{ padding: 20px; }} h1 {{ font-size: 24px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{repo_name}</h1>
            <p class="subtitle">Changelog & Release Notes</p>
        </header>
        {releases_html}
        <div class="subscribe">
            <h3>Stay updated</h3>
            <p style="color: var(--text-secondary); margin-bottom: 16px; font-size: 14px;">Get notified when new releases ship.</p>
            <form class="subscribe-form" action="/api/subscribe/{owner}/{repo}" method="post">
                <input type="email" name="email" placeholder="your@email.com" required>
                <button type="submit">Subscribe</button>
            </form>
        </div>
        <footer>
            <p>Generated with PR Changelog</p>
        </footer>
    </div>
</body>
</html>
"""


def render_markdown_to_html(markdown_text: str) -> str:
    """Simple markdown to HTML conversion."""
    import re

    html = markdown_text
    # Escape HTML
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Headers
    html = re.sub(r'^### (.+)$', r'<h3></h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2></h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1></h1>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em></em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong></strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em></em>', html)

    # Code inline
    html = re.sub(r'`([^`]+)`', r'<code></code>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href=""></a>', html)

    # Lists
    lines = html.split('
')
    result = []
    in_list = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            content = stripped[2:]
            result.append(f'<li>{content}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)
    if in_list:
        result.append('</ul>')

    html = '
'.join(result)

    # Paragraphs
    paragraphs = html.split('

')
    new_paragraphs = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith('<') and not p.startswith('<'):
            new_paragraphs.append(f'<p>{p}</p>')
        else:
            new_paragraphs.append(p)
    html = '

'.join(new_paragraphs)

    return html


@router.get("/changelog/{owner}/{repo}", response_class=HTMLResponse)
async def public_changelog(
    owner: str,
    repo: str,
    db: AsyncSession = Depends(get_db),
):
    """Public changelog page for a repo."""
    full_name = f"{owner}/{repo}"

    result = await db.execute(select(Repo).where(Repo.full_name == full_name))
    repo_obj = result.scalar_one_or_none()
    if not repo_obj:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get published releases
    releases_result = await db.execute(
        select(Release)
        .where(Release.repo_id == repo_obj.id, Release.published == True)
        .order_by(desc(Release.published_at))
    )
    releases = releases_result.scalars().all()

    releases_html = ""
    for release in releases:
        date_str = release.published_at.strftime("%B %d, %Y") if release.published_at else "Draft"
        badge = '<span class="badge">Latest</span>' if release == releases[0] else ''
        body_html = render_markdown_to_html(release.body or release.body_draft or "")

        releases_html += f"""
        <article class="release">
            <div class="release-header">
                <a class="tag" href="{release.github_html_url or '#'}">{release.tag_name}</a>
                <span class="date">{date_str}</span>
                {badge}
            </div>
            <div class="changelog-body">
                {body_html}
            </div>
        </article>
        """

    if not releases_html:
        releases_html = '<p style="text-align: center; color: var(--text-secondary); padding: 48px 0;">No releases published yet.</p>'

    html = CHANGELOG_PAGE_TEMPLATE.format(
        repo_name=full_name,
        owner=owner,
        repo=repo,
        releases_html=releases_html,
    )

    return HTMLResponse(content=html)
