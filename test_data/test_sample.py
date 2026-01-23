# 测试文件示例 - 用于 run_tests function

import unittest

def calculate_total(items):
    """计算总价"""
    total = 0
    for item in items:
        total += item.get('price', 0) * item.get('quantity', 1)
    return total

class TestCalculateTotal(unittest.TestCase):
    
    def test_empty_list(self):
        """测试空列表"""
        self.assertEqual(calculate_total([]), 0)
    
    def test_single_item(self):
        """测试单个商品"""
        items = [{'price': 10, 'quantity': 2}]
        self.assertEqual(calculate_total(items), 20)
    
    def test_multiple_items(self):
        """测试多个商品"""
        items = [
            {'price': 10, 'quantity': 2},
            {'price': 5, 'quantity': 3}
        ]
        self.assertEqual(calculate_total(items), 35)
    
    def test_missing_quantity(self):
        """测试缺少数量字段"""
        items = [{'price': 10}]
        self.assertEqual(calculate_total(items), 10)

if __name__ == '__main__':
    unittest.main()
