# 🔐 项目安全规范

> 防止敏感信息（API key、token、password 等）泄露到 git / GitHub。

## 🚨 现状

2026-06-29 之前曾因硬编码 `DASHSCOPE_API_KEY` 造成泄露，事后：

- ✅ 在阿里云百炼控制台 **rotate** 了原 key
- ✅ 用 `git filter-repo` 重写历史
- ✅ force-push 到 `origin/main`（旧 commit `70b103d` → 新 hash `e62aa02`）
- ✅ 代码改为从 `backend/.env` 读取（**绝不再硬编码**）

> ⚠️ **重要**：仅 rotate key 就能避免被盗用。如果要彻底抹除 GitHub 历史中的旧 key（公开仓库尤其建议），需要用 [git-filter-repo](https://github.com/newren/git-filter-repo) 或 [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)。

---

## 🛡️ 纵深防御（已部署）

本项目用 **3 道防线** 防止再犯：

### 1️⃣ 仓库根 `.gitignore`（基础防线）

`backend/.env`、所有 `data/`、编译产物、IDE 临时文件**一律不进入 git**。
任何想 `git add` 进去的操作都会被 git 拒绝。

### 2️⃣ Pre-commit Hook（本地拦截）

每次 `git commit` 前，自动跑 [gitleaks](https://github.com/gitleaks/gitleaks) 扫描 staged 改动。

- 配置文件：`.gitleaks.toml`
- Hook 脚本：`.githooks/pre-commit`
- Hook 路径已通过 `git config core.hooksPath .githooks` 配置

**触发示例**：

```bash
$ echo 'api_key="sk-aabbccddeeff00112233445566778899"' > test.txt
$ git add test.txt && git commit -m "test"

[pre-commit] Scanning staged changes for secrets (gitleaks)...
11:45AM INF 0 commits scanned.
11:45AM WRN leaks found: 2

[pre-commit] ✗ Secret(s) detected in staged changes!
                Commit blocked to prevent leaking credentials.

  If this is a false positive, you can either:
    1. Add the finding to .gitleaks.toml [allowlist] rules
    2. Bypass with:  git commit --no-verify  (use only if you're sure)
```

**绕过（不推荐）**：`git commit --no-verify`

### 3️⃣ GitHub Actions（CI 二次防御）

`.github/workflows/secret-scan.yml` 在以下时机自动跑 gitleaks：

| 触发时机 | 范围 |
|---|---|
| `push` 到 `main` | 全仓库 |
| `pull_request` | 增量（仅 PR 新增 commit）|
| 每日 06:00 UTC | 全仓库（捕获 force-push 后可能的漏网之鱼）|
| 手动触发 | 走 Actions tab → Run workflow |

匹配到的 secret 会：
1. ❌ **阻断 CI 流水线**（PR 无法 merge）
2. 📤 上传 SARIF 到 GitHub Security tab
3. 📨 在 PR 评论里显示（key 已 redact）

---

## 🛠️ 工具安装

### 一次性安装 gitleaks

**Windows (PowerShell)**：

```powershell
# 下载最新 release
$toolsDir = "$env:USERPROFILE\tools"
New-Item -ItemType Directory -Path $toolsDir -Force | Out-Null
Invoke-WebRequest -Uri "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_windows_x64.zip" `
  -OutFile "$toolsDir\gitleaks.zip"
Expand-Archive "$toolsDir\gitleaks.zip" "$toolsDir" -Force
Remove-Item "$toolsDir\gitleaks.zip"

# 添加到 PATH（PowerShell 永久）
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$toolsDir", "User")
```

**macOS**：

```bash
brew install gitleaks
```

**Linux**：

```bash
# 见 https://github.com/gitleaks/gitleaks/releases
wget https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
tar -xzf gitleaks_8.30.1_linux_x64.tar.gz
sudo mv gitleaks /usr/local/bin/
```

### 启用项目 pre-commit hook

Clone 仓库后跑一次：

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit   # macOS / Linux
```

Windows 下 `git config core.hooksPath` 后 git 自动识别文件可执行位（无需 chmod）。

---

## 🧪 手动扫描

```bash
# 扫全仓库历史
gitleaks detect --source . --config .gitleaks.toml --redact --verbose

# 只扫工作区（未 commit 的改动）
gitleaks detect --no-git --source . --config .gitleaks.toml --redact

# 只扫 staged（pre-commit 用法）
gitleaks protect --staged --config .gitleaks.toml --redact
```

---

## ✏️ 添加新的 Secret 规则

如果项目接入新 provider（例如 OpenAI、Anthropic），编辑 `.gitleaks.toml`：

```toml
[[rules]]
id = "openai-api-key"
description = "OpenAI API key"
regex = '''\bsk-[A-Za-z0-9_-]{20,}\b'''
keywords = ["openai", "api_key"]
tags = ["secret", "openai"]

  [rules.allowlist]
  regexes = ['''\bsk-(xxxx|placeholder)\b''']
```

RE2 引擎**不支持** `(?=...)` / `(?!...)` 等 lookahead，需要允许列表时改用 `[rules.allowlist]`。

---

## 📋 误报处理

如果 gitleaks 误报（例如测试 fixture 里的假 key）：

**方案 A**：在 `.gitleaks.toml` 的 `[allowlist]` 或具体规则的 `[rules.allowlist]` 加 regex：

```toml
[allowlist]
regexes = [
  '''backend/tests/fixtures/.*\.txt$''',
]
```

**方案 B**：用 `gitleaks:allow` 注释：

```python
api_key = "sk-aabbccddeeff00112233445566778899"  # gitleaks:allow
```

---

## 🔄 已泄露 Key 的处理流程

如果发现 secret 已经推送到 `origin/main`：

1. **立刻**到 provider 控制台 **rotate**（删除/禁用）该 key
2. 在 `backend/.env` 写入新 key
3. 在新 commit 中**只引用**新 key（参考 `backend/test_qwen3.py` 的做法）
4. 用 `git filter-repo` 清理历史（见 `docs/INCIDENT-2026-06-29-LEAK.md` 如果有）
5. `git push --force origin main`
6. 通知所有 fork / 协作者

---

## 📚 参考

- [gitleaks 官方文档](https://github.com/gitleaks/gitleaks)
- [git-secrets（备选方案）](https://github.com/awslabs/git-secrets)
- [GitHub: 移除敏感数据](https://docs.github.com/zh/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [OWASP: Secret Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
