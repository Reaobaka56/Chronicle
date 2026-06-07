export default function Home() {
  return (
    <div className="min-h-screen bg-github-bg">
      {/* Hero */}
      <div className="max-w-5xl mx-auto px-6 pt-24 pb-16 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-github-surface border border-github-border text-xs text-github-text-secondary mb-6">
          <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          Now in beta
        </div>
        <h1 className="text-5xl font-bold mb-6 leading-tight">
          AI-generated changelogs
          <br />
          <span className="text-github-accent">for every release</span>
        </h1>
        <p className="text-xl text-github-text-secondary max-w-2xl mx-auto mb-10">
          Stop writing changelogs manually. Connect your GitHub repo, push a tag, 
          and get a beautiful, AI-crafted release note in seconds.
        </p>
        <div className="flex gap-4 justify-center">
          <a
            href="/dashboard"
            className="px-8 py-3 bg-github-accent hover:bg-blue-500 text-white font-medium rounded-xl transition"
          >
            Get Started Free
          </a>
          <a
            href="/changelog/demo/repo"
            className="px-8 py-3 bg-github-surface hover:bg-github-border border border-github-border text-github-text font-medium rounded-xl transition"
          >
            View Example
          </a>
        </div>
      </div>

      {/* Features */}
      <div className="max-w-5xl mx-auto px-6 py-16 border-t border-github-border">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="p-6 rounded-xl bg-github-surface border border-github-border">
            <div className="w-10 h-10 bg-purple-600/20 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <h3 className="font-semibold mb-2">AI-Powered</h3>
            <p className="text-sm text-github-text-secondary">
              Gemini 1.5 Pro groups your PRs intelligently and writes in your chosen tone.
            </p>
          </div>
          <div className="p-6 rounded-xl bg-github-surface border border-github-border">
            <div className="w-10 h-10 bg-green-600/20 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
            </div>
            <h3 className="font-semibold mb-2">Public Changelog Page</h3>
            <p className="text-sm text-github-text-secondary">
              Auto-generated, SEO-friendly changelog page at yourapp.com/changelog/org/repo.
            </p>
          </div>
          <div className="p-6 rounded-xl bg-github-surface border border-github-border">
            <div className="w-10 h-10 bg-blue-600/20 rounded-lg flex items-center justify-center mb-4">
              <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>
            <h3 className="font-semibold mb-2">Edit Before Publish</h3>
            <p className="text-sm text-github-text-secondary">
              Review and refine the AI output. Split-screen markdown editor with live preview.
            </p>
          </div>
        </div>
      </div>

      {/* Pricing */}
      <div className="max-w-4xl mx-auto px-6 py-16 border-t border-github-border">
        <h2 className="text-3xl font-bold text-center mb-12">Simple Pricing</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="p-6 rounded-xl bg-github-surface border border-github-border">
            <h3 className="font-semibold mb-1">Free</h3>
            <p className="text-3xl font-bold mb-4">$0</p>
            <ul className="space-y-2 text-sm text-github-text-secondary mb-6">
              <li>1 repository</li>
              <li>Technical tone only</li>
              <li>GitHub releases</li>
            </ul>
            <button className="w-full py-2 border border-github-border rounded-lg text-sm font-medium hover:bg-github-border transition">
              Current Plan
            </button>
          </div>
          <div className="p-6 rounded-xl bg-github-surface border-2 border-github-accent relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-github-accent text-white text-xs font-medium rounded-full">
              Popular
            </div>
            <h3 className="font-semibold mb-1">Pro</h3>
            <p className="text-3xl font-bold mb-4">$12<span className="text-lg text-github-text-secondary">/mo</span></p>
            <ul className="space-y-2 text-sm text-github-text-secondary mb-6">
              <li>Unlimited repositories</li>
              <li>All tones + custom templates</li>
              <li>Slack notifications</li>
              <li>Public changelog pages</li>
            </ul>
            <button className="w-full py-2 bg-github-accent rounded-lg text-sm font-medium hover:bg-blue-500 transition">
              Upgrade
            </button>
          </div>
          <div className="p-6 rounded-xl bg-github-surface border border-github-border">
            <h3 className="font-semibold mb-1">Team</h3>
            <p className="text-3xl font-bold mb-4">$39<span className="text-lg text-github-text-secondary">/mo</span></p>
            <ul className="space-y-2 text-sm text-github-text-secondary mb-6">
              <li>Everything in Pro</li>
              <li>Multi-user access</li>
              <li>Custom templates</li>
              <li>Email subscribers</li>
              <li>Priority support</li>
            </ul>
            <button className="w-full py-2 border border-github-border rounded-lg text-sm font-medium hover:bg-github-border transition">
              Contact Sales
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
