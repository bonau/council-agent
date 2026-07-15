# Council Agent — AI 協作指南

本專案採 **Spec-driven Development（規格驅動開發）**，並以 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理規格與變更。

## 核心原則

1. **先對齊規格，再寫程式** — 功能、修正或重構都應先建立 OpenSpec change，產出 proposal、design、tasks 與 spec delta，經確認後才實作。
2. **規格與程式共存** — `openspec/specs/` 是系統行為的來源真相；`openspec/changes/` 記錄進行中的變更提案。
3. **Delta 優先** — 在既有 codebase 上只描述「新增、修改、移除」的部分，而非重寫整份規格。
4. **實作對照規格** — 完成 tasks 後，Verification 應能對照 spec 中的驗收條件。

## OpenSpec 工作流程

| 階段 | 指令 | 說明 |
|------|------|------|
| 探索 | `/opsx:explore` | 需求尚不明確時，先釐清選項與取捨 |
| 提案 | `/opsx:propose` | 建立 change 並產生 proposal、design、tasks、spec delta |
| 實作 | `/opsx:apply` | 依 tasks.md 逐步實作 |
| 更新 | `/opsx:update` | 需求變更時同步調整 artifacts |
| 歸檔 | `/opsx:archive` | 完成後將 delta 合併至 specs/ |
| 同步 | `/opsx:sync` | 將 specs 與 codebase 對齊 |

CLI 輔助（需 Node.js ≥ 20.19）：

```bash
npx @fission-ai/openspec@latest status
npx @fission-ai/openspec@latest validate --strict
```

## 目錄結構

```
openspec/
├── config.yaml      # 專案脈絡與 schema 設定
├── specs/           # 現行規格（來源真相）
└── changes/         # 進行中的變更提案
    └── <change-name>/
        ├── proposal.md
        ├── design.md
        ├── tasks.md
        └── specs/     # spec delta
```

## 開發慣例

- **分支**：`feature/*` 應對應一個 OpenSpec change（名稱建議一致，kebab-case）。
- **Commit**：遵循 [CONTRIBUTING.md](CONTRIBUTING.md) 的 conventional commits。
- **測試**：Python 專案使用 `uv run pytest`；新功能應在 tasks 中列出對應測試項目。
- **Roadmap**：版本規劃見 [ROADMAP.md](ROADMAP.md)；重大里程碑應先以 OpenSpec change 具體化再開發。

## 不應做的事

- 未建立 change 就直接大規模改動行為或 API。
- 實作完成後不同步更新 spec delta 或 tasks 狀態。
- 在 spec 中描述實作細節（spec 描述「做什麼」，design 描述「怎麼做」）。

## 相關文件

- [CONTRIBUTING.md](CONTRIBUTING.md) — Git Flow 與 commit 規範
- [ROADMAP.md](ROADMAP.md) — 版本路線圖
- [OpenSpec 文件](https://github.com/Fission-AI/OpenSpec)
