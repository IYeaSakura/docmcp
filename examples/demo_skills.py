"""
Skills插件化系统演示脚本

展示如何使用Skills系统的各种功能。
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills import (
    # 核心组件
    BaseSkill,
    SkillRegistry,
    SkillLoader,
    SkillScheduler,
    SkillContext,
    SkillResult,

    # 装饰器
    skill,
    parameter,
    require,
    tag,
    category,

    # 便捷函数
    create_skill_system,
    quick_execute,
)


# ==================== 1. 定义自定义Skill ====================

@skill(
    name="hello_world",
    version="1.0.0",
    description="简单的问候Skill",
    author="Demo",
    category="demo"
)
@parameter("name", str, "用户名", default="World")
@parameter("greeting", str, "问候语", default="Hello")
@tag("demo", "simple")
class HelloWorldSkill(BaseSkill):
    """简单的问候Skill示例"""

    def execute(self, context, **kwargs):
        name = kwargs.get("name", "World")
        greeting = kwargs.get("greeting", "Hello")

        message = f"{greeting}, {name}!"

        context.log_info(f"生成问候语: {message}")

        return SkillResult.success_result(data={
            "message": message,
            "name": name,
            "greeting": greeting
        })


@skill(
    name="text_processor",
    version="1.0.0",
    description="文本处理Skill",
    category="text_processing"
)
@parameter("text", str, "输入文本", required=True)
@parameter("operation", str, "操作类型", default="upper", choices=["upper", "lower", "reverse", "count"])
@require("hello_world")  # 声明依赖
class TextProcessorSkill(BaseSkill):
    """文本处理Skill示例"""

    def execute(self, context, **kwargs):
        text = kwargs.get("text", "")
        operation = kwargs.get("operation", "upper")

        # 调用依赖的Skill
        hello_result = context.invoke("hello_world", name="User")
        context.log_info(f"依赖Skill结果: {hello_result.data}")

        # 执行操作
        if operation == "upper":
            result = text.upper()
        elif operation == "lower":
            result = text.lower()
        elif operation == "reverse":
            result = text[::-1]
        elif operation == "count":
            result = len(text)
        else:
            return SkillResult.error_result(f"未知操作: {operation}")

        return SkillResult.success_result(data={
            "input": text,
            "operation": operation,
            "result": result,
            "greeting": hello_result.data.get("message")
        })


@skill(
    name="data_transformer",
    version="1.0.0",
    description="数据转换Skill",
    category="data_processing"
)
@parameter("data", dict, "输入数据", required=True)
@parameter("transform", str, "转换类型", default="flatten")
class DataTransformerSkill(BaseSkill):
    """数据转换Skill示例"""

    def execute(self, context, **kwargs):
        data = kwargs.get("data", {})
        transform = kwargs.get("transform", "flatten")

        if transform == "flatten":
            result = self._flatten_dict(data)
        elif transform == "nest":
            separator = kwargs.get("separator", ".")
            result = self._nest_dict(data, separator)
        else:
            return SkillResult.error_result(f"未知转换: {transform}")

        return SkillResult.success_result(data={
            "input": data,
            "transform": transform,
            "result": result
        })

    def _flatten_dict(self, d, parent_key='', sep='.'):
        """扁平化字典"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

    def _nest_dict(self, d, sep='.'):
        """嵌套化字典"""
        result = {}
        for key, value in d.items():
            parts = key.split(sep)
            current = result
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = value
        return result


# ==================== 2. 演示基本用法 ====================

def demo_basic_usage():
    """演示基本用法"""
    print("=" * 60)
    print("演示1: 基本用法")
    print("=" * 60)

    # 创建注册中心
    registry = SkillRegistry()

    # 注册Skill
    registry.register(HelloWorldSkill)
    print(f"✓ 注册Skill: hello_world")

    # 创建上下文
    context = SkillContext(registry=registry)

    # 加载并执行Skill
    skill = registry.load("hello_world", context)
    result = skill.run(context, name="Alice", greeting="Hi")

    print(f"✓ 执行结果: {result.data}")
    print(f"✓ 执行成功: {result.success}")
    print()


# ==================== 3. 演示依赖注入 ====================

def demo_dependency_injection():
    """演示依赖注入"""
    print("=" * 60)
    print("演示2: 依赖注入")
    print("=" * 60)

    # 创建系统
    registry = SkillRegistry()
    context = SkillContext(registry=registry)

    # 注册依赖的Skill
    registry.register(HelloWorldSkill)
    print(f"✓ 注册依赖Skill: hello_world")

    # 注册主Skill
    registry.register(TextProcessorSkill)
    print(f"✓ 注册主Skill: text_processor")

    # 加载并执行
    skill = registry.load("text_processor", context)
    result = skill.run(context, text="Hello World", operation="reverse")

    print(f"✓ 执行结果: {result.data}")
    print()


# ==================== 4. 演示调度器 ====================

def demo_scheduler():
    """演示调度器"""
    print("=" * 60)
    print("演示3: 任务调度")
    print("=" * 60)

    # 创建系统
    registry = SkillRegistry()
    scheduler = SkillScheduler(registry)
    context = SkillContext(registry=registry)

    # 注册Skills
    registry.register(HelloWorldSkill)
    registry.register(TextProcessorSkill)

    # 加载Skills
    registry.load("hello_world", context)
    registry.load("text_processor", context)

    # 提交任务
    task1_id = scheduler.submit("hello_world", {"name": "User1"})
    task2_id = scheduler.submit("hello_world", {"name": "User2"})
    task3_id = scheduler.submit(
        "text_processor",
        {"text": "Python", "operation": "upper"}
    )
    print(f"✓ 提交3个任务")

    # 执行所有任务
    results = scheduler.run_all()

    for task_id, result in results.items():
        print(f"✓ 任务 {task_id[:8]}...: {result.data if result.success else result.error}")

    print()


# ==================== 5. 演示管道执行 ====================

def demo_pipeline():
    """演示管道执行"""
    print("=" * 60)
    print("演示4: 管道执行")
    print("=" * 60)

    # 创建系统
    registry = SkillRegistry()
    scheduler = SkillScheduler(registry)
    context = SkillContext(registry=registry)

    # 注册Skills
    registry.register(HelloWorldSkill)
    registry.register(TextProcessorSkill)

    # 加载Skills
    registry.load("hello_world", context)
    registry.load("text_processor", context)

    # 管道执行
    # 注意：这里需要Skill支持管道输入输出
    print(f"✓ 管道执行示例")
    print(f"  步骤1: hello_world -> 生成问候")
    print(f"  步骤2: text_processor -> 处理文本")
    print()


# ==================== 6. 演示内置Skills ====================

def demo_builtin_skills():
    """演示内置Skills"""
    print("=" * 60)
    print("演示5: 内置Skills")
    print("=" * 60)

    # 使用便捷函数创建完整系统
    registry, loader, scheduler, context = create_skill_system(
        auto_discover=True,
        config={"test": True}
    )

    print(f"✓ 系统自动发现内置Skills")
    print(f"  已注册Skills: {registry.list_skills()}")

    # 加载内置Skills
    registry.load_all(context)

    print(f"✓ 已加载Skills: {registry.list_loaded()}")
    print()


# ==================== 7. 演示配置管理 ====================

def demo_configuration():
    """演示配置管理"""
    print("=" * 60)
    print("演示6: 配置管理")
    print("=" * 60)

    # 创建带配置的上下文
    config = {
        "app": {
            "name": "Demo App",
            "version": "1.0.0"
        },
        "database": {
            "host": "localhost",
            "port": 5432
        }
    }

    context = SkillContext(config=config)

    # 访问配置
    print(f"✓ 应用名称: {context.get_config('app.name')}")
    print(f"✓ 数据库主机: {context.get_config('database.host')}")
    print(f"✓ 不存在的键: {context.get_config('missing.key', 'default')}")

    # 设置配置
    context.set_config("new.key", "new_value")
    print(f"✓ 新配置: {context.get_config('new.key')}")
    print()


# ==================== 8. 演示资源共享 ====================

def demo_resource_sharing():
    """演示资源共享"""
    print("=" * 60)
    print("演示7: 资源共享")
    print("=" * 60)

    context = SkillContext()

    # 注册资源
    context.register_resource("database", {"type": "postgres", "connected": True})
    context.register_resource("cache", {"type": "redis", "size": 1000})

    # 获取资源
    db = context.get_resource("database")
    cache = context.get_resource("cache")

    print(f"✓ 数据库资源: {db}")
    print(f"✓ 缓存资源: {cache}")
    print(f"✓ 不存在的资源: {context.get_resource('missing')}")

    # 创建子上下文
    child = context.create_child()
    print(f"✓ 子上下文可以访问父资源: {child.get_resource('database')}")
    print()


# ==================== 9. 演示事件监听 ====================

def demo_event_listeners():
    """演示事件监听"""
    print("=" * 60)
    print("演示8: 事件监听")
    print("=" * 60)

    registry = SkillRegistry()

    # 注册事件监听器
    def on_register(skill_info):
        print(f"  [事件] Skill注册: {skill_info.name}")

    def on_load(skill_info):
        print(f"  [事件] Skill加载: {skill_info.name}")

    registry.on("register", on_register)
    registry.on("load", on_load)

    # 注册和加载Skill
    registry.register(HelloWorldSkill)

    context = SkillContext(registry=registry)
    registry.load("hello_world", context)

    print()


# ==================== 10. 演示统计信息 ====================

def demo_statistics():
    """演示统计信息"""
    print("=" * 60)
    print("演示9: 统计信息")
    print("=" * 60)

    registry = SkillRegistry()
    context = SkillContext(registry=registry)

    # 注册多个Skills
    registry.register(HelloWorldSkill)
    registry.register(TextProcessorSkill)
    registry.register(DataTransformerSkill)

    # 加载并执行
    registry.load_all(context)

    # 执行几次
    for i in range(3):
        skill = registry.get("hello_world")
        skill.run(context, name=f"User{i}")

    # 查看统计
    print(f"✓ 注册中心统计:")
    print(f"  {registry.stats}")

    skill = registry.get("hello_world")
    print(f"✓ Skill统计:")
    print(f"  {skill.stats}")
    print()


# ==================== 11. 演示完整工作流 ====================

def demo_complete_workflow():
    """演示完整工作流"""
    print("=" * 60)
    print("演示10: 完整工作流")
    print("=" * 60)

    # 创建完整系统
    registry, loader, scheduler, context = create_skill_system(auto_discover=True)

    # 注册自定义Skills
    registry.register(HelloWorldSkill)
    registry.register(TextProcessorSkill)
    registry.register(DataTransformerSkill)

    print(f"✓ 系统初始化完成")
    print(f"  已注册Skills: {len(registry.list_skills())}")

    # 加载所有Skills
    load_results = registry.load_all(context)
    print(f"✓ 加载完成")
    print(f"  成功: {sum(1 for r in load_results.values() if r.success)}")
    print(f"  失败: {sum(1 for r in load_results.values() if not r.success)}")

    # 提交任务
    scheduler.submit("hello_world", {"name": "Alice"}, priority=1)
    scheduler.submit("text_processor", {"text": "Hello", "operation": "upper"}, priority=2)
    scheduler.submit("data_transformer", {
        "data": {"a": {"b": 1, "c": 2}},
        "transform": "flatten"
    }, priority=3)

    print(f"✓ 提交3个任务")

    # 执行
    results = scheduler.run_all()

    print(f"✓ 执行结果:")
    for task_id, result in results.items():
        status = "✓" if result.success else "✗"
        print(f"  {status} {task_id[:8]}...: {result.data if result.success else result.error}")

    print()


# ==================== 主函数 ====================

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Skills插件化系统演示")
    print("=" * 60 + "\n")

    try:
        demo_basic_usage()
    except Exception as e:
        print(f"✗ 基本用法演示失败: {e}")

    try:
        demo_dependency_injection()
    except Exception as e:
        print(f"✗ 依赖注入演示失败: {e}")

    try:
        demo_scheduler()
    except Exception as e:
        print(f"✗ 调度器演示失败: {e}")

    try:
        demo_pipeline()
    except Exception as e:
        print(f"✗ 管道执行演示失败: {e}")

    try:
        demo_builtin_skills()
    except Exception as e:
        print(f"✗ 内置Skills演示失败: {e}")

    try:
        demo_configuration()
    except Exception as e:
        print(f"✗ 配置管理演示失败: {e}")

    try:
        demo_resource_sharing()
    except Exception as e:
        print(f"✗ 资源共享演示失败: {e}")

    try:
        demo_event_listeners()
    except Exception as e:
        print(f"✗ 事件监听演示失败: {e}")

    try:
        demo_statistics()
    except Exception as e:
        print(f"✗ 统计信息演示失败: {e}")

    try:
        demo_complete_workflow()
    except Exception as e:
        print(f"✗ 完整工作流演示失败: {e}")

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
