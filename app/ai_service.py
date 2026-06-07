"""AI-powered changelog generation using Gemini."""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types

from app.config import get_settings
from app.models import Tone


CHANGELOG_SYSTEM_PROMPTS = {
    Tone.TECHNICAL: """You are a technical changelog writer. Write concise, accurate release notes for developers.

Rules:
- Group changes by type: Features, Fixes, Breaking Changes, Performance, Refactoring, Dependencies
- Include PR numbers in parentheses: (#123)
- Mention specific APIs, functions, or modules affected
- Be precise about behavior changes
- Skip purely internal/chore changes unless they affect the public API
- Use present tense, imperative mood
- No marketing language, no emojis

Format as clean Markdown with h2 sections.""",

    Tone.USER_FACING: """You are a user-facing changelog writer. Write release notes that help end-users understand what changed and why they should care.

Rules:
- Group by: What's New, Improvements, Bug Fixes
- Explain the user benefit, not the implementation detail
- Use friendly, clear language
- Include screenshots placeholders where relevant: [Screenshot: description]
- Skip internal refactors, dependency bumps, CI changes
- Use present tense
- Light use of emojis for visual grouping is OK

Format as clean Markdown with h2 sections.""",

    Tone.MARKETING: """You are a product marketing writer crafting release announcements.

Rules:
- Lead with the most impactful change as a headline
- Group by: ✨ New, 🚀 Improved, 🐛 Fixed
- Tell a story about the release — connect changes to user outcomes
- Include a "Why this matters" paragraph when significant
- Skip internal/technical details entirely
- Use engaging, confident language
- Include a CTA at the end (e.g., "Try it now", "Read the docs")

Format as polished Markdown with h2 sections.""",
}


def build_changelog_prompt(
    prs: List[Dict[str, Any]],
    tone: Tone,
    tag_name: str,
    previous_tag: Optional[str] = None,
    custom_template: Optional[str] = None,
    repo_name: str = "",
) -> str:
    """Build the prompt for changelog generation."""

    system_prompt = CHANGELOG_SYSTEM_PROMPTS[tone]
    if custom_template:
        system_prompt += f"

## Custom Template
{custom_template}

Follow this template structure above."

    # Build PR summaries
    pr_summaries = []
    for pr in prs:
        labels = ", ".join(pr.get("labels", [])) or "none"
        summary = f"""PR #{pr['number']}: {pr['title']}
Author: {pr['author']}
Labels: {labels}
Merged: {pr['merged_at']}
Body: {pr.get('body', '')[:500]}
Files changed: {pr.get('files_changed', 0)} | +{pr.get('additions', 0)} -{pr.get('deletions', 0)}
---"""
        pr_summaries.append(summary)

    prs_text = "
".join(pr_summaries)

    user_prompt = f"""Generate a changelog for {repo_name} release {tag_name}.

Previous release: {previous_tag or "N/A (first release)"}

Merged Pull Requests ({len(prs)} total):

{prs_text}

Generate the changelog now. Output ONLY the changelog Markdown, no preamble."""

    return system_prompt, user_prompt


class ChangelogGenerator:
    """Generates changelogs using Gemini."""

    def __init__(self):
        self.settings = get_settings()
        self.client = genai.Client(api_key=self.settings.gemini_api_key)
        self.model = self.settings.gemini_model

    async def generate(
        self,
        prs: List[Dict[str, Any]],
        tone: Tone,
        tag_name: str,
        previous_tag: Optional[str] = None,
        custom_template: Optional[str] = None,
        repo_name: str = "",
    ) -> str:
        """Generate a changelog from PR data."""

        system_prompt, user_prompt = build_changelog_prompt(
            prs=prs,
            tone=tone,
            tag_name=tag_name,
            previous_tag=previous_tag,
            custom_template=custom_template,
            repo_name=repo_name,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

        return response.text.strip()

    async def generate_with_validation(
        self,
        prs: List[Dict[str, Any]],
        tone: Tone,
        tag_name: str,
        previous_tag: Optional[str] = None,
        custom_template: Optional[str] = None,
        repo_name: str = "",
    ) -> Dict[str, Any]:
        """Generate changelog with quality validation."""

        changelog = await self.generate(
            prs=prs,
            tone=tone,
            tag_name=tag_name,
            previous_tag=previous_tag,
            custom_template=custom_template,
            repo_name=repo_name,
        )

        # Quality checks
        issues = []

        # Check for hallucinated PR references
        import re
        pr_refs = set(re.findall(r'#(\\d+)', changelog))
        valid_pr_nums = {str(p['number']) for p in prs}
        hallucinated = pr_refs - valid_pr_nums
        if hallucinated:
            issues.append(f"Hallucinated PR references: {hallucinated}")

        # Check PR coverage
        covered = len(pr_refs & valid_pr_nums)
        coverage = covered / len(prs) if prs else 1.0
        if coverage < 0.7:
            issues.append(f"Low PR coverage: {coverage:.0%} ({covered}/{len(prs)})")

        # Check for empty/placeholder content
        if len(changelog) < 200:
            issues.append("Changelog too short")

        return {
            "changelog": changelog,
            "issues": issues,
            "coverage": coverage,
            "pr_count": len(prs),
            "model": self.model,
        }


generator = ChangelogGenerator()
