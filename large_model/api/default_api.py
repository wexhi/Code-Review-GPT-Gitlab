import os
from math import trunc

from unionllm import unionchat

from large_model.abstract_api import AbstractApi


class DefaultApi(AbstractApi):

    def __init__(self):
        self.params = {}
        self.response = None

    def set_config(self, api_config: dict) -> bool:
        if api_config is None:
            raise ValueError("api_config is None")
        for key in api_config:
            # 如果为大写，则写入环境变量
            if key.isupper():
                os.environ[key] = api_config[key]
                continue
            self.params[key] = api_config[key]
            
        # Enable verbose logging for debugging
        os.environ['LITELLM_LOG'] = 'DEBUG'
        
        return True

    def generate_text(self, messages: list) -> bool:
        try:
            self.response = unionchat(messages=messages, **self.params)
        except Exception as e:
            raise e
        return True

    def get_respond_content(self) -> str:
        if self.response is None:
            raise ValueError("Response is None. Call generate_text first.")
        return self.response['choices'][0]['message']['content']

    def get_respond_tokens(self) -> int:
        if self.response is None:
            raise ValueError("Response is None. Call generate_text first.")
        return trunc(int(self.response['usage']['total_tokens']))
