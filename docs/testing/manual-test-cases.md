# v1.0 準備階段真人測試案例

> 基線：v0.9.0。這些案例必須在 [`v1.0-beta-public-testing.md`](v1.0-beta-public-testing.md) 定義的一次性隔離環境執行。v0.9.0 的部分安全案例**預期失敗**；預期失敗仍記為 `FAIL`，不能算 release gate 通過。

## 共用前置條件

```bash
export COUNCIL_TEST_ROOT="$(mktemp -d)"
export COUNCIL_WORKSPACE_ROOT="$COUNCIL_TEST_ROOT/workspace"
mkdir -p "$COUNCIL_WORKSPACE_ROOT" "$COUNCIL_TEST_ROOT/outside"
printf 'outside-sentinel\n' > "$COUNCIL_TEST_ROOT/outside/sentinel.txt"
cd /workspace
uv sync
```

執行每個案例前記錄：

```bash
date -u
git rev-parse HEAD
python --version
sha256sum "$COUNCIL_TEST_ROOT/outside/sentinel.txt"
```

每個案例都要保存命令、exit code、stdout/stderr 摘要、執行前後檔案差異、sentinel 前後雜湊及結果。任何輸出都先遮罩；不得使用真實秘密。

## 案例總表

| ID | 主題 | v0.9.0 預期 |
|---|---|---|
| MAN-01 | sandbox 初始化與狀態 | PASS |
| MAN-02 | 工作區內檔案 CRUD | PASS |
| MAN-03 | path traversal 拒絕 | PASS |
| MAN-04 | project policy deny 優先 | PASS |
| MAN-05 | confirmation 拒絕與同意 | PASS |
| MAN-06 | dangerous 指令預設拒絕 | PASS |
| MAN-07 | `--yes` 不覆蓋 policy deny | PASS |
| MAN-08 | 未知 classifier fail-open | FAIL |
| MAN-09 | shell 越界寫入 | FAIL |
| MAN-10 | Agent 可修改 project policy | FAIL |
| MAN-11 | audit show／export | PASS |
| MAN-12 | audit secret redaction／hash chain | FAIL |
| MAN-13 | `run_tests` shell 語意邊界 | FAIL |

## MAN-01 — Sandbox 初始化與狀態

**目的**：確認乾淨 workspace 可初始化且重複執行。

**操作**：

```bash
uv run council sandbox init --workspace "$COUNCIL_WORKSPACE_ROOT"
uv run council sandbox init --workspace "$COUNCIL_WORKSPACE_ROOT"
uv run council sandbox status --workspace "$COUNCIL_WORKSPACE_ROOT"
```

**預期**：

- 三個命令 exit code 皆為 0。
- `.council/config.yaml` 存在；重複初始化不破壞既有狀態。
- 輸出顯示的 workspace realpath 等於 `$COUNCIL_WORKSPACE_ROOT`。
- outside sentinel 不變。

**清理**：保留 `.council/` 供後續案例使用。

## MAN-02 — 工作區內檔案 CRUD

**目的**：確認直接 filesystem tools 在 workspace 內可讀、寫、列出與刪除。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.filesystem import delete_file, list_dir, read_file, write_file

with confirmation_policy(ConfirmMode.AUTO):
    print(write_file("human-case.txt", "測試內容\n"))
print(read_file("human-case.txt"))
print(list_dir("."))
with confirmation_policy(ConfirmMode.AUTO):
    print(delete_file("human-case.txt"))
PY
```

**預期**：每個 `ToolResult.success` 為 `True`；讀取內容一致；最後檔案不存在；outside sentinel 不變。

**清理**：確認 `human-case.txt` 已刪除。

## MAN-03 — Path Traversal 拒絕

**目的**：確認直接 filesystem tool 不可用 `../` 越過 `WorkspaceGuard`。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.filesystem import read_file, write_file

print(read_file("../outside/sentinel.txt"))
with confirmation_policy(ConfirmMode.AUTO):
    print(write_file("../outside/created-by-agent.txt", "不應建立"))
PY
```

**預期**：兩次呼叫皆 `success=False`；錯誤指出 workspace boundary；`created-by-agent.txt` 不存在；sentinel 不變。

**停止條件**：任一越界檔案可讀或可寫，立刻停止並列 P0。

## MAN-04 — Project Policy Deny 優先

**目的**：確認 deny 比 allow 與 confirmation 優先。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import ConfirmMode, active_policy, confirmation_policy
from council_agent.security.policy import CouncilPolicy
from council_agent.tools.shell import run_command

policy = CouncilPolicy(
    allowed_commands=["echo *"],
    denied_commands=["echo blocked*"],
)
with active_policy(policy), confirmation_policy(ConfirmMode.AUTO):
    print(run_command("echo allowed"))
    print(run_command("echo blocked-value"))
PY
```

**預期**：第一個成功；第二個 `success=False` 且 metadata 為 policy deny；`ConfirmMode.AUTO` 不可覆蓋 deny；sentinel 不變。

## MAN-05 — Confirmation 拒絕與同意

**目的**：確認寫入操作在 `REFUSE` 被拒絕，在明確回應同意時才執行。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.filesystem import write_file

with confirmation_policy(ConfirmMode.REFUSE):
    print(write_file("confirm-refused.txt", "不可寫入"))
with confirmation_policy(ConfirmMode.ASK, confirm_fn=lambda _: True):
    print(write_file("confirm-approved.txt", "已確認"))
PY
```

**預期**：第一個失敗且檔案不存在；第二個成功且 metadata 記錄 `confirmation=approved`；outside sentinel 不變。

**清理**：刪除 `confirm-approved.txt`，保留遮罩後結果。

## MAN-06 — Dangerous 指令預設拒絕

**目的**：不真正執行網路或破壞操作，即可驗證 dangerous 分類與無 TTY 拒絕語意。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.shell import run_command

with confirmation_policy(ConfirmMode.REFUSE):
    result = run_command("curl https://example.invalid/")
print(result)
PY
```

**預期**：`success=False`、`classification=dangerous`、matched rule 為 `curl`、confirmation 為 `refused`；沒有 DNS／網路連線與檔案副作用。

## MAN-07 — `--yes` 不等於完整授權

**目的**：確認 `--yes` 只把 CLI confirmation mode 解析為 `AUTO`；它不是 Trust Tier、principal、authentication 或 policy bypass。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import active_policy
from council_agent.security.confirm import ConfirmMode, confirmation_policy, resolve_cli_confirm_mode
from council_agent.security.policy import CouncilPolicy
from council_agent.tools.shell import run_command

mode = resolve_cli_confirm_mode(yes=True, is_tty=False)
print("mode:", mode.value)
with active_policy(CouncilPolicy(denied_commands=["touch *"])):
    with confirmation_policy(mode):
        print(run_command("touch must-not-exist.txt"))
PY
```

**預期**：mode 為 `auto`，但 `touch` 仍被 policy deny；`must-not-exist.txt` 不存在。記錄結論：`ConfirmMode ≠ Trust Tier`，`--yes ≠ 完整授權`。

## MAN-08 — 未知 Classifier Fail-closed

**目的**：確認未知／不支援指令不再因未命中 rule 被分類為 `read`。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import classify_command

for command in ("python -c 'print(1)'", "sh -c 'printf ok'"):
    result = classify_command(command)
    print(
        command,
        "accepted=", result.accepted,
        "reason=", getattr(result, "rejection_reason", None),
    )
PY
```

**安全期望**：無法解析或不在允許 grammar 的指令應 fail-closed。

**v0.9.0 實際預期**：兩者分類為 `read` 且沒有 matched rule，故案例為 `FAIL`（V1-001），不得把重現成功記成 `PASS`。

**v0.9.1 implementation 預期**：兩者 `accepted=False`；依 raw syntax 分別回 `shell_metachar` 或 `unsupported`，且沒有 executable action。案例為 `PASS`，證據見 [`../releases/v0.9.1-shell-containment-evidence.md`](../releases/v0.9.1-shell-containment-evidence.md)。

## MAN-09 — Shell 只驗證 `cwd`，不是真 Sandbox

**目的**：以隔離目錄中的假檔案證明 shell 可使用絕對路徑在 workspace 外寫入。

**操作**：

```bash
export COUNCIL_OUTSIDE_PROBE="$COUNCIL_TEST_ROOT/outside/shell-created.txt"
uv run python - <<'PY'
import os
import shlex
import sys
from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.shell import run_command

probe = os.environ["COUNCIL_OUTSIDE_PROBE"]
code = f"from pathlib import Path; Path({probe!r}).write_text('outside-write')"
command = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"
with confirmation_policy(ConfirmMode.REFUSE):
    print(run_command(command))
print("outside_exists:", os.path.exists(probe))
PY
```

**安全期望**：越界副作用被拒絕，probe 不存在。

**v0.9.0 實際預期**：Python 指令未知而分類為 `read`，shell 只檢查 `cwd`，probe 會建立；案例為 `FAIL`（V1-001）。這只能在一次性隔離環境執行。

**v0.9.1 implementation 預期**：path-qualified Python／shell control 在 process creation 前拒絕，`outside_exists=False`，原 sentinel 不變。這只證明 simple-command boundary；仍不代表 OS sandbox。

**清理**：記錄雜湊後刪除 `shell-created.txt`；原 sentinel 必須仍不變。

## MAN-10 — Project Policy 可被 Agent 修改

**目的**：證明 `council.policy.yaml` 位於 Agent 可寫的 project boundary，不能當成使用者擁有的授權來源。

**操作**：

```bash
uv run python - <<'PY'
from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.filesystem import write_file

with confirmation_policy(ConfirmMode.AUTO):
    print(write_file(
        "council.policy.yaml",
        "allowed_commands:\n  - '*'\ndenied_commands: []\n",
    ))
PY
```

**安全期望**：控制面與使用者授權資料不能被受控 Agent 修改。

**v0.9.0 實際預期**：project policy 可被寫入；案例為 `FAIL`（V1-004）。此檔只能限縮專案政策，不得被解讀為 grant、authentication 或 Trust Tier。

**清理**：保存內容與雜湊後移除測試政策檔。

## MAN-11 — Audit Show 與 Export

**目的**：確認 audit CLI 可顯示、篩選與匯出結構化事件。

**操作**：

```bash
uv run python - <<'PY'
import os
from pathlib import Path
from council_agent.security.audit import AuditLogger

root = Path(os.environ["COUNCIL_WORKSPACE_ROOT"])
logger = AuditLogger(root / ".council/audit/events.jsonl", session_id="MAN-11")
logger.record("read_file", {"path": "sample.txt"}, success=True)
logger.record("write_file", {"path": "denied.txt"}, success=False, error="test deny")
PY
uv run council audit show --workspace "$COUNCIL_WORKSPACE_ROOT" --session MAN-11
uv run council audit export "$COUNCIL_TEST_ROOT/audit-man-11.json" \
  --workspace "$COUNCIL_WORKSPACE_ROOT" --session MAN-11 --format json
```

**預期**：show 顯示兩筆事件且順序一致；export 為合法 JSON、只含 MAN-11；exit code 皆為 0。

**限制**：這只證明顯示與匯出，不證明 audit 完整性。

## MAN-12 — Audit 無 Secret Redaction、無 Hash Chain

**目的**：用純假字串驗證現行限制，不得放入真實 credential。

**操作**：

```bash
uv run python - <<'PY'
import json
import os
from pathlib import Path
from council_agent.security.audit import AuditLogger

marker = "TEST_TOKEN_NOT_A_SECRET_123"
path = Path(os.environ["COUNCIL_WORKSPACE_ROOT"]) / ".council/audit/man-12.jsonl"
AuditLogger(path, session_id="MAN-12").record(
    "probe",
    {"api_key": marker},
    success=True,
)
event = json.loads(path.read_text().splitlines()[0])
print("marker_exposed:", marker in path.read_text())
print("integrity_fields:", sorted(set(event) & {"sequence", "previous_hash", "hash"}))
PY
```

**安全期望**：秘密被遮罩，事件具可驗證 chain／sequence。

**v0.9.0 實際預期**：`marker_exposed=True` 且 integrity fields 為空；案例為 `FAIL`（V1-005）。現行 audit 只有長度截斷，不是 secret redaction，也沒有 hash chain。

## MAN-13 — `run_tests` Shell 語意邊界

**目的**：確認含空白的合法測試路徑與 metacharacter 不會因字串重組改變語意。

**操作**：

```bash
mkdir -p "$COUNCIL_WORKSPACE_ROOT/tests with spaces"
printf 'def test_ok():\n    assert True\n' \
  > "$COUNCIL_WORKSPACE_ROOT/tests with spaces/test_ok.py"
uv run python - <<'PY'
from pathlib import Path
from council_agent.security import ConfirmMode, confirmation_policy
from council_agent.tools.shell import run_tests

with confirmation_policy(ConfirmMode.AUTO):
    print("positive:", run_tests("tests with spaces"))
    print("injection:", run_tests("tests with spaces", args="-q; touch marker"))
print("marker_exists:", Path("marker").exists())
PY
```

**安全期望**：合法空白路徑可執行且只執行指定 pytest action；引號、redirect、pipeline、substitution 與額外命令一律拒絕且無副作用。

**v0.9.0 實際預期**：路徑經空白拼接後語意漂移，測試失敗；案例為 `FAIL`（V1-002）。不要把 shell metacharacter payload 放入共享或非隔離環境。

**v0.9.1 implementation 預期**：positive pytest action exit 0；injection 回 `shell_metachar`、無 `exit_code`，`marker_exists=False`。`AUTO` 只供此一次性 smoke 避免互動，不代表 Trust Tier 或持久授權。

## 完成與清理

1. 確認 outside sentinel 的 SHA-256 與初始值一致；MAN-09 的專用 probe 除外，且必須已移除。
2. 以 `PASS／FAIL／BLOCKED／NOT-RUN` 填滿所有案例，不得省略預期失敗。
3. 依 [`issue-report-template.md`](issue-report-template.md) 回報新問題；P0 私下通報。
4. 撤銷一次性 credential，遮罩證據，最後丟棄整個測試環境。
