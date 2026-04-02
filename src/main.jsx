import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import MirrorRenderer from './components/runtime/MirrorRenderer.jsx'
import './index.css'

const BUILD_API_BASE = import.meta.env.VITE_API_BASE || ''
const LS_KEY = 'mirrorui_api_base'

// Detect if running on GitHub Pages (needs explicit backend URL)
const IS_GITHUB_PAGES = typeof window !== 'undefined' && window.location.hostname.endsWith('github.io')
// Detect if running inside a Codespaces port-forwarded URL (proxy works, no config needed)
const IS_CODESPACES = typeof window !== 'undefined' && window.location.hostname.endsWith('app.github.dev')

const BENCHMARK_DEFAULTS = {
  simple_stripe: 'https://stripe.com',
  simple_notion: 'https://www.notion.so',
  medium_amazon: 'https://www.amazon.com',
  medium_bbc: 'https://www.bbc.com',
  complex_apple: 'https://www.apple.com',
  complex_airbnb: 'https://www.airbnb.com',
}

const GENERATION_STEPS = [
  'Launching browser…',
  'Capturing screenshot…',
  'Extracting DOM & styles…',
  'Building layout graph…',
  'Segmenting components…',
  'Running proposer pass…',
  'Running verifier pass…',
  'Writing files…',
]

async function readApiPayload(res) {
  const raw = await res.text()
  if (!raw) {
    return { ok: false, error: `Empty response (HTTP ${res.status})` }
  }
  try {
    return JSON.parse(raw)
  } catch {
    const preview = raw.slice(0, 200).replace(/\s+/g, ' ').trim()
    return {
      ok: false,
      error: `Invalid JSON response (HTTP ${res.status})${preview ? `: ${preview}` : ''}`,
    }
  }
}

function MetricBadge({ label, value }) {
  const num = parseFloat(value)
  const pct = isNaN(num) ? null : Math.round(num * 100)
  const color = pct === null ? '#64748b' : pct >= 70 ? '#16a34a' : pct >= 45 ? '#ca8a04' : '#dc2626'
  return (
    <span className="metric-badge" style={{ '--badge-color': color }}>
      <span className="metric-label">{label}</span>
      <span className="metric-value">{pct !== null ? `${pct}%` : value ?? 'n/a'}</span>
    </span>
  )
}

function CodeTabs({ files }) {
  const entries = Object.entries(files)
  const [active, setActive] = useState(entries[0]?.[0] || '')
  useEffect(() => {
    if (entries.length && !files[active]) setActive(entries[0][0])
  }, [files])

  if (!entries.length) return <p className="hint">Generate to view code.</p>

  const shortName = (path) => path.split('/').pop()

  return (
    <div className="code-tabs-wrap">
      <div className="code-tab-bar">
        {entries.map(([path]) => (
          <button
            key={path}
            type="button"
            className={`code-tab ${active === path ? 'code-tab-active' : ''}`}
            onClick={() => setActive(path)}
            title={path}
          >
            {shortName(path)}
          </button>
        ))}
      </div>
      <pre className="code-view">{files[active] || ''}</pre>
    </div>
  )
}

function SetupModal({ onSave }) {
  const [input, setInput] = useState('')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null) // null | 'ok' | 'fail'

  async function testConnection(url) {
    const trimmed = url.replace(/\/$/, '').trim()
    if (!trimmed) return
    setTesting(true)
    setTestResult(null)
    try {
      const res = await fetch(`${trimmed}/api/layout`, { signal: AbortSignal.timeout(5000) })
      setTestResult(res.ok || res.status === 404 ? 'ok' : 'fail')
    } catch {
      setTestResult('fail')
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="setup-overlay">
      <div className="setup-modal">
        <div className="setup-modal-icon">🪞</div>
        <h2>Connect Backend</h2>
        <p>
          MirrorUI needs a running Python backend to capture and reconstruct websites.
          The frontend is hosted on GitHub Pages (static), so you need to point it at your backend.
        </p>
        <div className="setup-steps">
          <div className="setup-step">
            <span className="setup-step-num">1</span>
            <span>Start the backend in your terminal or Codespaces:</span>
          </div>
          <pre className="setup-code">uvicorn main:app --host 0.0.0.0 --port 8000</pre>
          <div className="setup-step">
            <span className="setup-step-num">2</span>
            <span>If using Codespaces, open the <strong>Ports</strong> panel → right-click port 8000 → <strong>Make Public</strong> → copy the URL.</span>
          </div>
          <div className="setup-step">
            <span className="setup-step-num">3</span>
            <span>Paste the backend URL below and test the connection:</span>
          </div>
        </div>
        <div className="setup-input-row">
          <input
            value={input}
            onChange={(e) => { setInput(e.target.value); setTestResult(null) }}
            placeholder="https://your-codespace-8000.app.github.dev  or  http://localhost:8000"
            onKeyDown={(e) => e.key === 'Enter' && testConnection(input)}
          />
          <button type="button" onClick={() => testConnection(input)} disabled={testing || !input.trim()}>
            {testing ? '…' : 'Test'}
          </button>
        </div>
        {testResult === 'ok' && <p className="setup-test-ok">✅ Connected! Click Save to continue.</p>}
        {testResult === 'fail' && <p className="setup-test-fail">❌ Could not reach backend. Check the URL and make sure the server is running.</p>}
        <div className="setup-presets">
          <span>Quick presets:</span>
          <button type="button" className="secondary" onClick={() => { setInput('http://localhost:8000'); setTestResult(null) }}>localhost:8000</button>
        </div>
        <button
          type="button"
          className="setup-save-btn"
          disabled={!input.trim() || testResult !== 'ok'}
          onClick={() => onSave(input)}
        >
          Save &amp; Continue →
        </button>
      </div>
    </div>
  )
}

function App() {
  const [url, setUrl] = useState('https://example.com')
  const storedBase = localStorage.getItem(LS_KEY) ?? BUILD_API_BASE
  // On Codespaces, same-origin proxy always works — no config needed
  const [apiBase, setApiBase] = useState(() => IS_CODESPACES ? '' : storedBase)
  const [showApiConfig, setShowApiConfig] = useState(false)
  const [apiBaseInput, setApiBaseInput] = useState(() => IS_CODESPACES ? '' : storedBase)
  // Show setup modal if on GitHub Pages and no backend configured
  const [showSetup, setShowSetup] = useState(() => IS_GITHUB_PAGES && !storedBase)
  const [loading, setLoading] = useState(false)
  const [loadingStep, setLoadingStep] = useState(0)
  const [loadingMsg, setLoadingMsg] = useState('Generating...')
  const [benchmarkLoading, setBenchmarkLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [benchmarkResult, setBenchmarkResult] = useState(null)
  const [pageData, setPageData] = useState(null)
  const [layout, setLayout] = useState(null)
  const [codeFiles, setCodeFiles] = useState({})
  const [selectedNodeId, setSelectedNodeId] = useState('')
  const [editor, setEditor] = useState({ text: '', href: '', image_src: '', class_name: '' })
  const [compareMode, setCompareMode] = useState('side')
  const [overlayOpacity, setOverlayOpacity] = useState(0.1)

  function saveApiBase(val) {
    const trimmed = val.replace(/\/$/, '').trim()
    setApiBase(trimmed)
    setApiBaseInput(trimmed)
    localStorage.setItem(LS_KEY, trimmed)
    setShowApiConfig(false)
    setShowSetup(false)
    setError('')
  }

  const generatedCount = useMemo(() => (result?.written || []).length, [result])
  const screenshotUrl = useMemo(() => {
    if (!result?.screenshot) return `${apiBase}/api/screenshot`
    const ts = Date.now()
    return `${apiBase}/api/screenshot?t=${ts}`
  }, [result, apiBase])

  const nodesById = useMemo(() => {
    const map = new Map()
    for (const node of layout?.nodes || []) {
      map.set(node.node_id, node)
    }
    return map
  }, [layout])

  const selectedNode = selectedNodeId ? nodesById.get(selectedNodeId) : null

  useEffect(() => {
    if (!selectedNode) {
      setEditor({ text: '', href: '', image_src: '', class_name: '' })
      return
    }
    setEditor({
      text: selectedNode.text || '',
      href: selectedNode.attrs?.href || '',
      image_src: selectedNode.attrs?.src || '',
      class_name: (selectedNode.classes || []).join(' '),
    })
  }, [selectedNodeId, selectedNode])

  useEffect(() => {
    let cancelled = false

    async function bootstrapGeneratedState() {
      try {
        const [layoutRes, codeRes, pageDataRes] = await Promise.all([
          fetch(`${apiBase}/api/layout`),
          fetch(`${apiBase}/api/code`),
          fetch(`${apiBase}/api/page-data`),
        ])

        if (cancelled) return

        if (layoutRes.ok) {
          const payload = await readApiPayload(layoutRes)
          if (!cancelled) setLayout(payload.layout)
        }

        if (codeRes.ok) {
          const payload = await readApiPayload(codeRes)
          if (!cancelled) setCodeFiles(payload.files || {})
        }

        if (pageDataRes.ok) {
          const payload = await readApiPayload(pageDataRes)
          if (!cancelled) setPageData(payload.pageData || null)
        }
      } catch {
        // Keep shell usable even if API is restarting.
      }
    }

    bootstrapGeneratedState()

    return () => { cancelled = true }
  }, [apiBase])

  async function refreshLayoutAndCode() {
    const [layoutRes, codeRes, pageDataRes] = await Promise.all([
      fetch(`${apiBase}/api/layout`),
      fetch(`${apiBase}/api/code`),
      fetch(`${apiBase}/api/page-data`),
    ])
    if (layoutRes.ok) {
      const payload = await readApiPayload(layoutRes)
      setLayout(payload.layout)
    }
    if (codeRes.ok) {
      const payload = await readApiPayload(codeRes)
      setCodeFiles(payload.files || {})
    }
    if (pageDataRes.ok) {
      const payload = await readApiPayload(pageDataRes)
      setPageData(payload.pageData || null)
    }
  }

  async function loadGeneratedPreview() {
    // Preview is now driven by /api/page-data — no dynamic import needed
    try {
      const res = await fetch(`${apiBase}/api/page-data`)
      if (res.ok) {
        const payload = await readApiPayload(res)
        setPageData(payload.pageData || null)
        setError('')
      }
    } catch {
      // Non-fatal — preview will remain empty
    }
  }

  async function onGenerate(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    setPageData(null)
    setLoadingStep(0)
    setLoadingMsg(GENERATION_STEPS[0])

    try {
      const res = await fetch(`${apiBase}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const data = await readApiPayload(res)
      if (!res.ok || !data.job_id) {
        throw new Error(data?.error || 'Failed to start generation job')
      }

      const jobId = data.job_id
      const startedAt = Date.now()
      let pollCount = 0

      let jobResult = null
      while (true) {
        await new Promise((r) => setTimeout(r, 2000))
        pollCount++
        const elapsed = Math.round((Date.now() - startedAt) / 1000)

        // Cycle through descriptive steps as we poll
        const stepIdx = Math.min(pollCount, GENERATION_STEPS.length - 1)
        setLoadingStep(stepIdx)
        setLoadingMsg(`${GENERATION_STEPS[stepIdx]} (${elapsed}s)`)

        const pollRes = await fetch(`${apiBase}/api/job/${jobId}`)
        const pollData = await readApiPayload(pollRes)

        if (pollData.status === 'done') {
          jobResult = pollData
          break
        }
        if (pollData.status === 'error') {
          throw new Error(pollData.error || 'Generation failed')
        }
        if (elapsed > 210) {
          throw new Error('Generation timed out. The site may be blocking headless capture.')
        }
      }

      setResult(jobResult)
      await refreshLayoutAndCode()
      await loadGeneratedPreview()
    } catch (err) {
      setError(err.message || 'Request failed')
    } finally {
      setLoading(false)
      setLoadingStep(0)
      setLoadingMsg('Generating...')
    }
  }

  async function onRunBenchmarks() {
    setBenchmarkLoading(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/benchmark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ urls: BENCHMARK_DEFAULTS }),
      })
      const data = await readApiPayload(res)
      if (!res.ok) throw new Error(data?.error || 'Benchmark run failed')
      setBenchmarkResult(data)
    } catch (err) {
      setError(err.message || 'Benchmark failed')
    } finally {
      setBenchmarkLoading(false)
    }
  }

  async function onApplyEdit(e) {
    e.preventDefault()
    if (!selectedNodeId) return

    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${apiBase}/api/editor/update-node`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          node_id: selectedNodeId,
          text: editor.text,
          href: editor.href,
          image_src: editor.image_src,
          class_name: editor.class_name,
        }),
      })
      const data = await readApiPayload(res)
      if (!res.ok) throw new Error(data?.error || 'Update failed')
      await refreshLayoutAndCode()
      await loadGeneratedPreview()
    } catch (err) {
      setError(err.message || 'Failed to update node')
    } finally {
      setLoading(false)
    }
  }

  function onPreviewClick(e) {
    const hit = e.target.closest?.('[data-mirror-id]')
    if (!hit) return
    const nodeId = hit.getAttribute('data-mirror-id')
    if (nodeId && nodesById.has(nodeId)) {
      setSelectedNodeId(nodeId)
    }
  }

  return (
    <>
      {showSetup && <SetupModal onSave={saveApiBase} />}
      <div className="app-shell">
        <div className="mesh" aria-hidden="true" />
        <main className="panel dashboard">
          <section className="hero">
            <p className="kicker">MIRRORUI</p>
            <h1>Website Reconstruction Lab</h1>
            <p>Generate pixel-faithful editable React + Tailwind from any URL. Benchmark across Simple / Medium / Complex tiers.</p>
          </section>

          {/* Backend URL configurator */}
          <div className="api-config-bar">
            <span className="api-config-label">
              🔌 Backend:{' '}
              <code className={`api-base-display ${apiBase ? 'connected' : IS_CODESPACES ? 'connected' : 'not-set'}`}>
                {apiBase || (IS_CODESPACES ? 'proxy (same-origin)' : 'not configured')}
              </code>
            </span>
            <button type="button" className="secondary api-config-btn" onClick={() => setShowApiConfig((v) => !v)}>
              {showApiConfig ? 'Cancel' : '⚙ Configure'}
            </button>
            {!apiBase && !IS_CODESPACES && (
              <button type="button" className="setup-trigger-btn" onClick={() => setShowSetup(true)}>
                ⚠ Setup Required
              </button>
            )}
          </div>

          {showApiConfig && (
            <div className="api-config-panel">
              <p className="hint">
                Run <code>uvicorn main:app --host 0.0.0.0 --port 8000</code> locally or in Codespaces,
                then paste its public URL below. In Codespaces: right-click port 8000 → <em>Make Public</em>.
              </p>
              <div className="row">
                <input
                  value={apiBaseInput}
                  onChange={(e) => setApiBaseInput(e.target.value)}
                  placeholder="http://localhost:8000  or  https://your-codespace-8000.app.github.dev"
                />
                <button type="button" onClick={() => saveApiBase(apiBaseInput)}>Save</button>
              </div>
              <div className="api-hints">
                <button type="button" className="secondary" onClick={() => saveApiBase('http://localhost:8000')}>localhost:8000</button>
                <button type="button" className="secondary" onClick={() => saveApiBase('')}>Clear (same-origin)</button>
              </div>
            </div>
          )}

          <form onSubmit={onGenerate} className="controls">
            <label htmlFor="url">Target URL</label>
            <div className="row">
              <input
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                required
              />
              <button type="submit" disabled={loading || (!apiBase && IS_GITHUB_PAGES)}>
                {loading ? '⏳ ' + loadingMsg : '▶ Generate'}
              </button>
            </div>
            <div className="actions">
              <button type="button" onClick={loadGeneratedPreview} className="secondary">↻ Preview</button>
              <button type="button" onClick={refreshLayoutAndCode} className="secondary">↻ Graph/Code</button>
              <button type="button" onClick={onRunBenchmarks} className="secondary" disabled={benchmarkLoading}>
                {benchmarkLoading ? 'Running…' : '📊 Benchmark'}
              </button>
              <a href={`${apiBase}/api/export`} target="_blank" rel="noreferrer" className="secondary link-btn">⬇ Export Zip</a>
              <a href={`${apiBase}/api/screenshot`} target="_blank" rel="noreferrer" className="secondary link-btn">📸 Screenshot</a>
              <a href={`${apiBase}/docs`} target="_blank" rel="noreferrer" className="secondary link-btn">📖 API Docs</a>
            </div>
          </form>

          {/* Progress stepper shown while loading */}
          {loading && (
            <div className="progress-stepper" role="status" aria-live="polite">
              {GENERATION_STEPS.map((step, idx) => (
                <div key={step} className={`progress-step ${idx < loadingStep ? 'done' : idx === loadingStep ? 'active' : ''}`}>
                  <span className="step-dot" />
                  <span className="step-label">{step}</span>
                </div>
              ))}
            </div>
          )}

          {error && <div className="error" role="alert">{error}</div>}

          {result?.warnings?.length ? (
            <section className="warning-panel">
              <h2>⚠ Warnings</h2>
              <ul>{result.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
              {result.challenge_detected ? <p className="hint">Hint: {result.challenge_reason || 'challenge detected'}</p> : null}
            </section>
          ) : null}

          {result && (
            <section className="result">
              <div className="result-header">
                <span><strong>{result.title || 'Untitled'}</strong></span>
                <span className="hint">{generatedCount} file{generatedCount !== 1 ? 's' : ''} written</span>
              </div>
              <div className="metrics-row">
                <MetricBadge label="SSIM" value={result.metrics?.ssim} />
                <MetricBadge label="Style" value={result.metrics?.visual_style_similarity} />
                <MetricBadge label="Structure" value={result.metrics?.structure_similarity} />
                <MetricBadge label="Text" value={result.metrics?.text_accuracy} />
                <MetricBadge label="Recall" value={result.metrics?.key_element_recall} />
                <MetricBadge label="A11y" value={result.metrics?.accessibility_score} />
              </div>
              <div className="metrics-row">
                <MetricBadge label="Single pass" value={result.comparison?.single_pass_quality} />
                <MetricBadge label="Dual pass" value={result.comparison?.dual_pass_quality} />
                <MetricBadge label="Δ Improvement" value={result.comparison?.improvement} />
              </div>
            </section>
          )}

          {benchmarkResult?.summary ? (
            <section className="benchmark-panel">
              <h2>3-Tier Benchmark</h2>
              <div className="metrics-row">
                <MetricBadge label="Mean SSIM" value={benchmarkResult.summary.mean?.ssim} />
                <MetricBadge label="Mean Text" value={benchmarkResult.summary.mean?.text_accuracy} />
                <MetricBadge label="Mean Recall" value={benchmarkResult.summary.mean?.key_element_recall} />
              </div>
              <div className="benchmark-table-wrap">
                <table className="benchmark-table">
                  <thead>
                    <tr><th>Site</th><th>Score</th><th>Nodes</th><th>Challenge</th></tr>
                  </thead>
                  <tbody>
                    {(benchmarkResult.summary.ranked || []).map((row) => (
                      <tr key={row.site}>
                        <td>{row.site}</td>
                        <td>{Math.round(row.score * 100)}%</td>
                        <td>{benchmarkResult.runs?.[row.site]?.metrics?.recreated_nodes ?? '—'}</td>
                        <td>{benchmarkResult.runs?.[row.site]?.challenge_detected ? '⚠ Yes' : '✓ No'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          <section className="workspace-grid">
            {/* Compare workspace — full width row */}
            <article className="compare-workspace" onClick={onPreviewClick}>
              <div className="compare-head">
                <h2>Compare Workspace</h2>
                <div className="compare-controls">
                  <label>
                    Mode
                    <select value={compareMode} onChange={(e) => setCompareMode(e.target.value)}>
                      <option value="side">Side-by-Side</option>
                      <option value="overlay">Overlay</option>
                      <option value="recreated">Recreated Only</option>
                    </select>
                  </label>
                  {compareMode === 'overlay' && (
                    <label>
                      Opacity
                      <input
                        type="range" min="0" max="0.35" step="0.01"
                        value={overlayOpacity}
                        onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                      />
                    </label>
                  )}
                </div>
              </div>
              <p className="hint">Click nodes in the recreated view to select them for editing.</p>

              {!pageData && <p className="hint">Run generation to load the preview.</p>}

              {pageData && compareMode !== 'side' && (
                <div className="preview-stage">
                  <MirrorRenderer
                    pageData={{ ...pageData, screenshotUrl: compareMode === 'overlay' ? screenshotUrl : undefined }}
                    selectedNodeId={selectedNodeId}
                    showReferenceOverlay={compareMode === 'overlay'}
                    referenceOpacity={overlayOpacity}
                  />
                </div>
              )}

              {pageData && compareMode === 'side' && (
                <div className="split-compare">
                  <div className="reference-pane">
                    <h3>Reference Capture</h3>
                    <img src={screenshotUrl} alt="Reference website capture" />
                  </div>
                  <div className="recreated-pane">
                    <h3>Recreated (Editable)</h3>
                    <MirrorRenderer
                      pageData={pageData}
                      selectedNodeId={selectedNodeId}
                      showReferenceOverlay={false}
                      referenceOpacity={0}
                    />
                  </div>
                </div>
              )}
            </article>

            {/* Node editor */}
            <article className="editor-panel">
              <h2>Node Editor</h2>
              {selectedNodeId ? (
                <>
                  <p className="hint selected-node-id" title={selectedNodeId}>
                    🎯 {selectedNodeId}
                  </p>
                  {selectedNode && (
                    <div className="node-preview-info">
                      <span className="node-tag-badge">&lt;{selectedNode.tag}&gt;</span>
                      {selectedNode.text && <span className="node-text-preview">{selectedNode.text.slice(0, 60)}</span>}
                    </div>
                  )}
                </>
              ) : (
                <p className="hint">Click a node in the preview to select it.</p>
              )}
              <form onSubmit={onApplyEdit} className="editor-form">
                <label htmlFor="node-text">Text content</label>
                <textarea
                  id="node-text"
                  value={editor.text}
                  onChange={(e) => setEditor((prev) => ({ ...prev, text: e.target.value }))}
                  placeholder="Inner text…"
                />
                <label htmlFor="node-href">Link (href)</label>
                <input
                  id="node-href"
                  value={editor.href}
                  onChange={(e) => setEditor((prev) => ({ ...prev, href: e.target.value }))}
                  placeholder="https://…"
                />
                <label htmlFor="node-image">Image src</label>
                <input
                  id="node-image"
                  value={editor.image_src}
                  onChange={(e) => setEditor((prev) => ({ ...prev, image_src: e.target.value }))}
                  placeholder="https://…/image.png"
                />
                <label htmlFor="node-class">Tailwind classes</label>
                <input
                  id="node-class"
                  value={editor.class_name}
                  onChange={(e) => setEditor((prev) => ({ ...prev, class_name: e.target.value }))}
                  placeholder="bg-blue-500 text-white…"
                />
                <button type="submit" disabled={!selectedNodeId || loading}>
                  ✎ Apply &amp; Regenerate
                </button>
              </form>
            </article>

            {/* Tabbed code viewer */}
            <article className="code-panel">
              <h2>Generated Code</h2>
              <CodeTabs files={codeFiles} />
            </article>
          </section>
        </main>
      </div>
    </>
  )
}

createRoot(document.getElementById('root')).render(<App />)
