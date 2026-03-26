"""
DocMCP 使用示例

展示如何使用安全和性能模块。
"""

import time
import threading
from docmcp import (
    # 配置
    SystemConfig, init_config,

    # 沙箱
    SandboxExecutor, sandbox_context, safe_execute,

    # 认证
    AuthManager, Permission, Role, create_auth_manager,

    # 扫描
    ContentScanner, quick_scan, scan_text,

    # 审计
    AuditEventType, AuditLevel, log_event, log_login,

    # 缓存
    MultiLevelCache, cached, get_cache,

    # 连接池
    ConnectionPool, PoolConfig, create_pool,

    # 监控
    get_monitor, record_metric, MetricType, register_health_check,
    AlertRule,

    # 限流
    RateLimiter, rate_limit, check_rate_limit, RateLimitStrategy,
    ConcurrencyLimiter, BackpressureController,
)


# ==================== 配置示例 ====================

def example_config():
    """配置示例"""
    print("=== 配置示例 ===")

    # 从环境变量加载配置
    config = SystemConfig.from_env()
    print(f"应用名称: {config.app_name}")
    print(f"调试模式: {config.debug}")
    print(f"沙箱内存限制: {config.sandbox.max_memory_mb} MB")
    print(f"缓存内存大小: {config.cache.memory_cache_size}")

    # 保存配置到文件
    config.save("/tmp/docmcp_config.json")

    # 从文件加载配置
    loaded_config = SystemConfig.load("/tmp/docmcp_config.json")
    print(f"加载的配置: {loaded_config.app_name}")


# ==================== 沙箱示例 ====================

def example_sandbox():
    """沙箱执行示例"""
    print("\n=== 沙箱执行示例 ===")

    # 使用上下文管理器
    with sandbox_context(max_memory_mb=256, max_execution_time=10.0) as sandbox:
        # 执行Python代码
        code = """
import sys
print("Hello from sandbox!")
print(f"Python version: {sys.version}")
result = 2 + 2
print(f"Result: {result}")
"""
        result = sandbox.execute_code(code)

        print(f"状态: {result.status.value}")
        print(f"返回码: {result.return_code}")
        print(f"执行时间: {result.execution_time:.3f}s")
        print(f"标准输出:\n{result.stdout}")
        if result.stderr:
            print(f"标准错误:\n{result.stderr}")

    # 便捷函数
    result = safe_execute("print('Quick execute')", timeout=5.0)
    print(f"便捷执行结果: {result.status.value}")


# ==================== 认证示例 ====================

def example_auth():
    """认证示例"""
    print("\n=== 认证示例 ===")

    # 创建认证管理器
    auth = create_auth_manager(secret_key="my-secret-key")

    # 注册用户
    success, user, errors = auth.register_user(
        username="john_doe",
        email="john@example.com",
        password="SecurePass123!",
        role=Role.USER
    )

    if success:
        print(f"用户注册成功: {user.username} (ID: {user.id})")

        # 用户认证
        auth_success, tokens, error = auth.authenticate("john_doe", "SecurePass123!")

        if auth_success:
            print(f"认证成功!")
            print(f"访问令牌: {tokens['access_token'][:30]}...")

            # 验证令牌
            user_from_token = auth.get_user_by_token(tokens['access_token'])
            if user_from_token:
                print(f"从令牌获取用户: {user_from_token.username}")

                # 检查权限
                has_permission = user_from_token.has_permission(Permission.READ)
                print(f"有READ权限: {has_permission}")
        else:
            print(f"认证失败: {error}")
    else:
        print(f"注册失败: {errors}")


# ==================== 扫描示例 ====================

def example_scanner():
    """内容扫描示例"""
    print("\n=== 内容扫描示例 ===")

    # 创建扫描器
    scanner = ContentScanner()

    # 扫描文本
    text = """
function test() {
    eval(userInput);  // 危险代码
    var password = "secret123";  // 敏感信息
}
"""
    result = scanner.scan_text(text, source="test.js")

    print(f"扫描状态: {result.status.value}")
    print(f"发现威胁数: {len(result.threats)}")

    for threat in result.threats:
        print(f"  - {threat.name}: {threat.description} (严重度: {threat.severity})")

    # 便捷函数
    text_result = scan_text("var api_key = 'AKIAIOSFODNN7EXAMPLE';")
    print(f"API Key检测: {text_result.status.value}")


# ==================== 审计示例 ====================

def example_audit():
    """审计日志示例"""
    print("\n=== 审计日志示例 ===")

    # 记录登录事件
    log_login(
        user_id="user123",
        username="john_doe",
        ip_address="192.168.1.1",
        success=True
    )

    # 记录自定义事件
    log_event(
        event_type=AuditEventType.CREATE,
        level=AuditLevel.INFO,
        message="Created new document",
        user_id="user123",
        username="john_doe",
        resource_id="doc456",
        resource_type="document",
        details={"title": "My Document", "size": 1024}
    )

    print("审计事件已记录")


# ==================== 缓存示例 ====================

def example_cache():
    """缓存示例"""
    print("\n=== 缓存示例 ===")

    # 获取默认缓存
    cache = get_cache()

    # 设置缓存
    cache.set("user:123", {"name": "John", "age": 30}, ttl=3600)
    cache.set("config:app", {"debug": True, "version": "1.0"})

    # 获取缓存
    user = cache.get("user:123")
    print(f"缓存用户: {user}")

    # 使用装饰器
    @cached(ttl=60, key_prefix="expensive")
    def expensive_operation(n: int) -> int:
        """模拟耗时操作"""
        time.sleep(0.1)
        return n * n

    # 第一次调用（无缓存）
    start = time.time()
    result1 = expensive_operation(5)
    elapsed1 = time.time() - start
    print(f"第一次调用: {result1}, 耗时: {elapsed1:.3f}s")

    # 第二次调用（有缓存）
    start = time.time()
    result2 = expensive_operation(5)
    elapsed2 = time.time() - start
    print(f"第二次调用: {result2}, 耗时: {elapsed2:.3f}s")

    # 获取统计
    stats = cache.get_stats()
    print(f"缓存统计: L1命中 {stats['l1_memory'].hits}, L2命中 {stats['l2_disk'].hits}")


# ==================== 连接池示例 ====================

def example_pool():
    """连接池示例"""
    print("\n=== 连接池示例 ===")

    from docmcp.performance.pool import MockDatabaseConnection, DatabaseConnectionFactory

    # 创建连接工厂
    factory = DatabaseConnectionFactory(
        host="localhost",
        port=5432,
        database="docmcp",
        user="docmcp",
        password="password"
    )

    # 创建连接池
    config = PoolConfig(
        min_connections=2,
        max_connections=10,
        connection_timeout=30.0
    )

    pool = create_pool("database", factory, config)

    # 获取连接
    with pool.acquire() as conn:
        result = conn.execute("SELECT 1")
        print(f"查询结果: {result}")

    # 获取统计
    stats = pool.get_stats()
    print(f"连接池统计: {stats}")


# ==================== 监控示例 ====================

def example_monitor():
    """监控示例"""
    print("\n=== 监控示例 ===")

    monitor = get_monitor()
    monitor.start()

    # 记录指标
    record_metric("requests_total", 100, MetricType.COUNTER, {"method": "GET"})
    record_metric("response_time_ms", 50.5, MetricType.HISTOGRAM, {"endpoint": "/api/users"})
    record_metric("active_connections", 25, MetricType.GAUGE)

    # 注册健康检查
    def check_database():
        # 模拟数据库检查
        return True, "Database is healthy"

    register_health_check("database", check_database, interval=30.0)

    # 添加告警规则
    rule = AlertRule(
        name="high_cpu",
        metric_name="system_cpu_percent",
        condition=">",
        threshold=80.0,
        duration=60.0,
        severity="warning",
        message="CPU usage is high"
    )
    from docmcp.performance.monitor import add_alert_rule
    add_alert_rule(rule)

    # 获取概览
    overview = monitor.get_overview()
    print(f"监控概览: {overview}")

    monitor.stop()


# ==================== 限流示例 ====================

def example_limiter():
    """限流示例"""
    print("\n=== 限流示例 ===")

    # 创建限流器
    limiter = RateLimiter()

    # 配置限流
    from docmcp.performance.limiter import RateLimitConfig
    config = RateLimitConfig(
        rate=10.0,  # 每秒10个请求
        burst=5,    # 突发5个
        strategy=RateLimitStrategy.TOKEN_BUCKET
    )

    # 模拟请求
    allowed_count = 0
    denied_count = 0

    for i in range(20):
        if limiter.allow("api_endpoint", config=config):
            allowed_count += 1
            print(f"请求 {i+1}: 允许")
        else:
            denied_count += 1
            info = limiter.get_info("api_endpoint")
            print(f"请求 {i+1}: 拒绝 (重试时间: {info.retry_after:.2f}s)")
        time.sleep(0.05)  # 50ms间隔

    print(f"\n统计: 允许 {allowed_count}, 拒绝 {denied_count}")

    # 使用装饰器
    @rate_limit(rate=5.0, burst=2)
    def api_call(user_id: str) -> dict:
        return {"user_id": user_id, "data": "some data"}

    try:
        result = api_call("user123")
        print(f"API调用结果: {result}")
    except Exception as e:
        print(f"API调用失败: {e}")

    # 并发限制
    concurrency = ConcurrencyLimiter(max_concurrent=5)

    def worker(n: int):
        if concurrency.acquire(timeout=1.0):
            try:
                print(f"Worker {n} 开始执行")
                time.sleep(0.5)
                print(f"Worker {n} 完成")
            finally:
                concurrency.release()
        else:
            print(f"Worker {n} 获取许可失败")

    # 启动多个工作线程
    threads = []
    for i in range(10):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # 背压控制
    backpressure = BackpressureController(
        threshold=0.8,
        recovery_threshold=0.5
    )

    # 模拟负载
    for load in [0.5, 0.7, 0.85, 0.9, 0.6, 0.4]:
        backpressure.update_load("cpu", load)
        status = backpressure.get_status()
        print(f"负载 {load:.0%}: 背压 {'激活' if status['active'] else '未激活'}")
        time.sleep(0.1)


# ==================== 主函数 ====================

def main():
    """运行所有示例"""
    print("=" * 60)
    print("DocMCP 使用示例")
    print("=" * 60)

    example_config()
    example_sandbox()
    example_auth()
    example_scanner()
    example_audit()
    example_cache()
    example_pool()
    example_monitor()
    example_limiter()

    print("\n" + "=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
