# api 接口封装类

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

llm_api_impl = "large_model.api.default_api.DefaultApi"

# DeepSeek配置示例
# api 配置方式参考 docs/config.md
# 默认使用认UnionLLM，参考：https://github.com/EvalsOne/UnionLLM/tree/main/docs
# UnionLLM兼容LiteLLM，参考LiteLLM文档：https://docs.litellm.ai/docs

# 当前的 DeepSeek 配置
# api_config = {
#     "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
#     "model": 'deepseek-chat',
#     "provider": "deepseek",
# }

# 改为 Gemini 配置
api_config = {
    "api_key": os.getenv("GEMINI_API_KEY", ""),  # 或直接写入 "your-gemini-api-key"
    "model": 'gemini-1.5-pro',  # 或其他 Gemini 模型
    "provider": "gemini",
    "temperature": 0.7,  # 可选参数
    "max_tokens": 8192,  # 增加输出token限制以支持多文件commit审查
    "set_verbose": True,  # 启用详细日志用于调试
}

# demo-proxy-gpt
# api_config = {
#     "api_key": "your openai key",
#     "api_base": "https://api.openai.com/v1",
#     "model": "gpt_4o",
#     "provider": "openai",
# }

# demo-ollama 
# api_config = {
#     "api_base": "http://localhost:11434",
#     "model": "llama3.2",
#     "provider": "ollama",
# }

# demo-azure
# api_config = {
#     "AZURE_API_KEY": "*",
#     "AZURE_API_BASE": "https://*.openai.azure.com",
#     "AZURE_API_VERSION": "2024-10-21",
#     "model": "azure/o1-mini",
# }

# 旧的prompt配置已移动到 review_engine/review_prompt.py 文件中


# ------------------Gitlab info--------------------------
# Gitlab url
GITLAB_SERVER_URL = os.getenv("GITLAB_SERVER_URL", "https://gitlab.com")

# Gitlab private token
GITLAB_PRIVATE_TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN", "")

# Gitlab modifies the maximum number of files
MAX_FILES = 50

# ------------- 应用程序行为配置 --------------------

# 代码审查模式配置 - 重要说明：
# 
# 如果您的MR中有N个commit，各模式的行为如下：
# 
# 1. "summary_only" - 生成1个MR总结评论（包含所有文件的详细审查）
#    适合：希望只有一个评论的场景
# 
# 2. "summary_and_commit" - 生成1个MR总结 + N个commit评论
#    注意：如果有4个commit，会产生1+4=5个评论！
#    适合：需要详细commit级别审查的场景
# 
# 3. "commit_only" - 生成N个commit评论（不生成MR总结）
#    注意：如果有4个commit，会产生4个commit评论！
#    适合：只关注单个commit审查的场景
#
# 支持3种模式：
# "summary_only" - 只有MR总结（包含详细文件审查）
# "summary_and_commit" - MR总结 + 每个commit的详细审查
# "commit_only" - 只有每个commit的详细审查，不生成MR总结
REVIEW_MODE = "summary_and_commit" 

# 重复控制设置
ENABLE_DUPLICATE_CHECK = True     # 是否启用重复评论检查（避免重复发送相同内容）
SIMILARITY_THRESHOLD = 0.8        # 评论相似度阈值（0.0-1.0，数值越高要求越严格）

# MR审查触发控制
REVIEW_ONLY_ON_FIRST_OPEN = False # 是否只在MR首次打开时审查（避免多次触发,保持False即可）
REVIEW_ON_UPDATE = True           # 是否在MR更新时重新审查（仅在 REVIEW_ONLY_ON_FIRST_OPEN=false 时生效）

# Commit审查设置
MAX_FILES_PER_COMMIT = 20         # 每个commit审查的最大文件数限制
COMMIT_REVIEW_MODE = "simple"     # Per-commit审查模式：simple（简化模式）或 detailed（详细模式）

# 增强版commit审查功能
ENABLE_ENHANCED_COMMIT_REVIEW = True  # 启用增强版commit审查（防止失误功能）
# 增强版commit审查功能说明：
# - 智能token长度预检查，防止超出LLM上下文限制
# - 占位符替换失败时的自动回退机制
# - 当内容过多时自动采用分批处理策略
# - 响应格式验证和错误恢复机制
# - 渐进式降级处理，确保始终有可用的审查结果
# 建议在生产环境中启用此功能以提高稳定性

# 增强版commit审查的调优参数
MAX_ESTIMATED_TOKENS = 50000      # 触发分批处理的预估token阈值
BATCH_SIZE_FOR_COMMIT_REVIEW = 5  # 分批处理时每批的文件数量
INCOMPLETE_RESPONSE_THRESHOLD = 0.5  # 占位符缺失超过此比例时触发降级处理（0.5表示50%）

# 其他功能开关
ENABLE_INLINE_COMMENTS = False   # 是否启用inline评论功能（每个diff块生成单独评论, 源码功能，如果大量文件变更，会导致一堆评论）
SHOW_FILE_LIST_TITLE = False     # 是否在总结评论中显示"修改文件列表"标题
REVIEW_SECTION_TITLE = ""        # 自定义审查部分的标题，设为空字符串则不显示标题

# ------------- Message notification --------------------
# dingding notification （un necessary）
DINGDING_BOT_WEBHOOK = ""  # 设为空字符串禁用钉钉通知
DINGDING_SECRET = ""       # 设为空字符串禁用钉钉通知

# ------------- code review settings --------------------
# 支持审查的文件类型
SUPPORTED_FILE_TYPES = ['.py', '.class', '.vue', ".go", ".c", ".cpp", ".dart"]

# 忽略审查的文件类型
IGNORE_FILE_TYPES = ["mod.go"]

# context code lines 上下文关联代码行数
CONTEXT_LINES_NUM = 5

# 增强版上下文分析配置（仅在 COMMIT_REVIEW_MODE = "detailed" 时生效）
ENHANCED_CONTEXT_ANALYSIS = True    # 启用增强版上下文分析
CONTEXT_ANALYSIS_MODE = "smart"     # 上下文分析模式：basic（基础行数）、smart（智能边界）、full（完整函数/类）

# 智能上下文配置
SMART_CONTEXT_MAX_LINES = 20        # 智能模式下的最大上下文行数
FUNCTION_CONTEXT_ENABLED = True     # 启用函数级别上下文分析
CLASS_CONTEXT_ENABLED = True       # 启用类级别上下文分析
IMPORTS_CONTEXT_ENABLED = True     # 启用导入语句上下文分析

# 上下文分析增强功能
CONTEXT_SEMANTIC_ANALYSIS = True   # 启用上下文语义分析（分析变更对周围代码的影响）
CONTEXT_DEPENDENCY_ANALYSIS = True # 启用上下文依赖分析（分析变更涉及的变量、函数依赖关系）
CONTEXT_IMPACT_ANALYSIS = True     # 启用上下文影响分析（分析变更可能的连锁影响）

# 内容长度限制设置
MAX_CONTENT_LENGTH = 500000  # 最大内容长度（字符数）
MAX_DIFF_LENGTH = 100000     # 最大diff长度（字符数）
MAX_SOURCE_LENGTH = 200000   # 最大源代码长度（字符数）

# Validate required environment variables
if not GITLAB_PRIVATE_TOKEN:
    raise ValueError("GITLAB_PRIVATE_TOKEN environment variable is required")

if not api_config["api_key"]:
    raise ValueError("GEMINI_API_KEY environment variable is required")
