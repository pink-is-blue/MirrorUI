import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const GENERATED_ENTRY = './components/generated/AppBody.jsx'

const BENCHMARK_DEFAULTS = {
  simple_stripe: 'https://stripe.com',
  simple_notion: 'https://www.notion.so',
  medium_amazon: 'https://www.amazon.com',
  medium_bbc: 'https://www.bbc.com',
  complex_apple: 'https://www.apple.com',
  complex_airbnb: 'https://www.airbnb.com',
}

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

function App() {
  const [url, setUrl] = useState('https://example.com')
  const [loading, setLoading] = useState(false)
  const [loadingMsg, setLoadingMsg] = useState('Generating...')
  const [benchmarkLoading, setBenchmarkLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [benchmarkResult, setBenchmarkResult] = useState(null)
  const [layout, setLayout] = useState(null)
  const [codeFiles, setCodeFiles] = useState({})
  const [selectedNodeId, setSelectedNodeId] = useState('')
  const [editor, setEditor] = useState({ text: '', href: '', image_src: '', class_name: '' })
  const [GeneratedComponent, setGeneratedComponent] = useState(null)
  const [compareMode, setCompareMode] = useState('overlay')
  const [overlayOpacity, setOverlayOpacity] = useState(0.1)

  const generatedCount = useMemo(() => (result?.written || []).length, [result])
  const screenshotUrl = useMemo(() => {
    if (!result?.screenshot) return `${API_BASE}/api/screenshot`
    const ts = Date.now()
    return `${API_BASE}/api/screenshot?t=${ts}`
  }, [result])

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
        const [layoutRes, codeRes] = await Promise.all([
          fetch(`${API_BASE}/api/layout`),
          fetch(`${API_BASE}/api/code`),
        ])

        if (cancelled) return

        if (layoutRes.ok) {
          const payload = await readApiPayload(layoutRes)
          if (!cancelled) {
            setLayout(payload.layout)
          }
        }

        if (codeRes.ok) {
          const payload = await readApiPayload(codeRes)
          if (cancelled) return

          const files = payload.files || {}
          setCodeFiles(files)

          if (files['src/components/generated/AppBody.jsx']) {
            await loadGeneratedPreview()
          }
        }
      } catch {
        // Keep shell usable even if API is restarting.
      }
    }

    bootstrapGeneratedState()

    return () => {
      cancelled = true
    }
  }, [])

  async function refreshLayoutAndCode() {
    const [layoutRes, codeRes] = await Promise.all([
      fetch(`${API_BASE}/api/layout`),
      fetch(`${API_BASE}/api/code`),
    ])
    if (layoutRes.ok) {
      const payload = await readApiPayload(layoutRes)
      setLayout(payload.layout)
    }
    if (codeRes.ok) {
      const payload = await readApiPayload(codeRes)
      setCodeFiles(payload.files || {})
    }
  }

  async function loadGeneratedPreview() {
    try {
      const module = await import(GENERATED_ENTRY)
      setGeneratedComponent(() => module.default)
      setError('')
    } catch {
      setGeneratedComponent(null)
      setError('Generated preview is not available yet. Run Generate first.')
    }
  }

  async function onGenerate(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)
    setGeneratedComponent(null)
    setLoadingMsg('Starting generation...')

    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
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

      let jobResult = null
      while (true) {
        await new Promise((r) => setTimeout(r, 2000))
        const elapsed = Math.round((Date.now() - startedAt) / 1000)
        setLoadingMsg(`Capturing & generating... (${elapsed}s)`)

        const pollRes = await fetch(`${API_BASE}/api/job/${jobId}`)
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
      setLoadingMsg('Generating...')
    }
  }

  async function onRunBenchmarks() {
    setBenchmarkLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/benchmark`, {
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
      const res = await fetch(`${API_BASE}/api/editor/update-node`, {
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
    <div className="app-shell">
      <div className="mesh" aria-hidden="true" />
      <main className="panel dashboard">
        <section className="hero">
          <p className="kicker">MIRRORUI</p>
          <h1>Website Reconstruction Lab</h1>
          <p>
            Generate editable React + Tailwind from a URL, compare against captured reference, and benchmark
            Simple/Medium/Complex tiers.
          </p>
        </section>

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
            <button type="submit" disabled={loading}>
              {loading ? loadingMsg : 'Generate'}
            </button>
          </div>
          <div className="actions">
            <button type="button" onClick={loadGeneratedPreview} className="secondary">
              Refresh Preview
            </button>
            <button type="button" onClick={refreshLayoutAndCode} className="secondary">
              Refresh Graph/Code
            </button>
            <button type="button" onClick={onRunBenchmarks} className="secondary" disabled={benchmarkLoading}>
              {benchmarkLoading ? 'Running Benchmarks...' : 'Run 3-Tier Benchmark'}
            </button>
            <a href={`${API_BASE}/api/export`} target="_blank" rel="noreferrer" className="secondary link-btn">
              Export Zip
            </a>
            <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" className="secondary link-btn">
              API Docs
            </a>
          </div>
        </form>

        {error && <div className="error">{error}</div>}

        {result?.warnings?.length ? (
          <section className="warning-panel">
            <h2>Generation Warnings</h2>
            <ul>
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
            {result.challenge_detected ? <p>Challenge hint: {result.challenge_reason || 'detected'}</p> : null}
          </section>
        ) : null}

        {result && (
          <section className="result">
            <p>
              <strong>Page Title:</strong> {result.title || 'Unknown'}
            </p>
            <p>
              <strong>Files Written:</strong> {generatedCount}
            </p>
            <p>
              <strong>SSIM:</strong> {result.metrics?.ssim ?? 'n/a'} | <strong>Style:</strong>{' '}
              {result.metrics?.visual_style_similarity ?? 'n/a'} | <strong>Structure:</strong>{' '}
              {result.metrics?.structure_similarity ?? 'n/a'}
            </p>
            <p>
              <strong>Text Accuracy:</strong> {result.metrics?.text_accuracy ?? 'n/a'} | <strong>Key Recall:</strong>{' '}
              {result.metrics?.key_element_recall ?? 'n/a'} | <strong>A11y:</strong>{' '}
              {result.metrics?.accessibility_score ?? 'n/a'}
            </p>
            <p>
              <strong>Single Pass:</strong> {result.comparison?.single_pass_quality ?? 'n/a'} |{' '}
              <strong>Dual Pass:</strong> {result.comparison?.dual_pass_quality ?? 'n/a'} | <strong>Improvement:</strong>{' '}
              {result.comparison?.improvement ?? 'n/a'}
            </p>
          </section>
        )}

        {benchmarkResult?.summary ? (
          <section className="benchmark-panel">
            <h2>3-Tier Benchmark Summary</h2>
            <p>
              <strong>Mean SSIM:</strong> {benchmarkResult.summary.mean?.ssim ?? 'n/a'} | <strong>Mean Text:</strong>{' '}
              {benchmarkResult.summary.mean?.text_accuracy ?? 'n/a'} | <strong>Mean Key Recall:</strong>{' '}
              {benchmarkResult.summary.mean?.key_element_recall ?? 'n/a'}
            </p>
            <div className="benchmark-table-wrap">
              <table className="benchmark-table">
                <thead>
                  <tr>
                    <th>Site</th>
                    <th>Score</th>
                    <th>Challenge</th>
                  </tr>
                </thead>
                <tbody>
                  {(benchmarkResult.summary.ranked || []).map((row) => (
                    <tr key={row.site}>
                      <td>{row.site}</td>
                      <td>{row.score}</td>
                      <td>{benchmarkResult.runs?.[row.site]?.challenge_detected ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        <section className="workspace-grid">
          <article className="preview compare-workspace" onClick={onPreviewClick}>
            <div className="compare-head">
              <h2>Compare Workspace</h2>
              <div className="compare-controls">
                <label>
                  Mode
                  <select value={compareMode} onChange={(e) => setCompareMode(e.target.value)}>
                    <option value="overlay">Overlay</option>
                    <option value="recreated">Recreated Only</option>
                    <option value="side">Side-by-Side</option>
                  </select>
                </label>
                <label>
                  Overlay
                  <input
                    type="range"
                    min="0"
                    max="0.35"
                    step="0.01"
                    value={overlayOpacity}
                    onChange={(e) => setOverlayOpacity(Number(e.target.value))}
                  />
                </label>
              </div>
            </div>
            <p className="hint">Click in recreated view to select/edit nodes. Use side-by-side to inspect fidelity quickly.</p>

            {!GeneratedComponent ? <p>Run generation to load the preview.</p> : null}

            {GeneratedComponent && compareMode !== 'side' ? (
              <div className="preview-stage">
                <GeneratedComponent
                  selectedNodeId={selectedNodeId}
                  showReferenceOverlay={compareMode === 'overlay'}
                  referenceOpacity={overlayOpacity}
                />
              </div>
            ) : null}

            {GeneratedComponent && compareMode === 'side' ? (
              <div className="split-compare">
                <div className="reference-pane">
                  <h3>Reference Capture</h3>
                  <img src={screenshotUrl} alt="Reference website capture" />
                </div>
                <div className="recreated-pane">
                  <h3>Recreated Editable UI</h3>
                  <GeneratedComponent selectedNodeId={selectedNodeId} showReferenceOverlay={false} referenceOpacity={0} />
                </div>
              </div>
            ) : null}
          </article>

          <article className="editor-panel">
            <h2>Node Editor</h2>
            <p className="hint">Selected Node: {selectedNodeId || 'none'}</p>
            <form onSubmit={onApplyEdit} className="editor-form">
              <label htmlFor="node-text">Text</label>
              <textarea
                id="node-text"
                value={editor.text}
                onChange={(e) => setEditor((prev) => ({ ...prev, text: e.target.value }))}
              />
              <label htmlFor="node-href">Link (href)</label>
              <input
                id="node-href"
                value={editor.href}
                onChange={(e) => setEditor((prev) => ({ ...prev, href: e.target.value }))}
              />
              <label htmlFor="node-image">Image src</label>
              <input
                id="node-image"
                value={editor.image_src}
                onChange={(e) => setEditor((prev) => ({ ...prev, image_src: e.target.value }))}
              />
              <label htmlFor="node-class">Tailwind classes</label>
              <input
                id="node-class"
                value={editor.class_name}
                onChange={(e) => setEditor((prev) => ({ ...prev, class_name: e.target.value }))}
              />
              <button type="submit" disabled={!selectedNodeId || loading}>
                Apply Edit + Regenerate
              </button>
            </form>
          </article>

          <article className="code-panel">
            <h2>Generated Code</h2>
            <p className="hint">{Object.keys(codeFiles).length} files</p>
            <pre>{codeFiles['src/components/generated/AppBody.jsx'] || 'Generate to view code.'}</pre>
          </article>
        </section>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')).render(<App />)
