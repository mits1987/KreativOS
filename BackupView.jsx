import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Copy, Check, Play, Download } from 'lucide-react'
import clsx from 'clsx'
import api from '../utils/api'

function CodeBlock({ language, code }) {
  const [copied, setCopied] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)

  const canRun = ['python', 'bash', 'sh', 'javascript', 'js', 'node'].includes(language?.toLowerCase())

  const copy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const run = async () => {
    setRunning(true)
    setResult(null)
    try {
      const lang = ['js', 'javascript'].includes(language) ? 'node' : language
      const res = await api.execute(code, lang)
      setResult(res)
    } catch (e) {
      setResult({ error: e.message, success: false })
    } finally {
      setRunning(false)
    }
  }

  const saveFile = () => {
    // Try to extract filename from first line comment
    const firstLine = code.split('\n')[0]
    const match = firstLine.match(/(?:filename:|file:)\s*(.+)/i)
    const filename = match ? match[1].trim() : `code.${language || 'txt'}`
    api.writeFile(filename, code)
      .then(() => alert(`Saved to workspace: ${filename}`))
      .catch(e => alert(`Save failed: ${e.message}`))
  }

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-white/10">
      <div className="flex items-center justify-between px-4 py-2 bg-surface-3 border-b border-white/10">
        <span className="text-xs text-slate-400 font-mono">{language || 'code'}</span>
        <div className="flex items-center gap-1">
          {canRun && (
            <button onClick={run} disabled={running}
              className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-accent-green/20 text-accent-green hover:bg-accent-green/30 transition-all disabled:opacity-50">
              <Play size={11} />
              {running ? 'Running…' : 'Run'}
            </button>
          )}
          <button onClick={saveFile}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-surface-4 text-slate-400 hover:text-white transition-all">
            <Download size={11} />
          </button>
          <button onClick={copy}
            className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-surface-4 text-slate-400 hover:text-white transition-all">
            {copied ? <Check size={11} className="text-accent-green" /> : <Copy size={11} />}
          </button>
        </div>
      </div>
      <SyntaxHighlighter
        language={language || 'text'}
        style={oneDark}
        customStyle={{ margin: 0, background: '#12121a', padding: '16px', fontSize: '13px' }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
      {result && (
        <div className={clsx('px-4 py-3 border-t border-white/10 text-xs font-mono',
          result.success ? 'bg-green-950/30 text-green-300' : 'bg-red-950/30 text-red-300')}>
          <div className="text-slate-400 mb-1">{'>'} Output</div>
          {result.stdout && <pre className="whitespace-pre-wrap text-green-300">{result.stdout}</pre>}
          {result.stderr && <pre className="whitespace-pre-wrap text-yellow-300">{result.stderr}</pre>}
          {result.error && <pre className="whitespace-pre-wrap text-red-300">{result.error}</pre>}
        </div>
      )}
    </div>
  )
}

export default function MessageRenderer({ content, isStreaming }) {
  return (
    <div className={clsx('prose prose-invert max-w-none text-sm leading-relaxed', isStreaming && 'typing-cursor')}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const code = String(children).replace(/\n$/, '')
            if (!inline && (match || code.includes('\n'))) {
              return <CodeBlock language={match?.[1]} code={code} />
            }
            return (
              <code className="bg-surface-3 text-accent-purple px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
                {children}
              </code>
            )
          },
          p: ({ children }) => <p className="mb-3 text-slate-300 leading-relaxed">{children}</p>,
          h1: ({ children }) => <h1 className="text-xl font-bold text-white mb-3 mt-4">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold text-white mb-2 mt-4">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-semibold text-slate-200 mb-2 mt-3">{children}</h3>,
          ul: ({ children }) => <ul className="mb-3 pl-5 space-y-1 text-slate-300">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 pl-5 space-y-1 text-slate-300 list-decimal">{children}</ol>,
          li: ({ children }) => <li className="text-slate-300">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-accent-purple pl-4 my-3 text-slate-400 italic">{children}</blockquote>
          ),
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent-purple hover:underline">{children}</a>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-3">
              <table className="w-full text-sm border-collapse border border-white/10">{children}</table>
            </div>
          ),
          th: ({ children }) => <th className="border border-white/10 px-3 py-2 bg-surface-3 text-left font-medium text-white">{children}</th>,
          td: ({ children }) => <td className="border border-white/10 px-3 py-2 text-slate-300">{children}</td>,
          hr: () => <hr className="border-white/10 my-4" />,
          strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
