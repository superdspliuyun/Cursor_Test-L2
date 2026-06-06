/**
 * 右侧栏 - 可视化图表展示
 * 功能：Chart.js 渲染（折线图、柱状图、饼图）+ 数据表格 + 图表类型切换
 */
import { Empty, Radio, Table, Tag, Space, Card, Tabs } from 'antd'
import {
  LineChartOutlined,
  BarChartOutlined,
  PieChartOutlined,
  TableOutlined,
} from '@ant-design/icons'
import { useEffect, useRef } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title as ChartTitle,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from 'chart.js'
import { Line, Bar, Pie, Doughnut } from 'react-chartjs-2'
import { useChatStore } from '@/store/chatStore'
import type { ChartData } from '@/services/api'

// 注册 Chart.js 组件
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  ChartTitle,
  ChartTooltip,
  Legend,
  Filler
)

const chartTypeOptions = [
  { value: 'line', label: '折线图', icon: <LineChartOutlined /> },
  { value: 'bar', label: '柱状图', icon: <BarChartOutlined /> },
  { value: 'pie', label: '饼图', icon: <PieChartOutlined /> },
  { value: 'table', label: '表格', icon: <TableOutlined /> },
]

const Visualization = () => {
  const { currentChart, chartType, setChartType } = useChatStore()

  if (!currentChart) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div style={{ color: '#999' }}>
            <div>暂无图表</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>开始对话后将自动生成图表</div>
          </div>
        }
        style={{ marginTop: 60 }}
      />
    )
  }

  return (
    <div>
      <Card
        size="small"
        title={currentChart.title || '数据图表'}
        style={{ marginBottom: 12 }}
        styles={{ body: { padding: 0 } }}
      >
        <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
          <Radio.Group
            value={chartType}
            onChange={(e) => setChartType(e.target.value)}
            optionType="button"
            size="small"
            buttonStyle="solid"
          >
            {chartTypeOptions.map((opt) => (
              <Radio.Button key={opt.value} value={opt.value}>
                <Space size={4}>
                  {opt.icon}
                  {opt.label}
                </Space>
              </Radio.Button>
            ))}
          </Radio.Group>
        </div>

        <div style={{ padding: 16, minHeight: 280 }}>
          <ChartRenderer type={chartType} chartData={currentChart} />
        </div>
      </Card>

      {currentChart.tableData && currentChart.tableData.length > 0 && chartType === 'table' && (
        <Card size="small" title="数据明细">
          <DataTable data={currentChart.tableData} />
        </Card>
      )}
    </div>
  )
}

// 图表渲染器
const ChartRenderer = ({ type, chartData }: { type: string; chartData: ChartData }) => {
  const chartRef = useRef(null)

  // 容错：data 不是 number[] 时降级为表格视图
  const safeData = chartData.datasets.every((ds) =>
    Array.isArray(ds.data) && ds.data.every((v) => typeof v === 'number' || v === null)
  )
  if (!safeData && type !== 'table') {
    return (
      <DataTable data={chartData.tableData || generateTableFromChart(chartData)} />
    )
  }

  // 公共 options 配置
  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' as const, labels: { font: { size: 12 } } },
      tooltip: { backgroundColor: 'rgba(0,0,0,0.85)' },
    },
    scales: type === 'pie' ? undefined : {
      y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
      x: { grid: { display: false } },
    },
  }

  if (type === 'line') {
    return (
      <div style={{ height: 280 }}>
        <Line
          ref={chartRef}
          data={{
            labels: chartData.labels,
            datasets: chartData.datasets.map((ds) => ({
              ...ds,
              tension: 0.4,
              fill: true,
              pointRadius: 4,
              pointHoverRadius: 6,
            })) as any,
          }}
          options={commonOptions as any}
        />
      </div>
    )
  }

  if (type === 'bar') {
    return (
      <div style={{ height: 280 }}>
        <Bar
          ref={chartRef}
          data={{
            labels: chartData.labels,
            datasets: chartData.datasets as any,
          }}
          options={commonOptions as any}
        />
      </div>
    )
  }

  if (type === 'pie') {
    return (
      <div style={{ height: 280 }}>
        <Pie
          ref={chartRef}
          data={{
            labels: chartData.labels,
            datasets: chartData.datasets.map((ds) => ({
              ...ds,
              backgroundColor: ds.backgroundColor || [
                '#1677ff', '#52c41a', '#faad14', '#f5222d',
                '#722ed1', '#13c2c2', '#eb2f96',
              ],
            })) as any,
          }}
          options={{
            ...commonOptions,
            scales: undefined,
            plugins: {
              ...commonOptions.plugins,
              legend: { position: 'right' as const },
            },
          } as any}
        />
      </div>
    )
  }

  if (type === 'table') {
    return <DataTable data={chartData.tableData || generateTableFromChart(chartData)} />
  }

  return null
}

// 从图表数据生成简单表格
const generateTableFromChart = (chartData: ChartData) => {
  if (!chartData.labels.length) return []
  const firstDataset = chartData.datasets[0]
  return chartData.labels.map((label, idx) => ({
    name: label,
    value: firstDataset?.data[idx] ?? 0,
  }))
}

// 数据表格组件
const DataTable = ({ data }: { data: Record<string, any>[] }) => {
  if (!data || data.length === 0) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="无数据" />
  }

  const columns = Object.keys(data[0]).map((key) => ({
    title: key,
    dataIndex: key,
    key,
    render: (val: any) => {
      if (typeof val === 'number') {
        return <Tag color="blue">{val.toLocaleString()}</Tag>
      }
      return val
    },
  }))

  return (
    <Table
      dataSource={data.map((row, idx) => ({ ...row, key: idx }))}
      columns={columns}
      size="small"
      pagination={{ pageSize: 10, showSizeChanger: false }}
      scroll={{ x: 'max-content' }}
    />
  )
}

export default Visualization
