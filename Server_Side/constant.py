import os
import atexit
import secrets


main_dir = os.path.dirname(os.path.abspath(__file__))


templates_path = os.path.abspath(os.path.join(main_dir, "templates"))


email_config = {
    "EMAIL_HOST": '您自己邮箱的SMTP',
    "EMAIL_PORT": 0,#您自己邮箱的PORT
    "EMAIL_USER": '您自己的邮箱',
    "EMAIL_PWD": '您自己邮箱的PWD授权码'
}


LEARNER_REDIS_URL = "redis://localhost:6379/0"
ADMIN_REDIS_URL = "redis://localhost:6379/1"
WORD_QUESTION_URL = "redis://localhost:6379/2"


num_workers = 4






ROUTE_FILE = "admin_route.txt"

def get_admin_route():
    if os.path.exists(ROUTE_FILE):
        with open(ROUTE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()

    route = secrets.token_hex(8)
    with open(ROUTE_FILE, "w", encoding="utf-8") as f:
        f.write(route)
    return route
    
    

subject_evaluter_api_config = {
    "api_key": "将这串秘钥换成您自己的",
    "base_url": "https://api.siliconflow.cn/v1",
    "model": "deepseek-ai/DeepSeek-V3",
    "temperature": 0.1,
    "max_tokens": 1024,
    "stream": False 
}


