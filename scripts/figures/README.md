# 本书自绘配图（scripts/figures）

`specs.py` 写每张图的图题、插入位置、图源和绘制函数，`figlib.py` 是绘制库，`render.py` 把全部自绘图渲染到各册 `assets/`：

```bash
python3 scripts/figures/render.py      # 结尾打印"无残留溢出"才算通过
```

中册的自绘图在 `中册-行业解决方案/assets/sources.json` 里登记了 `asset_sha256`，改图后要同步更新，否则 `validate-middle.py` 报 "Figure changed after source registration"。

## 全书配图规范

| 项目 | 要求 |
|---|---|
| 成图宽度 | 14.504 cm，300 dpi 下为 1713 px（`figlib.W`）。docx 中按版心宽 14.5 cm 显示，图内字号即印刷字号 |
| 图内文字 | **最小 9 pt（小五）**，包括框内标签、注释、坐标轴、刻度、图例和数值标注（`figlib.MIN_FS`） |
| 不自动缩字 | 文字放不下时，`render.py` 报"框内文字放不下"或"文字越出画布"，不会自动缩小字号。处理办法是加大框、调整布局，或在不改变含义的前提下缩短措辞；数字、数据和出自来源的术语保持原文 |
| 五号（10.5 pt） | 只用于图题和表格，图里的文字不受这条约束 |
| 线宽 | 普通线 0.75 pt，强调线 1.0 pt，辅助虚线不低于 0.6 pt |
| 配色与字体 | 黑白灰加强调色深青 #1F6F8B；字体 Noto Sans CJK SC；图题不画进图内，由正文图注给出 |

布局坐标按宽 15 个单位的网格书写（`figlib.LW`），整体按 `K = W / LW` 等比缩放到 14.504 cm。字号和线宽不随网格缩放，是成图上的实际磅值。
