// 示例 JavaScript 代码 - 包含一些需要审查的问题

function calculateTotal(items) {
    // 性能问题：没有使用 reduce
    let total = 0;
    for (let i = 0; i < items.length; i++) {
        total += items[i].price;
    }
    return total;
}

function processUserInput(userInput) {
    // 安全问题：使用 eval
    return eval(userInput);
}

async function fetchData(url) {
    // 缺少错误处理
    const response = await fetch(url);
    return await response.json();
}

class UserManager {
    constructor() {
        this.users = [];
    }
    
    addUser(username, password) {
        // 安全问题：密码明文存储
        this.users.push({
            username: username,
            password: password
        });
    }
    
    authenticate(username, password) {
        // 性能问题：线性搜索
        for (let user of this.users) {
            if (user.username === username && user.password === password) {
                return true;
            }
        }
        return false;
    }
}
