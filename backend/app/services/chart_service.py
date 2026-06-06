"""
图表生成服务
输入：SQL 查询结果（rows + columns）
输出：Chart.js 兼容的 ChartData 结构
依据：前端 Visualization 组件的 schema
"""
from typing import Literal
import re

# 调色板（与前端一致）
PALETTE = [
    "#1677ff", "#52c41a", "#faad14", "#f5222d",
    "#722ed1", "#13c2c2", "#eb2f96", "#a0d911",
]

AGG_KEYWORDS = ("SUM", "AVG", "COUNT", "MIN", "MAX", "TOTAL")


def detect_chart_type(columns: list[str], rows: list[list]) -> Literal["bar", "line", "pie", "table"]:
    """根据列名启发式推荐图表类型"""
    if not rows or not columns:
        return "table"
    if len(columns) < 2:
        return "table"

    # 第一列当 label，其余为数值列
    has_numeric = any(_is_number(v) for v in rows[0][1:] if v is not None)
    if not has_numeric:
        return "table"

    upper_cols = [c.upper() for c in columns]
    # 含日期/时间列 + 数值 → 折线
    if any(re.search(r"(date|month|day|time|week|year|日|月|年)", c, re.I) for c in columns):
        return "line"
    # 数值列含 SUM/COUNT/AVG → 柱状
    if any(any(kw in c for kw in AGG_KEYWORDS) for c in upper_cols):
        return "bar"
    # 单行 + 少量数值 → 饼图
    if len(rows) == 1 and len(columns) <= 6:
        return "pie"
    return "bar"


def _is_number(v) -> bool:
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return True
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def build_chart(
    columns: list[str],
    rows: list[list],
    title: str | None = None,
    chart_type: str | None = None,
) -> dict:
    """
    构造 ChartData（与前端 ChatArea / Visualization 类型一致）
    """
    if not rows or not columns:
        return {
            "type": "table",
            "title": title,
            "labels": [],
            "datasets": [],
            "tableData": [],
        }

    # 自动类型
    if not chart_type:
        chart_type = detect_chart_type(columns, rows)

    # 第一列 = label，其余列 = 每个 series
    label_col = columns[0]
    labels = [str(r[0]) if r[0] is not None else "" for r in rows]

    # 找到所有数值列
    value_cols = []
    for ci in range(1, len(columns)):
        # 取该列的样本判断是否为数值
        sample = next((r[ci] for r in rows if r[ci] is not None), None)
        if _is_number(sample):
            value_cols.append(ci)

    if not value_cols:
        return {
            "type": "table",
            "title": title,
            "labels": labels,
            "datasets": [],
            "tableData": _rows_to_dicts(columns, rows),
        }

    datasets = []
    for di, ci in enumerate(value_cols):
        col_name = columns[ci]
        data = [_to_float(r[ci]) for r in rows]
        ds = {
            "label": col_name,
            "data": data,
        }
        if chart_type in ("bar", "pie"):
            ds["backgroundColor"] = (
                PALETTE[: len(rows)] if len(value_cols) == 1
                else PALETTE[di % len(PALETTE)]
            )
        if chart_type == "line":
            ds["borderColor"] = PALETTE[di % len(PALETTE)]
            ds["backgroundColor"] = PALETTE[di % len(PALETTE)] + "20"  # alpha
            ds["tension"] = 0.4
        datasets.append(ds)

    result = {
        "type": chart_type,
        "title": title,
        "labels": labels,
        "datasets": datasets,
    }
    if chart_type == "table":
        result["tableData"] = _rows_to_dicts(columns, rows)
    return result


def _to_float(v):
    if v is None:
        return 0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def _rows_to_dicts(columns: list[str], rows: list[list]) -> list[dict]:
    return [dict(zip(columns, r)) for r in rows]
