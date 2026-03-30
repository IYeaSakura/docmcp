#!/usr/bin/env python3
"""
生成测试用的文档文件
"""

import os
from pathlib import Path


def generate_test_files():
    """生成测试文件"""
    output_dir = Path(__file__).parent

    # 创建测试目录
    output_dir.mkdir(parents=True, exist_ok=True)

    print("生成测试文件...")

    # 由于需要外部依赖来创建真实的Office文档，
    # 这里我们创建一些简单的测试文件

    # 创建纯文本文件（用于基本测试）
    text_content = """This is a test document.
It contains multiple lines.
Used for testing document processing.
"""

    # 创建不同扩展名的测试文件
    test_files = {
        "sample.txt": text_content,
        "sample.md": "# Test Document\n\nThis is a test.",
        "sample.json": '{"test": true, "content": "sample"}',
        "sample.xml": '<?xml version="1.0"?><root><test>value</test></root>',
    }

    for filename, content in test_files.items():
        filepath = output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  创建: {filepath}")

    # 创建README
    readme = output_dir / "README.md"
    with open(readme, 'w', encoding='utf-8') as f:
        f.write("""# 测试数据

此目录包含用于测试的文档文件。

## 说明

由于Office文档需要专门的库来创建，实际测试时请使用真实的文档文件：

- .doc, .docx - Word文档
- .xls, .xlsx - Excel文档
- .ppt, .pptx - PowerPoint文档
- .pdf - PDF文档

## 获取测试文件

您可以使用以下方式获取测试文件：

1. 使用现有文档进行测试
2. 使用Microsoft Office或LibreOffice创建测试文档
3. 从互联网下载公开的测试文档

## 测试文件要求

- 文件大小: 建议1KB - 10MB
- 内容: 包含文本、表格、图片等元素
- 格式: 标准格式，非损坏文件
""")
    print(f"  创建: {readme}")

    print(f"\n测试文件已生成到: {output_dir}")
    print("\n注意: 要进行完整测试，请添加真实的Office和PDF文档到此目录。")


if __name__ == "__main__":
    generate_test_files()
