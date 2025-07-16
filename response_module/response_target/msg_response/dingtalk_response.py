import base64
import hashlib
import hmac
import time
import urllib.parse
import requests
import json
from config.config import *
from utils.logger import *
from response_module.abstract_response import AbstractResponseMessage


class DingtalkResponse(AbstractResponseMessage):
    def __init__(self, config):
        super().__init__(config)
        self.type = config['type']
        if self.type == 'merge_request':
            self.project_id = config['project_id']
            self.merge_request_id = config['merge_request_iid']

    def send(self, message):
        # 检查钉钉配置是否有效
        if not DINGDING_BOT_WEBHOOK or not DINGDING_SECRET or DINGDING_BOT_WEBHOOK == "your_dingtalk_webhook_url_here":
            log.info("钉钉配置未设置或无效，跳过钉钉通知")
            return True
            
        if self.type == 'merge_request':
            return self.send_dingtalk_message_by_sign(message)
        else:
            return False

    def send_dingtalk_message_by_sign(self, message_text):
        """
        使用签名方式发送消息通知到钉钉群

        Args:
            message_text (str): 消息文本内容

        Returns:
            bool: 消息是否发送成功
        """
        timestamp = str(round(time.time() * 1000))
        sign = self.__get_sign(timestamp)
        webhookurl = f"{DINGDING_BOT_WEBHOOK}&timestamp={timestamp}&sign={sign}"
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
        }

        # 构建请求体
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": "Gitlab 通知",
                "text": message_text
            },
            "timestamp": timestamp,
            "sign": sign
        }

        # 发送HTTP POST请求
        response = requests.post(
            webhookurl,
            headers=headers,
            data=json.dumps(message)
        )

        # 检查响应
        if response.status_code == 200 and response.json()["errcode"] == 0:
            log.info(f"评论信息发送成功：project_id:{self.project_id}  merge_request_id:{self.merge_request_id}")
            return True
        else:
            log.error(
                f"评论信息发送失败：project_id:{self.project_id}  merge_request_id:{self.merge_request_id} response:{response}")
            return False

    def send_dingtalk_message_by_key_word(self, project_url):
        """
        通过关键词发送

        """
        # 设置钉钉机器人的 Webhook URL
        webhook_url = DINGDING_BOT_WEBHOOK

        # 要发送的消息内容
        message = f"新工程接入\nurl：{project_url}"

        headers = {"Content-Type": "application/json"}
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        response = requests.post(webhook_url, headers=headers, data=json.dumps(payload))
        return response.json()

    def __get_sign(self, timestamp):
        '''
        计算签名
        :param timestamp: 时间戳
        :return: 签名
        '''

        secret = DINGDING_SECRET
        secret_enc = secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return sign

if __name__ == '__main__':
    config = {
        'type': 'merge_request',
        'project_id': 1,
        'merge_request_iid': 1
    }
    dingtalk = DingtalkResponse(config)
    dingtalk.send("test message")