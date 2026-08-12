#!/usr/bin/env python3
"""Generate Council Agent development-journey PDF deck (brand palette)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# --- Brand palette ---------------------------------------------------------
PRIMARY = HexColor("#7E9F35")
PRIMARY_LIGHT = HexColor("#A8C764")
PRIMARY_PALE = HexColor("#D6EF9F")
PRIMARY_DEEP = HexColor("#597814")
PRIMARY_DARKEST = HexColor("#375000")

ACCENT_RED = HexColor("#A7383D")
ACCENT_RED_LIGHT = HexColor("#D1686E")
ACCENT_RED_PALE = HexColor("#FBA7AB")
ACCENT_RED_DEEP = HexColor("#7D151A")

ACCENT_PURPLE = HexColor("#562A72")
ACCENT_PURPLE_LIGHT = HexColor("#744B8E")
ACCENT_PURPLE_PALE = HexColor("#9675AB")
ACCENT_PURPLE_DEEP = HexColor("#3B1255")

INK = HexColor("#1A1F14")
INK_MUTED = HexColor("#4A5340")
SURFACE = HexColor("#F7FAF0")
SURFACE_WARM = HexColor("#EEF4E0")

# 16:9 slide
W, H = 338.67 * mm, 190.5 * mm  # 13.333" x 7.5"
MARGIN = 18 * mm
OUT = Path(__file__).resolve().parent / "council-agent-dev-journey.pdf"

FONT = "DeckSans"
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT, FONT_PATH, subfontIndex=0))


def lerp_color(a: Color, b: Color, t: float) -> Color:
    return Color(
        a.red + (b.red - a.red) * t,
        a.green + (b.green - a.green) * t,
        a.blue + (b.blue - a.blue) * t,
    )


def draw_gradient_rect(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    c1: Color,
    c2: Color,
    steps: int = 48,
    horizontal: bool = False,
) -> None:
    for i in range(steps):
        t0 = i / steps
        color = lerp_color(c1, c2, t0)
        c.setFillColor(color)
        if horizontal:
            slice_w = w / steps
            c.rect(x + i * slice_w, y, slice_w + 0.5, h, fill=1, stroke=0)
        else:
            slice_h = h / steps
            c.rect(x, y + i * slice_h, w, slice_h + 0.5, fill=1, stroke=0)


def draw_leaf_motif(c: canvas.Canvas, x: float, y: float, scale: float = 1.0, alpha: float = 0.18) -> None:
    """Abstract olive-leaf mark — brand visual anchor, not decorative noise."""
    c.saveState()
    c.setFillColor(Color(PRIMARY.red, PRIMARY.green, PRIMARY.blue, alpha=alpha))
    path = c.beginPath()
    path.moveTo(x, y)
    path.curveTo(x + 28 * scale, y + 42 * scale, x + 62 * scale, y + 58 * scale, x + 88 * scale, y + 36 * scale)
    path.curveTo(x + 52 * scale, y + 48 * scale, x + 22 * scale, y + 22 * scale, x, y)
    c.drawPath(path, fill=1, stroke=0)
    c.restoreState()


def footer(c: canvas.Canvas, page: int, total: int, label: str = "Council Agent · 開發歷程") -> None:
    c.setFillColor(PRIMARY_DEEP)
    c.rect(0, 0, W, 9 * mm, fill=1, stroke=0)
    c.setFillColor(PRIMARY_PALE)
    c.setFont(FONT, 8)
    c.drawString(MARGIN, 3.2 * mm, label)
    c.drawRightString(W - MARGIN, 3.2 * mm, f"{page} / {total}")


def section_chip(c: canvas.Canvas, x: float, y: float, text: str, fill: Color, ink: Color = white) -> float:
    c.setFont(FONT, 9)
    tw = c.stringWidth(text, FONT, 9)
    pad_x, pad_y = 4.5 * mm, 2.2 * mm
    c.setFillColor(fill)
    c.roundRect(x, y - pad_y, tw + pad_x * 2, 7 * mm, 1.5 * mm, fill=1, stroke=0)
    c.setFillColor(ink)
    c.drawString(x + pad_x, y, text)
    return tw + pad_x * 2


def title_block(c: canvas.Canvas, title: str, subtitle: str | None = None) -> float:
    """Standard content-slide header. Returns y under the header."""
    c.setFillColor(PRIMARY_DARKEST)
    c.rect(0, H - 28 * mm, W, 28 * mm, fill=1, stroke=0)
    c.setFillColor(PRIMARY)
    c.rect(0, H - 28 * mm, 4 * mm, 28 * mm, fill=1, stroke=0)
    c.setFillColor(PRIMARY_PALE)
    c.setFont(FONT, 22)
    c.drawString(MARGIN, H - 16 * mm, title)
    if subtitle:
        c.setFillColor(PRIMARY_LIGHT)
        c.setFont(FONT, 11)
        c.drawString(MARGIN, H - 23 * mm, subtitle)
    return H - 40 * mm


def bullet(c: canvas.Canvas, x: float, y: float, text: str, size: float = 11, color: Color = INK, bullet_color: Color = PRIMARY) -> float:
    c.setFillColor(bullet_color)
    c.circle(x + 1.6 * mm, y + 1.4 * mm, 1.1 * mm, fill=1, stroke=0)
    c.setFillColor(color)
    c.setFont(FONT, size)
    max_w = W - x - MARGIN - 6 * mm
    lines = wrap(text, FONT, size, max_w)
    for i, line in enumerate(lines):
        c.drawString(x + 5 * mm, y - i * (size + 3), line)
    return y - len(lines) * (size + 3) - 3 * mm


def wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    # Character-aware wrap for CJK + Latin
    lines: list[str] = []
    buf = ""
    for ch in text:
        trial = buf + ch
        if pdfmetrics.stringWidth(trial, font, size) <= max_w:
            buf = trial
        else:
            if buf:
                lines.append(buf)
            buf = ch
    if buf:
        lines.append(buf)
    return lines or [""]


def card(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    accent: Color,
    title: str,
    body_lines: list[str],
    title_size: float = 12,
) -> None:
    c.setFillColor(white)
    c.setStrokeColor(PRIMARY_PALE)
    c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 3 * mm, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y + h - 3 * mm, w, 3 * mm, 1.5 * mm, fill=1, stroke=0)
    c.rect(x, y + h - 6 * mm, w, 4 * mm, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont(FONT, title_size)
    c.drawString(x + 4 * mm, y + h - 12 * mm, title)
    c.setFillColor(INK_MUTED)
    c.setFont(FONT, 9.5)
    ty = y + h - 20 * mm
    for line in body_lines:
        for wrapped in wrap(line, FONT, 9.5, w - 8 * mm):
            c.drawString(x + 4 * mm, ty, wrapped)
            ty -= 4.2 * mm


# --- Slides ----------------------------------------------------------------

def slide_cover(c: canvas.Canvas, page: int, total: int) -> None:
    draw_gradient_rect(c, 0, 0, W, H, PRIMARY_DARKEST, PRIMARY_DEEP, steps=64)
    # Right atmospheric panel
    draw_gradient_rect(c, W * 0.55, 0, W * 0.45, H, PRIMARY_DEEP, PRIMARY, steps=40, horizontal=True)
    draw_leaf_motif(c, W * 0.62, H * 0.28, scale=2.4, alpha=0.22)
    draw_leaf_motif(c, W * 0.72, H * 0.55, scale=1.6, alpha=0.14)

    c.setFillColor(PRIMARY_PALE)
    c.setFont(FONT, 11)
    c.drawString(MARGIN, H - 28 * mm, "COUNCIL AGENT")

    c.setFillColor(white)
    c.setFont(FONT, 36)
    c.drawString(MARGIN, H - 52 * mm, "開發歷程簡報")

    c.setFillColor(PRIMARY_LIGHT)
    c.setFont(FONT, 14)
    for i, line in enumerate(
        [
            "從三階段管線到 Trust Tier 公開測試",
            "Tool-First · Spec-driven · OpenSpec",
        ]
    ):
        c.drawString(MARGIN, H - 68 * mm - i * 8 * mm, line)

    # Accent bar cluster
    c.setFillColor(PRIMARY)
    c.rect(MARGIN, H - 92 * mm, 42 * mm, 3.2 * mm, fill=1, stroke=0)
    c.setFillColor(ACCENT_RED)
    c.rect(MARGIN + 46 * mm, H - 92 * mm, 14 * mm, 3.2 * mm, fill=1, stroke=0)
    c.setFillColor(ACCENT_PURPLE)
    c.rect(MARGIN + 64 * mm, H - 92 * mm, 14 * mm, 3.2 * mm, fill=1, stroke=0)

    c.setFillColor(PRIMARY_PALE)
    c.setFont(FONT, 11)
    c.drawString(MARGIN, 28 * mm, "現況基線  v1.0.0-beta.2")
    c.drawString(MARGIN, 20 * mm, "資料截止  2026-08-11 · 簡報產出  2026-08-12")
    footer(c, page, total)


def slide_agenda(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    y = title_block(c, "目錄", "這份簡報帶你走完一條版本路徑")
    items = [
        ("01", "專案定位與策略", PRIMARY),
        ("02", "版本時間軸總覽", PRIMARY_DEEP),
        ("03", "能力奠基：Tools → Sandbox（v0.2–v0.5）", PRIMARY),
        ("04", "安全補強：Classifier → Policy（v0.6–v0.9）", ACCENT_RED),
        ("05", "清債序列：通往 v1.0 的九個修補（v0.9.1–v0.9.9）", ACCENT_PURPLE),
        ("06", "信任框架與公開測試（v1.0-alpha → beta.2）", ACCENT_PURPLE_DEEP),
        ("07", "現況能力、已知限制與下一步", PRIMARY_DEEP),
    ]
    for i, (num, text, color) in enumerate(items):
        row_y = y - i * 16 * mm
        c.setFillColor(white)
        c.roundRect(MARGIN, row_y - 4 * mm, W - 2 * MARGIN, 13 * mm, 2 * mm, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(MARGIN, row_y - 4 * mm, 18 * mm, 13 * mm, 2 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(FONT, 12)
        c.drawCentredString(MARGIN + 9 * mm, row_y + 0.5 * mm, num)
        c.setFillColor(INK)
        c.setFont(FONT, 13)
        c.drawString(MARGIN + 24 * mm, row_y + 0.5 * mm, text)
    footer(c, page, total)


def slide_positioning(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    y = title_block(c, "專案定位", "OpenRouter + CrewAI 三階段 CLI 框架")
    # Pipeline strip
    stages = [
        ("Planning", "計畫", PRIMARY),
        ("Execution", "執行（掛載 Tools）", PRIMARY_DEEP),
        ("Verification", "校驗（證據導向）", ACCENT_PURPLE),
        ("Escalation", "升級修正後重驗", ACCENT_RED),
    ]
    box_w = (W - 2 * MARGIN - 3 * 6 * mm) / 4
    for i, (en, zh, color) in enumerate(stages):
        x = MARGIN + i * (box_w + 6 * mm)
        c.setFillColor(color)
        c.roundRect(x, y - 28 * mm, box_w, 30 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(FONT, 11)
        c.drawString(x + 4 * mm, y - 8 * mm, en)
        c.setFont(FONT, 14)
        c.drawString(x + 4 * mm, y - 18 * mm, zh)
        if i < 3:
            c.setFillColor(PRIMARY_LIGHT)
            c.setFont(FONT, 16)
            c.drawCentredString(x + box_w + 3 * mm, y - 12 * mm, "→")

    y2 = y - 48 * mm
    c.setFillColor(INK)
    c.setFont(FONT, 13)
    c.drawString(MARGIN, y2, "兩條並行原則")
    card(
        c,
        MARGIN,
        y2 - 52 * mm,
        (W - 2 * MARGIN - 8 * mm) / 2,
        48 * mm,
        PRIMARY,
        "Tool-First 漸進式",
        [
            "先讓 Execution 能在本機工作區動手",
            "邊界先行：WorkspaceGuard 限制 cwd",
            "安全以 middleware 後補，不阻塞主線",
            "Verification 讀真實 tool / pytest 結果",
        ],
    )
    card(
        c,
        MARGIN + (W - 2 * MARGIN - 8 * mm) / 2 + 8 * mm,
        y2 - 52 * mm,
        (W - 2 * MARGIN - 8 * mm) / 2,
        48 * mm,
        ACCENT_PURPLE,
        "Spec-driven + OpenSpec",
        [
            "先提案（proposal / design / tasks / delta）",
            "再依 tasks 漸進整合，不可跳步",
            "feature 分支對應一個 change",
            "提交前必須通過 ./scripts/check.sh",
        ],
    )
    footer(c, page, total)


def slide_timeline(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "版本時間軸", "v0.1 → v1.0.0-beta.2")

    eras = [
        ("奠基", "v0.2–v0.5", "Tools · Guard · Tests · Sandbox", PRIMARY, PRIMARY_PALE),
        ("安全", "v0.6–v0.9", "分類 · 確認 · 審計 · 政策", ACCENT_RED, ACCENT_RED_PALE),
        ("清債", "v0.9.1–0.9.9", "九版各解一個 P0/P1", ACCENT_PURPLE, HexColor("#E8DFF0")),
        ("信任", "v1.0 α→β.2", "Trust Tier · 公開測試", ACCENT_PURPLE_DEEP, HexColor("#EDE6F3")),
    ]
    lane_y = H - 70 * mm
    c.setStrokeColor(PRIMARY_LIGHT)
    c.setLineWidth(3)
    c.line(MARGIN, lane_y, W - MARGIN, lane_y)

    for i, (name, ver, desc, color, soft) in enumerate(eras):
        x = MARGIN + i * ((W - 2 * MARGIN) / 4) + 8 * mm
        c.setFillColor(color)
        c.circle(x + 28 * mm, lane_y, 5 * mm, fill=1, stroke=0)
        c.setFillColor(soft)
        c.roundRect(x, lane_y - 55 * mm, 58 * mm, 42 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(color)
        c.setFont(FONT, 12)
        c.drawString(x + 4 * mm, lane_y - 18 * mm, name)
        c.setFillColor(INK)
        c.setFont(FONT, 10)
        c.drawString(x + 4 * mm, lane_y - 28 * mm, ver)
        c.setFillColor(INK_MUTED)
        c.setFont(FONT, 9)
        for j, line in enumerate(wrap(desc, FONT, 9, 50 * mm)):
            c.drawString(x + 4 * mm, lane_y - 38 * mm - j * 4 * mm, line)

    c.setFillColor(INK_MUTED)
    c.setFont(FONT, 10)
    c.drawString(MARGIN, 28 * mm, "策略節奏：先可用 → 再可控 → 再可信任。紅色／紫色標示安全與信任模組。")
    footer(c, page, total)


def slide_foundation(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "能力奠基  v0.2–v0.5", "讓 Agent 真的能動手，而不是只會說話")

    versions = [
        ("v0.2", "Tool 基礎層", ["read / write / list / delete", "run_command", "統一 ToolResult"], PRIMARY),
        ("v0.3", "Workspace 邊界", ["WorkspaceGuard", "路徑穿越防護", "敏感路徑黑名單"], PRIMARY_DEEP),
        ("v0.4", "測試整合", ["run_tests + pytest 報告", "Verification 讀摘要", "max_tool_calls"], ACCENT_PURPLE),
        ("v0.5", "Sandbox MVP", ["council sandbox CLI", "Execution 掛載 tools", "session 紀錄"], PRIMARY),
    ]
    for i, (ver, title, lines, color) in enumerate(versions):
        x = MARGIN + (i % 4) * ((W - 2 * MARGIN) / 4 + 0)
        card_w = (W - 2 * MARGIN - 9 * mm) / 4
        x = MARGIN + i * (card_w + 3 * mm)
        card(c, x, H - 145 * mm, card_w, 95 * mm, color, f"{ver}  {title}", lines, title_size=11)

    c.setFillColor(PRIMARY_DARKEST)
    c.setFont(FONT, 11)
    c.drawString(MARGIN, 26 * mm, "v0.5 DoD：CRUD 檔案、跑 pytest、擋穿越、Verification 對照真實結果、tool 呼叫上限。")
    footer(c, page, total)


def slide_security(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "安全補強  v0.6–v0.9", "功能穩定後，把風險關進政策與審計")

    rows = [
        ("v0.6", "指令分類", "read / write / dangerous pattern 啟發式", ACCENT_RED),
        ("v0.7", "互動確認", "TTY ask · --yes · 無 TTY refuse", ACCENT_RED_LIGHT),
        ("v0.8", "審計日誌", ".council/audit/ + show / export", ACCENT_PURPLE),
        ("v0.9", "政策設定", "council.policy.yaml allow/deny + denied_paths", ACCENT_PURPLE_DEEP),
    ]
    y = H - 48 * mm
    for ver, title, desc, color in rows:
        c.setFillColor(white)
        c.roundRect(MARGIN, y - 18 * mm, W - 2 * MARGIN, 22 * mm, 2.5 * mm, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(MARGIN, y - 18 * mm, 28 * mm, 22 * mm, 2.5 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(FONT, 12)
        c.drawCentredString(MARGIN + 14 * mm, y - 8 * mm, ver)
        c.setFillColor(INK)
        c.setFont(FONT, 13)
        c.drawString(MARGIN + 34 * mm, y - 5 * mm, title)
        c.setFillColor(INK_MUTED)
        c.setFont(FONT, 11)
        c.drawString(MARGIN + 34 * mm, y - 13 * mm, desc)
        y -= 26 * mm

    c.setFillColor(ACCENT_RED_DEEP)
    c.setFont(FONT, 10)
    c.drawString(MARGIN, 24 * mm, "提醒：分類是 pattern 啟發式，此時尚未宣稱完整信任框架。")
    footer(c, page, total)


def slide_debt(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "清債序列  v0.9.1–v0.9.9", "一版只解一個主要問題，為 Trust Tier 清場")

    items = [
        ("0.9.1", "Shell containment", "未知／混淆指令 fail-closed"),
        ("0.9.2", "Policy Middleware", "唯一 dispatcher + SecurityContext"),
        ("0.9.3", "Policy trust boundary", "專案政策只能縮權"),
        ("0.9.4", "Audit integrity", "redaction · sequence · 控制面"),
        ("0.9.5", "Principal / scopes", "區分 provider key 與授權範圍"),
        ("0.9.6", "Session auth", "高權限 step-up；--yes ≠ 認證"),
        ("0.9.7", "Trust grant store", "使用者擁有、可 revoke"),
        ("0.9.8", "Decision matrix", "與 ConfirmMode 分離、可測"),
        ("0.9.9", "Evidence closure", "escalation 後重新驗證"),
    ]
    cols = 3
    card_w = (W - 2 * MARGIN - 2 * 5 * mm) / cols
    card_h = 28 * mm
    start_y = H - 48 * mm
    for i, (ver, title, desc) in enumerate(items):
        col = i % cols
        row = i // cols
        x = MARGIN + col * (card_w + 5 * mm)
        y = start_y - row * (card_h + 4 * mm) - card_h
        accent = ACCENT_PURPLE if row < 2 else ACCENT_PURPLE_LIGHT
        c.setFillColor(white)
        c.setStrokeColor(HexColor("#E8DFF0"))
        c.setLineWidth(0.7)
        c.roundRect(x, y, card_w, card_h, 2 * mm, fill=1, stroke=1)
        c.setFillColor(accent)
        c.rect(x, y, 2.2 * mm, card_h, fill=1, stroke=0)
        c.setFillColor(ACCENT_PURPLE_DEEP)
        c.setFont(FONT, 9)
        c.drawString(x + 5 * mm, y + card_h - 8 * mm, ver)
        c.setFillColor(INK)
        c.setFont(FONT, 11)
        c.drawString(x + 5 * mm, y + card_h - 15 * mm, title)
        c.setFillColor(INK_MUTED)
        c.setFont(FONT, 9)
        for j, line in enumerate(wrap(desc, FONT, 9, card_w - 10 * mm)):
            c.drawString(x + 5 * mm, y + 8 * mm - j * 4 * mm, line)
    footer(c, page, total)


def slide_v1(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "信任框架與公開測試", "v1.0.0-alpha.1 → v1.0.0-beta.2")

    # Tier cards
    tiers = [
        ("Tier 0", "預設", "所有操作需確認", ACCENT_PURPLE_DEEP),
        ("Tier 1", "安全自動", "安全指令自動執行", ACCENT_PURPLE),
        ("Tier 2", "全自動", "需明確啟用", ACCENT_RED),
    ]
    for i, (name, tag, desc, color) in enumerate(tiers):
        x = MARGIN + i * ((W - 2 * MARGIN) / 3 + 0)
        w = (W - 2 * MARGIN - 10 * mm) / 3
        x = MARGIN + i * (w + 5 * mm)
        c.setFillColor(color)
        c.roundRect(x, H - 95 * mm, w, 42 * mm, 3 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont(FONT, 16)
        c.drawString(x + 5 * mm, H - 65 * mm, name)
        c.setFont(FONT, 10)
        c.drawString(x + 5 * mm, H - 74 * mm, tag)
        c.setFont(FONT, 11)
        c.drawString(x + 5 * mm, H - 85 * mm, desc)

    y = H - 112 * mm
    bullets = [
        "alpha.1：啟用 Trust Tier 0/1/2 runtime 與 CLI --trust-tier",
        "beta.1：schema 凍結；Agent 公開測試矩陣（含 LIVE-01）PASS（ACCEPTED GATE A）",
        "beta.2：承接凍結語意的公開測試後續基線；獨立真人 TTY 仍待後續 beta",
        "明確分離：ConfirmMode / --yes ≠ Trust Tier；專案政策不能設定 tier",
    ]
    for text in bullets:
        y = bullet(c, MARGIN, y, text, size=11, bullet_color=ACCENT_PURPLE)
    footer(c, page, total)


def slide_architecture(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "架構演進一覽", "模組以顏色區隔：綠＝核心能力、紅＝風險閘道、紫＝信任／政策")

    modules = [
        ("crews / orchestrator", "三階段管線與協調", PRIMARY, ["planning", "execution + tools", "verification + evidence"]),
        ("tools / sandbox", "動手與邊界", PRIMARY_DEEP, ["filesystem / shell", "WorkspaceGuard", "session"]),
        ("security 閘道", "分類 · 確認 · 審計", ACCENT_RED, ["classifier", "confirm modes", "audit JSONL"]),
        ("trust / policy", "決策與授權", ACCENT_PURPLE, ["middleware", "policy.yaml", "Trust Tier matrix"]),
    ]
    w = (W - 2 * MARGIN - 9 * mm) / 4
    for i, (title, sub, color, lines) in enumerate(modules):
        x = MARGIN + i * (w + 3 * mm)
        card(c, x, H - 150 * mm, w, 100 * mm, color, title, [sub, "—", *lines])
    footer(c, page, total)


def slide_status(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "現況快照  v1.0.0-beta.2", "已交付 vs 已知限制")

    left_x = MARGIN
    right_x = W / 2 + 4 * mm
    col_w = W / 2 - MARGIN - 8 * mm

    c.setFillColor(PRIMARY)
    c.roundRect(left_x, H - 155 * mm, col_w, 108 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FONT, 14)
    c.drawString(left_x + 5 * mm, H - 55 * mm, "已就緒")
    done = [
        "三階段管線 + Escalation",
        "Tools / Sandbox / Session",
        "Classifier + Confirm + Audit",
        "Policy middleware（唯一路徑）",
        "Trust Tier 0/1/2 + matrix-v2",
        "Agent 公開測試門檻通過",
    ]
    yy = H - 68 * mm
    c.setFont(FONT, 11)
    for t in done:
        c.drawString(left_x + 5 * mm, yy, "▸  " + t)
        yy -= 7 * mm

    c.setFillColor(ACCENT_RED_DEEP)
    c.roundRect(right_x, H - 155 * mm, col_w, 108 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FONT, 14)
    c.drawString(right_x + 5 * mm, H - 55 * mm, "尚未／限制")
    pending = [
        "Audit predecessor hash chain（GA）",
        "非 OS／容器級 sandbox",
        "run_tests 會執行專案程式碼",
        "真人獨立 TTY 測試待補",
        "policy 不可設定 trust tier",
        "--yes 不是 Tier 2",
    ]
    yy = H - 68 * mm
    c.setFont(FONT, 11)
    for t in pending:
        c.drawString(right_x + 5 * mm, yy, "▸  " + t)
        yy -= 7 * mm
    footer(c, page, total)


def slide_next(c: canvas.Canvas, page: int, total: int) -> None:
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "下一步：邁向 GA", "v1.0 DoD 剩餘焦點")

    items = [
        ("完整性", "審計日誌 predecessor-linked hash chain 與可匯出完整性證明", ACCENT_PURPLE),
        ("體驗驗證", "獨立真人 TTY 手冊走完，補齊 beta 後續證據", ACCENT_RED),
        ("文件與威脅模型", "安全模型、政策指南、威脅模型簡述齊備", PRIMARY),
        ("發版紀律", "active change 歸檔、release 分支 bump、ROADMAP／config 同步", PRIMARY_DEEP),
    ]
    y = H - 50 * mm
    for title, desc, color in items:
        c.setFillColor(white)
        c.roundRect(MARGIN, y - 18 * mm, W - 2 * MARGIN, 22 * mm, 2.5 * mm, fill=1, stroke=0)
        c.setFillColor(color)
        c.circle(MARGIN + 8 * mm, y - 7 * mm, 3.2 * mm, fill=1, stroke=0)
        c.setFillColor(INK)
        c.setFont(FONT, 13)
        c.drawString(MARGIN + 16 * mm, y - 4 * mm, title)
        c.setFillColor(INK_MUTED)
        c.setFont(FONT, 11)
        c.drawString(MARGIN + 16 * mm, y - 12 * mm, desc)
        y -= 26 * mm
    footer(c, page, total)


def slide_closing(c: canvas.Canvas, page: int, total: int) -> None:
    draw_gradient_rect(c, 0, 0, W, H, PRIMARY_DARKEST, HexColor("#243808"), steps=64)
    draw_leaf_motif(c, W * 0.68, H * 0.2, scale=2.8, alpha=0.2)

    c.setFillColor(PRIMARY_PALE)
    c.setFont(FONT, 12)
    c.drawString(MARGIN, H - 36 * mm, "COUNCIL AGENT")

    c.setFillColor(white)
    c.setFont(FONT, 30)
    c.drawString(MARGIN, H - 58 * mm, "先動手，再控權，後可信")

    c.setFillColor(PRIMARY_LIGHT)
    c.setFont(FONT, 13)
    lines = [
        "這條路不是一次堆出完整安全機制，",
        "而是用 Spec-driven 把每一次增量變成可驗證的基線。",
        "",
        "目前站在 v1.0.0-beta.2：信任語意已凍結，公開測試已過門，",
        "下一步是把完整性與真人驗證補齊，穩穩走向 GA。",
    ]
    y = H - 80 * mm
    for line in lines:
        c.drawString(MARGIN, y, line)
        y -= 8 * mm

    c.setFillColor(PRIMARY)
    c.rect(MARGIN, 36 * mm, 36 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColor(ACCENT_RED)
    c.rect(MARGIN + 40 * mm, 36 * mm, 12 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColor(ACCENT_PURPLE)
    c.rect(MARGIN + 56 * mm, 36 * mm, 12 * mm, 3 * mm, fill=1, stroke=0)

    c.setFillColor(PRIMARY_PALE)
    c.setFont(FONT, 10)
    c.drawString(MARGIN, 22 * mm, "配色：主色橄欖綠 #7E9F35 · 強調磚紅 #A7383D · 強調紫 #562A72")
    footer(c, page, total)


def slide_palette(c: canvas.Canvas, page: int, total: int) -> None:
    """Optional brand appendix — shows the palette applied in this deck."""
    c.setFillColor(SURFACE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    title_block(c, "附錄：品牌色階", "本簡報實際使用的 Primary / Accent 分工")

    families = [
        ("Primary 橄欖綠", ["#D6EF9F", "#A8C764", "#7E9F35", "#597814", "#375000"], "畫面基調、標題列、核心能力模組"),
        ("Secondary 磚紅", ["#FBA7AB", "#D1686E", "#A7383D", "#7D151A", "#540004"], "風險、限制、危險狀態強調"),
        ("Secondary 紫", ["#9675AB", "#744B8E", "#562A72", "#3B1255", "#240339"], "信任、政策、清債與 Tier 模組"),
    ]
    y = H - 55 * mm
    for name, shades, role in families:
        c.setFillColor(INK)
        c.setFont(FONT, 13)
        c.drawString(MARGIN, y, name)
        c.setFillColor(INK_MUTED)
        c.setFont(FONT, 10)
        c.drawString(MARGIN + 55 * mm, y, role)
        sw = (W - 2 * MARGIN) / 5 - 2 * mm
        for i, hex_code in enumerate(shades):
            x = MARGIN + i * (sw + 2 * mm)
            c.setFillColor(HexColor(hex_code))
            c.roundRect(x, y - 28 * mm, sw, 22 * mm, 2 * mm, fill=1, stroke=0)
            label_color = white if i >= 2 else INK
            c.setFillColor(label_color)
            c.setFont(FONT, 8)
            c.drawCentredString(x + sw / 2, y - 18 * mm, hex_code)
        y -= 40 * mm
    footer(c, page, total)


def build() -> Path:
    register_fonts()
    slides = [
        slide_cover,
        slide_agenda,
        slide_positioning,
        slide_timeline,
        slide_foundation,
        slide_security,
        slide_debt,
        slide_v1,
        slide_architecture,
        slide_status,
        slide_next,
        slide_palette,
        slide_closing,
    ]
    total = len(slides)
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle("Council Agent 開發歷程簡報")
    c.setAuthor("Council Agent")
    c.setSubject("v0.1 → v1.0.0-beta.2 development journey")
    for i, fn in enumerate(slides, start=1):
        fn(c, i, total)
        c.showPage()
    c.save()
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
