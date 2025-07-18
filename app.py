import os
import socket
from flask import Flask, jsonify, make_response
from app.gitlab_webhook import git
from utils.args_check import check_config
from utils.logger import log

app = Flask(__name__)
app.config['debug'] = True

# router group
app.register_blueprint(git, url_prefix='/git')


def get_local_ip():
    """获取本地IP地址"""
    # 在Docker环境中，优先使用环境变量中的宿主机IP
    host_ip = os.getenv('HOST_IP')
    if host_ip:
        return host_ip
    
    try:
        # 连接到一个远程地址来获取本地IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except:
        return "localhost"


def is_docker():
    """检测是否在Docker环境中运行"""
    return os.path.exists('/.dockerenv') or os.getenv('DOCKER_ENV') == 'true'


def print_webhook_info():
    """打印webhook配置信息"""
    is_docker_env = is_docker()
    local_ip = get_local_ip()
    
    # 获取GitLab服务器URL
    gitlab_url = os.getenv('GITLAB_SERVER_URL', 'https://gitlab.com')
    
    print("\n" + "="*80)
    print("🚀 AI Code Review 服务已启动!")
    print("="*80)
    
    if is_docker_env:
        print("📦 运行环境: Docker容器")
        print("🌐 容器内部端口: 80")
        print("🔗 宿主机端口: 8080")
        print("\n📋 GitLab Webhook 配置:")
        print("┌─────────────────────────────────────────────────────────────────┐")
        print("│  请在您的GitLab项目中配置以下Webhook URL:                        │")
        print("│                                                                 │")
        print("│  🔗 本地测试:                                                    │")
        print("│     http://localhost:8080/git/webhook                          │")
        print("│                                                                 │")
        print("│  🔗 同网络访问:                                                  │")
        print(f"│     http://{local_ip}:8080/git/webhook                          │")
        print("│                                                                 │")
        print("│  🔗 公网访问:                                                    │")
        print("│     http://your-domain.com:8080/git/webhook                    │")
        print("│                                                                 │")
        print("│  ⚙️  配置步骤:                                                    │")
        print("│     1. 进入GitLab项目 → Settings → Webhooks                    │")
        print("│     2. 填入上述URL之一                                          │")
        print("│     3. 勾选 'Merge request events'                             │")
        print("│     4. 保存并测试                                               │")
        print("└─────────────────────────────────────────────────────────────────┘")
    else:
        print("💻 运行环境: 本地开发")
        print("🌐 监听地址: 0.0.0.0:80")
        print("\n📋 GitLab Webhook 配置:")
        print("┌─────────────────────────────────────────────────────────────────┐")
        print("│  请在您的GitLab项目中配置以下Webhook URL:                        │")
        print("│                                                                 │")
        print("│  🔗 本地访问:                                                    │")
        print("│     http://localhost:80/git/webhook                            │")
        print("│                                                                 │")
        print("│  🔗 局域网访问:                                                  │")
        print(f"│     http://{local_ip}:80/git/webhook                            │")
        print("└─────────────────────────────────────────────────────────────────┘")
    
    print(f"\n🔧 GitLab服务器: {gitlab_url}")
    print("📝 查看实时日志以监控webhook调用")
    print("🎯 创建Merge Request来测试AI代码审查功能")
    print("="*80)
    print("")
    
    # 记录到日志
    log.info("🚀 AI Code Review服务启动完成")
    log.info(f"🌐 运行环境: {'Docker容器' if is_docker_env else '本地开发'}")
    log.info(f"🔗 Webhook URL: http://{local_ip}:{'8080' if is_docker_env else '80'}/git/webhook")
    log.info(f"🔧 GitLab服务器: {gitlab_url}")


@app.errorhandler(400)
@app.errorhandler(404)
def handle_error(error):
    error_msg = 'Args Error' if error.code == 400 else 'Page Not Found'
    return make_response(jsonify({'code': error.code, 'msg': error_msg}), error.code)


if __name__ == '__main__':
    os.environ['STABILITY_HOST'] = 'grpc.stability.ai:443'
    app.config['JSON_AS_ASCII'] = False
    log.info('Starting args check...')
    check_config()
    log.info('Starting the app...')
    
    # 显示webhook配置信息
    print_webhook_info()
    
    app.run(debug=True, host="0.0.0.0", port=80, use_reloader=False)
