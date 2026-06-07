"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Repo {
  id: number;
  full_name: string;
  name: string;
  tone: string;
  auto_publish: boolean;
  slack_webhook_url: string | null;
}

interface Release {
  id: number;
  tag_name: string;
  name: string | null;
  body_draft: string | null;
  body: string | null;
  published: boolean;
  published_at: string | null;
  generated_at: string;
}

export default function Dashboard() {
  const [repos, setRepos] = useState<Repo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repo | null>(null);
  const [releases, setReleases] = useState<Release[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [editingRelease, setEditingRelease] = useState<Release | null>(null);
  const [editBody, setEditBody] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [sinceTag, setSinceTag] = useState("");
  const [tone, setTone] = useState("technical");

  useEffect(() => {
    fetchRepos();
  }, []);

  useEffect(() => {
    if (selectedRepo) {
      fetchReleases(selectedRepo.id);
      setTone(selectedRepo.tone);
    }
  }, [selectedRepo]);

  async function fetchRepos() {
    try {
      const res = await fetch("/api/repos");
      const data = await res.json();
      setRepos(data);
      if (data.length > 0) setSelectedRepo(data[0]);
    } catch (err) {
      console.error("Failed to fetch repos", err);
    } finally {
      setLoading(false);
    }
  }

  async function fetchReleases(repoId: number) {
    try {
      const res = await fetch(`/api/releases/${repoId}`);
      const data = await res.json();
      setReleases(data);
    } catch (err) {
      console.error("Failed to fetch releases", err);
    }
  }

  async function generateChangelog() {
    if (!selectedRepo || !tagInput) return;
    setGenerating(true);
    try {
      const res = await fetch(`/api/releases/${selectedRepo.id}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tag_name: tagInput,
          since_tag: sinceTag || undefined,
          tone: tone,
        }),
      });
      const data = await res.json();
      if (data.changelog) {
        await fetchReleases(selectedRepo.id);
        // Find the newly created release
        const releaseRes = await fetch(`/api/releases/${selectedRepo.id}`);
        const releases = await releaseRes.json();
        const newRelease = releases.find((r: Release) => r.tag_name === tagInput);
        if (newRelease) {
          setEditingRelease(newRelease);
          setEditBody(data.changelog);
        }
      }
    } catch (err) {
      console.error("Generation failed", err);
      alert("Failed to generate changelog");
    } finally {
      setGenerating(false);
    }
  }

  async function publishRelease() {
    if (!selectedRepo || !editingRelease) return;
    try {
      const res = await fetch(
        `/api/releases/${selectedRepo.id}/${editingRelease.id}/publish`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: editBody }),
        }
      );
      const data = await res.json();
      if (data.status === "published") {
        setEditingRelease(null);
        await fetchReleases(selectedRepo.id);
      }
    } catch (err) {
      console.error("Publish failed", err);
      alert("Failed to publish");
    }
  }

  async function updateSettings(field: string, value: any) {
    if (!selectedRepo) return;
    try {
      await fetch(`/api/repos/${selectedRepo.id}/settings`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
      });
      setRepos(repos.map(r => r.id === selectedRepo.id ? { ...r, [field]: value } : r));
      setSelectedRepo({ ...selectedRepo, [field]: value });
    } catch (err) {
      console.error("Settings update failed", err);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-github-text-secondary">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-github-bg">
      {/* Header */}
      <header className="border-b border-github-border bg-github-surface">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-github-accent rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold">PR Changelog</h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-github-text-secondary">Free plan — 1 repo</span>
            <button className="px-4 py-2 bg-github-accent hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition">
              Upgrade to Pro
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8 flex gap-8">
        {/* Sidebar */}
        <aside className="w-64 flex-shrink-0">
          <h2 className="text-xs font-semibold text-github-text-secondary uppercase tracking-wider mb-3">
            Repositories
          </h2>
          <div className="space-y-1">
            {repos.map(repo => (
              <button
                key={repo.id}
                onClick={() => setSelectedRepo(repo)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${
                  selectedRepo?.id === repo.id
                    ? "bg-github-accent/10 text-github-accent"
                    : "text-github-text hover:bg-github-surface"
                }`}
              >
                <div className="font-medium truncate">{repo.name}</div>
                <div className="text-xs text-github-text-secondary truncate">{repo.full_name}</div>
              </button>
            ))}
          </div>

          {selectedRepo && (
            <div className="mt-8">
              <h2 className="text-xs font-semibold text-github-text-secondary uppercase tracking-wider mb-3">
                Settings
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-github-text-secondary block mb-1">Tone</label>
                  <select
                    value={selectedRepo.tone}
                    onChange={e => updateSettings("tone", e.target.value)}
                    className="w-full bg-github-surface border border-github-border rounded-lg px-3 py-2 text-sm text-github-text"
                  >
                    <option value="technical">Technical</option>
                    <option value="user_facing">User-facing</option>
                    <option value="marketing">Marketing</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="auto_publish"
                    checked={selectedRepo.auto_publish}
                    onChange={e => updateSettings("auto_publish", e.target.checked)}
                    className="rounded border-github-border"
                  />
                  <label htmlFor="auto_publish" className="text-sm text-github-text">
                    Auto-publish
                  </label>
                </div>
                <div>
                  <label className="text-xs text-github-text-secondary block mb-1">
                    Slack Webhook
                  </label>
                  <input
                    type="text"
                    value={selectedRepo.slack_webhook_url || ""}
                    onChange={e => updateSettings("slack_webhook_url", e.target.value || null)}
                    placeholder="https://hooks.slack.com/..."
                    className="w-full bg-github-surface border border-github-border rounded-lg px-3 py-2 text-sm text-github-text placeholder-github-text-secondary"
                  />
                </div>
              </div>
            </div>
          )}
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0">
          {selectedRepo ? (
            <div>
              {/* Generate section */}
              <div className="bg-github-surface border border-github-border rounded-xl p-6 mb-6">
                <h2 className="text-lg font-semibold mb-4">Generate Changelog</h2>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <label className="text-xs text-github-text-secondary block mb-1">Tag name</label>
                    <input
                      type="text"
                      value={tagInput}
                      onChange={e => setTagInput(e.target.value)}
                      placeholder="v1.2.0"
                      className="w-full bg-github-bg border border-github-border rounded-lg px-3 py-2 text-sm text-github-text placeholder-github-text-secondary"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-github-text-secondary block mb-1">Since tag (optional)</label>
                    <input
                      type="text"
                      value={sinceTag}
                      onChange={e => setSinceTag(e.target.value)}
                      placeholder="v1.1.0"
                      className="w-full bg-github-bg border border-github-border rounded-lg px-3 py-2 text-sm text-github-text placeholder-github-text-secondary"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-github-text-secondary block mb-1">Tone</label>
                    <select
                      value={tone}
                      onChange={e => setTone(e.target.value)}
                      className="w-full bg-github-bg border border-github-border rounded-lg px-3 py-2 text-sm text-github-text"
                    >
                      <option value="technical">Technical</option>
                      <option value="user_facing">User-facing</option>
                      <option value="marketing">Marketing</option>
                    </select>
                  </div>
                </div>
                <button
                  onClick={generateChangelog}
                  disabled={generating || !tagInput}
                  className="px-6 py-2.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition flex items-center gap-2"
                >
                  {generating ? (
                    <>
                      <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Generating...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      Generate with AI
                    </>
                  )}
                </button>
              </div>

              {/* Editor */}
              {editingRelease && (
                <div className="bg-github-surface border border-github-border rounded-xl p-6 mb-6">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold">Edit Changelog</h2>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setEditingRelease(null)}
                        className="px-4 py-2 text-sm text-github-text-secondary hover:text-github-text transition"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={publishRelease}
                        className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm font-medium rounded-lg transition"
                      >
                        Publish Release
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <label className="text-xs text-github-text-secondary block mb-1">Markdown</label>
                      <textarea
                        value={editBody}
                        onChange={e => setEditBody(e.target.value)}
                        className="w-full h-96 bg-github-bg border border-github-border rounded-lg p-4 text-sm text-github-text font-mono resize-none"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-github-text-secondary block mb-1">Preview</label>
                      <div className="h-96 overflow-auto bg-github-bg border border-github-border rounded-lg p-4">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-invert prose-sm max-w-none">
                          {editBody}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Release history */}
              <div>
                <h2 className="text-lg font-semibold mb-4">Release History</h2>
                {releases.length === 0 ? (
                  <div className="text-center py-12 text-github-text-secondary">
                    No releases yet. Generate your first changelog above.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {releases.map(release => (
                      <div
                        key={release.id}
                        className="bg-github-surface border border-github-border rounded-xl p-4 hover:border-github-accent/50 transition"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-3">
                            <span className="text-github-accent font-semibold">{release.tag_name}</span>
                            {release.published ? (
                              <span className="px-2 py-0.5 bg-green-600/20 text-green-400 text-xs rounded-full">Published</span>
                            ) : (
                              <span className="px-2 py-0.5 bg-github-text-secondary/20 text-github-text-secondary text-xs rounded-full">Draft</span>
                            )}
                          </div>
                          <span className="text-xs text-github-text-secondary">
                            {new Date(release.generated_at).toLocaleDateString()}
                          </span>
                        </div>
                        {release.body && (
                          <div className="text-sm text-github-text-secondary line-clamp-2">
                            {release.body.substring(0, 200)}...
                          </div>
                        )}
                        {!release.published && (
                          <button
                            onClick={() => {
                              setEditingRelease(release);
                              setEditBody(release.body_draft || "");
                            }}
                            className="mt-2 text-xs text-github-accent hover:underline"
                          >
                            Edit & Publish
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center py-24 text-github-text-secondary">
              <p className="text-lg mb-2">No repositories connected</p>
              <p className="text-sm">Install the GitHub App to get started</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
