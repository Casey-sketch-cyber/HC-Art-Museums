# iScience 作者须知核对

核对日期：2026-11-12。本文件只记录当天从 Cell Press 页面读到的要求。官网改了，以新页面为准，不要沿用这里的数字。

直接下载时，`cell.com` 的部分 HTML 返回 HTTP 403 或超时。下面每一项都写了当时实际用的文本从哪来。

## Summary

- 要求：单独一段，不超过 150 个词。
- 出处：iScience Final File Requirements，标题页一节。
- 网址：<https://www.cell.com/pb-assets/journals/EM/MasterFFCs/ISCIFFC.pdf>
- 核对方式：2026-11-12 下载了该 PDF（4 页），抽出正文后核对。原文是 “The Summary should consist of a single paragraph of 150 words or fewer.”

## Highlights

- 终稿清单：单独一个 Word 文件，3–4 条，每条不超过 85 个字符，含空格。
- 出处与网址：同上，ISCIFFC.pdf。原文是 “Highlights are 3–4 bullet points of no more than 85 characters in length, including spaces”。
- 另一页的措辞不同：<https://www.cell.com/iscience/information-for-authors/final-submission> 写的是最多 4 条，每条不得超过 85 个字符（含空格），并避免缩写。这一页当天直接下载返回 403，文字来自同日的页面摘录，不是保存到本地的文件。
- 骨架按更具体的终稿清单执行：写 3–4 条，每条不超过 85 个字符。两页不一致时，投稿前再打开这两个网址。

## 图形摘要

- 终稿清单：必须是正方形，正好 1200×1200 像素、300 dpi。优先用 TIFF、PDF 或 JPG。
- 出处与网址：ISCIFFC.pdf，同上。原文是 “The image should be an exact square, 1200 x 1200 pixels in dimension at 300 dpi. Preferred file types are TIFF, PDF, or JPG.”
- 是否必交：<https://www.cell.com/iscience/information-for-authors/final-submission> 写明，图形摘要只对 Cell Systems、Current Biology、Patterns、Neuron、Newton 可选；对其余期刊必交。iScience 不在可选名单里。该页当天直接下载返回 403，这条来自同日页面摘录。
- 更细的版式说明指向 <https://www.cell.com/pb/assets/raw/shared/figureguidelines/GA_guide.pdf>。该 PDF 当天直接下载返回 403，所以字号、配色和内容规则没有抄进本文件。
- 通用生成式图像工具不得用来做图形摘要。出处：<https://www.cell.com/iscience/information-for-authors/journal-policies>，2026-11-12 保存了该页正文。

## 正文结构

研究论文的篇幅是建议，不是硬性上限。文章类型页写：为便于阅读，建议全文少于 8,000 词；详细方法放在正文的 STAR Methods 里。

- 网址：<https://www.cell.com/iscience/information-for-authors/article-types>
- 核对方式：当天直接下载返回 403，文字来自同日页面摘录。

终稿主文件的章节顺序（ISCIFFC.pdf，已下载核对）：

1. 标题。不超过 145 个字符，含空格。
2. 作者和单位。姓名写全，不缩写成首字母。Lead Contact 用脚注标出。通讯作者给邮箱。
3. Summary
4. Introduction
5. Results
6. Discussion
7. Resource Availability。下面必须有三个小标题：Lead Contact、Materials Availability、Data and Code Availability。
8. Limitations of the Study。终稿清单要求有一段 “Limitations of study”。
9. Acknowledgments
10. Author Contributions。放在 Acknowledgments 之后。可用简短叙述，也鼓励用 CRediT。
11. Declaration of Interests。即使没有利益冲突也要写。表格另交。
12. 主图的标题和图注。图本身单独交 TIFF 或 PDF，不嵌进主文件。
13. 主表和表注。
14. STAR Methods
15. 补充视频、数据和 Excel 表的标题与图注。
16. References

LaTeX 可以投稿，但接收后要转换成期刊排版流程。终稿清单要求同时交主 PDF、`.tex` 以及 `.bbl`、`.bib`、`.sty`、`.bst` 等附属文件，并在校样里核对公式。官方 Word 和 LaTeX 模板在 <https://www.cell.com/information-for-authors/article-templates>。本仓库的骨架只按上述顺序留出章节，没有放入出版社的模板文件。

## STAR Methods 和 Key Resources Table

- 网址：<https://www.cell.com/pb-assets/journals/research/cell/methods/Methods_Guide_general-1724873926937.pdf>
- 核对方式：2026-11-12 的页面文本摘录。该指南写明适用于 iScience。
- STAR Methods 在接收时必须有。初稿不强制，但鼓励提交。没有字数上限。参考文献计入主文献表，不计入稿件字数上限。指南没有写 STAR Methods 正文本身不计入 8,000 词。
- 四个标准标题，加一张 Key Resources Table：
  1. EXPERIMENTAL MODEL AND STUDY PARTICIPANT DETAILS。不用生命科学实验模型（例如纯计算或物理科学研究）时省略。
  2. METHOD DETAILS。所有稿件都要有。
  3. QUANTIFICATION AND STATISTICAL ANALYSIS。没有统计或定量时省略。
  4. ADDITIONAL RESOURCES。没有新建网站或论坛、也不是临床试验时省略。
  5. KEY RESOURCES TABLE。不要自造表头或小标题。用官网的表格模板或网页表单。表里引用的文献要进入主文献表。自加的小标题不超过 45 个字符，不编号，不含文献、图或表的引用。
- 在主文件里，STAR Methods 放在图注之后。见 ISCIFFC.pdf。

## 数据与代码可得性

- 网址：<https://www.cell.com/iscience/information-for-authors/journal-policies>
- 核对方式：2026-11-12 保存了该页正文。终稿清单对三个小标题的要求另见已下载的 ISCIFFC.pdf。
- 研究论文必须有 Resource Availability，含 Lead Contact、Materials Availability、Data and Code Availability。没有产生新材料也要写 Materials Availability。
- 论文报告的数据和原创代码，除非法律或伦理禁止，都要能共享。
- 有社区仓库的标准化数据，接收前存入 Cell Press 推荐的专用库，论文里写登录号或永久标识，出版日解除禁运。
- 其他数据：存入通用库并在出版日公开，或出版后由 Lead Contact 应要求提供。
- 原创代码：接收前存入能给出 DOI 的仓库，或放进补充材料。存入仓库的，论文里写 DOI，出版日公开。
- Data and Code Availability 必须有三段，建议用条目：数据、代码、以及固定的第三句 “Any additional information required to reanalyze the data reported in this paper is available from the lead contact upon request.”

## 生成式 AI 使用声明

- 网址：<https://www.cell.com/iscience/information-for-authors/journal-policies>，2026-11-12 保存的正文。终稿清单有同一节的短版本，见 ISCIFFC.pdf。
- 写作过程用了生成式 AI 或 AI 辅助技术，投稿时就要声明。声明放在 Declaration of Interests 之后，标题为 “Declaration of generative AI and AI-assisted technologies in the manuscript preparation process”。示例句式见该页：写明工具或服务的名称、用途，并写明作者已核对并承担责任。
- 只用于语法、拼写和文献检查的基础工具不用声明。没有可声明的内容时，不要加这一节。
- 不得把 AI 列为作者。
- AI 若属于研究设计或方法，要在 Methods 或 STAR Methods 里写到可以复现，包括模型或工具名称、版本、开发者，并同时写入 AI 声明。
- 不得用生成式 AI 生成或改动研究数据图，包括亮度、对比度和色调。通用生成式图像工具不得用于图形摘要。解释性图可以使用，但要在图注和总声明里写明工具、版本和用途。

## 版面费

- 金额：iScience 的开放获取费是 3,240 美元，不含税。该刊参加地域定价试点；试点的具体减免额度，当天的摘录里没有列出，这里不补。
- 网址：<https://www.cell.com/open-access> 的开放获取期刊价格表，以及 <https://www.cell.com/iscience/home> 页首的 “Article publishing charge: $3,240”。
- 核对方式：两处都是 2026-11-12 的页面摘录。当天对本机直接下载开放获取页超时，期刊主页返回 403，所以这个金额没有从保存到本地的文件里再核一遍。
- 许可：FAQ 写明可选用 CC BY 或 CC BY-NC-ND，覆盖全文和补充材料。网址 <https://www.cell.com/iscience/faqs>。当天直接下载返回 403，文字来自同日页面摘录。FAQ 确认这是完全金色开放获取，并有少量困难减免，但没有在摘录里重复写出美元金额。
