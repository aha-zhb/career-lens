# V5：从岗位材料到个人判断

本流程服务于各职业的岗位理解、个人定位和路径选择。评分不是默认成果；改善表达、补经历、改变投入或调整目标都可能成立。通用的是方法，岗位知识、阶段和图形维度随目标改变，不把企业AI案例推广成所有职业的答案。先读适用岗位知识，再决定增量研究和访谈，不要求每案重建全国语料。

## 知识与范围

首版`knowledge/enterprise-ai-applications.json`来自既有核验正文，仅支持企业AI应用职责解释，成熟度limited，不代表深度全国画像。笼统的“AI产品经理”目标不应被默默改成企业应用；先解释适用的共同责任，说明平台、增长等方向不在本包中，需要补查。具体JD的责任和硬条件优先，不用知识包覆盖相反要求。

记录知识id/version和适用原因。行业不同、责任未覆盖、硬条件过时、当前机会和来源失效触发针对性补查。知识扩建和深度画像仍遵循`market-research.md`；个案复用不重做60模板采集。知识中的observed是职责事实归纳，mechanism与evidence_standard是分析推断，不冒充企业的官方标准。

## 推理方法

先独立解释实际工作、成功条件和失败，再对应个人责任、决定、项目阶段与结果。保留原出处，区分参与/主责；阶段按职业定义，例如销售的线索/签约/续约、管理者的个人执行/项目协调/人员管理、产品的设计/试用/上线。比较其他解释：缺经历、已有经历未表达、目标责任不适配、业务价值未验证等。缺材料不能推出能力差，两次面试失败不能确认失败原因，JD频率不能直接变成短板排序。

给出范围明确的当前定位，记录什么新材料会改变它。比较继续目标与发挥现有优势的条件、代价和机会成本；没有可靠替代时给筛选条件，不能编造在招职位。通常0—3个结论会改变的问题，先读材料、复用旧回答；不是必须完成的配额。

## 文件契约

知识包保存范围、版本、成熟度、来源及责任。判断文件保存case_id、revision、kind（personal/synthetic）、target、knowledge、evidence、judgments、presentation。target.precision为family/direction/posting，保留用户原目标；posting须有target类型的JD证据。

judgment保存statement、scope、finding_kind、responsibility_refs、evidence_refs、rationale、alternatives、change_conditions。finding_kind区分经历缺口、举证缺口、目标差异等，不是能力等级。evidence.kind为personal或target，text是有出处的事实概述，locator指向原材料位置。

presentation保存自由叙述intro、role_intro、responsibility_refs、personal_intro、main_judgment、comparison、paths及choice_note。展示的岗位责任独立按目标选择，不由个人强项或主判断裁剪；主结论直接引用judgment；对照和路径也引用相关判断，避免另写一套独立结论。不固定判断、图形、路径数量；只有确有选择时才比较路径。

```sh
career-lens/.venv/bin/python career-lens/scripts/build_decision.py case.json career-lens/knowledge/enterprise-ai-applications.json report.html
```

脚本校验字段、版本与引用并导出，不运行模型、不研究、不判断引用语义充分性。Agent须读实际来源复审。新证据或对原材料的实质性解释修订需重新推理，保留旧文件，用同一case_id、递增revision及可选`--previous old-case.json`检查修订关系。revision_note说明原因、实际变动的材料及判断；只有解释修订时changed_evidence_ids可为空，不能假称新增事实。模板变化不能成为改判断或抬高评级的理由。检查器核对变化与引用，不验证解释优劣。

真实材料与报告放state/或outputs/private/，公开fixtures全部虚构。岗位网页HTML不能作为模板直接插入，渲染文本须转义。旧build_analysis和build_report继续兼容；新契约不塞进旧六维评级字段。

## 展示与复审

最新默认阅读顺序：雷达与总体判断 → 逐维企业要求、个人经历与差异 → 一至两项优先关注 → 证据附录。旧版章节流保持兼容，不要求新版报告重复展示。主结论回答问题，不写成“你应区分哪些岗位”让用户继续分析。正文保留理解所需理由；原始JD、完整推理、替代解释与改变条件收进附录，重要范围限制仍靠近结论。责任过程图、经历对照和路径比较分别回答具体问题，不按未知补低分或制作空缺雷达。

记录工程检查、同Agent案例回放、独立评审与真实读者试测的区别。公开合成演练不证明真实用户价值。用户看懂岗位与自身关系本身是成果；行动是后续观察项。

## 2026-10-12呈现扩展

presentation.reader为可选字段，原V5输入仍可导出。它包括updated_at、snapshot（label/text/judgment_refs）、market_intro、conditions（title/requirement/meaning/check/source_refs/evidence_refs/judgment_refs）、insight（title/text/judgment_refs）、findings（status/title/fact/meaning/next/judgment_refs）、path_steps、next_step（title/text/judgment_refs）。status用于已有优势、需要讲清、需要积累和目标差异，不是能力等级。条目数量按材料选择，不强制三种情况齐全。

每项条件须引用招聘source或target JD证据，个人材料不能代替市场条件；每项快照和解释须引用既有判断。insight可带paragraphs（非空文本数组）保存连贯解释，沿用其judgment_refs；旧输入不需要迁移，不要求凑段落或统一论点。几种条件可以重叠，不是固定A/B/C分类、岗位比例或投递成功率。path_steps与路径一一对应，只给具体起点，不制造两套庞大训练计划。

有些事实已提供但未抽取时，可补抽取原材料并注明出处；这不是新增访谈。修订仍保留旧记录，注明判断与呈现变化。仅呈现变化可以保持判断版本，显示独立updated_at；有新抽取材料及关键判断修订则递增revision并记录。

## 首屏雷达契约

presentation.radar为可选输入，见[雷达指导](radar-guidance.md)。逐轴保留共同锚点、岗位要求与个人依据、缺口类型和来源；首屏图形、逐维解释及附录从这一记录生成，脚本不新增判断。原V5无radar输入继续兼容。

## 维度中心的精简阅读契约

presentation.focus为可选字段：summary（text、judgment_refs）、research_note（研究时间与适用范围）、priorities（一至两项title、text、judgment_refs）。有focus时须有radar，每轴须包含explanation（requirement、experience、difference），分别对应“企业要什么、你有什么、还差什么”；文字复用该轴的岗位、个人与判断引用。没有focus的旧输入照常导出。

focus只切换呈现，不重判等级。交互侧栏与打印／无JavaScript阅读块使用同一份explanation，正常网页不重复展开全部维度；脚本不把审计术语自动拼成正文，也不通过界面更新宣称研究更新。新增文本照常转义，不能直接渲染招聘网页HTML。图无评分依据时保留说明，不填0。
