#!/usr/bin/env python3
"""Generate a professional minimalist PDF deck for Council Agent development journey."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

# --- Brand palette ---
PRIMARY = (126, 159, 53)  # #7E9F35
PRIMARY_LIGHT = (214, 239, 159)  # #D6EF9F
PRIMARY_MID = (168, 199, 100)  # #A8C764
PRIMARY_DEEP = (89, 120, 20)  # #597814
PRIMARY_DARKEST = (55, 80, 0)  # #375000

ACCENT_RED = (167, 56, 61)  # #A7383D
ACCENT_RED_LIGHT = (251, 167, 171)  # #FBA7AB
ACCENT_RED_MID = (209, 104, 110)  # #D1686E
ACCENT_RED_DEEP = (125, 21, 26)  # #7D151A

ACCENT_PURPLE = (86, 42, 114)  # #562A72
ACCENT_PURPLE_LIGHT = (150, 117, 171)  # #9675AB
ACCENT_PURPLE_MID = (116, 75, 142)  # #744B8E
ACCENT_PURPLE_DEEP = (59, 18, 85)  # #3B1255

INK = (34, 40, 28)  # near-black with green undertone
MUTED = (90, 98, 78)
HAIRLINE = (210, 216, 198)
SURFACE = (252, 253, 248)  # warm off-white
WHITE = (255, 255, 255)

# 16:9 landscape mm
W, H = 297.0, 167.0
MARGIN_X = 18.0
MARGIN_Y = 14.0

FONT = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
OUT = Path(__file__).resolve().parent / "council-agent-dev-journey.pdf"


class Deck(FPDF):
    def __init__(self) -> None:
        # fpdf2 swaps width/height when orientation="L"; pass portrait dims
        # so landscape resolves to 297×167 (16:9).
        super().__init__(orientation="L", unit="mm", format=(H, W))
        self.set_auto_page_break(auto=False)
        self.add_font("body", "", FONT)
        self.add_font("body", "B", FONT)
        self._slide_no = 0
        self._total = 0

    def set_total(self, n: int) -> None:
        self._total = n

    def new_slide(self) -> None:
        self.add_page()
        self._slide_no += 1
        self.set_fill_color(*SURFACE)
        self.rect(0, 0, W, H, "F")

    def footer_bar(self, label: str = "Council Agent · 開發歷程") -> None:
        # bottom hairline
        self.set_draw_color(*HAIRLINE)
        self.set_line_width(0.2)
        self.line(MARGIN_X, H - 10, W - MARGIN_X, H - 10)
        self.set_font("body", "", 7.5)
        self.set_text_color(*MUTED)
        self.set_xy(MARGIN_X, H - 9)
        self.cell(120, 5, label, align="L")
        self.set_xy(W - MARGIN_X - 40, H - 9)
        self.cell(40, 5, f"{self._slide_no:02d} / {self._total:02d}", align="R")

    def accent_bar(self, color: tuple[int, int, int] = PRIMARY, y: float = 0) -> None:
        self.set_fill_color(*color)
        self.rect(0, y, W, 2.2, "F")

    def left_rail(self, color: tuple[int, int, int] = PRIMARY) -> None:
        self.set_fill_color(*color)
        self.rect(0, 0, 3.2, H, "F")

    def eyebrow(self, text: str, color: tuple[int, int, int] = PRIMARY_DEEP) -> None:
        self.set_font("body", "", 9)
        self.set_text_color(*color)
        self.set_xy(MARGIN_X, MARGIN_Y + 2)
        self.cell(0, 5, text.upper())

    def slide_title(self, text: str, y: float | None = None) -> None:
        self.set_font("body", "B", 26)
        self.set_text_color(*INK)
        self.set_xy(MARGIN_X, y if y is not None else MARGIN_Y + 12)
        self.multi_cell(W - 2 * MARGIN_X, 11, text)

    def subtitle(self, text: str, y: float | None = None) -> None:
        self.set_font("body", "", 12)
        self.set_text_color(*MUTED)
        self.set_xy(MARGIN_X, y if y is not None else self.get_y() + 2)
        self.multi_cell(W - 2 * MARGIN_X, 6.5, text)

    def section_label(self, x: float, y: float, text: str, color: tuple[int, int, int]) -> None:
        self.set_fill_color(*color)
        self.rect(x, y, 2.0, 4.2, "F")
        self.set_font("body", "", 9)
        self.set_text_color(*color)
        self.set_xy(x + 4, y - 0.4)
        self.cell(60, 5, text)

    def bullet(self, text: str, x: float, y: float, width: float, color: tuple[int, int, int] = PRIMARY) -> float:
        self.set_fill_color(*color)
        self.ellipse(x, y + 1.6, 1.8, 1.8, "F")
        self.set_font("body", "", 10.5)
        self.set_text_color(*INK)
        self.set_xy(x + 5, y)
        self.multi_cell(width - 5, 5.5, text)
        return self.get_y() + 1.5

    def card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str,
        accent: tuple[int, int, int] = PRIMARY,
        title_size: float = 12,
    ) -> None:
        self.set_fill_color(*WHITE)
        self.set_draw_color(*HAIRLINE)
        self.set_line_width(0.25)
        self.rect(x, y, w, h, "DF")
        self.set_fill_color(*accent)
        self.rect(x, y, 2.0, h, "F")
        self.set_font("body", "B", title_size)
        self.set_text_color(*INK)
        self.set_xy(x + 7, y + 5)
        self.multi_cell(w - 12, 5.5, title)
        ty = self.get_y() + 1.5
        self.set_font("body", "", 9.5)
        self.set_text_color(*MUTED)
        self.set_xy(x + 7, ty)
        self.multi_cell(w - 12, 5, body)

    def pill(self, x: float, y: float, text: str, fill: tuple[int, int, int], text_color: tuple[int, int, int] = WHITE) -> float:
        self.set_font("body", "", 8)
        tw = self.get_string_width(text) + 8
        self.set_fill_color(*fill)
        self.rect(x, y, tw, 6, "F")
        self.set_text_color(*text_color)
        self.set_xy(x, y + 0.5)
        self.cell(tw, 5, text, align="C")
        return tw


def build() -> Path:
    pdf = Deck()
    slides: list = []

    # Collect builders then render with known total
    def cover() -> None:
        pdf.new_slide()
        pdf.set_fill_color(*PRIMARY_DARKEST)
        pdf.rect(0, 0, W, H, "F")
        # brand panel — primary olive
        pdf.set_fill_color(*PRIMARY)
        pdf.rect(0, 0, W * 0.42, H, "F")
        # accent stripe
        pdf.set_fill_color(*PRIMARY_MID)
        pdf.rect(W * 0.42, 0, 3.5, H, "F")
        # secondary accent dots strip
        pdf.set_fill_color(*ACCENT_RED)
        pdf.rect(0, H - 8, W * 0.42, 8, "F")
        pdf.set_fill_color(*ACCENT_PURPLE)
        pdf.rect(W * 0.42 + 3.5, H - 8, W, 8, "F")

        pdf.set_font("body", "", 11)
        pdf.set_text_color(*PRIMARY_DARKEST)
        pdf.set_xy(MARGIN_X, 38)
        pdf.cell(100, 6, "COUNCIL AGENT")

        pdf.set_font("body", "B", 34)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(MARGIN_X, 50)
        pdf.multi_cell(105, 14, "開發歷程簡報")

        pdf.set_font("body", "", 12)
        pdf.set_text_color(*PRIMARY_DARKEST)
        pdf.set_xy(MARGIN_X, 90)
        pdf.multi_cell(105, 6.5, "從三階段管線到 Trust Tier\nSpec-driven · Tool-First · 漸進式安全")

        pdf.set_font("body", "", 10)
        pdf.set_text_color(*PRIMARY_LIGHT)
        pdf.set_xy(W * 0.42 + 18, 55)
        pdf.multi_cell(
            120,
            6.5,
            "OpenRouter + CrewAI CLI 框架\n"
            "現行版本  v1.0.0-beta.2\n"
            "策略  Tool-First 漸進式\n"
            "方法  OpenSpec 規格驅動\n"
            "日期  2026-08-12",
        )
        pdf.set_font("body", "B", 11)
        pdf.set_text_color(*PRIMARY_MID)
        pdf.set_xy(W * 0.42 + 18, 110)
        pdf.cell(100, 6, "專業 · 極簡 · 證據導向")

    def agenda() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("Agenda")
        pdf.slide_title("本日綱要")
        pdf.subtitle("以版本軸線回顧能力成長、安全強化與目前公開測試狀態。")

        items = [
            ("01", "專案定位與核心架構", PRIMARY),
            ("02", "開發策略：Tool-First + Spec-driven", PRIMARY_DEEP),
            ("03", "版本時間軸總覽", PRIMARY_MID),
            ("04", "能力奠基期（v0.1–v0.5）", ACCENT_PURPLE),
            ("05", "安全補強期（v0.6–v0.9）", ACCENT_RED),
            ("06", "清債與信任框架（v0.9.1–v1.0-beta）", ACCENT_PURPLE_DEEP),
            ("07", "現況、限制與下一步", PRIMARY_DARKEST),
        ]
        cols = 2
        start_y = 62
        for i, (num, label, color) in enumerate(items):
            col = i % cols
            row = i // cols
            x = MARGIN_X + col * 130
            y = start_y + row * 18
            pdf.set_font("body", "B", 16)
            pdf.set_text_color(*color)
            pdf.set_xy(x, y)
            pdf.cell(18, 8, num)
            pdf.set_font("body", "", 12)
            pdf.set_text_color(*INK)
            pdf.cell(100, 8, label)
        pdf.footer_bar()

    def positioning() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("01 · Positioning")
        pdf.slide_title("專案定位")
        pdf.subtitle("Council Agent：讓 AI 以可驗證、可追溯的方式在本機工作區完成任務。")

        stages = [
            ("Planning", "規劃小隊產出計畫與成功標準", PRIMARY),
            ("Execution", "執行小隊掛載 tools 實際動手", ACCENT_PURPLE),
            ("Verification", "校驗小隊對照證據判定 PASS/FAIL", ACCENT_RED),
        ]
        for i, (name, desc, color) in enumerate(stages):
            x = MARGIN_X + i * 88
            y = 62
            pdf.set_fill_color(*WHITE)
            pdf.set_draw_color(*HAIRLINE)
            pdf.rect(x, y, 82, 52, "DF")
            pdf.set_fill_color(*color)
            pdf.rect(x, y, 82, 3, "F")
            pdf.set_font("body", "B", 14)
            pdf.set_text_color(*INK)
            pdf.set_xy(x + 6, y + 12)
            pdf.cell(70, 8, name)
            pdf.set_font("body", "", 10)
            pdf.set_text_color(*MUTED)
            pdf.set_xy(x + 6, y + 24)
            pdf.multi_cell(70, 5.5, desc)
            if i < 2:
                pdf.set_font("body", "B", 16)
                pdf.set_text_color(*PRIMARY)
                pdf.set_xy(x + 78, y + 22)
                pdf.cell(10, 8, "→")

        pdf.set_font("body", "", 10)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(MARGIN_X, 126)
        pdf.multi_cell(
            W - 2 * MARGIN_X,
            5.5,
            "校驗失敗時進入 Escalation，修正後以原成功標準重新驗證；全程可搭配 session 與 audit 留下證據。",
        )
        pdf.footer_bar()

    def strategy() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("02 · Strategy")
        pdf.slide_title("兩條並行的開發軸線")

        pdf.card(
            MARGIN_X,
            52,
            125,
            88,
            "Tool-First 漸進式",
            "先讓 Execution Crew 在本機工作區真實動手；"
            "安全機制自 v0.6 起逐步補強，避免過早阻塞主線。"
            "\n\n原則：最小改動 · 邊界先行 · 安全外掛 · 證據導向校驗",
            PRIMARY,
            13,
        )
        pdf.card(
            MARGIN_X + 135,
            52,
            125,
            88,
            "Spec-driven + OpenSpec",
            "每個 feature 先有 proposal / design / tasks / spec delta，"
            "再依階段實作：純函式 → CLI 接線 → CrewAI 掛載 → e2e。"
            "\n\n驗證門檻：pytest + openspec validate --changes/--specs",
            ACCENT_PURPLE,
            13,
        )
        pdf.footer_bar()

    def timeline() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("03 · Timeline")
        pdf.slide_title("版本時間軸總覽")
        pdf.subtitle("從骨架到公開 beta：能力先落地，信任機制後收斂。")

        phases = [
            ("v0.1", "骨架", "CLI / Crews\nPreset / LLM", PRIMARY_LIGHT, PRIMARY_DARKEST),
            ("v0.2–0.5", "動手", "Tools\nSandbox MVP", PRIMARY_MID, PRIMARY_DARKEST),
            ("v0.6–0.9", "守門", "分類 / 確認\n審計 / 政策", ACCENT_RED_LIGHT, ACCENT_RED_DEEP),
            ("v0.9.1–0.9.9", "清債", "一版一問題\nP0/P1 關閉", ACCENT_PURPLE_LIGHT, ACCENT_PURPLE_DEEP),
            ("v1.0 α→β", "信任", "Trust Tier\n公開測試", PRIMARY, WHITE),
        ]
        # axis
        axis_y = 95
        pdf.set_draw_color(*PRIMARY_MID)
        pdf.set_line_width(1.0)
        pdf.line(MARGIN_X + 8, axis_y, W - MARGIN_X - 8, axis_y)

        box_w = 46
        gap = 8
        usable = W - 2 * MARGIN_X
        total_w = len(phases) * box_w + (len(phases) - 1) * gap
        start_x = MARGIN_X + max(0, (usable - total_w) / 2)
        for i, (ver, tag, body, fill, text_c) in enumerate(phases):
            x = start_x + i * (box_w + gap)
            # node
            pdf.set_fill_color(*PRIMARY_DEEP)
            pdf.ellipse(x + box_w / 2 - 2.2, axis_y - 2.2, 4.4, 4.4, "F")
            # card above/below alternating
            cy = 55 if i % 2 == 0 else 105
            pdf.set_fill_color(*fill)
            pdf.rect(x, cy, box_w, 32, "F")
            pdf.set_font("body", "B", 10)
            pdf.set_text_color(*text_c)
            pdf.set_xy(x + 3, cy + 3)
            pdf.cell(box_w - 6, 5, ver)
            pdf.set_font("body", "", 8.5)
            pdf.set_xy(x + 3, cy + 10)
            pdf.multi_cell(box_w - 6, 4.5, f"{tag}\n{body}")
            # connector
            pdf.set_draw_color(*PRIMARY_MID)
            pdf.set_line_width(0.4)
            if i % 2 == 0:
                pdf.line(x + box_w / 2, cy + 32, x + box_w / 2, axis_y - 2.2)
            else:
                pdf.line(x + box_w / 2, axis_y + 2.2, x + box_w / 2, cy)
        pdf.footer_bar()

    def phase_foundation() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("04 · Foundation")
        pdf.slide_title("能力奠基期  v0.1 → v0.5")
        pdf.subtitle("把「能計劃、能改檔、能跑測、能校驗」打通成可用 MVP。")

        rows = [
            ("v0.1", "專案骨架", "Typer CLI、三階段 Crew、OpenRouter、YAML Preset", PRIMARY),
            ("v0.2", "Tool 基礎層", "read / write / list / delete / run_command → ToolResult", PRIMARY_MID),
            ("v0.3", "Workspace 邊界", "WorkspaceGuard、路徑穿越防護、敏感路徑黑名單", PRIMARY_DEEP),
            ("v0.4", "測試整合", "run_tests、結構化報告、max_tool_calls、Verification 讀摘要", ACCENT_PURPLE),
            ("v0.5", "Sandbox MVP", "sandbox init/status、Execution 掛載 tools、session 紀錄", ACCENT_RED),
        ]
        y = 54
        for ver, name, desc, color in rows:
            pdf.set_fill_color(*color)
            pdf.rect(MARGIN_X, y, 22, 14, "F")
            pdf.set_font("body", "B", 9)
            pdf.set_text_color(*WHITE)
            pdf.set_xy(MARGIN_X, y + 4)
            pdf.cell(22, 6, ver, align="C")
            pdf.set_font("body", "B", 11)
            pdf.set_text_color(*INK)
            pdf.set_xy(MARGIN_X + 26, y + 1.5)
            pdf.cell(60, 5, name)
            pdf.set_font("body", "", 9.5)
            pdf.set_text_color(*MUTED)
            pdf.set_xy(MARGIN_X + 26, y + 7)
            pdf.cell(220, 5, desc)
            y += 17
        pdf.footer_bar()

    def phase_security() -> None:
        pdf.new_slide()
        pdf.left_rail(ACCENT_RED)
        pdf.accent_bar(ACCENT_RED)
        pdf.eyebrow("05 · Security Hardening")
        pdf.slide_title("安全補強期  v0.6 → v0.9")
        pdf.subtitle("功能穩定後，逐步補上分類、確認、審計與專案政策。")

        cards = [
            ("v0.6 指令分類", "read / write / dangerous\npattern 啟發式分類\n危險指令預設守門", ACCENT_RED),
            ("v0.7 互動確認", "TTY ask · --yes auto\n無 TTY refuse\n寫入／危險操作閘道", ACCENT_RED_MID),
            ("v0.8 審計日誌", "結構化 JSONL\naudit show / export\nsession 關聯可追溯", ACCENT_PURPLE),
            ("v0.9 政策設定", "council.policy.yaml\nallow / deny 指令\ndenied_paths 聯集", ACCENT_PURPLE_DEEP),
        ]
        for i, (title, body, color) in enumerate(cards):
            col = i % 2
            row = i // 2
            x = MARGIN_X + col * 135
            y = 54 + row * 42
            pdf.card(x, y, 128, 38, title, body.replace("\n", " · "), color, 12)
        pdf.footer_bar()

    def phase_debt() -> None:
        pdf.new_slide()
        pdf.left_rail(ACCENT_PURPLE)
        pdf.accent_bar(ACCENT_PURPLE)
        pdf.eyebrow("06 · Pre-v1 Debt Cleanup")
        pdf.slide_title("清債序列  v0.9.1 → v0.9.9")
        pdf.subtitle("一版一主要問題：關閉與 v1.0 DoD 衝突的 P0／P1，再談 Trust Tier runtime。")

        items = [
            ("0.9.1", "Shell containment", "未知／混淆 fail-closed"),
            ("0.9.2", "Policy Middleware", "唯一 dispatcher"),
            ("0.9.3", "Policy trust boundary", "只可縮權 · fail-fast"),
            ("0.9.4", "Audit integrity", "redaction · sequence"),
            ("0.9.5", "Principal scope", "key ≠ 授權主體"),
            ("0.9.6", "Session auth", "--yes ≠ 認證"),
            ("0.9.7", "Trust grant store", "workspace 外可撤銷"),
            ("0.9.8", "Decision matrix", "與 ConfirmMode 分離"),
            ("0.9.9", "Evidence closure", "escalation 後再驗"),
        ]
        for i, (ver, name, note) in enumerate(items):
            col = i % 3
            row = i // 3
            x = MARGIN_X + col * 90
            y = 54 + row * 30
            pdf.set_fill_color(*WHITE)
            pdf.set_draw_color(*HAIRLINE)
            pdf.rect(x, y, 85, 26, "DF")
            pdf.set_fill_color(*ACCENT_PURPLE if row == 0 else (ACCENT_PURPLE_MID if row == 1 else ACCENT_PURPLE_LIGHT))
            pdf.rect(x, y, 85, 2.2, "F")
            pdf.set_font("body", "B", 9)
            pdf.set_text_color(*ACCENT_PURPLE_DEEP)
            pdf.set_xy(x + 4, y + 5)
            pdf.cell(77, 5, ver)
            pdf.set_font("body", "B", 10)
            pdf.set_text_color(*INK)
            pdf.set_xy(x + 4, y + 11)
            pdf.cell(77, 5, name)
            pdf.set_font("body", "", 8)
            pdf.set_text_color(*MUTED)
            pdf.set_xy(x + 4, y + 17)
            pdf.cell(77, 5, note)
        pdf.footer_bar()

    def phase_v1() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY_DEEP)
        pdf.accent_bar(PRIMARY_DEEP)
        pdf.eyebrow("06 · Trust Framework")
        pdf.slide_title("信任框架  v1.0-alpha → beta.2")

        # tiers
        tiers = [
            ("Tier 0", "預設", "高敏感操作需確認；最保守起點", PRIMARY_LIGHT, PRIMARY_DARKEST),
            ("Tier 1", "安全自動", "低風險指令可自動；寫入仍受控", PRIMARY_MID, PRIMARY_DARKEST),
            ("Tier 2", "全自動", "需明確啟用；非 --yes 的替代", PRIMARY, WHITE),
        ]
        for i, (name, tag, desc, fill, tc) in enumerate(tiers):
            x = MARGIN_X + i * 90
            pdf.set_fill_color(*fill)
            pdf.rect(x, 50, 85, 42, "F")
            pdf.set_font("body", "B", 14)
            pdf.set_text_color(*tc)
            pdf.set_xy(x + 6, 56)
            pdf.cell(73, 7, name)
            pdf.set_font("body", "", 9)
            pdf.set_xy(x + 6, 66)
            pdf.cell(73, 5, tag)
            pdf.set_xy(x + 6, 74)
            pdf.multi_cell(73, 5, desc)

        milestones = [
            ("alpha.1", "Trust Tier runtime 入場", PRIMARY),
            ("beta.1", "公開測試文件 · stop-line", ACCENT_PURPLE),
            ("beta.2", "Agent 矩陣 PASS（含 LIVE-01）", ACCENT_RED),
        ]
        y = 105
        for ver, note, color in milestones:
            pdf.pill(MARGIN_X, y, ver, color)
            pdf.set_font("body", "", 10.5)
            pdf.set_text_color(*INK)
            pdf.set_xy(MARGIN_X + 42, y)
            pdf.cell(200, 6, note)
            y += 12
        pdf.footer_bar()

    def architecture() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("Architecture")
        pdf.slide_title("模組演進地圖")
        pdf.subtitle("核心管線保持穩定；tools → sandbox → security 分層擴充。")

        layers = [
            ("介面", "cli.py · presets · settings", PRIMARY),
            ("協調", "orchestrator · types · crews", PRIMARY_MID),
            ("工具", "filesystem · shell · tracker", ACCENT_PURPLE),
            ("邊界", "WorkspaceGuard · session", ACCENT_PURPLE_MID),
            ("安全", "classifier · confirm · policy · audit · trust", ACCENT_RED),
        ]
        y = 55
        for name, body, color in layers:
            pdf.set_fill_color(*color)
            pdf.rect(MARGIN_X, y, 36, 16, "F")
            pdf.set_font("body", "B", 10)
            pdf.set_text_color(*WHITE)
            pdf.set_xy(MARGIN_X, y + 5)
            pdf.cell(36, 6, name, align="C")
            pdf.set_fill_color(*WHITE)
            pdf.set_draw_color(*HAIRLINE)
            pdf.rect(MARGIN_X + 38, y, W - 2 * MARGIN_X - 38, 16, "DF")
            pdf.set_font("body", "", 11)
            pdf.set_text_color(*INK)
            pdf.set_xy(MARGIN_X + 44, y + 4.5)
            pdf.cell(200, 7, body)
            y += 19

        pdf.set_font("body", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(MARGIN_X, 152)
        # leave room for footer
        pdf.footer_bar()

    def status() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("07 · Current Status")
        pdf.slide_title("現況  v1.0.0-beta.2")

        done = [
            "三階段管線與 Escalation",
            "Tools + Sandbox + Session",
            "指令分類 / 確認 / 審計 / 政策",
            "Trust Tier 0/1/2 + matrix-v2",
            "Agent 公開測試矩陣 ACCEPTED",
            "LIVE-01 PASS",
        ]
        pending = [
            "Audit predecessor hash chain（GA）",
            "獨立真人 TTY 驗證",
            "完整 OS／容器級 sandbox（非宣稱範圍）",
            "剩餘 GA Definition of Done",
        ]
        pdf.section_label(MARGIN_X, 52, "已交付", PRIMARY_DEEP)
        y = 60
        for t in done:
            y = pdf.bullet(t, MARGIN_X, y, 125, PRIMARY)

        pdf.section_label(MARGIN_X + 140, 52, "仍待 / 已知限制", ACCENT_RED_DEEP)
        y = 60
        for t in pending:
            y = pdf.bullet(t, MARGIN_X + 140, y, 120, ACCENT_RED)

        pdf.set_fill_color(*PRIMARY_LIGHT)
        pdf.rect(MARGIN_X, 128, W - 2 * MARGIN_X, 18, "F")
        pdf.set_font("body", "", 10)
        pdf.set_text_color(*PRIMARY_DARKEST)
        pdf.set_xy(MARGIN_X + 6, 132)
        pdf.multi_cell(
            W - 2 * MARGIN_X - 12,
            5,
            "已知邊界：shell／WorkspaceGuard 非 OS sandbox；ConfirmMode／--yes ≠ Trust Tier；project policy 不能設定 tier。",
        )
        pdf.footer_bar()

    def principles() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY)
        pdf.accent_bar(PRIMARY)
        pdf.eyebrow("Lessons")
        pdf.slide_title("沿途累積的硬性原則")

        principles = [
            ("先規格，再程式", "OpenSpec change 就緒後才實作；Non-goals 對齊 ROADMAP", PRIMARY),
            ("不可跳步整合", "函式 → 接線 → 框架掛載 → e2e，每階 pytest 全綠", PRIMARY_DEEP),
            ("可預期錯誤不 throw", "Tool 回傳 ToolResult(success=False)", ACCENT_PURPLE),
            ("安全不可誇大", "啟發式分類 ≠ 完整信任；文件必須說清楚邊界", ACCENT_RED),
            ("驗證三件套", "pytest + validate --changes + validate --specs", ACCENT_PURPLE_MID),
            ("發版有流程", "archive → release 分支 bump → tag → 文件同步", PRIMARY_MID),
        ]
        for i, (title, body, color) in enumerate(principles):
            col = i % 3
            row = i // 3
            x = MARGIN_X + col * 90
            y = 52 + row * 46
            pdf.card(x, y, 85, 42, title, body, color, 11)
        pdf.footer_bar()

    def next_steps() -> None:
        pdf.new_slide()
        pdf.left_rail(PRIMARY_DEEP)
        pdf.accent_bar(PRIMARY_DEEP)
        pdf.eyebrow("Next")
        pdf.slide_title("通往 GA 的下一哩路")

        steps = [
            ("01", "補齊 audit predecessor-linked hash chain", "完整性可驗證、防事後竄改", PRIMARY),
            ("02", "完成獨立真人 TTY 測試與證據封存", "補齊 beta 後仍 defer 的人工驗證", ACCENT_PURPLE),
            ("03", "對照 v1.0 DoD 關閉剩餘項目", "trust CLI、威脅模型文件、邊界聲明一致", ACCENT_RED),
            ("04", "發版流程：archive → release → tag → ROADMAP", "openspec/changes 不得留 active change", PRIMARY_DEEP),
        ]
        y = 52
        for num, title, note, color in steps:
            pdf.set_fill_color(*color)
            pdf.rect(MARGIN_X, y, 16, 16, "F")
            pdf.set_font("body", "B", 11)
            pdf.set_text_color(*WHITE)
            pdf.set_xy(MARGIN_X, y + 5)
            pdf.cell(16, 6, num, align="C")
            pdf.set_font("body", "B", 12)
            pdf.set_text_color(*INK)
            pdf.set_xy(MARGIN_X + 22, y + 2)
            pdf.cell(220, 6, title)
            pdf.set_font("body", "", 10)
            pdf.set_text_color(*MUTED)
            pdf.set_xy(MARGIN_X + 22, y + 9)
            pdf.cell(220, 5, note)
            y += 22
        pdf.footer_bar()

    def closing() -> None:
        pdf.new_slide()
        pdf.set_fill_color(*PRIMARY_DARKEST)
        pdf.rect(0, 0, W, H, "F")
        pdf.set_fill_color(*PRIMARY)
        pdf.rect(0, 0, W, 3, "F")
        pdf.set_fill_color(*ACCENT_RED)
        pdf.rect(0, 3, W / 2, 1.5, "F")
        pdf.set_fill_color(*ACCENT_PURPLE)
        pdf.rect(W / 2, 3, W / 2, 1.5, "F")

        pdf.set_font("body", "", 11)
        pdf.set_text_color(*PRIMARY_LIGHT)
        pdf.set_xy(MARGIN_X, 48)
        pdf.cell(200, 6, "COUNCIL AGENT")

        pdf.set_font("body", "B", 30)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(MARGIN_X, 60)
        pdf.multi_cell(240, 13, "能動手，也要能守門。")

        pdf.set_font("body", "", 12)
        pdf.set_text_color(*PRIMARY_MID)
        pdf.set_xy(MARGIN_X, 95)
        pdf.multi_cell(
            240,
            6.5,
            "從 Tool-First MVP 到 Trust Tier beta——\n"
            "規格驅動、漸進整合、證據閉環，是這段歷程的主軸。\n\n"
            "現行版本  v1.0.0-beta.2  ·  2026-08-12",
        )

        pdf.set_font("body", "", 9)
        pdf.set_text_color(*PRIMARY_LIGHT)
        pdf.set_xy(MARGIN_X, H - 18)
        pdf.cell(200, 5, "配色：Primary #7E9F35 · Accent #A7383D · Accent #562A72")

    builders = [
        cover,
        agenda,
        positioning,
        strategy,
        timeline,
        phase_foundation,
        phase_security,
        phase_debt,
        phase_v1,
        architecture,
        status,
        principles,
        next_steps,
        closing,
    ]
    pdf.set_total(len(builders))
    for fn in builders:
        fn()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path} ({path.stat().st_size} bytes)")
