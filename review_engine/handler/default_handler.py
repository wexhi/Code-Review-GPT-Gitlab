import concurrent.futures
import threading

from retrying import retry
from config.config import GPT_MESSAGE, MAX_FILES, SUPPORTED_FILE_TYPES, IGNORE_FILE_TYPES, MAX_CONTENT_LENGTH, MAX_DIFF_LENGTH, MAX_SOURCE_LENGTH
from review_engine.abstract_handler import ReviewHandle
from utils.gitlab_parser import (filter_diff_content, add_context_to_diff, extract_diffs,
                                 get_comment_request_json, extract_comment_end_line)
from utils.logger import log
from utils.args_check import file_need_check
from utils.tools import batch
from review_engine.review_prompt import (REVIEW_SUMMARY_SETTING, FILE_DIFF_REVIEW_PROMPT, BATCH_SUMMARY_PROMPT,
                                         FINAL_SUMMARY_PROMPT,SUMMARY_OUTPUT_PROMPT)


def chat_review(changes, generate_review, *args, **kwargs):
    log.info(f'开始code review - 共 {len(changes)} 个文件')
    
    # 只记录需要审查的文件
    reviewable_files = []
    for change in changes:
        file_path = change["new_path"]
        if file_need_check(file_path):
            reviewable_files.append(file_path)
    
    if reviewable_files:
        log.info(f'📄 需要审查的文件: {", ".join(reviewable_files)}')
    else:
        log.info('📄 没有需要审查的文件')
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        review_results = []
        result_lock = threading.Lock()

        def process_change(change):
            file_path = change["new_path"]
            log.info(f'🔍 开始处理文件: {file_path}')
            try:
                result = generate_review(change, *args, **kwargs)
                log.info(f'✅ 完成处理文件: {file_path}')
                with result_lock:
                    review_results.append(result)
            except Exception as e:
                log.error(f'❌ 处理文件 {file_path} 时出错: {e}')

        futures = []
        processed_count = 0
        for change in changes:
            if not file_need_check(change["new_path"]):
                log.info(f"{change['new_path']} 非目标检测文件！")
                continue
            
            processed_count += 1
            futures.append(executor.submit(process_change, change))

        log.info(f'📊 将处理 {processed_count} 个文件，跳过 {len(changes) - processed_count} 个文件')
        
        # 等待所有任务完成
        concurrent.futures.wait(futures)

    log.info(f'✅ Code review 完成，生成了 {len(review_results)} 个审查结果')
    return "<details open><summary><h1>修改文件列表</h1></summary>" + "\n\n".join(review_results) +"</details>" if review_results else ""


def chat_review_summary(changes, model):
    log.info("开始 code review summary")
    file_diff_map = {}
    file_summary_map = {}
    summary_lock = threading.Lock()

    for change in changes:
        if change['new_path'] not in file_diff_map:
            if not file_need_check(change["new_path"]):
                continue
            file_diff_map[change['new_path']] = filter_diff_content(change['diff'])

    # 对单个文件diff进行总结
    with concurrent.futures.ThreadPoolExecutor() as executor:
        def process_summary(file, diff, model):
            summary = generate_diff_summary(file, diff, model)
            with summary_lock:
                file_summary_map[file] = summary

        futures = []
        for file, diff in file_diff_map.items():
            futures.append(executor.submit(process_summary, file, diff, model))
        # 等待所有任务完成
        concurrent.futures.wait(futures)

    log.info("code diff review完成，batch summary中")
    summaries_content = ""
    batchsize = 8
    # 分批对单文件summary 进行汇总
    for batch_data in batch(file_summary_map, batchsize):
        for file in batch_data:
            summaries_content += f"---\n{file}: {file_summary_map[file]}\n"
        batch_changesets_prompt = BATCH_SUMMARY_PROMPT.replace("$raw_summary", summaries_content)
        batch_summary_msg = [
            {"role": "system",
             "content": REVIEW_SUMMARY_SETTING
             },
            {"role": "user",
             "content": f"{batch_changesets_prompt}"
             }
        ]
        model.generate_text(batch_summary_msg)
        content = model.get_respond_content()
        if not content:
            log.error("LLM返回内容为空 (chat_review_summary)")
            return ""
        summaries_content = content.replace('\n\n', '\n')

    # 总结生成 summary 和 file summary 表格
    final_summaries_content = SUMMARY_OUTPUT_PROMPT.replace("$summaries_content", summaries_content)
    final_summary_msg = [
        {"role": "system",
         "content": REVIEW_SUMMARY_SETTING
         },
        {"role": "user",
         "content": FINAL_SUMMARY_PROMPT
         },
        {"role": "user",
         "content": f"{final_summaries_content}"
         }
    ]
    summary_result = generate_diff_summary(model=model, messages=final_summary_msg)
    log.info("code diff review summary完成")
    return summary_result+"\n\n---\n\n" if summary_result else ""

def chat_review_inline_comment(changes, model, merge_info):
    """行内comment"""
    log.info("开始code review inline comment")
    comment_results = []
    comment_lock = threading.Lock()
    diff_refs = merge_info['diff_refs']

    # 对单个diff块生成 inline comment
    with concurrent.futures.ThreadPoolExecutor() as executor:
        def process_comment(diff, model, change, old_line_end, new_line_end):
            comment = generate_inline_comment(diff, model)
            comment_json = get_comment_request_json(comment, change, old_line_end, new_line_end ,diff_refs)
            with comment_lock:
                comment_results.append(comment_json)

        futures = []
        for change in changes:
            if not file_need_check(change["new_path"]):
                continue
            # 获取单文件 多处diff内容
            diffs = extract_diffs(change['diff'])
            for diff in diffs:
                # diff = filter_diff_content(diff)
                old_line_end, new_line_end =  extract_comment_end_line(diff)
                futures.append(executor.submit(process_comment, diff, model, change, old_line_end, new_line_end))
        # 等待所有任务完成
        concurrent.futures.wait(futures)

    log.info("inline comment 完成")
    return comment_results if comment_results else None


@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_inline_comment(diff, model):
    file_diff_prompt = FILE_DIFF_REVIEW_PROMPT.replace('$file_diff', diff)
    file_diff_prompt += "\n\n要求总结用中文回答，评价尽可能全面且精炼，字数不超过50字。"
    messages = [
        {"role": "system",
         "content": REVIEW_SUMMARY_SETTING
         },
        {
            "role": "user",
            "content": f"{file_diff_prompt}",
        },
    ]
    model.generate_text(messages)
    content = model.get_respond_content()
    if not content:
        log.error("LLM返回内容为空 (generate_inline_comment)")
        return "comment: nothing obtained from LLM"
    response_content = content.replace('\n\n', '\n')
    if response_content:
        return response_content
    else:
        return "comment: nothing obtained from LLM"





@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_diff_summary(file=None, diff=None, model=None, messages=None):
    file_diff_prompt =  FILE_DIFF_REVIEW_PROMPT.replace('$file_diff', diff) if diff else ""
    messages = [
        {"role": "system",
         "content": REVIEW_SUMMARY_SETTING
         },
        {
            "role": "user",
            "content": f"{file_diff_prompt}",
        },
    ] if messages is None else messages
    if model is None:
        return "summarize: model is None"
    model.generate_text(messages)
    content = model.get_respond_content()
    if not content:
        log.error("LLM返回内容为空 (generate_diff_summary)")
        return "summarize: nothing obtained from LLM"
    response_content = content.replace('\n\n', '\n')
    if response_content:
        return response_content
    else:
        return "summarize: nothing obtained from LLM"


@retry(stop_max_attempt_number=3, wait_fixed=60000)
def generate_review_note_with_context(change, model, gitlab_fetcher, merge_info):
    try:
        # prepare
        new_path = change['new_path']
        log.info(f"📄 开始处理文件: {new_path}")
        log.info(f"📋 分支信息: {merge_info['source_branch']}")
        
        # 获取源代码
        source_code = gitlab_fetcher.get_file_content(change['new_path'], merge_info['source_branch'])
        
        # 检查diff内容
        diff_content = change['diff']
        if not diff_content:
            log.warning(f"⚠️ 文件 {new_path} 的diff内容为空")
            return ""
        
        # 检查diff长度限制
        if len(diff_content) > MAX_DIFF_LENGTH:
            log.warning(f"⚠️ 文件 {new_path} 的diff内容过长，将被截断")
            diff_content = diff_content[:MAX_DIFF_LENGTH] + "\n\n... (内容过长，已截断)"
        
        # 检查源代码长度限制
        if source_code and len(source_code) > MAX_SOURCE_LENGTH:
            log.warning(f"⚠️ 文件 {new_path} 的源代码过长，将不添加上下文")
            source_code = None
        
        # 添加上下文
        content = add_context_to_diff(diff_content, source_code)
        
        # 检查最终内容长度限制
        if content and len(content) > MAX_CONTENT_LENGTH:
            log.warning(f"⚠️ 文件 {new_path} 的最终内容过长，将被截断")
            content = content[:MAX_CONTENT_LENGTH] + "\n\n... (内容过长，已截断)"
        
        # 检查最终内容
        if not content or content.strip() == "":
            log.warning(f"⚠️ 文件 {new_path} 处理后内容为空，跳过审查")
            return ""
        
        # 构建消息
        user_message = f"请review这部分代码变更 {content}"
        if len(user_message.strip()) <= 10:
            log.warning(f"⚠️ 文件 {new_path} 用户消息过短，跳过审查")
            return ""
            
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
        log.info(f"📤 正在审查文件: {new_path}")
        model.generate_text(messages)
        content = model.get_respond_content()
        if not content:
            log.error(f"LLM返回内容为空 (generate_review_note_with_context) for {new_path}")
            return ""
        response_content = content.replace('\n\n', '\n')
        total_tokens = model.get_respond_tokens()

        # response
        review_note = f"<details><summary>📚<strong><code>{new_path}</code></strong></summary>\
        <div>({total_tokens} tokens) AI review 意见如下:</div> \n\n\n\n {response_content} \n\n <hr><hr></details>"

        # review_note += f'# 📚`{new_path}`' + '\n\n'
        # review_note += f'({total_tokens} tokens) {"AI review 意见如下:"}' + '\n\n'
        # review_note += response_content + "\n\n---\n\n---\n\n"
        
        log.info(f'✅ 文件 {new_path} 审查完成')
        return review_note
    
    except Exception as e:
        log.error(f"LLM Review error:{e}")
        return ""


class MainReviewHandle(ReviewHandle):
    def merge_handle(self, gitlabMergeRequestFetcher, gitlabRepoManager, hook_info, reply, model):
        changes = gitlabMergeRequestFetcher.get_changes()
        merge_info = gitlabMergeRequestFetcher.get_info()
        self.default_handle(changes, merge_info, hook_info, reply, model, gitlabMergeRequestFetcher)


    def default_handle(self, changes, merge_info, hook_info, reply, model, gitlab_fetcher):
        if changes and len(changes) <= MAX_FILES:
            review_summary = chat_review_summary(changes, model)
            review_info = chat_review(changes, generate_review_note_with_context, model, gitlab_fetcher, merge_info)
            review_info = review_summary + review_info

            review_inline_comments = chat_review_inline_comment(changes, model, merge_info)

            if review_info:
                reply.add_reply({
                    'content': review_info,
                    'msg_type': 'MAIN, SINGLE',
                    'target': 'all',
                })
                reply.add_reply({
                    'title': '__MAIN_REVIEW__',
                    'content': (
                        f"## 项目名称: **{hook_info['project']['name']}**\n\n"
                        f"### 合并请求详情\n"
                        f"- **MR URL**: [查看合并请求]({hook_info['object_attributes']['url']})\n"
                        f"- **源分支**: `{hook_info['object_attributes']['source_branch']}`\n"
                        f"- **目标分支**: `{hook_info['object_attributes']['target_branch']}`\n\n"
                        f"### 变更详情\n"
                        f"- **修改文件个数**: `{len(changes)}`\n"
                        f"- **Code Review 状态**: ✅\n"
                    ),
                    'target': 'dingtalk',
                    'msg_type': 'MAIN, SINGLE',
                })
            else:
                reply.add_reply({
                    'title': '__MAIN_REVIEW__',
                    'content': (
                        f"## 项目名称: **{hook_info['project']['name']}**\n\n"
                        f"### 合并请求详情\n"
                        f"- **MR URL**: [查看合并请求]({hook_info['object_attributes']['url']})\n"
                        f"- **源分支**: `{hook_info['object_attributes']['source_branch']}`\n"
                        f"- **目标分支**: `{hook_info['object_attributes']['target_branch']}`\n\n"
                        f"### 变更详情\n"
                        f"- **修改文件个数**: `{len(changes)}`\n"
                        f"- **备注**: 存在已经提交的 MR，所有文件已进行 MR\n"
                        f"- **Code Review 状态**: pass ✅\n"
                    ),
                    'target': 'dingtalk',
                    'msg_type': 'MAIN, SINGLE',
                })

            if review_inline_comments:
                for comment in review_inline_comments:
                    reply.add_comment({
                        'content': comment,
                        'target': 'gitlab',
                        'msg_type': 'COMMENT',
                    })




        elif changes and len(changes) > MAX_FILES:
            reply.add_reply({
                'title': '__MAIN_REVIEW__',
                'content': (
                    f"## 项目名称: **{hook_info['project']['name']}**\n\n"
                    f"### 备注\n"
                    f"修改 `{len(changes)}` 个文件 > 50 个文件，不进行 Code Review ⚠️\n\n"
                    f"### 合并请求详情\n"
                    f"- **MR URL**: [查看合并请求]({hook_info['object_attributes']['url']})\n"
                    f"- **源分支**: `{hook_info['object_attributes']['source_branch']}`\n"
                    f"- **目标分支**: `{hook_info['object_attributes']['target_branch']}`\n"
                ),
                'target': 'dingtalk',
                'msg_type': 'MAIN, SINGLE',
            })

        else:
            log.error(f"获取merge_request信息失败，project_id: {hook_info['project']['id']} |"
                      f" merge_iid: {hook_info['object_attributes']['iid']} | merge_info: {merge_info}")


