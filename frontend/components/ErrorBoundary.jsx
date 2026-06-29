import React from 'react'

/**
 * Phase 1 Fix: ErrorBoundary
 * Catches render errors in any child view so the whole app doesn't crash.
 * Wrap the main content area in App.jsx with <ErrorBoundary>.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    this.setState({ info })
    console.error('[KreativOS ErrorBoundary]', error, info)
  }

  clearLocalData() {
    try {
      localStorage.removeItem('conversations')
      localStorage.removeItem('selectedModel')
      localStorage.removeItem('selectedAgent')
    } catch (_) {}
    window.location.reload()
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex items-center justify-center h-screen bg-surface-0">
        <div className="glass rounded-2xl border border-red-500/20 p-8 max-w-lg w-full mx-4">
          <div className="text-4xl mb-4 text-center">⚠️</div>
          <h2 className="text-lg font-bold text-white text-center mb-2">
            Something went wrong
          </h2>
          <p className="text-sm text-slate-400 text-center mb-6">
            A render error occurred in the current view. Your workspace files are safe.
          </p>

          {this.state.error && (
            <pre className="text-xs text-red-400 bg-surface-2 rounded-lg p-3 mb-5 overflow-auto max-h-32 border border-red-500/10">
              {this.state.error.toString()}
            </pre>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => window.location.reload()}
              className="flex-1 btn-primary text-sm"
            >
              Reload page
            </button>
            <button
              onClick={this.clearLocalData}
              className="flex-1 px-4 py-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 text-sm transition-all"
            >
              Clear local data &amp; reload
            </button>
          </div>

          <p className="text-xs text-slate-600 text-center mt-4">
            If this keeps happening, try clearing local data.
            Your workspace files on the server are not affected.
          </p>
        </div>
      </div>
    )
  }
}
