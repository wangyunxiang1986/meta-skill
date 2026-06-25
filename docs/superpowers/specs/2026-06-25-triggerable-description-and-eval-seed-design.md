# 设计:让「生成的 skill」可触发 + 评测种子(对齐 skill-creator）

**日期:** 2026-06-25
**状态:** 待用户审查

## 这是 meta-skill 的功能 —— 先说清层次(关键)

本设计改的是 **meta-skill 的引擎**,让它**生成出来的 skill** 在两点上更好。引擎**保持模型无关**:下文所有 `<...>` 槽位都在**生成时从 scan / pack 填入**,引擎里**不写任何模型名**(clvisc/lbt/...)。文中出现的 "CLVisc"/"LBT" 只是**把 meta-skill 跑在那份代码上时的输出示例**,不是写进引擎的内容。`tests/test_boundary.py` 守此。

## 目标

- **A(触发):** 生成的 SKILL.md 当前 `description` 写死为 `"Version-specific skill for this scanned checkout."`——空泛、无"何时用",agent 据此**无法判断要不要调用**,等于触发不了。改为**引擎用通用模板、从 scan+pack 派生**一句能触发、且**框定到「这一份 checkout」**的描述。
- **B(评测种子):** 我们只验证"代码能跑出文件"(T0/T1/T2),从不验证"这个 skill 对 agent 是否有用"。**不自建评测引擎**——衔接现成的 `skill-creator`(它已做 with-skill-vs-baseline → 打分 → benchmark → 迭代)。meta-skill 只**顺手生成评测种子**(几个测试任务)+ 一句指引;真正评测由用户之后可选地用 skill-creator 跑,meta-skill 不调用它。

## A. 通用 description 生成

新增**通用**函数 `render_skill_description(scan, pack) -> str`;`render_skill_md` 用它替换写死的那行。

### 通用模板(引擎内,零模型名)
```
<what>. Use this skill to <verbs> this scanned checkout of <code_id><, e.g. <triggers>>.
```

### 槽位来源(全部运行时填)
- **`<what>`**(做什么,一句):
  - 有 pack → `pack.knowledge.description`
  - 无 pack → 名词短语 `"The <code_id> code (entry \`<primary_entry>\`)"`(不带动词,避免和 `<verbs>` 重复)
- **`<code_id>`**(代码身份):有 pack 用 `pack` 名;无 pack 用 `scan.project_root` 的目录名。
- **`<verbs>`**(能做的事,**按 scan 实际扫到的东西取舍**,至少含 "run it"):
  - `run it` —— 总有(scan 扫到了入口)
  - `edit its parameters` —— 仅当 `scan.parameters` 非空
  - `analyze its outputs` —— 仅当 `scan.output_files` 非空(或 pack 有 `observable_locator`)
- **`<triggers>`**(可选的"人话"触发短语,**只取用户会说的话**):取 `pack.knowledge.intent_rules[].match` 拍平去重后的前 ~4 个;**不取** `observable_locator` 的键(`v2`/`dNchdeta` 是内部代号,不是用户措辞,易成噪声)。无来源就**整段省略** `, e.g. ...`。

### 设计取向:框定,不是"最大化触发"
生成的 skill 绑定**某一份 checkout**。description 的目标是让 agent 认出**"用户正在用这一份代码"**,所以强调 `this scanned checkout`,**短**(1–2 句),**不堆关键词**——避免在别的分支/无关语境下误触发。(这与 skill-creator 给「通用 skill」的"pushy"建议相反,是有意为之。)

### 约束
整句作为 YAML 单行字符串输出(沿用 `description: "..."`);**内部双引号转义、换行去除**,保证 frontmatter 合法。

### 输出示例(把 meta-skill 跑在不同代码上的结果,仅示例)
- **clvisc**(有 pack、有 params/outputs/intent_rules):
  > "CLVisc: (3+1)D viscous relativistic hydrodynamics on GPU (OpenCL) … spectra/flow. Use this skill to run it, edit its parameters, and analyze its outputs for this scanned checkout of clvisc, e.g. scan eta/s, scan energy."
- **lbt**:
  > "LBT (Linear Boltzmann Transport): parton energy loss / jet quenching … . Use this skill to run it, edit its parameters, and analyze its outputs for this scanned checkout of lbt, e.g. scan alphas, turn off radiation."
- **无 pack 的某代码**(scan 没扫到参数):
  > "The FooSolver code (entry \`main.py\`). Use this skill to run it and analyze its outputs for this scanned checkout of FooSolver."

## B. 评测种子:`evals/evals.json` + SKILL.md 指引

新增**通用**函数 `render_evals(scan, pack) -> dict`;`generate()` 写出 `evals/evals.json`。

### schema(对齐 skill-creator,只填 prompt,不填 assertions —— 后者由 skill-creator 补)
```json
{
  "skill_name": "<generated_skill_name>",
  "evals": [
    {"id": 1, "prompt": "<任务 prompt>", "expected_output": "<预期结果描述>", "files": []}
  ]
}
```

### prompt 派生(优先级,全部运行时填、零模型名)
1. `pack.knowledge.demos`(每个有 title/intent/args)→ 取前 3:
   - `prompt` = `"Using this skill, <intent>."`(若有 args,追加 `" Suggested settings: <args>."`)
   - `expected_output` = `<intent>`
2. 无 demos 但有 `intent_rules` → 用前 3 个 `match` 短语派生。
3. 都没有(无 pack)→ 单条通用:
   - `prompt` = `"Run this code's documented minimal example and report its primary output."`
   - `expected_output` = `"the minimal run completes and the primary output is produced"`

### SKILL.md 新增一节(说明是「衔接」skill-creator,非内建)
```
## Evaluating & Improving This Skill
This skill was auto-generated. To measure whether it actually helps an agent
on real tasks — and to improve it — run the `skill-creator` skill on this
directory. Starter test tasks are in `evals/evals.json`; skill-creator runs
them with and without this skill, grades the results, and iterates.
```
并把 `evals/evals.json` 加入 SKILL.md 的 References 列表。

## 要改的文件

- `engine/generate.py`
  - 新增 `render_skill_description(scan, pack)`;`render_skill_md` 用它替换写死的 `description`,并加 "Evaluating & Improving This Skill" 段、References 增列 `evals/evals.json`。
  - 新增 `render_evals(scan, pack)`;`generate()` 写出 `evals/evals.json`。
  - `_GENERATED_FILES` 增加 `"evals/evals.json"`(stale 清理)。
- 测试(新建 `tests/test_generate_trigger_eval.py`):覆盖 A、B 与边界。

## 测试(TDD)

**A — `render_skill_description`:**
- 有 pack:含 `pack.description`、含 `<code_id>`、含 "this scanned checkout"、含至少一个 intent_rules 触发短语;**不**含写死旧句。
- 无 pack:含目录名 + primary entry、含 "run it"、不含 "edit its parameters"(当 `parameters` 为空);无 `, e.g.` 子句。
- `verbs` 取舍:`parameters` 空 → 无 "edit its parameters";`output_files` 空且无 observable_locator → 无 "analyze its outputs"。
- 产物可安全嵌入 `description: "..."`——渲染整份 SKILL.md 后 YAML 可解析(无裸双引号/换行)。
- **边界**:`render_skill_description` 源码内不含任何模型名(已由 `test_boundary.py` 覆盖;新函数纳入其扫描范围)。

**B — `render_evals` / 写出:**
- 有 demos:产出 `N = min(3, #demos)` 条,每条 prompt/expected_output 非空、`files: []`,`skill_name` 正确。
- 无 demos 有 intent_rules:用 match 派生。
- 无 pack:产出 1 条通用 eval。
- `generate()` 写出 `evals/evals.json`,SKILL.md 含 "Evaluating & Improving" 段与 `skill-creator` 字样;`evals/evals.json` 在 `_GENERATED_FILES` 中(重生成清理 stale)。

## 不做(YAGNI / 范围外)

- **不自建任何评测引擎**(打分/benchmark/viewer/迭代全交给 skill-creator)。
- **meta-skill 不调用 skill-creator**——只产种子 + 文字指引;评不评由用户。
- 不写 assertions(skill-creator 后补)。
- description **不做** NLP/语义抽取,只汇聚 pack 现有"人话"短语;不堆内部代号。
- 不为触发做"pushy 最大化",有意走"框定到 this checkout"。

## 边界检查

新代码不得引入模型 token。description 的领域词/触发短语**只能**来自 `pack.knowledge` 或 `scan`,**不得**在 `engine/` 写死任何模型名——`tests/test_boundary.py` 守此(其扫描已覆盖 `engine/**`)。
