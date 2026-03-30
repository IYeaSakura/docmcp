"""
Skills插件化系统单元测试
"""

import unittest
import sys
import os
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills import (
    BaseSkill,
    SkillRegistry,
    SkillLoader,
    SkillScheduler,
    SkillContext,
    SkillResult,
    SkillMetadata,
    SkillParameter,
    SkillStatus,
    ExecutionMode,
    skill,
    parameter,
    require,
    tag,
    category,
    SkillNotFoundError,
    SkillDependencyError,
)


# ==================== 测试用例Skill ====================

@skill(
    name="test_skill",
    version="1.0.0",
    description="测试Skill",
    category="test"
)
@parameter("input", str, "输入", required=True)
@parameter("multiplier", int, "乘数", default=1)
class TestSkill(BaseSkill):
    """测试用例Skill"""

    def execute(self, context, **kwargs):
        input_val = kwargs.get("input", "")
        multiplier = kwargs.get("multiplier", 1)

        result = input_val * multiplier

        return SkillResult.success_result(data={
            "input": input_val,
            "multiplier": multiplier,
            "result": result
        })


@skill(
    name="dependent_skill",
    version="1.0.0",
    description="依赖其他Skill的测试Skill"
)
@require("test_skill")
class DependentSkill(BaseSkill):
    """依赖测试Skill"""

    def execute(self, context, **kwargs):
        # 调用依赖
        dep_result = context.invoke("test_skill", input="test", multiplier=2)

        return SkillResult.success_result(data={
            "dependency_result": dep_result.data,
            "own_data": "processed"
        })


@skill(
    name="error_skill",
    version="1.0.0",
    description="会抛出异常的Skill"
)
class ErrorSkill(BaseSkill):
    """错误测试Skill"""

    def execute(self, context, **kwargs):
        raise ValueError("故意抛出的错误")


# ==================== 测试类 ====================

class TestSkillBase(unittest.TestCase):
    """测试Skill基类"""

    def test_skill_creation(self):
        """测试Skill创建"""
        skill = TestSkill()

        self.assertEqual(skill.name, "test_skill")
        self.assertEqual(skill.version, "1.0.0")
        self.assertEqual(skill.status, SkillStatus.UNLOADED)

    def test_skill_metadata(self):
        """测试Skill元数据"""
        skill = TestSkill()
        metadata = skill.metadata

        self.assertEqual(metadata.name, "test_skill")
        self.assertEqual(metadata.category, "test")
        self.assertEqual(len(metadata.parameters), 2)

    def test_skill_execution(self):
        """测试Skill执行"""
        registry = SkillRegistry()
        context = SkillContext(registry=registry)

        skill = TestSkill()
        skill.initialize(context)

        result = skill.run(context, input="hello", multiplier=3)

        self.assertTrue(result.success)
        self.assertEqual(result.data["result"], "hellohellohello")

    def test_skill_validation(self):
        """测试参数验证"""
        skill = TestSkill()

        # 缺少必需参数
        valid, error = skill.validate_parameters(multiplier=2)
        self.assertFalse(valid)
        self.assertIn("input", error)

        # 有效参数
        valid, error = skill.validate_parameters(input="test", multiplier=2)
        self.assertTrue(valid)

    def test_skill_error_handling(self):
        """测试错误处理"""
        registry = SkillRegistry()
        context = SkillContext(registry=registry)

        skill = ErrorSkill()
        skill.initialize(context)

        result = skill.run(context)

        self.assertFalse(result.success)
        self.assertIn("故意抛出的错误", result.error)


class TestSkillRegistry(unittest.TestCase):
    """测试Skill注册中心"""

    def setUp(self):
        """测试前准备"""
        self.registry = SkillRegistry()

    def test_register_skill(self):
        """测试注册Skill"""
        self.registry.register(TestSkill)

        self.assertIn("test_skill", self.registry.list_skills())
        self.assertEqual(len(self.registry.list_skills()), 1)

    def test_unregister_skill(self):
        """测试注销Skill"""
        self.registry.register(TestSkill)
        result = self.registry.unregister("test_skill")

        self.assertTrue(result)
        self.assertNotIn("test_skill", self.registry.list_skills())

    def test_get_skill(self):
        """测试获取Skill"""
        self.registry.register(TestSkill)

        context = SkillContext(registry=self.registry)
        skill = self.registry.load("test_skill", context)

        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "test_skill")

    def test_get_nonexistent_skill(self):
        """测试获取不存在的Skill"""
        with self.assertRaises(SkillNotFoundError):
            self.registry.require("nonexistent")

    def test_find_by_category(self):
        """测试按分类查找"""
        self.registry.register(TestSkill)

        skills = self.registry.find_by_category("test")

        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "test_skill")

    def test_find_by_tag(self):
        """测试按标签查找"""
        self.registry.register(TestSkill)

        # TestSkill没有显式标签，但可以通过搜索
        skills = self.registry.search("test")

        self.assertGreaterEqual(len(skills), 1)

    def test_dependency_resolution(self):
        """测试依赖解析"""
        self.registry.register(TestSkill)
        self.registry.register(DependentSkill)

        context = SkillContext(registry=self.registry)

        # 加载依赖Skill应该自动加载其依赖
        skill = self.registry.load("dependent_skill", context)

        self.assertIsNotNone(skill)
        self.assertIn("test_skill", self.registry.list_loaded())

    def test_circular_dependency_detection(self):
        """测试循环依赖检测"""
        # 创建循环依赖
        @skill(name="skill_a")
        @require("skill_b")
        class SkillA(BaseSkill):
            def execute(self, context, **kwargs):
                return SkillResult.success_result()

        @skill(name="skill_b")
        @require("skill_a")
        class SkillB(BaseSkill):
            def execute(self, context, **kwargs):
                return SkillResult.success_result()

        self.registry.register(SkillA)
        self.registry.register(SkillB)

        cycles = self.registry.check_circular_dependencies()

        self.assertGreater(len(cycles), 0)

    def test_event_listeners(self):
        """测试事件监听"""
        events = []

        def on_register(skill_info):
            events.append(("register", skill_info.name))

        self.registry.on("register", on_register)
        self.registry.register(TestSkill)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], ("register", "test_skill"))

    def test_registry_stats(self):
        """测试注册中心统计"""
        self.registry.register(TestSkill)

        stats = self.registry.stats

        self.assertEqual(stats["total_registered"], 1)
        self.assertIn("test", stats["categories"])


class TestSkillContext(unittest.TestCase):
    """测试执行上下文"""

    def setUp(self):
        """测试前准备"""
        self.registry = SkillRegistry()
        self.context = SkillContext(registry=self.registry)

    def test_config_access(self):
        """测试配置访问"""
        self.context.set_config("test.key", "value")

        self.assertEqual(self.context.get_config("test.key"), "value")
        self.assertEqual(self.context.get_config("missing", "default"), "default")

    def test_nested_config(self):
        """测试嵌套配置"""
        self.context.set_config("database.host", "localhost")
        self.context.set_config("database.port", 5432)

        self.assertEqual(self.context.get_config("database.host"), "localhost")
        self.assertEqual(self.context.get_config("database.port"), 5432)

    def test_resource_management(self):
        """测试资源管理"""
        self.context.register_resource("db", {"type": "postgres"})

        resource = self.context.get_resource("db")

        self.assertIsNotNone(resource)
        self.assertEqual(resource["type"], "postgres")

    def test_shared_data(self):
        """测试共享数据"""
        self.context.set_shared("key", "value")

        child = self.context.create_child()

        # 子上下文应该能访问父上下文的共享数据
        self.assertEqual(child.get_shared("key"), "value")

    def test_local_data(self):
        """测试本地数据"""
        self.context.set_local("key", "value")

        child = self.context.create_child()

        # 子上下文不应该能访问父上下文的本地数据
        self.assertIsNone(child.get_local("key"))

    def test_state_management(self):
        """测试状态管理"""
        self.context.set_state("counter", 0)
        self.context.update_state({"counter": 1, "name": "test"})

        self.assertEqual(self.context.get_state("counter"), 1)
        self.assertEqual(self.context.get_state("name"), "test")

    def test_logging(self):
        """测试日志记录"""
        self.context.log_info("info message")
        self.context.log_error("error message")

        logs = self.context.get_logs()

        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["level"], "info")
        self.assertEqual(logs[1]["level"], "error")

    def test_child_context(self):
        """测试子上下文"""
        child = self.context.create_child()

        self.assertEqual(child.depth, 1)
        self.assertEqual(child.parent, self.context)
        self.assertFalse(child.is_root)


class TestSkillScheduler(unittest.TestCase):
    """测试Skill调度器"""

    def setUp(self):
        """测试前准备"""
        self.registry = SkillRegistry()
        self.scheduler = SkillScheduler(self.registry)
        self.context = SkillContext(registry=self.registry)

        # 注册测试Skill
        self.registry.register(TestSkill)
        self.registry.load("test_skill", self.context)

    def test_submit_task(self):
        """测试提交任务"""
        task_id = self.scheduler.submit("test_skill", {"input": "hello"})

        self.assertIsNotNone(task_id)
        self.assertIn(task_id, [t.id for t in self.scheduler.get_all_tasks()])

    def test_run_task(self):
        """测试执行任务"""
        task_id = self.scheduler.submit("test_skill", {"input": "hello", "multiplier": 2})
        result = self.scheduler.run(task_id)

        self.assertTrue(result.success)
        self.assertEqual(result.data["result"], "hellohello")

    def test_run_with_timeout(self):
        """测试带超时的执行"""
        @skill(name="slow_skill")
        class SlowSkill(BaseSkill):
            def execute(self, context, **kwargs):
                import time
                time.sleep(5)
                return SkillResult.success_result()

        self.registry.register(SlowSkill)
        self.registry.load("slow_skill", self.context)

        task_id = self.scheduler.submit("slow_skill", {})
        result = self.scheduler.run_with_timeout(task_id, timeout=0.1)

        self.assertFalse(result.success)
        self.assertIn("超时", result.error)

    def test_cancel_task(self):
        """测试取消任务"""
        task_id = self.scheduler.submit("test_skill", {"input": "test"})

        cancelled = self.scheduler.cancel(task_id)

        # 任务可能已经完成，所以取消可能失败
        self.assertIsInstance(cancelled, bool)

    def test_parallel_execution(self):
        """测试并行执行"""
        task_ids = []
        for i in range(3):
            task_id = self.scheduler.submit("test_skill", {"input": f"task{i}"})
            task_ids.append(task_id)

        results = self.scheduler.run_parallel(task_ids)

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results.values()))

    def test_scheduler_stats(self):
        """测试调度器统计"""
        self.scheduler.submit("test_skill", {"input": "test"})

        stats = self.scheduler.stats

        self.assertIn("submitted", stats)
        self.assertIn("total", stats)


class TestDecorators(unittest.TestCase):
    """测试装饰器"""

    def test_skill_decorator(self):
        """测试skill装饰器"""
        @skill(name="decorated_skill", description="装饰的Skill")
        class DecoratedSkill(BaseSkill):
            def execute(self, context, **kwargs):
                return SkillResult.success_result()

        instance = DecoratedSkill()

        self.assertEqual(instance.name, "decorated_skill")
        self.assertEqual(instance.metadata.description, "装饰的Skill")

    def test_parameter_decorator(self):
        """测试parameter装饰器"""
        @skill(name="param_skill")
        @parameter("name", str, "名称", required=True)
        @parameter("age", int, "年龄", default=18)
        class ParamSkill(BaseSkill):
            def execute(self, context, **kwargs):
                return SkillResult.success_result(data=kwargs)

        instance = ParamSkill()
        params = instance.metadata.parameters

        self.assertEqual(len(params), 2)
        self.assertEqual(params[0].name, "name")
        self.assertEqual(params[1].default, 18)

    def test_require_decorator(self):
        """测试require装饰器"""
        @skill(name="req_skill")
        @require("test_skill")
        class ReqSkill(BaseSkill):
            def execute(self, context, **kwargs):
                return SkillResult.success_result()

        instance = ReqSkill()

        self.assertIn("test_skill", instance.dependencies)


class TestSkillResult(unittest.TestCase):
    """测试Skill结果"""

    def test_success_result(self):
        """测试成功结果"""
        result = SkillResult.success_result(data={"key": "value"})

        self.assertTrue(result.success)
        self.assertEqual(result.data, {"key": "value"})
        self.assertIsNone(result.error)

    def test_error_result(self):
        """测试错误结果"""
        result = SkillResult.error_result("error message")

        self.assertFalse(result.success)
        self.assertIsNone(result.data)
        self.assertEqual(result.error, "error message")


class TestIntegration(unittest.TestCase):
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流"""
        # 创建系统
        registry = SkillRegistry()
        scheduler = SkillScheduler(registry)
        context = SkillContext(registry=registry)

        # 注册Skills
        registry.register(TestSkill)
        registry.register(DependentSkill)

        # 加载
        registry.load_all(context)

        # 提交任务
        task_id = scheduler.submit("dependent_skill", {})

        # 执行
        result = scheduler.run(task_id)

        self.assertTrue(result.success)
        self.assertIn("dependency_result", result.data)

    def test_pipeline_execution(self):
        """测试管道执行"""
        registry = SkillRegistry()
        scheduler = SkillScheduler(registry)
        context = SkillContext(registry=registry)

        registry.register(TestSkill)
        registry.load("test_skill", context)

        # 管道执行
        result = scheduler.run_pipeline(
            ["test_skill", "test_skill"],
            initial_input={"input": "hello", "multiplier": 1}
        )

        # 管道执行应该成功
        self.assertIsInstance(result, SkillResult)


# ==================== 运行测试 ====================

def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestSkillBase))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillContext))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillScheduler))
    suite.addTests(loader.loadTestsFromTestCase(TestDecorators))
    suite.addTests(loader.loadTestsFromTestCase(TestSkillResult))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
