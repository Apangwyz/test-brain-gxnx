# 需求文档深度分析功能 — 测试报告（v2 采纳工作流）

> **日期**: 2026-06-12
> **测试环境**: Python 3.10, Django 5.1, SQLite (内存数据库)
> **测试框架**: Django TestCase + unittest.mock
> **测试总数**: **60** | **通过**: **60** | **失败**: 0 | **错误**: 0
> **对比 v1**: 新增 12 个测试（采纳功能 12 个）

---

## 一、测试范围总览

| 测试分类 | 覆盖层级 | 测试数 | 说明 |
|---------|---------|:------:|------|
| 白盒测试 — 模型层 | 单元测试 | 5 | RequirementAnalysis 模型 CRUD、默认值、排序 |
| 白盒测试 — 采纳状态模型 | 单元测试 | 4 | adoption_status 默认值、采纳/拒绝状态变更、选项完整性 |
| 白盒测试 — Prompt 层 | 单元测试 | 4 | YAML 加载、6 种 prompt 生成、缓存机制 |
| 白盒测试 — 编排器 | 单元测试 | 8 | hash 计算、缓存命中/未命中、策略计算、异常安全 |
| 白盒测试 — 分析 Agent | 单元测试 | 6 | 6 个 Agent 各 1 个基础测试（mock LLM） |
| 白盒测试 — 文件解析 | 单元测试 | 3 | 路由分发、mock 集成 |
| 白盒测试 — 生成策略联动 | 单元测试 | 5 | 策略字段完整性、权重计算、焦点区域映射 |
| 黑盒测试 — Views API | 接口测试 | 13 | 页面加载、上传/分析/结果/生成 API |
| 黑盒测试 — 采纳/拒绝 API | 接口测试 | 8 | 采纳/拒绝成功、重复操作拦截、不存在的记录、已采纳列表、md上传 |
| 黑盒测试 — 未认证访问 | 安全测试 | 4 | 页面重定向、API 鉴权拦截 |

---

## 二、新增测试详情（v2 采纳工作流）

### 2.1 采纳状态模型 — AdoptionModelTest

| 测试用例 | 测试场景 | 结果 |
|---------|---------|:----:|
| `test_default_adoption_status` | 新创建的分析记录默认 adoption_status = "pending" | ✅ |
| `test_adopt_document` | 标记为 adopted，验证审核人和审核时间写入 | ✅ |
| `test_reject_document` | 标记为 rejected，验证状态正确 | ✅ |
| `test_adoption_status_choices` | ADOPTION_CHOICES 包含 pending/adopted/rejected 三项 | ✅ |

### 2.2 采纳/拒绝 API — AdoptionAPITest

| 测试用例 | 测试场景 | 结果 |
|---------|---------|:----:|
| `test_adopt_success` | POST /api/<id>/adopt/ → success + 状态改为 adopted | ✅ |
| `test_reject_success` | POST /api/<id>/reject/ → success + 状态改为 rejected | ✅ |
| `test_duplicate_adopt` | 已采纳再次调用 → false + "无法重复操作" | ✅ |
| `test_duplicate_reject` | 已拒绝再次调用 → false + 错误提示 | ✅ |
| `test_adopt_nonexistent` | 采纳不存在的 analysis_id=99999 → false | ✅ |
| `test_adopted_docs_api` | GET /api/adopted-docs/ → 只返回 adopted 状态的文档 | ✅ |
| `test_adopted_docs_excludes_rejected` | 已采纳列表不应包含已拒绝文档 | ✅ |
| `test_markdown_upload_success` | 上传 .md 文件 → success + file_type=".md" | ✅ |

---

## 三、已知问题

| 问题 | 影响 | 说明 |
|------|:----:|------|
| Milvus 未运行，`adopt` 时知识库入库失败 | 低 | 代码有 try/except 兜底，日志警告但不影响采纳操作 |
| 采纳 API 中的知识库添加依赖外部 Milvus 服务 | 低 | 生产环境部署 Milvus 后自动生效 |

---

## 四、全量测试结果

```
Ran 60 tests in 2.016s
OK
```

---

## 对应文件

| 测试报告 | 对应实现计划 |
|---------|-------------|
| `docs/test_reports/2026-06-12-requirement-analysis-adoption-test-report.md` | 本次需求分析功能改进（MD 支持 + 采纳工作流 + TCG 改造） |
| 实现计划 | —（用户直接指定的需求，无独立计划文档） |
