import requests
from retrying import retry
from config.config import *
from response_module.abstract_response import AbstractResponseMessage
from utils.logger import log

# 继承AbstractReply类，实现send方法
class GitlabResponse(AbstractResponseMessage):
    def __init__(self, config):
        super().__init__(config)
        self.type = config['type']
        if self.type == 'merge_request':
            self.project_id = config['project_id']
            self.merge_request_id = config['merge_request_iid']

    def send(self, message):
        if self.type == 'merge_request':
            return self.send_merge(message)
        else:
            return False

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def send_merge(self, message):
        # 检查是否已存在相同评论，避免重复
        if ENABLE_DUPLICATE_CHECK and self._check_duplicate_comment(message):
            log.info(f"发现重复评论，跳过发送：project_id:{self.project_id} merge_request_id:{self.merge_request_id}")
            return True
            
        headers = {
            "Private-Token": GITLAB_PRIVATE_TOKEN,
            "Content-Type": "application/json"
        }
        project_id = self.project_id
        merge_request_id = self.merge_request_id
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{project_id}/merge_requests/{merge_request_id}/notes"
        data = {
            "body": message
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 201:
            log.info(f"评论信息发送成功：project_id:{project_id}  merge_request_id:{merge_request_id}")
            return True
        else:
            log.error(
                f"评论信息发送失败：project_id:{project_id}  merge_request_id:{merge_request_id} response:{response}")
            return False

    def _check_duplicate_comment(self, new_message):
        """
        检查是否存在重复评论
        """
        try:
            headers = {
                "Private-Token": GITLAB_PRIVATE_TOKEN,
                "Content-Type": "application/json"
            }
            url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}/merge_requests/{self.merge_request_id}/notes"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                existing_notes = response.json()
                
                # 检查是否有相同内容的评论（忽略时间戳等差异）
                new_message_clean = self._clean_message_for_comparison(new_message)
                
                for note in existing_notes:
                    if note.get('system', False):  # 跳过系统消息
                        continue
                    existing_message_clean = self._clean_message_for_comparison(note.get('body', ''))
                    
                    # 如果清理后的消息内容相似度很高，认为是重复
                    if self._is_similar_content(new_message_clean, existing_message_clean):
                        return True
                        
            return False
        except Exception as e:
            log.warning(f"检查重复评论时出错：{e}")
            return False  # 出错时不阻止发送
            
    def _clean_message_for_comparison(self, message):
        """
        清理消息内容用于比较（移除时间戳、tokens数量等变化内容）
        """
        import re
        if not message:
            return ""
            
        # 移除tokens信息
        cleaned = re.sub(r'\(\d+\s*tokens?\)', '', message)
        
        # 移除时间戳相关内容
        cleaned = re.sub(r'\d{4}-\d{2}-\d{2}.*?\d{2}:\d{2}:\d{2}', '', cleaned)
        
        # 移除多余空白字符
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
        
    def _is_similar_content(self, content1, content2, threshold=None):
        """
        判断两个内容是否相似（简单的相似度检查）
        """
        if threshold is None:
            threshold = SIMILARITY_THRESHOLD
            
        if not content1 or not content2:
            return False
            
        # 简单的相似度检查：如果设定阈值以上内容相同，认为是重复
        if len(content1) == 0 or len(content2) == 0:
            return False
            
        # 使用集合交集计算相似度
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if len(words1) == 0 or len(words2) == 0:
            return False
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold


    def send_inline_comments(self, message):
        if self.type == 'merge_request':
            return self.comment_on_changes(message)
        else:
            return False

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def comment_on_changes(self, message):
        headers = {
            "Private-Token": GITLAB_PRIVATE_TOKEN,
            "Content-Type": "application/json"
        }
        project_id = self.project_id
        merge_request_id = self.merge_request_id
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{project_id}/merge_requests/{merge_request_id}/discussions"
        response = requests.post(url, headers=headers,json={'body': message['body'], 'position': message['position']})
        if response.status_code == 201:
            log.info(f"Inline Comment发送成功：project_id:{project_id}  merge_request_id:{merge_request_id}, comment_file: {message['position']['new_path']}")
            return True
        else:
            log.error(
                f"Inline Comment发送失败：project_id:{project_id}  merge_request_id:{merge_request_id}, comment_file: {message['position']['new_path']}")
            return False