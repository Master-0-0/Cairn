# Cairn 文件上传完整流程

## 一、启动 Cairn

启动后两个容器运行：`cairn-server`（Web UI `:8000`）和 `cairn-dispatcher`（调度器）

## 二、启动文件上传服务

## 三、创建审计项目

1. 浏览器打开 `http://:8000` → Cairn Web UI
2. 创建新项目，填写：
   - **Origin**：代码在容器内的路径，如：代码位于 `/home/src/`
   - **Goal**：审计目标，如：审计该项目的安全漏洞，查找 SQL 注入、XSS、命令注入等问题
   - **Hints**：可选额外指导
3. 创建后**立即暂停**项目（点 Stop）

## 四、上传代码

1. 浏览器打开 `http://:9000` → 上传页面
2. 输入**项目 ID**（如 `proj_029`）
3. 拖拽/选择代码文件（目录先 `tar -czf code.tar.gz dir/` 打包）
4. 上传 → 自动 `docker cp` 到 `cairn-dispatch-proj_029:/home/`

## 五、开始审计

回到 Cairn Web UI（`:8000`），将项目恢复为 Active，Dispatcher 自动调度 Worker 开始审计。

---

## 架构速览

```
浏览器 :9000       浏览器 :8000
 上传文件          创建/管理项目
    │                  │
    ▼                  ▼
upload_server.py    cairn-server (docker)
    │                  │
    │ docker cp        │ API 读写
    ▼                  ▼
cairn-dispatch-proj_XXX  ←──  cairn-dispatcher (docker)
  (项目容器)                   调度 Worker 执行 LLM
    │
    ▼
Worker (Claude Code / Codex)
  读取 /home/ 下代码，开始审计
```