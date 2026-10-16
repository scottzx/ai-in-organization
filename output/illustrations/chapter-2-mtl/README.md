# 第二章 MTL 插图索引

本组16张原创插图服务第二章“MTL：从市场到有效线索”的分析，以MTL（Market to Lead，从市场到线索）梳理市场岗位的工作、业务差距和任务分工。图中六类工作、六项改进目标、18项举措及各项关系均由本报告整理，不代表华为官方流程阶段或定义。候选对象的核实、销售实际接手和完整投入共同用于检验业务表现。

[返回第二章](../../../上册-研究报告/02-最小执行单位-从人到任务.md) · [查看整章插图总览](chapter-2-overview.png)

| 编号 | 所在章节 | 图题 | 文件 |
| --- | --- | --- | --- |
| 图2-01 | 2.1 | MTL职责落实为可以交接的任务产物 | [PNG](01-mtl-responsibilities.png) · [SVG](01-mtl-responsibilities.svg) |
| 图2-02 | 2.2 | MTL的业务结果与六项改进目标 | [PNG](02-mtl-results.png) · [SVG](02-mtl-results.svg) |
| 图2-03 | 2.2 | 业务差距经核实后形成改进目标 | [PNG](03-business-diagnosis.png) · [SVG](03-business-diagnosis.svg) |
| 图2-04 | 2.2 | 有效率与接收率按同一批对象计算 | [PNG](04-conversion-cohort.png) · [SVG](04-conversion-cohort.svg) |
| 图2-05 | 2.3 | 业务举措落实为可分工与可验收的任务 | [PNG](05-task-allocation.png) · [SVG](05-task-allocation.svg) |
| 图2-06 | 2.3 目标1 | 目标1：明确目标市场与客户 | [PNG](06-goal-1-market-customers.png) · [SVG](06-goal-1-market-customers.svg) |
| 图2-07 | 2.3 目标2 | 目标2：形成准确的价值表达 | [PNG](07-goal-2-value-expression.png) · [SVG](07-goal-2-value-expression.svg) |
| 图2-08 | 2.3 目标3 | 目标3：让市场活动产生可追踪回应 | [PNG](08-goal-3-market-response.png) · [SVG](08-goal-3-market-response.svg) |
| 图2-09 | 2.3 目标4 | 目标4：及时接住询盘并留下背景 | [PNG](09-goal-4-inquiry-context.png) · [SVG](09-goal-4-inquiry-context.svg) |
| 图2-10 | 2.3 目标5 | 目标5：提高候选对象成为有效线索的比例 | [PNG](10-goal-5-qualified-leads.png) · [SVG](10-goal-5-qualified-leads.svg) |
| 图2-11 | 2.3 目标6 | 目标6：让有效线索被销售实际接手 | [PNG](11-goal-6-sales-handoff.png) · [SVG](11-goal-6-sales-handoff.svg) |
| 图2-12 | 2.3 成本比较 | 合格交付成本按完整投入比较 | [PNG](12-qualified-delivery-cost.png) · [SVG](12-qualified-delivery-cost.svg) |
| 图2-13 | 2.4 能力沉淀 | 个人工作方法经复用验证形成组织能力 | [PNG](13-capability-reuse.png) · [SVG](13-capability-reuse.svg) |
| 图2-14 | 2.5 前四类岗位 | 技术辅助围绕岗位业务目标展开 | [PNG](14-other-roles-a.png) · [SVG](14-other-roles-a.svg) |
| 图2-15 | 2.5 后四类岗位 | 任务条件决定技术辅助的具体范围 | [PNG](15-other-roles-b.png) · [SVG](15-other-roles-b.svg) |
| 图2-16 | 2.6 | MTL岗位改造按任务分工与业务结果检验 | [PNG](16-chapter-summary.png) · [SVG](16-chapter-summary.svg) |

图2-13以市场人员准备线索交接客户简报为例，展示如何保留查找核实与修改依据，整理为Skill、工具或任务示例，再由其他市场人员在新任务中复用验证。图2-12、图2-14和图2-15沿用原版的通用任务分析；旧版目录`chapter-2`继续保留，供历史发行PDF及其索引使用。

## 生成与校验

PNG与SVG由同一组图元和文字生成，正文引用PNG，PDF构建读取同名SVG，以保留矢量线条和可检索文字。修改图内文字时编辑[figures.py](figures.py)或[supplemental_figures.py](supplemental_figures.py)，再运行[build.py](build.py)，不要直接修改PNG。

图内保留浅蓝底、深蓝文字和蓝色强调风格。内部布局使用1800×1280坐标，导出按实际内容裁切，四边统一保留16px白色边距。单图JSON与[manifest.json](manifest.json)记录图题、可见文字、文字边界、实际尺寸、裁切原点、字体与来源说明。

字体通过`BOOK_DIAGRAM_FONT`与`BOOK_DIAGRAM_HEADING_FONT`指定；可选的`BOOK_DIAGRAM_FONT_INDEX`和`BOOK_DIAGRAM_HEADING_FONT_INDEX`指定字体集合索引。当前Linux环境沿用已经安装的WenQuanYi Zen Hei黑体替代，未下载或加入新的GB2312字体文件。字体家族从实际文件读取，SVG和元数据同步记录。文字角色与字号由[drawing.py](drawing.py)中的`TEXT_STYLES`定义，与原版保持一致。

当前云环境在仓库根目录运行：

```bash
source /workspace/cloud-setup/ai-in-organization/activate.sh
python output/illustrations/chapter-2-mtl/build.py
```

其他环境安装Pillow和fontTools，设置覆盖中文的字体文件后运行同一生成命令。生成器核验16组PNG、SVG和JSON，检查四侧16px边距、图像尺寸、文字角色、可见文字、实际字体覆盖和文字重叠；缺字或文字重叠会终止生成。总览按各图实际比例缩放。
