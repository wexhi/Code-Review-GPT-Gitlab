import concurrent.futures
import threading
from retrying import retry

from config.config import (
    GPT_MESSAGE, 
    MAX_FILES_PER_COMMIT, 
    SUPPORTED_FILE_TYPES, 
    IGNORE_FILE_TYPES,
    MAX_CONTENT_LENGTH, 
    MAX_DIFF_LENGTH, 
    MAX_SOURCE_LENGTH,
    COMMIT_REVIEW_MODE
)
from review_engine.abstract_handler import ReviewHandle
from utils.gitlab_parser import (
    filter_diff_content, 
    add_context_to_diff, 
    extract_diffs,
    get_comment_request_json, 
    extract_comment_end_line
)
from utils.logger import log
from utils.args_check import file_need_check
from utils.tools import batch


@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_commit_review_note(commit_info, commit_changes, model, gitlab_fetcher, merge_info):
    """为单个commit生成简化的审查意见（一次性分析所有文件变更）"""
    try:
        commit_id = commit_info['id'][:8]  # 取前8位作为短ID
        commit_message = commit_info['message']
        commit_author = commit_info['author_name']
        commit_date = commit_info['created_at']
        
        log.info(f"📝 开始审查commit: {commit_id} - {commit_message} (by {commit_author})")
        
        # 过滤需要审查的文件
        reviewable_changes = []
        for change in commit_changes:
            file_path = change.get('new_path') or change.get('old_path')
            if file_path and file_need_check(file_path):
                reviewable_changes.append(change)
        
        if not reviewable_changes:
            log.info(f"📝 Commit {commit_id} 没有需要审查的文件")
            return ""
        
        # 限制文件数量
        if len(reviewable_changes) > MAX_FILES_PER_COMMIT:
            log.warning(f"📝 Commit {commit_id} 文件数量过多，将只审查前 {MAX_FILES_PER_COMMIT} 个文件")
            reviewable_changes = reviewable_changes[:MAX_FILES_PER_COMMIT]
        
        # 收集所有文件的变更内容
        all_changes_content = []
        file_list = []
        
        for i, change in enumerate(reviewable_changes, 1):
            file_path = change.get('new_path') or change.get('old_path')
            file_list.append(file_path)
            
            # 获取diff内容
            diff_content = change.get('diff', '')
            if not diff_content:
                log.warning(f"⚠️ 文件 {file_path} 的diff内容为空")
                continue
            
            # 检查diff长度限制
            if len(diff_content) > MAX_DIFF_LENGTH:
                log.warning(f"⚠️ 文件 {file_path} 的diff内容过长，将被截断")
                diff_content = diff_content[:MAX_DIFF_LENGTH] + "\n\n... (内容过长，已截断)"
            
            # 添加文件标识和diff内容
            file_content = f"### 文件 {i}: {file_path}\n\n```diff\n{diff_content}\n```\n\n"
            all_changes_content.append(file_content)
        
        # 构建统一的提示词，一次性分析所有文件
        all_changes_text = "\n".join(all_changes_content)
        
        unified_prompt = f"""
请分析以下commit的所有文件变更，这是一个完整的commit审查。

**Commit信息**:
- ID: {commit_id}
- 提交信息: {commit_message}
- 作者: {commit_author}
- 变更文件数: {len(reviewable_changes)} 个

**所有文件变更**:
{all_changes_text}

请按以下格式提供审查意见：

1. **📋 Commit概述**: 简要总结这次commit的主要变更和目的

2. **📄 文件变更分析**: 对每个文件的变更进行简洁分析，请严格按照以下格式：

文件 1: 文件名

变更的主要内容:
[分析内容]

潜在的问题或风险:
[问题分析]

改进建议:
[改进建议]

[DIFF_PLACEHOLDER_FILE_1]

文件 2: 文件名

变更的主要内容:
[分析内容]

潜在的问题或风险:
[问题分析]

改进建议:
[改进建议]

[DIFF_PLACEHOLDER_FILE_2]

(以此类推...)

3. **🔍 整体评价**: 对整个commit的总体评价和建议

请保持分析简洁明了，重点关注代码质量和潜在问题。每个文件分析后都要包含对应的占位符[DIFF_PLACEHOLDER_FILE_X]，我会用实际的diff内容替换这些占位符。
"""
        
        messages = [
            {
                "role": "user",
                "content": unified_prompt,
            },
        ]
        
        # 一次性进行commit审查
        log.info(f"📝 开始LLM分析commit {commit_id}，包含 {len(reviewable_changes)} 个文件")
        model.generate_text(messages)
        content = model.get_respond_content()
        
        if not content:
            log.error(f"LLM返回内容为空 (commit review) for {commit_id}")
            # 如果LLM没有返回内容，生成基本的审查信息
            commit_review = f"## 🔍 Commit 审查: `{commit_id}`\n\n"
            commit_review += f"**📝 提交信息**: {commit_message}\n"
            commit_review += f"**👤 作者**: {commit_author}\n"
            commit_review += f"**🕒 时间**: {commit_date}\n"
            commit_review += f"**📊 变更文件**: {len(reviewable_changes)} 个\n\n"
            commit_review += "**📄 变更文件列表**:\n"
            for i, file_path in enumerate(file_list, 1):
                commit_review += f"{i}. `{file_path}`\n"
            commit_review += "\n⚠️ AI分析暂时不可用，请手动审查代码变更。\n\n"
        else:
            response_content = content.strip()
            total_tokens = model.get_respond_tokens()
            
            # 检查AI响应是否完整（包含所有必需的占位符）
            missing_placeholders = []
            for i in range(1, len(reviewable_changes) + 1):
                placeholder = f"[DIFF_PLACEHOLDER_FILE_{i}]"
                if placeholder not in response_content:
                    missing_placeholders.append(placeholder)
            
            if missing_placeholders:
                log.warning(f"⚠️ AI响应可能不完整，缺少占位符: {missing_placeholders}")
                log.warning(f"📏 AI响应长度: {len(response_content)} 字符")
                log.warning(f"🔚 AI响应结尾: ...{response_content[-200:]}")
                
                # 为缺失的占位符添加说明
                for placeholder in missing_placeholders:
                    file_index = int(placeholder.split('_')[-1].rstrip(']'))
                    file_path = file_list[file_index - 1] if file_index <= len(file_list) else "未知文件"
                    replacement = f"\n\n⚠️ **{file_path}** 的详细变更信息由于响应截断而无法显示。\n\n"
                    response_content += replacement
            else:
                log.info(f"✅ AI响应完整，包含所有 {len(reviewable_changes)} 个文件的占位符")
            
            # 替换占位符为实际的diff内容
            for i, change in enumerate(reviewable_changes, 1):
                file_path = change.get('new_path') or change.get('old_path')
                diff_content = change.get('diff', '')
                if diff_content:
                    if len(diff_content) > MAX_DIFF_LENGTH:
                        diff_content = diff_content[:MAX_DIFF_LENGTH] + "\n\n... (内容过长，已截断)"
                    
                    # 创建实际的diff展示内容
                    diff_display = f"\n<details><summary>📋 展开查看{file_path}详细变更</summary>\n\n"
                    diff_display += f"```diff\n{diff_content}\n```\n\n"
                    diff_display += "</details>\n\n"
                    
                    # 替换占位符
                    placeholder = f"[DIFF_PLACEHOLDER_FILE_{i}]"
                    if placeholder in response_content:
                        response_content = response_content.replace(placeholder, diff_display)
                        log.info(f"✅ 成功替换 {file_path} 的占位符")
                    else:
                        log.warning(f"⚠️ 未找到 {file_path} 的占位符，将在末尾添加")
                        response_content += f"\n\n### 文件 {i}: `{file_path}`\n\n"
                        response_content += diff_display
            
            # 构建完整的commit审查结果
            commit_review = f"## 🔍 Commit 审查: `{commit_id}`\n\n"
            commit_review += f"**📝 提交信息**: {commit_message}\n"
            commit_review += f"**👤 作者**: {commit_author}\n"
            commit_review += f"**🕒 时间**: {commit_date}\n"
            commit_review += f"**📊 变更文件**: {len(reviewable_changes)} 个\n\n"
            commit_review += "---\n\n"
            commit_review += f"**🤖 AI 审查结果** ({total_tokens} tokens):\n\n"
            commit_review += f"{response_content}\n\n"
            
            # 移除原来的文件详情展示部分，因为现在已经集成在AI分析中了
            # commit_review += "---\n\n"
            # 为每个文件添加单独的可折叠区域
            # for i, change in enumerate(reviewable_changes, 1):
            #     ...
            # 这部分代码已经移除，因为diff现在直接嵌入在AI分析中
        
        log.info(f'✅ Commit {commit_id} 审查完成')
        log.info(f'📝 Commit {commit_id} 审查结果长度: {len(commit_review)}')
        return commit_review
        
    except Exception as e:
        log.error(f"生成commit审查失败: {e}")
        return ""


@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_detailed_commit_review_note(commit_info, commit_changes, model, gitlab_fetcher, merge_info):
    """为单个commit生成详细的审查意见（每个文件单独调用LLM进行详细分析）"""
    try:
        commit_id = commit_info['id'][:8]  # 取前8位作为短ID
        commit_message = commit_info['message']
        commit_author = commit_info['author_name']
        commit_date = commit_info['created_at']
        
        log.info(f"📝 开始详细审查commit: {commit_id} - {commit_message} (by {commit_author})")
        
        # 过滤需要审查的文件
        reviewable_changes = []
        for change in commit_changes:
            file_path = change.get('new_path') or change.get('old_path')
            if file_path and file_need_check(file_path):
                reviewable_changes.append(change)
        
        if not reviewable_changes:
            log.info(f"📝 Commit {commit_id} 没有需要审查的文件")
            return ""
        
        # 限制文件数量
        if len(reviewable_changes) > MAX_FILES_PER_COMMIT:
            log.warning(f"📝 Commit {commit_id} 文件数量过多，将只审查前 {MAX_FILES_PER_COMMIT} 个文件")
            reviewable_changes = reviewable_changes[:MAX_FILES_PER_COMMIT]
        
        # 为每个文件单独进行详细分析
        file_reviews = []
        for i, change in enumerate(reviewable_changes, 1):
            file_path = change.get('new_path') or change.get('old_path')
            log.info(f"📝 详细分析文件 {i}/{len(reviewable_changes)}: {file_path}")
            
            # 获取源代码
            source_code = gitlab_fetcher.get_file_content(file_path, merge_info['source_branch'])
            
            # 检查diff内容
            diff_content = change.get('diff', '')
            if not diff_content:
                log.warning(f"⚠️ 文件 {file_path} 的diff内容为空")
                continue
            
            # 检查diff长度限制
            if len(diff_content) > MAX_DIFF_LENGTH:
                log.warning(f"⚠️ 文件 {file_path} 的diff内容过长，将被截断")
                diff_content = diff_content[:MAX_DIFF_LENGTH] + "\n\n... (内容过长，已截断)"
            
            # 检查源代码长度限制
            if source_code and len(source_code) > MAX_SOURCE_LENGTH:
                log.warning(f"⚠️ 文件 {file_path} 的源代码过长，将不添加上下文")
                source_code = None
            
            # 添加上下文
            content = add_context_to_diff(diff_content, source_code)
            
            # 检查最终内容长度限制
            if content and len(content) > MAX_CONTENT_LENGTH:
                log.warning(f"⚠️ 文件 {file_path} 的最终内容过长，将被截断")
                content = content[:MAX_CONTENT_LENGTH] + "\n\n... (内容过长，已截断)"
            
            # 检查最终内容
            if not content or content.strip() == "":
                log.warning(f"⚠️ 文件 {file_path} 处理后内容为空，跳过审查")
                continue
            
            # 为单个文件构建详细审查提示词
            file_prompt = f"""
你是一位资深编程专家，请对以下文件的变更进行详细的代码审查。

**文件信息**:
- 文件路径: {file_path}
- 所属Commit: {commit_id}
- 提交信息: {commit_message}
- 作者: {commit_author}

**文件变更内容（包含上下文）**:
{content}

{GPT_MESSAGE}

请特别注意:
1. 代码质量和最佳实践
2. 潜在的bug和安全问题
3. 性能影响
4. 代码可读性和维护性
5. 错误处理和边界情况

请按以下格式提供详细的审查意见：

**变更的主要内容:**
[详细分析这个文件的变更内容和目的]

**潜在的问题或风险:**
[详细分析可能存在的问题、风险或改进点]

**改进建议:**
[提供具体的改进建议和最佳实践]

请保持分析详细且专业，重点关注代码质量和潜在问题。
"""
            
            messages = [
                {
                    "role": "system",
                    "content": GPT_MESSAGE
                },
                {
                    "role": "user",
                    "content": file_prompt,
                },
            ]
            
            # 进行单文件详细审查
            log.info(f"📝 开始LLM详细分析文件: {file_path}")
            model.generate_text(messages)
            content = model.get_respond_content()
            
            if not content:
                log.error(f"LLM返回内容为空 (detailed file review) for {file_path}")
                file_review = {
                    'file_path': file_path,
                    'index': i,
                    'content': f"⚠️ AI分析暂时不可用，请手动审查 {file_path} 的代码变更。",
                    'tokens': 0,
                    'diff': diff_content
                }
            else:
                response_content = content.strip()
                total_tokens = model.get_respond_tokens()
                
                file_review = {
                    'file_path': file_path,
                    'index': i,
                    'content': response_content,
                    'tokens': total_tokens,
                    'diff': diff_content
                }
                
                log.info(f"✅ 完成文件 {file_path} 的详细审查，使用 {total_tokens} tokens")
            
            file_reviews.append(file_review)
        
        if not file_reviews:
            log.info(f"📝 Commit {commit_id} 没有成功审查的文件")
            return ""
        
        # 构建完整的详细commit审查结果
        total_tokens = sum(review['tokens'] for review in file_reviews)
        
        commit_review = f"## 🔍 Commit 详细审查: `{commit_id}`\n\n"
        commit_review += f"**📝 提交信息**: {commit_message}\n\n"
        commit_review += f"**👤 作者**: {commit_author}\n\n"
        commit_review += f"**🕒 时间**: {commit_date}\n\n"
        commit_review += f"**📊 变更文件**: {len(file_reviews)} 个\n\n"
        commit_review += "---\n\n"
        
        # 生成commit概述
        commit_review += "## 📋 Commit概述\n\n"
        commit_review += f"本次commit包含 {len(file_reviews)} 个文件的变更：\n"
        for review in file_reviews:
            commit_review += f"- `{review['file_path']}`\n"
        commit_review += "\n---\n\n"
        
        # 添加每个文件的详细审查结果
        commit_review += "## 📄 文件变更分析\n\n"
        for review in file_reviews:
            commit_review += f"### 文件 {review['index']}: `{review['file_path']}`\n\n"
            commit_review += f"**🤖 AI 详细分析** ({review['tokens']} tokens):\n\n"
            commit_review += f"{review['content']}\n\n"
            
            # 添加可折叠的diff详情
            commit_review += f"<details><summary>📋 展开查看{review['file_path']}详细变更</summary>\n\n"
            commit_review += f"```diff\n{review['diff']}\n```\n\n"
            commit_review += "</details>\n\n"
            commit_review += "---\n\n"
        
        # 添加整体总结
        commit_review += f"## 🔍 整体评价\n\n"
        commit_review += f"本次commit的详细审查已完成，共分析了 {len(file_reviews)} 个文件，总计使用 {total_tokens} tokens。\n\n"
        commit_review += "**审查要点:**\n"
        commit_review += "- 每个文件都经过了独立的详细分析\n"
        commit_review += "- 分析包含了完整的上下文代码\n"
        commit_review += "- 重点关注了代码质量、安全性和最佳实践\n\n"
        
        log.info(f'✅ Commit {commit_id} 详细审查完成')
        log.info(f'📝 Commit {commit_id} 详细审查总tokens: {total_tokens}')
        log.info(f'📝 Commit {commit_id} 审查结果长度: {len(commit_review)}')
        return commit_review
        
    except Exception as e:
        log.error(f"生成详细commit审查失败: {e}")
        return ""


def chat_commit_review(commits, commit_changes_map, generate_review, *args, **kwargs):
    """对多个commits进行并发审查"""
    log.info(f'开始per-commit code review - 共 {len(commits)} 个commits')
    
    # 只记录有变更的commits
    commits_with_changes = []
    for commit in commits:
        commit_id = commit['id'][:8]
        commit_message = commit['message']
        changes_count = len(commit_changes_map.get(commit['id'], []))
        if changes_count > 0:
            commits_with_changes.append(f"{commit_id} ({changes_count} 文件)")
    
    if commits_with_changes:
        log.info(f'📝 有变更的commits: {", ".join(commits_with_changes)}')
    else:
        log.info('📝 没有有变更的commits')
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        review_results = []
        result_lock = threading.Lock()

        def process_commit(commit):
            try:
                commit_id = commit['id']
                commit_changes = commit_changes_map.get(commit_id, [])
                
                if not commit_changes:
                    log.info(f"📝 Commit {commit_id[:8]} 没有文件变更，跳过审查")
                    return ""
                
                result = generate_review(commit, commit_changes, *args, **kwargs)
                log.info(f"📝 Commit {commit_id[:8]} 审查结果长度: {len(result) if result else 0}")
                
                # 只有非空结果才添加到review_results
                if result and result.strip():
                    with result_lock:
                        review_results.append((commit_id, result))
                    log.info(f"📝 Commit {commit_id[:8]} 审查结果已添加到结果列表")
                else:
                    log.warning(f"📝 Commit {commit_id[:8]} 审查结果为空或无效")
                
                return result
            except Exception as e:
                log.error(f"处理commit {commit['id'][:8]} 时出错: {e}")
                return ""

        # 提交所有任务
        futures = [executor.submit(process_commit, commit) for commit in commits]
        
        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log.error(f"Commit审查任务执行失败: {e}")

    # 按commit顺序排序结果，返回review内容列表
    sorted_results = []
    for commit in commits:
        commit_id = commit['id']
        for cid, result in review_results:
            if commit_id == cid and result.strip():
                sorted_results.append(result)
                log.info(f"📝 添加commit {commit_id[:8]} 的审查结果到返回列表，长度: {len(result)}")
                break
    
    log.info(f"📝 chat_commit_review 返回 {len(sorted_results)} 个审查结果")
    return sorted_results


class CommitReviewHandle(ReviewHandle):
    """处理每个commit的单独审查"""
    
    def merge_handle(self, gitlabMergeRequestFetcher, gitlabRepoManager, hook_info, reply, model):
        from config.config import REVIEW_PER_COMMIT
        
        if not REVIEW_PER_COMMIT:
            log.info("📝 Per-commit审查已禁用，跳过")
            return
        
        try:
            # 获取MR信息
            merge_info = gitlabMergeRequestFetcher.get_info()
            if not merge_info:
                log.error("无法获取MR信息")
                return
            
            # 获取所有commits
            commits = gitlabMergeRequestFetcher.get_commits()
            if not commits:
                log.info("MR中没有commits，跳过per-commit审查")
                return
            
            # 获取webhook的action信息
            action = hook_info.get('object_attributes', {}).get('action', '')
            
            log.info(f"📝 发现 {len(commits)} 个commits，MR action: {action}")
            log.info(f"📝 审查模式: {COMMIT_REVIEW_MODE} ({'详细分析' if COMMIT_REVIEW_MODE == 'detailed' else '简化diff审查'})")
            
            # 决定审查策略
            commits_to_review = []
            
            if action == 'open':
                # 首次打开MR，审查所有commits
                commits_to_review = commits
                log.info(f"📝 首次打开MR，将审查所有 {len(commits)} 个commits")
            elif action == 'update':
                # MR更新，只审查新增的commits
                reviewed_commits = gitlabMergeRequestFetcher.get_reviewed_commits()
                reviewed_commit_ids = set(reviewed_commits)
                
                # 过滤出未审查的commits
                for commit in commits:
                    commit_short_id = commit['id'][:8]
                    if commit_short_id not in reviewed_commit_ids:
                        commits_to_review.append(commit)
                
                log.info(f"📝 MR更新事件，发现 {len(reviewed_commits)} 个已审查的commits")
                log.info(f"📝 将审查 {len(commits_to_review)} 个新增commits")
                
                # 如果没有新增commits，跳过审查
                if not commits_to_review:
                    log.info("📝 没有新增commits需要审查，跳过")
                    return
            else:
                # 其他情况，按照之前的逻辑审查所有commits
                commits_to_review = commits
                log.info(f"📝 未知action '{action}'，将审查所有 {len(commits)} 个commits")
            
            # 获取需要审查的commits的变更
            commit_changes_map = {}
            for commit in commits_to_review:
                commit_id = commit['id']
                commit_changes = gitlabMergeRequestFetcher.get_commit_changes(commit_id)
                if commit_changes:
                    commit_changes_map[commit_id] = commit_changes
            
            # 打印即将审查的commits信息
            if commits_to_review:
                commit_infos = []
                for commit in commits_to_review:
                    commit_id = commit['id'][:8]
                    commit_message = commit['message'][:50] + ('...' if len(commit['message']) > 50 else '')
                    changes_count = len(commit_changes_map.get(commit['id'], []))
                    commit_infos.append(f"{commit_id} ({changes_count} 文件) - {commit_message}")
                log.info(f"📝 即将审查的commits: {', '.join(commit_infos)}")
            
            # 进行per-commit审查，返回每个commit的review列表
            review_infos = chat_commit_review(
                commits_to_review, 
                commit_changes_map, 
                generate_detailed_commit_review_note if COMMIT_REVIEW_MODE == 'detailed' else generate_commit_review_note,
                model, 
                gitlabMergeRequestFetcher, 
                merge_info
            )
            
            if review_infos:
                log.info(f"📝 获得 {len(review_infos)} 个commit的审查结果")
                for i, review_info in enumerate(review_infos):
                    if review_info.strip():
                        log.info(f"📝 发送第 {i+1} 个commit的审查结果，内容长度: {len(review_info)}")
                        # 截取前100字符用于调试
                        preview = review_info[:100].replace('\n', ' ')
                        log.info(f"📝 内容预览: {preview}...")
                        reply.add_reply({
                            'title': '__PER_COMMIT_REVIEW__',
                            'content': review_info,
                            'target': 'gitlab',
                            'msg_type': 'MAIN',
                        })
                    else:
                        log.warning(f"📝 第 {i+1} 个commit的审查结果为空，跳过")
                log.info("📝 Per-commit审查完成，每个commit已单独评论")
            else:
                log.info("📝 Per-commit审查没有产生结果")
                
        except Exception as e:
            log.error(f"Per-commit审查失败: {e}") 