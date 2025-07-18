import os
import re
import shutil
import subprocess
import time

import requests
from retrying import retry
from config.config import *
from utils.logger import log
from utils.tools import run_command


class GitlabMergeRequestFetcher:
    def __init__(self, project_id, merge_request_iid):
        self.project_id = project_id
        self.iid = merge_request_iid
        self._changes_cache = None
        self._file_content_cache = {}
        self._info_cache = None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_changes(self, force=False):
        """
        Get the changes of the merge request
        :return: changes
        """
        if self._changes_cache and not force:
            return self._changes_cache
        # URL for the GitLab API endpoint
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}/changes"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._changes_cache = response.json()["changes"]
            return response.json()["changes"]
        else:
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    # 获取文件内容
    def get_file_content(self, file_path, branch_name='main', force=False):
        """
        Get the content of the file
        :param file_path: The path of the file
        :return: The content of the file
        """
        # 对file_path中的'/'转换为'%2F'
        file_path = file_path.replace('/', '%2F')
        if file_path in self._file_content_cache and not force:
            return self._file_content_cache[file_path]
        # URL for the GitLab API endpoint
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}/repository/files/{file_path}/raw?ref={branch_name}"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._file_content_cache[file_path] = response.text
            return response.text
        else:
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_info(self, force=False):
        """
        Get the merge request information
        :return: Merge request information
        """
        if self._info_cache and not force:
            return self._info_cache
        # URL for the GitLab API endpoint
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._info_cache = response.json()
            return response.json()
        else:
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_commits(self, force=False):
        """
        Get the commits of the merge request
        :return: commits list
        """
        if hasattr(self, '_commits_cache') and self._commits_cache and not force:
            return self._commits_cache
        # URL for the GitLab API endpoint
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}/commits"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._commits_cache = response.json()
            return response.json()
        else:
            log.error(f"获取MR commits失败: {response.status_code} {response.text}")
            return []

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_commit_changes(self, commit_id, force=False):
        """
        Get the changes of a specific commit
        :param commit_id: The commit SHA
        :return: changes for this commit
        """
        cache_key = f"commit_{commit_id}"
        if hasattr(self, '_commit_changes_cache') and cache_key in self._commit_changes_cache and not force:
            return self._commit_changes_cache[cache_key]
        
        # URL for the GitLab API endpoint
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}/repository/commits/{commit_id}/diff"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            if not hasattr(self, '_commit_changes_cache'):
                self._commit_changes_cache = {}
            self._commit_changes_cache[cache_key] = response.json()
            return response.json()
        else:
            log.error(f"获取commit {commit_id} 变更失败: {response.status_code} {response.text}")
            return []

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def get_existing_notes(self, force=False):
        """
        Get existing notes/comments from the merge request
        :return: notes list
        """
        if hasattr(self, '_notes_cache') and self._notes_cache and not force:
            return self._notes_cache
        
        # URL for the GitLab API endpoint
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}/merge_requests/{self.iid}/notes"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            self._notes_cache = response.json()
            return response.json()
        else:
            log.error(f"获取MR notes失败: {response.status_code} {response.text}")
            return []

    def get_reviewed_commits(self, force=False):
        """
        获取已经被审查过的commit列表
        通过分析现有的评论来判断哪些commits已经被审查过
        :return: 已审查的commit ID列表
        """
        import re
        
        existing_notes = self.get_existing_notes(force)
        if not existing_notes:
            return []
        
        reviewed_commits = set()
        
        for note in existing_notes:
            if note.get('system', False):  # 跳过系统消息
                continue
            
            body = note.get('body', '')
            if not body:
                continue
            
            # 查找评论中的commit ID（通常是8位短ID）
            # 匹配格式如: "🔍 Commit 审查: `12345678`" 或 "Commit 审查: `12345678`"
            commit_matches = re.findall(r'(?:🔍\s*)?[Cc]ommit\s*审查?\s*[：:]\s*`([a-f0-9]{8})`', body)
            if commit_matches:
                reviewed_commits.update(commit_matches)
            
            # 也匹配其他可能的格式
            commit_matches = re.findall(r'`([a-f0-9]{8})`', body)
            if commit_matches:
                reviewed_commits.update(commit_matches)
        
        log.info(f"📋 发现 {len(reviewed_commits)} 个已审查的commits: {list(reviewed_commits)}")
        return list(reviewed_commits)

# gitlab仓库clone和管理
class GitlabRepoManager:
    def __init__(self, project_id, branch_name = ""):
        self.project_id = project_id
        self.timestamp = int(time.time() * 1000)
        self.repo_path = f"./repo/{self.project_id}_{self.timestamp}"
        self.has_cloned = False

    def get_info(self):
        """
        Get the project information
        :return: Project information
        """
        # URL for the GitLab API endpoint
        url = f"{GITLAB_SERVER_URL}/api/v4/projects/{self.project_id}"

        # Headers for the request
        headers = {
            "PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN
        }

        # Make the GET request
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            log.error(f"获取项目信息失败: {response.status_code} {response.text}")
            return None

    @retry(stop_max_attempt_number=3, wait_fixed=2000)
    def shallow_clone(self, branch_name = "main"):
        """
        Perform a shallow clone of the repository
        param branch_name: The name of the branch to clone
        """
        # If the target directory exists, remove it
        self.delete_repo()

        # Build the authenticated URL
        repo_info = self.get_info()
        if not repo_info or "http_url_to_repo" not in repo_info:
            raise ValueError("无法获取仓库信息或http_url_to_repo")
        authenticated_url = self._build_authenticated_url(repo_info["http_url_to_repo"])

        # Build the Git command
        command = ["git", "clone", authenticated_url, "--depth", "1"]
        if branch_name:
            command.extend(["--branch", branch_name])
            command.extend([self.repo_path + "/" + str(branch_name)])
        else:
            command.extend([self.repo_path + "/default"])
        # command 添加clone到的位置：
        if run_command(command) != 0:
            log.error("Failed to clone the repository")
        self.has_cloned = True

    # 切换分支
    def checkout_branch(self, branch_name, force=False):
        # Build the Git command
        if not self.has_cloned:
            self.shallow_clone(branch_name)
        else:
            # 检查是否已经在目标分支上
            if not force and os.path.exists(self.repo_path + "/" + str(branch_name) + "/.git"):
                return
            else:
                self.shallow_clone(branch_name)

    # 删除库
    def delete_repo(self):
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)

    # 查找相关文件列表
    def find_files_by_keyword(self, keyword, branch_name="main"):
        matching_files = []
        regex = re.compile(keyword)
        self.checkout_branch(branch_name)
        for root, _, files in os.walk(self.repo_path + "/" + str(branch_name)):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if regex.search(content):
                            matching_files.append(file_path)
                except (UnicodeDecodeError, FileNotFoundError, PermissionError):
                    # 跳过无法读取的文件
                    continue

        return matching_files


    # 构建带有身份验证信息的 URL
    def _build_authenticated_url(self, repo_url):
        # 如果 URL 使用 https
        token = GITLAB_PRIVATE_TOKEN
        if repo_url.startswith("https://"):
            return f"https://oauth2:{token}@{repo_url[8:]}"
        # 如果 URL 使用 http
        elif repo_url.startswith("http://"):
            return f"http://oauth2:{token}@{repo_url[7:]}"
        else:
            raise ValueError("Unsupported URL scheme")

def is_merge_request_opened(gitlab_payload) -> bool:
    """
    判断是否是需要审查的merge request事件
    支持首次打开和更新事件，但通过其他机制防止重复
    """
    try:
        from config.config import REVIEW_ONLY_ON_FIRST_OPEN, REVIEW_ON_UPDATE
        
        if not gitlab_payload or not isinstance(gitlab_payload, dict):
            return False
            
        object_attributes = gitlab_payload.get("object_attributes")
        if not object_attributes or not isinstance(object_attributes, dict):
            return False
            
        state = object_attributes.get("state")
        merge_status = object_attributes.get("merge_status")
        action = object_attributes.get("action")
        
        if REVIEW_ONLY_ON_FIRST_OPEN:
            # 严格模式：只在MR首次打开时触发
            is_first_open = (
                state == "opened" and 
                merge_status in ["preparing", "unchecked"] and 
                action == "open"
            )
            log.info(f"严格模式检查: {is_first_open}")
            return is_first_open
        else:
            # 灵活模式：根据配置决定是否在更新时审查
            allowed_actions = ["open"]
            if REVIEW_ON_UPDATE:
                allowed_actions.append("update")
            
            is_reviewable = (
                state == "opened" and 
                merge_status in ["preparing", "can_be_merged", "unchecked"] and 
                action in allowed_actions
            )
            
            log.info(f"灵活模式检查: {is_reviewable}")
            return is_reviewable
        
    except Exception as e:
        log.error(f"判断是否是merge request打开事件失败: {e}")
        return False