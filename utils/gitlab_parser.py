import re
from config.config import CONTEXT_LINES_NUM


def filter_diff_content(diff_content):
    # 过滤掉以 - 开头的行和 @@ 开头的行
    filtered_content = re.sub(r'(^-.*\n)|(^@@.*\n)', '', diff_content, flags=re.MULTILINE)
    # 处理代码，去掉以 + 开头的行的第一个字符
    processed_code = '\n'.join([line[1:] if line.startswith('+') else line for line in filtered_content.split('\n')])
    return processed_code


def extract_diffs(diff_content):
    """提取多个diff转成diff数组"""

    # 使用正则表达式来匹配diff数据块
    diff_pattern = re.compile(r'@@ -\d+,\d+ \+\d+,\d+ @@.*?(?=\n@@|\Z)', re.DOTALL)
    diffs = diff_pattern.findall(diff_content)
    return diffs

def extract_diff_line_range(diff_content):
    """提取diff中的开始和结束行号"""
    line_range = []
    
    for line in diff_content.split('\n'):
        if line.startswith('@@'):
            # 提取新的行号
            match = re.match(r'@@ -\d+(,\d+)? \+(\d+)(,\d+)? @@', line)
            if match:
                start_line = int(match.group(2))
                line_range.append(start_line)
                
                # 计算结束行号
                if match.group(3):
                    # 去除逗号并转成int获取行数
                    line_count = int(match.group(3)[1:])
                    end_line = start_line + line_count - 1
                else:
                    end_line = start_line
                    
                line_range.append(end_line)

    return line_range

def extract_comment_end_line(diff_content):
    line_range = []

    for line in diff_content.split('\n'):
        if line.startswith('@@'):
            # 提取新的行号
            match = re.match(r'@@ -(\d+)(,\d+)? \+(\d+)(,\d+)? @@', line)
            if match:
                old_line_start = int(match.group(1))
                new_line_start = int(match.group(3))

                # 计算结束行号
                if match.group(2):
                    # 去除逗号并转成int获取行数
                    old_line_count = int(match.group(2)[1:])
                    old_line_end = old_line_start + old_line_count - 1
                else:
                    old_line_end = old_line_start

                if match.group(4):
                    # 去除逗号并转成int获取行数
                    new_line_count = int(match.group(4)[1:])
                    new_line_end = new_line_start + new_line_count - 1
                else:
                    new_line_end = new_line_start

                line_range.append(old_line_end)
                line_range.append(new_line_end)

    # 过滤 diff 部分以 + 或者 -结尾的 diff 类型
    diff_lines = diff_content.split('\n')
    diff_lines = diff_lines[::-1]
    for line in diff_lines:
        if line.startswith('\ No newline at end of file') or line == '':
            continue
        if line.startswith('+'):
            line_range[0] = 0
            break
        elif line.startswith('-'):
            line_range[1] = 0
            break
        else:
            break

    return line_range


def get_context_boundaries(diff_range, source_code_length, context_lines_num=CONTEXT_LINES_NUM):
    """计算上下文的行号边界"""
    if not diff_range or len(diff_range) < 2:
        return None, None, None, None

    # 计算上文边界
    front_lines_end = max(diff_range[0] - 1, 1) if diff_range[0] > 1 else None
    front_lines_start = max(diff_range[0] - context_lines_num, 1) if diff_range[0] > 1 else None
    
    # 计算下文边界
    back_lines_start = min(diff_range[1] + 1, source_code_length) if diff_range[1] < source_code_length else None
    back_lines_end = min(diff_range[1] + context_lines_num, source_code_length) if diff_range[1] < source_code_length else None
    
    return front_lines_start, front_lines_end, back_lines_start, back_lines_end

def add_context_to_diff(diff_content, source_code=None, context_lines_num=CONTEXT_LINES_NUM):
    """在diff内容前后添加上下文代码"""
    from utils.logger import log
    
    # 过滤diff内容
    filtered_diff = filter_diff_content(diff_content)

    # 获取同一 diff_content 多处 diff 行号范围和 diff过滤内容
    diff_ranges = []
    filtered_contents = []
    diffs = extract_diffs(diff_content)
    
    for diff in diffs:
        # 获取单个diff的行号范围
        diff_ranges.append(extract_diff_line_range(diff))
        # 获取单个diff的内容
        filtered_contents.append(filter_diff_content(diff))

    diff_with_contexts = ""

    if source_code and diff_ranges:
        code_lines = source_code.splitlines()
        source_code_length = len(code_lines)

        for filtered_content, diff_range in zip(filtered_contents, diff_ranges):
            front_lines = ""
            back_lines = ""
            diff_with_context = ""
            front_start, front_end, back_start, back_end = get_context_boundaries(
                diff_range, source_code_length, context_lines_num)

            if front_start is not None and front_end is not None and front_end >= front_start:
                for line in range(front_start, front_end + 1):
                    front_lines +=  code_lines[line - 1] + '\n'
                diff_with_context += f"修改代码块前代码：\n{front_lines}\n"

            diff_with_context += f"修改代码块：\n{filtered_content}\n"

            if back_start is not None and back_end is not None and back_end >= back_start:
                for line in range(back_start, back_end + 1):
                    back_lines +=  code_lines[line - 1] + '\n'
                diff_with_context += f"修改代码块后代码：\n{back_lines}\n"

            diff_with_contexts += diff_with_context + '\n'

    result = diff_with_contexts if diff_with_contexts else filtered_diff
    return result


def get_comment_request_json(comment, change, old_line, new_line, diff_refs):
    """生成 inline comment 请求Json格式"""

    # 默认评论到 change diff 部分的最后一行
    old_line = old_line if old_line > 0 else None
    new_line = new_line if new_line > 0 else None
    note = {
        "body": f"{comment}",
        "position": {
            "base_sha": diff_refs['base_sha'],
            "start_sha": diff_refs['start_sha'],
            "head_sha": diff_refs['head_sha'],
            "position_type": "text",
            "old_path": change['old_path'],
            "old_line": old_line,
            "new_path": change['new_path'],
            "new_line": new_line,
            # "line_range": {
            #     "start": {
            #         # "line_code": "ca08fab203917f02c97701e43c3cf87140bb6643_31_30",
            #         "type": "new",
            #         "new_line": 30,
            #     },
            #     "end": {
            #         # "line_code": "ca08fab203917f02c97701e43c3cf87140bb6643_33_35",
            #         "type": "new",
            #         "new_line": 35,
            #     },
            #
            # }
        }
    }

    return note

def detect_function_boundaries(code_lines, line_number):
    """检测函数边界"""
    start_line = None
    end_line = None
    
    # 向上查找函数开始
    for i in range(line_number - 1, -1, -1):
        line = code_lines[i].strip()
        # Python函数定义
        if re.match(r'^def\s+\w+.*:', line) or re.match(r'^class\s+\w+.*:', line):
            start_line = i
            break
        # JavaScript/TypeScript函数
        elif re.match(r'^\s*(function\s+\w+|const\s+\w+\s*=|let\s+\w+\s*=|var\s+\w+\s*=).*{', line):
            start_line = i
            break
        # Java/C++方法
        elif re.match(r'^\s*(public|private|protected).*\{', line):
            start_line = i
            break
    
    # 向下查找函数结束
    if start_line is not None:
        indent_level = len(code_lines[start_line]) - len(code_lines[start_line].lstrip())
        brace_count = 0
        
        for i in range(start_line, len(code_lines)):
            line = code_lines[i]
            
            # 计算大括号平衡
            brace_count += line.count('{') - line.count('}')
            
            # Python风格：检查缩进
            if line.strip() and len(line) - len(line.lstrip()) <= indent_level and i > start_line:
                if not line.startswith(' ') and not line.startswith('\t'):
                    end_line = i - 1
                    break
            
            # 大括号风格：检查平衡
            elif brace_count == 0 and i > start_line and '}' in line:
                end_line = i
                break
    
    return start_line, end_line


def detect_class_boundaries(code_lines, line_number):
    """检测类边界"""
    start_line = None
    end_line = None
    
    # 向上查找类定义
    for i in range(line_number - 1, -1, -1):
        line = code_lines[i].strip()
        if re.match(r'^class\s+\w+.*:', line) or re.match(r'^class\s+\w+.*\{', line):
            start_line = i
            break
    
    # 向下查找类结束
    if start_line is not None:
        indent_level = len(code_lines[start_line]) - len(code_lines[start_line].lstrip())
        brace_count = 0
        
        for i in range(start_line, len(code_lines)):
            line = code_lines[i]
            brace_count += line.count('{') - line.count('}')
            
            # Python风格
            if line.strip() and len(line) - len(line.lstrip()) <= indent_level and i > start_line:
                if not line.startswith(' ') and not line.startswith('\t'):
                    end_line = i - 1
                    break
            
            # 大括号风格
            elif brace_count == 0 and i > start_line and '}' in line:
                end_line = i
                break
    
    return start_line, end_line


def extract_imports_and_dependencies(code_lines):
    """提取导入语句和依赖信息"""
    imports = []
    for i, line in enumerate(code_lines):
        line = line.strip()
        # Python imports
        if re.match(r'^(import|from)\s+', line):
            imports.append((i, line))
        # JavaScript/TypeScript imports
        elif re.match(r'^import\s+.*from\s+', line):
            imports.append((i, line))
        # Java imports
        elif re.match(r'^import\s+.*', line):
            imports.append((i, line))
        # C++ includes
        elif re.match(r'^#include\s+', line):
            imports.append((i, line))
    
    return imports


def get_smart_context_boundaries(diff_range, source_code_lines, max_lines=20):
    """智能获取上下文边界"""
    if not diff_range or len(diff_range) < 2:
        return None, None, None, None
    
    start_line = diff_range[0]
    end_line = diff_range[1]
    
    # 检测函数边界
    func_start, func_end = detect_function_boundaries(source_code_lines, start_line)
    
    # 计算智能边界
    if func_start is not None and func_end is not None:
        # 如果函数不太大，使用完整函数作为上下文
        func_size = func_end - func_start + 1
        if func_size <= max_lines * 2:
            front_start = func_start + 1
            front_end = max(start_line - 1, func_start + 1)
            back_start = min(end_line + 1, func_end + 1)
            back_end = func_end + 1
        else:
            # 函数太大，使用固定行数
            front_start = max(start_line - max_lines, 1)
            front_end = start_line - 1
            back_start = end_line + 1
            back_end = min(end_line + max_lines, len(source_code_lines))
    else:
        # 没有找到函数边界，使用固定行数
        front_start = max(start_line - max_lines, 1)
        front_end = start_line - 1
        back_start = end_line + 1
        back_end = min(end_line + max_lines, len(source_code_lines))
    
    return front_start, front_end, back_start, back_end


def add_enhanced_context_to_diff(diff_content, source_code=None, context_mode="smart"):
    """增强版上下文添加功能"""
    from utils.logger import log
    from config.config import (
        CONTEXT_LINES_NUM, SMART_CONTEXT_MAX_LINES, 
        FUNCTION_CONTEXT_ENABLED, CLASS_CONTEXT_ENABLED, 
        IMPORTS_CONTEXT_ENABLED
    )
    
    # 如果没有源代码，回退到基础模式
    if not source_code:
        return add_context_to_diff(diff_content, source_code, CONTEXT_LINES_NUM)
    
    # 过滤diff内容
    filtered_diff = filter_diff_content(diff_content)
    
    # 获取diff信息
    diff_ranges = []
    filtered_contents = []
    diffs = extract_diffs(diff_content)
    
    for diff in diffs:
        diff_ranges.append(extract_diff_line_range(diff))
        filtered_contents.append(filter_diff_content(diff))
    
    if not diff_ranges:
        return filtered_diff
    
    code_lines = source_code.splitlines()
    source_code_length = len(code_lines)
    result_contexts = []
    
    for filtered_content, diff_range in zip(filtered_contents, diff_ranges):
        context_info = {
            'diff_content': filtered_content,
            'before_context': "",
            'after_context': "",
            'function_context': "",
            'class_context': "",
            'imports_context': ""
        }
        
        if context_mode == "smart":
            front_start, front_end, back_start, back_end = get_smart_context_boundaries(
                diff_range, code_lines, SMART_CONTEXT_MAX_LINES)
        elif context_mode == "full":
            # 完整函数/类上下文
            func_start, func_end = detect_function_boundaries(code_lines, diff_range[0])
            class_start, class_end = detect_class_boundaries(code_lines, diff_range[0])
            
            if func_start is not None and func_end is not None:
                front_start, front_end = func_start + 1, diff_range[0] - 1
                back_start, back_end = diff_range[1] + 1, func_end + 1
            else:
                front_start, front_end, back_start, back_end = get_context_boundaries(
                    diff_range, source_code_length, SMART_CONTEXT_MAX_LINES)
        else:
            # 基础模式
            front_start, front_end, back_start, back_end = get_context_boundaries(
                diff_range, source_code_length, CONTEXT_LINES_NUM)
        
        # 提取前置上下文
        if front_start is not None and front_end is not None and front_end >= front_start:
            before_lines = []
            for line_num in range(front_start, front_end + 1):
                if 0 <= line_num - 1 < len(code_lines):
                    before_lines.append(code_lines[line_num - 1])
            context_info['before_context'] = '\n'.join(before_lines)
        
        # 提取后置上下文
        if back_start is not None and back_end is not None and back_end >= back_start:
            after_lines = []
            for line_num in range(back_start, back_end + 1):
                if 0 <= line_num - 1 < len(code_lines):
                    after_lines.append(code_lines[line_num - 1])
            context_info['after_context'] = '\n'.join(after_lines)
        
        # 提取函数上下文（如果启用）
        if FUNCTION_CONTEXT_ENABLED:
            func_start, func_end = detect_function_boundaries(code_lines, diff_range[0])
            if func_start is not None and func_end is not None:
                func_lines = []
                for line_num in range(func_start, min(func_start + 5, len(code_lines))):
                    func_lines.append(code_lines[line_num])
                context_info['function_context'] = '\n'.join(func_lines)
        
        # 提取类上下文（如果启用）
        if CLASS_CONTEXT_ENABLED:
            class_start, class_end = detect_class_boundaries(code_lines, diff_range[0])
            if class_start is not None:
                context_info['class_context'] = code_lines[class_start]
        
        # 提取导入上下文（如果启用）
        if IMPORTS_CONTEXT_ENABLED:
            imports = extract_imports_and_dependencies(code_lines)
            if imports:
                import_lines = [line for _, line in imports[:10]]  # 限制显示前10个导入
                context_info['imports_context'] = '\n'.join(import_lines)
        
        result_contexts.append(context_info)
    
    # 构建最终结果
    final_result = []
    for i, context in enumerate(result_contexts):
        context_text = f"=== 变更块 {i+1} ===\n\n"
        
        if context['imports_context']:
            context_text += f"🔗 **相关导入**:\n```\n{context['imports_context']}\n```\n\n"
        
        if context['class_context']:
            context_text += f"📦 **所属类**:\n```\n{context['class_context']}\n```\n\n"
        
        if context['function_context']:
            context_text += f"🔧 **所属函数**:\n```\n{context['function_context']}\n```\n\n"
        
        if context['before_context']:
            context_text += f"⬆️ **变更前上下文**:\n```\n{context['before_context']}\n```\n\n"
        
        context_text += f"🎯 **实际变更内容**:\n```\n{context['diff_content']}\n```\n\n"
        
        if context['after_context']:
            context_text += f"⬇️ **变更后上下文**:\n```\n{context['after_context']}\n```\n\n"
        
        final_result.append(context_text)
    
    return '\n'.join(final_result)

if __name__ == "__main__":
    diff_content = "@@ -3 +1,5 @@\n-hello\n+hello world\n"
    print(extract_diff_line_range(diff_content))