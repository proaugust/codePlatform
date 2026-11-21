import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import css from 'highlight.js/lib/languages/css'
import go from 'highlight.js/lib/languages/go'
import java from 'highlight.js/lib/languages/java'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import python from 'highlight.js/lib/languages/python'
import sql from 'highlight.js/lib/languages/sql'
import typescript from 'highlight.js/lib/languages/typescript'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

let registered = false

function ensureLanguages() {
  if (registered) return
  hljs.registerLanguage('bash', bash)
  hljs.registerLanguage('css', css)
  hljs.registerLanguage('go', go)
  hljs.registerLanguage('java', java)
  hljs.registerLanguage('javascript', javascript)
  hljs.registerLanguage('json', json)
  hljs.registerLanguage('markdown', markdown)
  hljs.registerLanguage('python', python)
  hljs.registerLanguage('sql', sql)
  hljs.registerLanguage('typescript', typescript)
  hljs.registerLanguage('xml', xml)
  hljs.registerLanguage('yaml', yaml)
  registered = true
}

const EXT_LANG: Record<string, string> = {
  java: 'java',
  go: 'go',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  vue: 'xml',
  html: 'xml',
  htm: 'xml',
  xml: 'xml',
  svg: 'xml',
  css: 'css',
  scss: 'css',
  less: 'css',
  json: 'json',
  md: 'markdown',
  markdown: 'markdown',
  yml: 'yaml',
  yaml: 'yaml',
  py: 'python',
  sql: 'sql',
  sh: 'bash',
  bash: 'bash',
  bat: 'bash',
  cmd: 'bash',
  properties: 'bash',
  gradle: 'java',
  mod: 'go',
  sum: 'bash',
}

function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function languageFromPath(path: string): string | null {
  const name = path.split(/[/\\]/).pop() || ''
  if (name === 'Dockerfile' || name === 'dockerfile') return 'bash'
  if (name === 'Makefile') return 'bash'
  if (name === 'pom.xml') return 'xml'
  const dot = name.lastIndexOf('.')
  if (dot < 0) return null
  return EXT_LANG[name.slice(dot + 1).toLowerCase()] || null
}

/** 返回可安全 v-html 的高亮 HTML */
export function highlightCode(content: string, path: string): string {
  ensureLanguages()
  if (!content) return ''
  const lang = languageFromPath(path)
  try {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(content, { language: lang, ignoreIllegals: true }).value
    }
    return hljs.highlightAuto(content).value
  } catch {
    return escapeHtml(content)
  }
}
