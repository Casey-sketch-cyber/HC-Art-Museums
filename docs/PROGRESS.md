# 项目进度（交接记录）

> 每个 AI 结束工作前在最上方追加一条记录，新的在上面。

## 当前状态

博物馆暖通安全强化学习的代码、配置和论文源稿在 `/mnt/e/lzt/guangxi`。mock 与多区域实验的输出目录已经在 `results/` 和 `logs/` 里，这些输出不上传。`paper/main.tex` 可以编出 `paper/main.pdf`，该 PDF 被 `paper/.gitignore` 排除。

## 待办

- [ ] 补自动化测试和代码检查命令
- [ ] 确认是否要把 `results/` 里的汇总表或 `paper/main.pdf` 放进仓库。现在两处都被忽略

## 已知问题

- 根目录没有测试套件。README 里的 mock 训练是目前的冒烟路径。
- README 记录完整实验大约需要 4–7 天，瓶颈是 EnergyPlus 的 CPU。

---

## 工作记录

### 2026-11-10 · cursor · main
- **完成**：按 ai-workflow 的项目上线步骤整理本目录，补齐协作文档，准备推送到 `Casey-sketch-cyber/HC-Art-Museums`。
- **未完成**：自动化测试；实验结果和论文 PDF 仍只留在本机。
- **注意 / 坑**：同一文件夹里还有其他课题和交接包。它们已写入 `.gitignore`，没有删除。
