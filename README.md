# Career Lens

帮助求职者理解目标岗位、看清已有经验与差距，并找到值得优先投入的方向。

这是一套供支持本地 Skill 的 Agent 使用的通用职业分析方法。Agent负责岗位研究和个人分析；本地工具负责校验引用、绘图与导出报告，不包含独立模型服务、自动招聘爬虫或收费系统。

## 使用 Skill

入口为 [career-lens/SKILL.md](career-lens/SKILL.md)。将 `career-lens/` 文件夹放入宿主支持的 Skills 目录，或在对话中明确提供该文件的路径。不同宿主的加载方式不同。

例如：

> 使用 career-lens，结合我的简历和目标岗位，解释市场需要哪些能力、我的经历能说明什么，以及差距在哪里。请主动研究必要来源，尽量复用材料，不要让我填写长问卷。

提供简历和目标即可开始；具体JD、面试问题及项目记录是可选补充。通常只问0—3个可能改变判断的问题。城市用于机会偏好，同类岗位职责默认跨地区研究。

## 报告怎样呈现

报告围绕目标岗位的能力维度，集中回答：

- 企业要什么，为什么重要。
- 你已经有什么相关经历。
- 还差什么，怎样理解或补齐。

支持比较时，雷达图配合点击切换的逐维解释，底部保留一至两项优先建议。网页不重复展开全部维度；打印或关闭JavaScript时仍可阅读完整解释。刻度、来源及详细推理放在可展开附录。无法合理比较时采用文字对照，不编造分数、匹配率或录用概率。

维度和工作阶段随职业变化。现有企业AI应用知识包只是一个有限领域模块，不代表已覆盖所有职业；其他目标需要Agent自行研究。

## 虚构示例

- [三维客户成功示例](career-lens/examples/focused-customer-success.html)：演示精简雷达报告，全部个人材料和目标职责均虚构。
- [跨职业材料](career-lens/examples/cross-role-cases.json)：客户成功、数据分析与工程管理的不同处境。
- [企业AI应用案例](career-lens/examples/v05/raw-cases.md)：缺经历、已有经历未表达、目标责任不同及新增材料后的修订。

虚构演练不证明真实用户效果或独立判断一致性。

## 本地工具

Python 3.11+。依赖定义在 [pyproject.toml](career-lens/pyproject.toml)。使用 uv 安装：

```sh
uv sync --project career-lens
career-lens/.venv/bin/python -m unittest discover -s career-lens/tests -v
```

将虚构客户成功材料导出为HTML：

```sh
career-lens/.venv/bin/python - <<'PYTHON'
import json, sys
from pathlib import Path
sys.path.insert(0, 'career-lens/scripts')
from build_decision import build
example = json.loads(Path('career-lens/examples/focused-customer-success.json').read_text())
build(example['case'], example['knowledge'], Path('outputs/customer-success.html'))
PYTHON
```

`build_decision.py`校验版本、引用和修订记录并导出HTML；`audit_corpus.py`核对来源、去重与覆盖记录。它们不运行模型，也不判定引用是否足以支持结论。旧版导出仍兼容，旧示例不代表最新默认呈现。

## 方法与范围

- [岗位研究](career-lens/references/market-research.md)：多来源、正文核验、去重与反例研究。
- [分析方法](career-lens/references/synthesis-and-delivery.md)：职责机制、个人经历、其他解释与投入选择。
- [报告指导](career-lens/references/report-guidelines.md)：具体、易懂、集中呈现。
- [诊断契约](career-lens/references/diagnosis-v05.md)：材料归因、可复核判断与修订。

企业AI知识复用2026-10-11核验的有限语料，不是成熟的全国市场画像，不保证来源岗位仍在招聘；时效性要求在实际诊断时补查。合理推断用于形成有帮助的当前判断，不能把材料空白当作能力低下，也不能确定面试失败原因。

真实简历、个人诊断、报告、开发过程材料和本地环境不纳入发布。个人数据留在 `state/`、`outputs/` 或其他忽略目录；公开示例与真实材料分开。
