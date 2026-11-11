import './App.css'
import HomePage from './pages/HomePage'

function App() {
  return (
    <div className="shell">
      <nav className="nav">
        <span className="brand">Code Platform · React</span>
        <span className="muted" style={{ color: '#94a3b8' }}>
          调用 Py Agent → 生成 Java 项目
        </span>
      </nav>
      <HomePage />
    </div>
  )
}

export default App
