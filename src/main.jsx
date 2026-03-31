import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const GENERATED_ENTRY = './components/generated/AppBody.jsx'

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
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [layout, setLayout] = useState(null)
  const [codeFiles, setCodeFiles] = useState({})
  const [selectedNodeId, setSelectedNodeId] = useState('')
  const [editor, setEditor] = useState({ text: '', href: '', image_src: '', class_name: '' })
  const [GeneratedComponent, setGeneratedComponent] = useState(null)

  const generatedCount = useMemo(() => (result?.written || []).length, [result])
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
        // Keep the shell usable even if the backend is temporarily unavailable.
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
      // Fire the job — returns immediately with a job_id.
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

      // Poll until done or error.
      let jobResult = null
      while (true) {
        await new Promise(r => setTimeout(r, 2000))
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
        // still 'running' — keep polling
        if (elapsed > 180) {
          throw new Error('Generation is taking too long. The site may be blocking headless browsers.')
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
          <h1>Hybrid Vision-AI for Editable Website Interface Reconstruction</h1>
          <p>
            URL to editable React + Tailwind with dual-pass proposer-verifier generation.
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
            <a href={`${API_BASE}/api/export`} target="_blank" rel="noreferrer" className="secondary link-btn">
              Export Zip
            </a>
            <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" className="secondary link-btn">
              API Docs
            </a>
          </div>
        </form>

        {error && <div className="error">{error}</div>}

        {result && (
          <section className="result">
            <p>
              <strong>Page Title:</strong> {result.title || 'Unknown'}
            </p>
            <p>
              <strong>Files Written:</strong> {generatedCount}
            </p>
            <p>
              <strong>SSIM:</strong> {result.metrics?.ssim ?? 'n/a'} | <strong>Text Accuracy:</strong>{' '}
              {result.metrics?.text_accuracy ?? 'n/a'} | <strong>Key Recall:</strong>{' '}
              {result.metrics?.key_element_recall ?? 'n/a'} | <strong>A11y:</strong>{' '}
              {result.metrics?.accessibility_score ?? 'n/a'}
            </p>
            <p>
              <strong>Single Pass:</strong> {result.comparison?.single_pass_quality ?? 'n/a'} |{' '}
              <strong>Dual Pass:</strong> {result.comparison?.dual_pass_quality ?? 'n/a'} |{' '}
              <strong>Improvement:</strong> {result.comparison?.improvement ?? 'n/a'}
            </p>
            <ul>
              {(result.written || []).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        )}

        <section className="workspace-grid">
          <article className="preview" onClick={onPreviewClick}>
            <h2>Editable Preview</h2>
            <p className="hint">Click text, links, and cards to edit and sync generated code.</p>
            {GeneratedComponent ? (
              <div className="preview-stage">
                <GeneratedComponent selectedNodeId={selectedNodeId} />
              </div>
            ) : (
              <p>Run generation to load the preview.</p>
            )}
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
