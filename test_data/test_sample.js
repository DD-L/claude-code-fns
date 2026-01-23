// 测试文件示例 - 用于 run_tests function

function calculateTotal(items) {
    let total = 0;
    for (let item of items) {
        total += (item.price || 0) * (item.quantity || 1);
    }
    return total;
}

// 简单的测试框架
function assert(condition, message) {
    if (!condition) {
        throw new Error(`Assertion failed: ${message}`);
    }
}

function test(name, fn) {
    try {
        fn();
        console.log(`✓ ${name}`);
        return true;
    } catch (error) {
        console.error(`✗ ${name}: ${error.message}`);
        return false;
    }
}

// 运行测试
function runTests() {
    let passed = 0;
    let failed = 0;
    
    test('empty list', () => {
        assert(calculateTotal([]) === 0, 'Empty list should return 0');
    }) && passed++ || failed++;
    
    test('single item', () => {
        assert(calculateTotal([{price: 10, quantity: 2}]) === 20, 'Should calculate correctly');
    }) && passed++ || failed++;
    
    test('multiple items', () => {
        assert(calculateTotal([
            {price: 10, quantity: 2},
            {price: 5, quantity: 3}
        ]) === 35, 'Should sum multiple items');
    }) && passed++ || failed++;
    
    console.log(`\nTests: ${passed} passed, ${failed} failed`);
    return failed === 0;
}

if (require.main === module) {
    const success = runTests();
    process.exit(success ? 0 : 1);
}

module.exports = { calculateTotal, runTests };
