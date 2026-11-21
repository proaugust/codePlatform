import { useEffect, useState } from 'react'

type DocFile = { key: string; title: string; path: string; content: string }

type Status = {
  lang: string
  port: number
  root: string
  exists: boolean
  has_docs: boolean
  file_count: number
  frontend_exists?: boolean
  frontend_root?: string | null
  frontend_port?: number | null
}

type GenerateResult = {
  lang: string
  root: string
  files: string[]
  used_docs: boolean
  frontend_ok?: boolean | null
  frontend_port?: number | null
  frontend_root?: string | null
  frontend_error?: string | null
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
  const [startingFe, setStartingFe] = useState(false)
  const [feMsg, setFeMsg] = useState('')

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
    setFeMsg('')
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

  const onStartFrontend = async () => {
    setStartingFe(true)
    setError('')
    setFeMsg('')
    try {
      const r = await fetch(`/api/agent/${TARGET}/frontend/start`, { method: 'POST' })
      const data = await r.json()
      if (!r.ok) throw new Error(detailOf(data))
      setFeMsg(typeof data.message === 'string' ? data.message : '已请求启动业务前端')
      const url = typeof data.url === 'string' ? data.url : 'http://127.0.0.1:5175'
      // 给 Vite 一点冷启动时间；已在跑则立即打开
      const delay = data.already_running ? 300 : 2500
      window.setTimeout(() => {
        window.open(url, '_blank', 'noopener,noreferrer')
      }, delay)
      refreshStatus()
    } catch (e) {
      setError(String(e))
    } finally {
      setStartingFe(false)
    }
  }

  const canStartFrontend = Boolean(status?.frontend_exists || result?.frontend_ok)

  return (
    <section className="page">
      <header className="page-header">
        <h1>需求 → Agent 生成（Java 产物）</h1>
        <p>
          本页只调用 Python <code>/api/agent/*</code>。生成目标 <code>target=java</code>，代码写入{' '}
          <code>auto_code/java</code>
          {status ? ` · 当前文件 ${status.file_count}` : ''}
        </p>
        <p className="fe-url-line">
          业务前端地址：{' '}
          <a href="http://127.0.0.1:5175" target="_blank" rel="noreferrer">
            http://127.0.0.1:5175
          </a>
          <span className="muted">
            {' '}
            （目录 <code>auto_code/frontend</code>
            {status?.frontend_exists ? ' · 已生成' : ' · 生成代码后可用'}）
          </span>
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
        <button
          type="button"
          className="btn-secondary"
          onClick={onStartFrontend}
          disabled={startingFe || !canStartFrontend}
          title={
            canStartFrontend
              ? '启动 auto_code/frontend（java/go 共用）'
              : '请先生成代码（会同步生成 Vue 业务前端）'
          }
        >
          {startingFe ? '启动中…' : '启动业务前端 (5175)'}
        </button>
        <a
          className="link-btn"
          href="http://127.0.0.1:5175"
          target="_blank"
          rel="noreferrer"
        >
          打开 5175
        </a>
        {status && (
          <span className="muted">
            文档：{status.has_docs ? '已就绪' : '未生成'}
            {status.frontend_exists ? ' · Vue 前端已生成' : ''}
          </span>
        )}
      </div>

      {!canStartFrontend && (
        <p className="muted">提示：「启动业务前端」需先点「生成代码」（会写出 auto_code/frontend）。</p>
      )}
      {feMsg && <p className="muted">{feMsg}</p>}
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
          {result.frontend_ok && (
            <p className="muted">
              业务前端：<code>{result.frontend_root}</code>
              {result.frontend_port ? ` · 端口 ${result.frontend_port}` : ''} · 可点「启动业务前端」
            </p>
          )}
          {result.frontend_ok === false && result.frontend_error && (
            <pre className="error">业务前端生成失败：{result.frontend_error}</pre>
          )}
        </div>
      )}
    </section>
  )
}
