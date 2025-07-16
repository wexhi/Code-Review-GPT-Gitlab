import json
import threading

from flask import request, jsonify

from gitlab_integration.gitlab_fetcher import GitlabMergeRequestFetcher, GitlabRepoManager
from response_module.response_controller import ReviewResponse
from review_engine.review_engine import ReviewEngine
from utils.logger import log
from gitlab_integration.gitlab_fetcher import is_merge_request_opened

class WebhookListener:
    def __init__(self):
        pass

    def handle_webhook(self):
        """
        处理webhook的请求
        :return:
        """
        gitlab_payload = request.data.decode('utf-8')
        gitlab_payload = json.loads(gitlab_payload)
        
        # 提取关键信息用于日志
        event_type = gitlab_payload.get('object_kind')
        if event_type == 'merge_request':
            object_attributes = gitlab_payload.get('object_attributes', {})
            project_info = gitlab_payload.get('project', {})
            log.info(f"📋 MR #{object_attributes.get('iid', 'Unknown')} - {object_attributes.get('title', 'Unknown')} (项目: {project_info.get('name', 'Unknown')})")
            log.info(f"📊 状态: {object_attributes.get('state')}/{object_attributes.get('action')}/{object_attributes.get('merge_status')}")
        else:
            log.info(f"📋 收到Webhook: {event_type}")
        
        return self.call_handle(gitlab_payload, event_type)

    def call_handle(self, gitlab_payload, event_type):
        if event_type == 'merge_request':
            config = {
                'type': 'merge_request',
                'project_id': gitlab_payload.get('project')['id'],
                'merge_request_iid': gitlab_payload.get('object_attributes')['iid']
            }
            reply = ReviewResponse(config)
            return self.handle_merge_request(gitlab_payload, reply)
        elif event_type == 'push':
            config = {
                'type': 'push',
                'project_id': gitlab_payload.get('project')['id']
            }
            reply = ReviewResponse(config)

            return self.handle_push(gitlab_payload, reply)
        else:
            config = {
                'type': 'other',
                'project_id': gitlab_payload.get('project')['id']
            }
            reply = ReviewResponse(config)
            return self.handle_other(gitlab_payload, reply)

    def handle_merge_request(self, gitlab_payload, reply):
        """
        处理合并请求事件
        """
        if is_merge_request_opened(gitlab_payload):
            project_id = gitlab_payload.get('project')['id']
            merge_request_iid = gitlab_payload.get("object_attributes")["iid"]
            log.info(f"🚀 开始处理MR #{merge_request_iid}")
            review_engine = ReviewEngine(reply)
            gitlabMergeRequestFetcher = GitlabMergeRequestFetcher(project_id, merge_request_iid)
            gitlabRepoManager = GitlabRepoManager(project_id)
            thread = threading.Thread(target=review_engine.handle_merge, args=(gitlabMergeRequestFetcher, gitlabRepoManager, gitlab_payload))
            thread.start()

            return jsonify({'status': 'success'}), 200
        return jsonify({'status': 'do not need check'}), 200

    def handle_push(self, gitlab_payload, reply):
        """
        处理推送事件
        """

        return jsonify({'status': 'success'}), 200

    def handle_other(self, gitlab_payload, reply):
        """
        处理其他事件
        """
        event_type = gitlab_payload.get('object_kind')
        log.info(f"Unhandled event type: {event_type}")
        return jsonify({'status': 'unhandled event type'}), 200

webhook_listener = WebhookListener()