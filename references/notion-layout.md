# 把笔记写进 Notion（可选步骤）

**只有用户明确提出"放进 Notion / 收录到笔记库"时才做这一步。** 用户没提，就只交付 Markdown 或本地文件。

## 一、先定栏目，再动手

照该学科已有的页面范式来做（先去同空间找一门已经建好的课页，看它的栏名和比例）。常见三栏：

| 栏 | 放什么 | 理由 |
|---|---|---|
| 章节精讲 / 理论学习 | 每个章节一个子页，按教材顺序 | 与页码对得上，可线性推进 |
| 考试与打法 / 题型 | 题型分值、排期、答题模板、保底策略 | 考前只看这一栏 |
| 速查 | 公式表、对比表、易错点、时间地图 | 考前 30 分钟用，越密越好 |

比例建议 `41 / 33 / 26`，三栏合计 100。**不要用"在学中 / 已完成"这类状态栏**——笔记不会"完成"。

## 二、建子页的正确姿势

在页面内容里直接写 `<page>标题</page>`（**不带 url**），会就地创建子页，**并且直接落在当前栏内**：

```
<columns>
<column ratio="41">
## 章节精讲

### 第 3 章 栈和队列

<page>第 3 章 栈和队列</page>
</column>
<column ratio="33">
## 考试与打法
</column>
<column ratio="26">
## 速查
</column>
</columns>
```

这比"先建页再搬 block"省事得多——后者要同一次 `update_page` 里放两个 `content_updates`（先删末尾的 `<page url>` 标签、再把带 url 的标签插到目标位置），容易出错。

## 三、已知报错与处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `internal_error`，连最小写入都失败，但读取正常 | 服务端瞬时故障 | **等 30–90 秒重试**，不要重连 connector、不要改写内容 |
| `create-pages` 报 `internal_error` | 该接口不稳定 | 改用上面的 `<page>标题</page>` 就地建页 |
| `replace_content` 整页重排含 columns 时 `internal_error` | 布局重排不稳 | 拆成多次 `update_content`，每次只改一处 |
| `Multiple matches found for "<p />"` | 页面里有多处空段落 | 加 `replace_all_matches`，或把锚点写长到唯一 |
| `No matches found for ...` | 存的文本已被转成 `<b>` / `<code>` 标签 | 先 `fetch` 一次，按返回的原文取锚点 |

## 四、格式细节

- **callout 颜色**只支持 `gray | brown | orange | yellow | green | blue | purple | pink | red` 及对应的 `_bg`；**没有 teal**。
- **块级公式**必须是三行：独立一行 `$$`、公式、独立一行 `$$`。写成同一行 `$$x$$` 会被转义成字面 `\$$x$$`。
- **窄栏别放宽表**：三栏里最窄那栏只放 2–3 列的表，列一多就会挤成竖排。宽表（时间地图、对比表）放到子页里，子页正文是全宽的。
- **子页建完要填内容**：`<page>` 建出来是空页，用 `update_page(insert_content)` 一页一页填。
- 收尾：`update_properties` 设图标与 `full_width`（`full_width` 只能跟 `update_properties` 一起用，跟 `update_content` 会报 400）；顺手清掉残留的空 `<p />`。

## 五、写什么

直接复用 SKILL.md 第 5 步的组织方式（是什么 / 关键点 / 例题 / 易错点），把「待核」清单单列一页，并给每项标上分 P 与时间——**没有定位的待核项等于没有**。
