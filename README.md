# 汽车口碑流水线套件

> WorkBuddy Skill · 屋里涛说

懂车帝口碑的**采集整理 → 批量创作 → 改写回填**完整流水线。三个技能协作完成同一件工作：把口碑素材变成可交付的成品。

## 技能清单

| 技能 | 说明 |
|---|---|
| **koubei-pipeline** · 口碑改写流水线 | HTML 提取 → 建记录 → 按小点智能分配风格/平台 → AI 改写 → 写回结果。触发：「跑口碑流水线」「处理口碑HTML」「批量改写口碑」 |
| **koubei-batch-create** · 口碑批量创作 | 从车型参数直接原创：小点 1~8 个随机组合 + 纯正文混排、每篇 380-450 字、每 5 篇换一套模板、人设互异。触发：「每个车型写50篇」「按模板轮换写口碑」 |
| **koubei-links-pipeline** · 链接整理与核实 | 开链浏览 → 下载快照 → 提取标题/评分/日期回填 → R1-R4 图片核实 + 重复核实 + 参数核实（标红标蓝写回备注）。触发：「核实口碑链接」「提取标题评分填回表格」 |

## 工作流

```
素材(HTML/链接)
     │
     ▼
koubei-links-pipeline  ──→  整理核实、回填表格
     │
     ▼
koubei-batch-create    ──→  从车型参数原创（懂车帝口径）
     │
     ▼
koubei-pipeline        ──→  改写已有素材、写回结果
```


## 安装

把 `skills/` 下的技能目录拷贝到 WorkBuddy 的技能目录：

```bash
cp -r skills/* ~/.workbuddy/skills/
```

Windows PowerShell：

```powershell
Copy-Item .\skills\* "$env:USERPROFILE\.workbuddy\skills\" -Recurse -Force
```

重启 WorkBuddy 后，技能列表即可看到。

## 使用要点

- **平台边界**：本套件是**懂车帝**口径（小点 1~8 随机、380-450 字、每 5 篇换模板）。写**汽车之家**口碑请用 `autohome-koubei-write`（9 项固定小点、800-1100 字长文），两套口径混用会直接翻车。
- **核实规则**：R1 合格车身照+人物分级 / R2 车身外观是否符合官方车型（以汽车之家官方图为基准）/ R3 车身颜色与内饰图片统一 / R4 图文颜色一致。
- **参数核实**为单边判：只判过头，不判打折。

## 环境依赖

- Python 3.13
- Node 22（CDP 批量开链）
- Chrome + CDP 调试端口（复用登录态）
- 腾讯文档（读写表格）

## 目录规范

```
koubei-pipeline-suite/
└── skills/
    ├── koubei-pipeline/
    ├── koubei-batch-create/
    ├── koubei-links-pipeline/
```

每个技能遵循统一结构：`SKILL.md`（必需，含 name/description frontmatter）+ `scripts/`（可选）+ `references/`（可选）。

---

## License

MIT — 随意取用、修改、二次分发。
