# 跨机协作协议（火枭 × LocalDouyin / 105 × 107）

> 本目录是两台电脑（105 = 本机/安卓Hook项目，107 = TOPAZ/LocalDouyin项目）
> 通过 Syncthing 共享同一份 F:\D 后的**协作中枢**。
> 规则很简单：**每个文件只有一个写者，交接靠"状态文件"接力。**

---

## 一、角色与地盘（谁写什么）

| 文件/目录 | 写者 | 读者 |
|---|---|---|
| `F:\D\Android-Hook\服务\*`（火枭代码） | 105 豆包项目（安卓Hook） | 107 只读 |
| `F:\D\Android-Hook\LocalDouyin\local-douyin\app\*.py`（LocalDouyin 代码） | **105 开发、107 运行** | 107 豆包项目负责部署重启 |
| `LocalDouyin\local-douyin\data\videos.db`（LocalDouyin 数据库） | **仅 107 运行态写** | 105 只读观察 |
| `输出数据\*`（采集资产） | 105（火枭/安卓Hook 项目） | 107 只读 |
| `验收网站\*`（验收页） | 105 | 107 只读 |
| `跨机协作\handoffs\*`（交接队列） | 双方轮流写 | 双方读 |

**铁律：同一个文件同一时刻只有一个写者。** Syncthing 冲突文件（`xxx.sync-conflict-*`）
出现 = 有人违反铁律，立即协商由谁接管。

## 二、交接怎么走（接力，不并行）

1. 105 侧（我）完成一段工作 → 在 `handoffs\` 写一个任务文件（见模板）→ 状态 `pending`
2. Syncthing 自动同步到 107
3. 你在 107 的豆包项目里说"继续推 LocalDouyin" → 107 智能体读 `handoffs\` 找 `pending`
4. 107 执行完 → 把状态改成 `done`，写完成说明 → 同步回来
5. 105 侧（我）看到 `done` → 继续下一段

```
handoffs/
  ├── 2026-09-19-001-部署对接桥.md   (status: done ← 107改的)
  ├── 2026-09-19-002-调参联调.md     (status: pending ← 105写的)
  └── README.md                      (模板，见下)
```

任务文件模板：

```markdown
---
status: pending        # pending / in_progress / done / blocked
owner: 105             # 谁写进来的
doer: 107              # 该谁做
created: 2026-09-19
---

# 任务标题

## 背景（为什么）
## 要做什么（1、2、3 可执行步骤）
## 验收标准（怎么算完成）
## 完成记录（doer 填写：结果/证据/遗留）
```

## 三、当前交接队列

见 `107侧待办.md`（105 已写好，107 照做）。

## 四、Syncthing 配置建议（重要）

同步整个 F:\D 没问题，但以下**建议排除**，否则会慢、会冲突、会坏：

| 排除路径 | 原因 |
|---|---|
| `**/.venv/**`、`**/venv/**`、`**/__pycache__/**`、`*.pyc` | 虚拟环境跨机不可用/垃圾文件；107 用自己环境或重建 |
| `LocalDouyin/local-douyin/data/videos/*.mp4` | 大文件持续增长（219MB+），且是 107 运行时产物，没必要回传 |
| `**/node_modules/**` | 同上，重建即可 |
| `服务/*.log`、`LocalDouyin/logs/*.log` | 运行日志高频变动，排除减少同步抖动 |
| `**/.git/**`（如有） | git 对象不适合经 Syncthing |

**如果 107 的 F 盘路径与 105 完全一致**（都是 `F:\D\Android-Hook\...`），
105 现有的 venv 同步过去后**可能直接能用**（Windows venv 大多数按相对路径激活）；
不行就在 107 上 `python -m venv venv` 重建再装 requirements。

## 五、双写约定（防数据库冲突）

- `videos.db`（LocalDouyin 库）：**只在 107 运行态写**；105 若要灌数据，**走 HTTP**
  （`POST http://192.168.0.107:8000/api/crawl/import`），绝不直接改文件。
- `huoxiao_cache.db`（火枭库）：**只在 105 写**；107 不碰。
- 两边服务端口互不冲突：105=火枭 8100，107=LocalDouyin 8000。
