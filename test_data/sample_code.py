# 示例代码文件 - 包含一些需要审查和修复的问题

def calculate_total(items):
    """计算总价"""
    total = 0
    for item in items:
        total += item['price']  # 缺少数量检查
    return total

def process_user_input(user_input):
    """处理用户输入 - 存在安全问题"""
    # 安全问题：直接执行用户输入
    result = eval(user_input)
    return result

def fetch_data(url):
    """获取数据 - 缺少错误处理"""
    import urllib.request
    response = urllib.request.urlopen(url)
    return response.read()

class UserManager:
    """用户管理器"""
    
    def __init__(self):
        self.users = []
    
    def add_user(self, username, password):
        """添加用户 - 密码明文存储"""
        self.users.append({
            'username': username,
            'password': password  # 安全问题：密码应该加密
        })
    
    def authenticate(self, username, password):
        """认证用户"""
        for user in self.users:
            if user['username'] == username and user['password'] == password:
                return True
        return False
