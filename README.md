# Chronicle

AI-powered changelog generation for GitHub releases. 

## Features

- **GitHub App Integration** — Webhook-driven PR tracking on every merge
- **AI Changelog Generation** — Gemini 1.5 Pro groups PRs by label and writes in your tone (technical / user-facing / marketing)
- **Edit Before Publish** — Split-screen markdown editor with live preview
- **Public Changelog Pages** — Auto-generated, SEO-friendly pages at `/changelog/{owner}/{repo}`
- **Slack & Email Notifications** — Auto-post to Slack, notify email subscribers on each release
- **Stripe Billing** — Free (1 repo) → Pro $12/mo → Team $39/mo

## Quick Start

### 1. Clone & Configure

```bash
cd pr_changelog_mvp
cp .env.example .env
# Edit .env with your credentials
```

### 2. Run with Docker

```bash
docker-compose up -d
```

### 3. Or run locally

```bash
# Backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### 4. Set up GitHub App

1. Go to GitHub → Settings → Developer settings → GitHub Apps → New GitHub App
2. Set webhook URL to `https://yourapp.com/webhooks/github`
3. Permissions: `pull_requests:read`, `contents:read`, `releases:write`
4. Subscribe to: `Pull request`, `Release`, `Installation` events
5. Download private key, paste into `.env`

### 5. Generate a changelog manually

```bash
python generate.py --repo owner/repo --since v1.2.0 --tone technical
```

## Project Structure

```
pr_changelog_mvp/
├── app/
│   ├── main.py              # FastAPI app entry
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # DB config & sessions
│   ├── config.py            # Settings management
│   ├── github_utils.py      # GitHub App auth & API
│   ├── ai_service.py        # Gemini changelog generation
│   └── routers/
│       ├── webhooks.py      # GitHub webhook handler
│       ├── releases.py      # Changelog CRUD API
│       ├── repos.py         # Repo settings
│       ├── public.py        # Public changelog pages
│       ├── oauth.py         # GitHub OAuth
│       ├── subscribers.py   # Email subscriptions
│       └── stripe.py        # Billing & payments
├── frontend/                # Next.js dashboard
│   ├── app/
│   │   ├── page.tsx         # Landing page
│   │   └── dashboard/
│   │       └── page.tsx     # Main dashboard
├── generate.py              # CLI trigger script
├── requirements.txt
├── docker-compose.yml
└── .env.example
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/github` | GitHub webhook receiver |
| GET | `/auth/github` | OAuth login |
| GET | `/api/repos` | List repos |
| PATCH | `/api/repos/{id}/settings` | Update repo settings |
| GET | `/api/releases/{repo_id}` | List releases |
| POST | `/api/releases/{repo_id}/generate` | Generate changelog |
| POST | `/api/releases/{repo_id}/{id}/publish` | Publish release |
| GET | `/changelog/{owner}/{repo}` | Public changelog page |
| POST | `/api/subscribe/{owner}/{repo}` | Email subscribe |
| POST | `/api/billing/checkout` | Stripe checkout |
| POST | `/api/billing/webhook` | Stripe webhook |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | Postgres connection string |
| `GITHUB_APP_ID` | Yes | GitHub App ID |
| `GITHUB_PRIVATE_KEY` | Yes | App private key PEM |
| `GITHUB_WEBHOOK_SECRET` | Yes | Webhook verification secret |
| `GITHUB_CLIENT_ID` | Yes | OAuth app client ID |
| `GITHUB_CLIENT_SECRET` | Yes | OAuth app secret |
| `GEMINI_API_KEY` | Yes | Google AI API key |
| `STRIPE_SECRET_KEY` | For billing | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | For billing | Stripe webhook secret |
| `RESEND_API_KEY` | For email | Resend API key |

## 4-Week Build Plan

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | GitHub App + webhook plumbing | Merged PRs auto-land in Postgres |
| 2 | AI generation + GitHub write-back | Tag push auto-drafts GitHub Release |
| 3 | Public page + Slack + email | Release generates public page + notifications |
| 4 | Dashboard + Stripe + Marketplace | End-to-end flow with payments |

## License

MIT
