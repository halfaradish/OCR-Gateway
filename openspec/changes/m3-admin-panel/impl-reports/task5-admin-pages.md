---
ticket: 5
title: 管理页面
head: e6dc1df6b9107f227b6e9e2b5d124b6553967ded
status: DONE
suite_scope: {"domains":["frontend","backend"],"layers":["lint","typecheck","build","e2e"],"base":"e6dc1df","mode":"ticket"}
---

# Task 5 · 管理页面

## 改动

- **账号页**（`src/pages/accounts-page.tsx`）：列表（厂商/名称/贡献者/优先级/配额标尺/状态/EWMA/最近错误/操作）、
  厂商与状态过滤进 URL、新建/编辑对话框（按厂商渲染凭证字段；编辑时凭证留空不修改、超时留空省略字段不提交
  `null`）、测活对话框（成功显示文本、失败显示错误码与说明）、重置确认（写明清零配额）、启停、删除确认、
  三项配额全空显示「未配置额度，可能超用」；写操作 `scope` 串行 + pending 禁用。
- **成员与 Key 页**（`members-page.tsx`）：成员表（名称/启用开关/Key 数/操作）、`member` 选择进 URL、
  创建成员、删除成员提示级联吊销 Key 数；Key 表（前缀/名称/日限额/RPM/最近使用/启用/吊销）、创建 Key
  （默认日限额 100、RPM 30、「不限」开关提交 `null`）、明文一次性对话框（复制按钮 + 关闭后不可再查看）。
- **用量页**（`usage-page.tsx`）：时间/成员/厂商/账号/指标/分组全部进 URL；筛选变化 `placeholderData:
  keepPreviousData` 保留上一结果；指标切换（请求数/成功率/平均延迟）、分组切换（厂商/成员/账号）、折线图、
  汇总表、CSV 导出（UTF-8 BOM + CRLF + RFC 4180 转义 + 公式注入前缀）；非法时间范围显示横幅并保留上一次结果。
- **日志页**（`logs-page.tsx`）：时间/状态/厂商/错误码过滤与分页进 URL；Total 与分页控件；详情对话框只展示
  元数据（request_id、用户、账号、耗时、配额、缓存、图片指纹）；UTC 时间按 Asia/Shanghai 展示。
- **设置页**（`settings-page.tsx`）：可编辑区（缓存开关/TTL/容量、请求总预算、账号默认超时）与只读区
  （鉴权、版本、上传上限、像素、并发、会话时长、面板产物）；字段级校验 + 后端 `error.fields` 回填；保存后
  提示「设置已保存」，缓存参数变化追加「缓存已清空」；清空缓存显示条数；配额模板与免责声明；脏表单
  `useBlocker` + `beforeunload` 双重离开确认。
- **横切**：写操作 pending 禁用与 `scope` 串行（双击只发一次请求）；GET 仅对网络/5xx 重试一次（`lib/query.ts`）；
  所有页面三态齐备；`App` 改为 `createBrowserRouter`（`useBlocker` 需要 data router）。
- **体积处理**：登录页改为受控单字段表单，不再引入 react-hook-form/zod（登录首屏 gzip 从 165.3 kB 降到
  ~126 kB，回到 150 kB 预算内）；管理页仍使用 RHF + zod。

## 验证

| 层 | 命令原文 | 退出码 | 用例数 | SHA |
|---|---|---|---|---|
| frontend lint | `pnpm --dir frontend lint` | 0 | 未知 | e6dc1df |
| frontend typecheck | `pnpm --dir frontend typecheck` | 0 | 未知 | e6dc1df |
| frontend build | `pnpm --dir frontend build` | 0 | 未知 | e6dc1df |
| e2e 鉴权/骨架 | `E2E_BASE_URL=http://127.0.0.1:8765 pnpm --dir frontend exec node e2e/smoke.mjs` | 0 | 14 checks | e6dc1df |
| e2e 管理页 | `E2E_BASE_URL=http://127.0.0.1:8765 pnpm --dir frontend exec node e2e/admin.mjs` | 0 | 32 checks | e6dc1df |
| 后端全量 | `uv run --project backend pytest backend/tests -q` | 1 | 213 passed, 1 failed（既有红测）, 2 skipped, 1 deselected | e6dc1df |

e2e 管理页覆盖：新建/编辑账号（凭证留空保持、超时留空保持 8000）、未配置额度提示、测活失败展示错误码、
重置确认含清零说明、厂商过滤、删除账号；创建成员与 Key（明文仅一次、列表只有前缀）、删除成员提示级联；
用量筛选进 URL、分组切换、CSV（BOM/CRLF/表头）；日志状态过滤、详情元数据、下一页分页；设置保存 +
缓存清空提示 + 双击只发一次 PUT + 刷新后保持 + 非法值字段错误 + 清空缓存条数 + 脏表单离开确认；
全流程无 CSP 违规、控制台无意外错误。截图见 `review/e2e-task5/`。

体积（gzip）：

| 产物 | gzip |
|---|---|
| 登录 + 壳（`index` + `login-page` + `label`） | 124.06 + 1.08 + ~0.5 ≈ **125.6 kB**（预算 ≤150） |
| 总览路由增量（Recharts + 页面 + 组件） | 105.96 + 2.80 + 3.53 + 0.9 ≈ **113.2 kB**（预算 ≤350） |
| zod + RHF（仅管理页按需加载） | 40.27 kB |

## concerns

- **登录页不用 RHF/zod**：为满足首屏 150 kB 预算，单字段登录表单改为受控组件 + 本地错误状态。这是对
  「表单统一 RHF + zod」的局部偏离，管理页表单仍全部使用 RHF + zod。
- **测活失败的错误码来源**：e2e 环境无真实厂商凭证/网络，测活返回网络类失败；错误码展示路径与真实
  失败一致（`ok=false` + `error_code` + `message`），不写事件、不扣配额由后端保证。
- **CSV 只在浏览器侧验证**：e2e 捕获 `URL.createObjectURL` 的 Blob，校验 BOM 字节、CRLF 与表头；单元格级
  RFC 4180 转义与公式前缀由 `lib/csv.ts` 实现，未单测（项目未引入前端单测框架）。
- **e2e 数据**：脚本自建自删账号/成员/Key；运行前需要一个可登录的实例（本票用 8765 端口的临时数据目录）。
- **`createBrowserRouter`**：路由从 `<BrowserRouter>` 改为 data router，以支持 `useBlocker` 的离开确认；
  其余行为不变（深链接、404、懒加载、错误边界均已 e2e 覆盖）。
