# 代码审查模式配置指南

## 🔍 概述

系统支持3种清晰的代码审查模式，通过 `REVIEW_MODE` 配置项进行控制：

## ⚙️ 三种模式

### 模式一：只有MR总结（summary_only）

```python
# config/config.py
REVIEW_MODE = "summary_only"
```

**特点**：
- ✅ 生成一个MR总结评论
- ✅ MR总结包含详细的文件审查内容
- ✅ 简洁高效，适合大多数场景

**输出**：
- 1个MR评论：包含整体概览 + 每个文件的详细审查

### 模式二：MR总结 + Commit审查（summary_and_commit）

```python
# config/config.py
REVIEW_MODE = "summary_and_commit"
```

**特点**：
- ✅ 生成一个MR总结评论（只包含概览）
- ✅ 每个commit生成一个详细审查评论
- ✅ 最全面的代码质量评估

**输出**：
- 1个MR评论：整体概览
- N个commit评论：每个commit的详细审查

### 模式三：只有Commit审查（commit_only）

```python
# config/config.py
REVIEW_MODE = "commit_only"
```

**特点**：
- ✅ 不生成MR总结
- ✅ 每个commit生成一个详细审查评论
- ✅ 适合需要详细commit级别追踪的项目

**输出**：
- N个commit评论：每个commit的详细审查

## 🛠️ 推荐配置

基于您当前的需求，推荐使用**模式二（MR总结 + Commit审查）**：

```python
# config/config.py

# 代码审查模式配置
REVIEW_MODE = "summary_and_commit"  # 当前模式：summary_only / summary_and_commit / commit_only

# Commit审查设置（仅在REVIEW_MODE包含commit时生效）
MAX_FILES_PER_COMMIT = 20         # 每个commit审查的最大文件数限制
COMMIT_REVIEW_MODE = "simple"     # Per-commit审查模式

# 增强版commit审查功能
ENABLE_ENHANCED_COMMIT_REVIEW = True  # 启用增强版commit审查
MAX_ESTIMATED_TOKENS = 50000      # 触发分批处理的预估token阈值
BATCH_SIZE_FOR_COMMIT_REVIEW = 5  # 分批处理时每批的文件数量
INCOMPLETE_RESPONSE_THRESHOLD = 0.5  # 占位符缺失超过此比例时触发降级处理

# 其他功能开关
ENABLE_INLINE_COMMENTS = False    # 根据需要开启
SHOW_FILE_LIST_TITLE = False      # 保持简洁
REVIEW_SECTION_TITLE = ""         # 保持简洁
```

## 📊 模式对比

| 模式 | 配置值 | MR总结 | Commit审查 | 评论数量 | 适用场景 |
|------|--------|--------|------------|----------|----------|
| 模式一 | `summary_only` | ✅ 详细 | ❌ | 1个 | 简洁需求 |
| 模式二 | `summary_and_commit` | ✅ 概览 | ✅ 详细 | 1+N个 | **推荐** |
| 模式三 | `commit_only` | ❌ | ✅ 详细 | N个 | 特殊需求 |

## 🔧 故障排除

### 问题1：重复审查
**原因**：配置了错误的REVIEW_MODE值
**解决**：确保REVIEW_MODE设置为以下三个值之一：
- `"summary_only"` - 只有MR总结
- `"summary_and_commit"` - MR总结 + commit审查
- `"commit_only"` - 只有commit审查

### 问题2：MR总结消失
**原因**：REVIEW_MODE设置为`"commit_only"`
**解决**：如果需要MR总结，请设置为`"summary_only"`或`"summary_and_commit"`

### 问题3：Commit审查不工作
**原因**：REVIEW_MODE设置为`"summary_only"`
**解决**：如果需要commit审查，请设置为`"summary_and_commit"`或`"commit_only"`

## 📝 日志检查

检查日志中的关键信息：
```
📝 当前审查模式: summary_and_commit  # 确认模式设置正确
📝 模式2：MR总结 + commit审查，MR总结只包含概览  # 确认MR总结逻辑
📝 当前模式为 summary_and_commit，开始commit审查  # 确认commit审查逻辑
```

## 🎯 最佳实践

1. **生产环境**：推荐使用方案一，保持评论整洁
2. **开发环境**：可以尝试方案二，获得更详细的审查信息
3. **大型项目**：考虑方案三，但需要仔细调优
4. **定期检查**：监控token使用量和审查质量 