# 数据契约与生成

JSON Schema位于schemas，validate_input.py执行跨引用和版本语义检查。V0.1兼容旧五部分报告；V0.2顶层、market_model和candidate_evidence均标schema_version: "0.2"。

V0.2来源带source_kind(job/practice)、source_layer(target_market/role_benchmark/work_practice)、body_access(full/summary/unavailable)。只纳入正文可读且复核过的来源；JD数量不含实践资料。实践来源不能单独支持真实市场等级。来源URL只接受HTTP(S)，location_first的地区层与目标地区一致，role_first按全国同岗位纳入，平台方向不得混入应用基准。

market_model每维保留定义、任务、子能力、五级行为锚点、market_level或market_level_range、来源和rating_review。点和区间二选一；每项等级均需独立批准和理由，其他未赋分维度不抹去此项。market_confidence汇总为全部可判级、mixed、仅探索或不足；它不代表抽样统计置信度。capability_tree和component_ids一一映射完整二级任务。research_rounds记录研究策略、新增来源、是否改变结论、剩余缺口，stop_reason记录停止依据。

candidate_evidence包含用户材料、能力证据、逐维assessments和可选events项目阶段。每维score或score_range二选一；unknown均为空。状态与证据强度是内部字段，不作为用户结论。传统经历评分必须写明适用范围。

report_content包含headline、三条findings（优势、阻碍、投入调整）、1–3条differences、1–3个有产出与验收条件的actions（通常两个）、scope_summary和chart_mode(auto/radar/relation)。每个判断引用有效能力、材料与来源。V0.2不再要求冗余three_conclusions。主报告不能用内部未决标签替代诊断；无个人材料时只交付市场理解，不编造个人发现。

运行：
```
uv sync --project career-lens --extra pdf
career-lens/.venv/bin/python career-lens/scripts/validate_input.py diagnosis.json
career-lens/.venv/bin/python career-lens/scripts/build_report.py diagnosis.json report.md --pdf
```

输出主报告MD、HTML、图表PNG、图表元数据及独立依据MD/HTML；--pdf另生成PDF。输入校验通过不等于判断正确，仍须核对实际渲染、来源归属、图表含义与建议。源码本身不自动联网；宿主Agent负责浏览、理解和补充输入。

## 岗位优先范围补充

market_model可设置geography_mode=role_first，geography写明全国同岗位范围；intake.target.location仍保存用户求职城市。此时target_market表示目标同岗位，不受该城市限制；方向隔离仍有效。location_first或旧输入省略该字段时保留原地区约束。渠道是企业官网/不同平台，用途层是目标/相邻任务/实践，二者分开统计。完整批量语料、去重与编码保存在单独研究包，报告JSON只做摘要。

新成稿规则允许深入推理正文，不受V0.2固定简报模板限制。旧模板仍能运行，但不代表已达到大样本研究或新呈现质量；不能把历史6条纳入案例标为新SOP完成。

历史eligible_jd_count/candidate_jd_count统计所有招聘登记（不含实践），保持兼容。新研究发布门槛按source_layer=target_market的完整、独立同岗位正文另计，不能用相邻参照数量代替；岗位语料层保存各口径的分子与分母。

## V0.3解释性输出

V0.3是工具包版本，不新增schema_version="0.3"的diagnosis JSON。旧JSON校验与简报仍按0.2契约运行。新工作流保存独立corpus登记、audit结果、岗位研究及推理备忘录，再作者化成Markdown正文和研究依据；build_analysis.py负责HTML呈现，无等级、六维、三条发现或页数要求。具体登记字段、状态和审查要求见[synthesis-and-delivery](synthesis-and-delivery.md)。

corpus的decision=target不代表完整正文；visibility=partial_description的目标材料可帮助解释可见要求，但不计完整模板发布配额。audit.deep_release_pass=false是研究范围限制，不是个人诊断等级；主报告仍应给出能由材料支持的定位与下一投入。计数和布尔检查不可替代语义、独立审查或读者理解验证。
