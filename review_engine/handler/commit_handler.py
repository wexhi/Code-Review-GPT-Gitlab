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
    """为单个commit生成简化的审查意见（只关注diff变更）"""
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
        
        # 构建commit审查结果
        commit_review = f"## 🔍 Commit 审查: `{commit_id}`\n\n"
        commit_review += f"**📝 提交信息**: {commit_message}\n"
        commit_review += f"**👤 作者**: {commit_author}\n"
        commit_review += f"**🕒 时间**: {commit_date}\n"
        commit_review += f"**📊 变更文件**: {len(reviewable_changes)} 个\n\n"
        commit_review += "---\n\n"
        
        # 处理每个文件的变更
        for change in reviewable_changes:
            file_path = change.get('new_path') or change.get('old_path')
            
            # 获取diff内容
            diff_content = change.get('diff', '')
            if not diff_content:
                log.warning(f"⚠️ 文件 {file_path} 的diff内容为空")
                continue
            
            # 检查diff长度限制
            if len(diff_content) > MAX_DIFF_LENGTH:
                log.warning(f"⚠️ 文件 {file_path} 的diff内容过长，将被截断")
                diff_content = diff_content[:MAX_DIFF_LENGTH] + "\n\n... (内容过长，已截断)"
            
            # 简化的提示词，只关注diff变更
            simplified_prompt = f"""
请简洁地分析以下代码变更，重点关注：
1. 变更的主要内容和目的
2. 潜在的问题或风险
3. 简单的改进建议

请用简洁的语言回答，不需要过于详细的分析。

代码变更：
{diff_content}
"""
            
            messages = [
                {
                    "role": "user",
                    "content": simplified_prompt,
                },
            ]
            
            # 进行简化的review
            model.generate_text(messages)
            content = model.get_respond_content()
            if not content:
                log.error(f"LLM返回内容为空 (commit review) for {file_path}")
                # 如果LLM没有返回内容，显示基本的diff信息
                file_review = f"### 📄 `{file_path}`\n\n"
                file_review += f"**变更概要**: 文件已修改\n\n"
                file_review += f"<details><summary>📋 查看diff</summary>\n\n"
                file_review += f"```diff\n{diff_content}\n```\n\n"
                file_review += f"</details>\n\n"
            else:
                response_content = content.strip()
                total_tokens = model.get_respond_tokens()
                
                # 构建简化的文件审查结果
                file_review = f"### 📄 `{file_path}`\n\n"
                file_review += f"**🤖 AI 分析** ({total_tokens} tokens):\n\n"
                file_review += f"{response_content}\n\n"
                file_review += f"<details><summary>📋 查看diff</summary>\n\n"
                file_review += f"```diff\n{diff_content}\n```\n\n"
                file_review += f"</details>\n\n"
            
            commit_review += file_review
            log.info(f'✅ 文件 {file_path} 审查完成')
        
        commit_review += "---\n\n"
        
        log.info(f'✅ Commit {commit_id} 审查完成')
        log.info(f'📝 Commit {commit_id} 审查结果长度: {len(commit_review)}')
        log.info(f'📝 Commit {commit_id} 审查结果预览: {commit_review[:100].replace(chr(10), " ")}...')
        return commit_review
        
    except Exception as e:
        log.error(f"Commit Review error: {e}")
        return ""


@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_detailed_commit_review_note(commit_info, commit_changes, model, gitlab_fetcher, merge_info):
    """为单个commit生成详细的审查意见（包含完整分析）"""
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
        
        # 处理每个文件的变更
        file_reviews = []
        for change in reviewable_changes:
            file_path = change.get('new_path') or change.get('old_path')
            
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
            
            # 构建消息
            user_message = f"请review这部分代码变更 {content}"
            if len(user_message.strip()) <= 10:
                log.warning(f"⚠️ 文件 {file_path} 用户消息过短，跳过审查")
                continue
                
            messages = [
                {
                    "role": "system",
                    "content": GPT_MESSAGE
                 },
                {
                    "role": "user",
                    "content": user_message,
                },
            ]
            
            # review
            model.generate_text(messages)
            content = model.get_respond_content()
            if not content:
                log.error(f"LLM返回内容为空 (detailed commit review) for {file_path}")
                continue
            response_content = content.replace('\n\n', '\n')
            total_tokens = model.get_respond_tokens()

            # 构建文件审查结果
            file_review = f"<details><summary>📄 <strong><code>{file_path}</code></strong></summary>\n"
            file_review += f"<div>({total_tokens} tokens) AI review 意见如下:</div>\n\n\n\n {response_content} \n\n <hr></details>"
            file_reviews.append(file_review)
            
            log.info(f'✅ 文件 {file_path} 详细审查完成')
        
        if not file_reviews:
            log.info(f"📝 Commit {commit_id} 没有成功审查的文件")
            return ""
        
        # 构建commit审查结果
        commit_review = f"## 🔍 Commit 详细审查: `{commit_id}`\n\n"
        commit_review += f"**提交信息**: {commit_message}\n\n"
        commit_review += f"**作者**: {commit_author}\n\n"
        commit_review += f"**时间**: {commit_date}\n\n"
        commit_review += f"**审查文件数**: {len(file_reviews)}\n\n"
        commit_review += "---\n\n"
        
        for file_review in file_reviews:
            commit_review += file_review + "\n\n"
        
        log.info(f'✅ Commit {commit_id} 详细审查完成')
        return commit_review
        
    except Exception as e:
        log.error(f"Detailed Commit Review error: {e}")
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
            
            log.info(f"📝 发现 {len(commits)} 个commits，开始per-commit审查")
            log.info(f"📝 审查模式: {COMMIT_REVIEW_MODE} ({'详细分析' if COMMIT_REVIEW_MODE == 'detailed' else '简化diff审查'})")
            
            # 获取每个commit的变更
            commit_changes_map = {}
            for commit in commits:
                commit_id = commit['id']
                commit_changes = gitlabMergeRequestFetcher.get_commit_changes(commit_id)
                if commit_changes:
                    commit_changes_map[commit_id] = commit_changes
            
            # 进行per-commit审查，返回每个commit的review列表
            review_infos = chat_commit_review(
                commits, 
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