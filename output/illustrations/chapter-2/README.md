# 第二章插图索引

本目录保留2026年10月12日的销售岗位版插图，与当日发行的第二章PDF对应。10月13日的第二章已改为MTL市场与客户开发主线，当前配图见[MTL插图索引](../chapter-2-mtl/README.md)。

本组16张原创插图采用浅蓝底、深蓝文字和蓝色强调风格。图题、图内标注及图注采用陈述式，分别服务职责梳理、业务诊断、任务分工与结果验证。图中关系属于本报告的分析设计，案例事实与效果口径继续以章节原文和出处为准。

[当前第二章MTL正文](../../../上册-研究报告/02-MTL-从市场到有效线索.md) · [阅读第二章配图版PDF](../../pdf/第二章-最小执行单位-从人到任务-配图版.pdf) · [查看整章插图总览](chapter-2-overview.png)

图2-13依据10月12日销售版2.4的客户拜访准备例子细化：资深销售留下判断与修改依据，经验分别整理为Skill、工具或任务示例，其他销售换入新客户资料复用，并将使用反馈带回方法修订。工具按任务需要选择，图示属于本节方法说明。

| 编号 | 所在章节 | 图题 | 文件 |
| --- | --- | --- | --- |
| 图2-01 | 2.1 | 销售职责落实为可以交接的任务产物 | [PNG](01-ltc-responsibilities.png) · [SVG](01-ltc-responsibilities.svg) |
| 图2-02 | 2.2 | 销售漏斗与六项业务改进目标 | [PNG](02-sales-funnel.png) · [SVG](02-sales-funnel.svg) |
| 图2-03 | 2.2 | 业务差距经核实后形成改进目标 | [PNG](03-business-diagnosis.png) · [SVG](03-business-diagnosis.svg) |
| 图2-04 | 2.2 | 阶段转化率按同一批入段对象计算 | [PNG](04-conversion-cohort.png) · [SVG](04-conversion-cohort.svg) |
| 图2-05 | 2.3 | 业务举措落实为可分工与可验收的任务 | [PNG](05-task-allocation.png) · [SVG](05-task-allocation.svg) |
| 图2-06 | 2.3 目标1 | 目标1：持续增加可以跟进的有效线索 | [PNG](06-goal-1-leads.png) · [SVG](06-goal-1-leads.svg) |
| 图2-07 | 2.3 目标2 | 目标2：提高线索转为商机的比例 | [PNG](07-goal-2-opportunities.png) · [SVG](07-goal-2-opportunities.svg) |
| 图2-08 | 2.3 目标3 | 目标3：形成可以交接的沟通输出 | [PNG](08-goal-3-requirements.png) · [SVG](08-goal-3-requirements.svg) |
| 图2-09 | 2.3 目标4 | 目标4：提高方案与商务准备质量 | [PNG](09-goal-4-proposals.png) · [SVG](09-goal-4-proposals.svg) |
| 图2-10 | 2.3 目标5 | 目标5：让会后任务完成并通过验收 | [PNG](10-goal-5-execution.png) · [SVG](10-goal-5-execution.svg) |
| 图2-11 | 2.3 目标6 | 目标6：围绕决策障碍推进至签约 | [PNG](11-goal-6-contracts.png) · [SVG](11-goal-6-contracts.svg) |
| 图2-12 | 2.3 成本比较 | 合格交付成本按完整投入比较 | [PNG](12-qualified-delivery-cost.png) · [SVG](12-qualified-delivery-cost.svg) |
| 图2-13 | 2.4 能力沉淀 | 个人工作方法经复用验证形成组织能力 | [PNG](13-capability-reuse.png) · [SVG](13-capability-reuse.svg) |
| 图2-14 | 2.5 前四类岗位 | 技术辅助围绕岗位业务目标展开 | [PNG](14-other-roles-a.png) · [SVG](14-other-roles-a.svg) |
| 图2-15 | 2.5 后四类岗位 | 任务条件决定技术辅助的具体范围 | [PNG](15-other-roles-b.png) · [SVG](15-other-roles-b.svg) |
| 图2-16 | 2.6 | 岗位改造以合格交付和业务结果接受检验 | [PNG](16-chapter-summary.png) · [SVG](16-chapter-summary.svg) |

## 维护与生成

正文引用PNG，便于GitHub与常用Markdown阅读器显示。PDF构建优先读取同名SVG，以矢量图元保留清晰度和可检索文字。SVG与生成器均随仓库维护，修改图内文字后重新生成，不直接修改PNG。

PNG与SVG按实际内容边界导出，四周统一保留16px留白，便于嵌入文档。内部布局仍使用1800×1280坐标，当前导出尺寸为1630×1214；总览按实际比例缩放。需要调整外围边距时，修改[drawing.py](drawing.py)中的`OUTER_MARGIN`后重新生成。每张图的实际尺寸与边距同步记录在JSON元数据中。

全部配图使用Heiti SC，正文采用Light（字重300），标题采用Medium（字重500）。PNG与PDF读取字体集合的索引1，SVG明确记录字体家族、字重和文字角色。相同角色统一字号，密集卡片使用专门的窄标题与正文样式。

| 文字角色 | 样式 | 字号 | 字重 |
| --- | --- | --- | --- |
| 图大标题 | `title` | 58px | 500 |
| 图副标题 | `subtitle` | 30px | 300 |
| 块标题 | `heading` | 36px | 500 |
| 次级标题与公式 | `subheading` | 32px | 500 |
| 窄卡片标题 | `narrow_heading` | 28px | 500 |
| 正文 | `body` | 28px | 300 |
| 密集卡片正文 | `dense_body` | 26px | 300 |
| 页眉、页脚、来源与辅助标签 | `label` | 24px | 300 |
| 流程步骤编号 | `step` | 40px | 500 |
| 漏斗阶段关键词 | `display` | 48px | 500 |

样式集中定义在[drawing.py](drawing.py)的`TEXT_STYLES`中，绘图代码通过`style`指定角色。单图JSON与主manifest同步记录字体、索引、样式规范及各图样式计数。生成器检查PNG四侧边距、SVG字体与字号字重、可见文字及元数据的一致性。

在仓库根目录运行：

```bash
python3 output/illustrations/chapter-2/build.py
python3 scripts/build-pdf.py --chapter 上册-研究报告/02-MTL-从市场到有效线索.md
python3 scripts/build-pdf.py
python3 scripts/validate.py
```

绘图依赖Pillow和覆盖中文的字体。当前字体采用macOS的`STHeiti Light.ttc`与`STHeiti Medium.ttc`，字体路径和索引在[drawing.py](drawing.py)中配置；其他系统应同步替换绘图与PDF使用的字体，并复核文字宽度与换行。
