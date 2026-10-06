# AGENTS.md

- 所有回應一律使用繁體中文。
- 專案語言為 Python，一律用 conda 管理套件，環境為 `iem_python`；執行用 `conda run -n iem_python python ...`，不要用 `venv` / `pip` 直接安裝。
- Greenfield：115-1 程式設計課程 codebase，目前僅有 `README.md`、`LICENSE` (MIT)、Python 用 `.gitignore`，無建置、測試、lint、CI；不要預設 toolchain。
- 新增作業以簡單獨立 script 為主，優先 stdlib-only；不要提交 venv 或 bytecode。
