import { Layout } from 'antd'
import ChatManagement from './components/ChatManagement'
import ChatArea from './components/ChatArea'
import Visualization from './components/Visualization'

function App() {
  return (
    <div className="app-layout">
      <div className="left-panel">
        <div className="panel-header">聊天管理</div>
        <div className="panel-content">
          <ChatManagement />
        </div>
      </div>
      <div className="middle-panel">
        <div className="panel-header">问答区域</div>
        <div className="panel-content" style={{ display: 'flex', flexDirection: 'column' }}>
          <ChatArea />
        </div>
      </div>
      <div className="right-panel">
        <div className="panel-header">可视化图表</div>
        <div className="panel-content">
          <Visualization />
        </div>
      </div>
    </div>
  )
}

export default App
