import { useEffect, useState } from 'react'

type DocFile = { key: string; title: string; path: string; content: string }

type Status = {
  lang: string
  port: number
  root: string
  exists: boolean
  has_docs: boolean
  file_count: number
}

type GenerateResult = {
  lang: string
  root: string
  files: string[]
  used_docs: boolean
}

const TARGET = 'java'

const SAMPLE = `做一个简易图书管理后端：
- 图书：书名、作者、ISBN、库存
- 可查询图书列表、按 id 查询、新增、更新库存
- 需要健康检查接口
`

/** React：只调本仓库 Py Agent，产物目标 java */
export default function HomePage() {
  const [spec, setSpec] = useState(SAMPLE)
  const [docs, setDocs] = useState<DocFile[]>([])
  const [activeDoc, setActiveDoc] = useState(0)
  const [status, setStatus] = useState<Status | null>(null)
  const [result, setResult] = useState<GenerateResult | null>(null)
  const [error, setError] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [generating, setGenerating] = useState(false)

  const refreshStatus = () => {
    fetch(`/api/agent/${TARGET}/status`)
      .then((r) => r.json())
      .then((d) => setStatus(d))
      .catch((e) => setError(String(e)))
  }

  const loadDocs = () => {
    fetch(`/api/agent/${TARGET}/docs`)
      .then((r) => r.json())
      .then((d) => {
        if (Array.isArray(d.files)) setDocs(d.files)
      })
      .catch(() => undefined)
  }

  useEffect(() => {
    refreshStatus()
    loadDocs()
  }, [])

  const detailOf = (data: unknown) => {
    if (data && typeof data === 'object' && 'detail' in data) {
      const d = (data as { detail: unknown }).detail
      return typeof d === 'string' ? d : JSON.stringify(d)
    }
    return JSON.stringify(data)
  }

  const onAnalyze = async () => {
    setAnalyzing(true)
    setError('')
    setResult(null)
    try {
      const r = await fetch('/api/agent/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spec, target: TARGET }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(detailOf(data))
      setDocs(data.files || [])
      setActiveDoc(0)
      refreshStatus()
    } catch (e) {
      setError(String(e))
    } finally {
      setAnalyzing(false)
    }
  }

  const onGenerate = async () => {
    setGenerating(true)
    setError('')
    setResult(null)
    try {
      const r = await fetch('/api/agent/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: TARGET, use_docs: true }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(detailOf(data))
      setResult(data)
      refreshStatus()
    } catch (e) {
      setError(String(e))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <section className="page">
      <header className="page-header">
        <h1>需求 → Agent 生成（Java 产物）</h1>
        <p>
          本页只调用 Python <code>/api/agent/*</code>。生成目标 <code>target=java</code>，代码写入{' '}
          <code>auto_code/java</code>
          {status ? ` · 当前文件 ${status.file_count}` : ''}
        </p>
      </header>

      <label className="label" htmlFor="spec">
        原始需求
      </label>
      <textarea
        id="spec"
        className="spec-area"
        value={spec}
        onChange={(e) => setSpec(e.target.value)}
        spellCheck={false}
      />

      <div className="row">
        <button type="button" onClick={onAnalyze} disabled={analyzing || !spec.trim()}>
          {analyzing ? '分析中…' : '生成文档'}
        </button>
        <button type="button" onClick={onGenerate} disabled={generating || docs.length === 0}>
          {generating ? '生成中…' : '生成代码'}
        </button>
        {status && (
          <span className="muted">文档：{status.has_docs ? '已就绪' : '未生成'}</span>
        )}
      </div>

      {error && <pre className="error">{error}</pre>}

      {docs.length > 0 && (
        <div className="result">
          <h2>需求文档（Agent 产出）</h2>
          <div className="doc-tabs">
            {docs.map((d, i) => (
              <button
                key={d.path}
                type="button"
                className={i === activeDoc ? 'tab active' : 'tab'}
                onClick={() => setActiveDoc(i)}
              >
                {d.title}
              </button>
            ))}
          </div>
          <p className="muted">
            <code>{docs[activeDoc]?.path}</code>
          </p>
          <pre className="doc-body">{docs[activeDoc]?.content}</pre>
        </div>
      )}

      {result && (
        <div className="result">
          <h2>代码已写入</h2>
          <p>
            <code>{result.root}</code>
          </p>
          <ul>
            {result.files.map((f) => (
              <li key={f}>
                <code>{f}</code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
