"""
DocMCP 基本使用示例

展示如何使用文档处理引擎进行基本的文档操作。
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from docmcp import DocumentEngine, DocumentType


def example_extract_text():
    """示例：提取文档文本"""
    print("=" * 60)
    print("示例：提取文档文本")
    print("=" * 60)

    engine = DocumentEngine()

    # 假设有一个Word文档
    # text = engine.extract_text("document.docx")
    # print(text)

    print("支持的文档类型:", [t.name for t in engine.get_supported_types()])
    print("支持的扩展名:", engine.get_supported_extensions())


def example_extract_metadata():
    """示例：提取文档元数据"""
    print("\n" + "=" * 60)
    print("示例：提取文档元数据")
    print("=" * 60)

    engine = DocumentEngine()

    # metadata = engine.extract_metadata("document.docx")
    # print(f"标题: {metadata.title}")
    # print(f"作者: {metadata.author}")
    # print(f"创建时间: {metadata.created}")


def example_batch_process():
    """示例：批量处理文档"""
    print("\n" + "=" * 60)
    print("示例：批量处理文档")
    print("=" * 60)

    engine = DocumentEngine()

    # 定义进度回调
    def progress_callback(current, total, message):
        percentage = (current / total * 100) if total > 0 else 0
        print(f"进度: {percentage:.1f}% ({current}/{total}) {message}")

    # 批量处理文件
    # files = ["file1.docx", "file2.pdf", "file3.xlsx"]
    # results = engine.batch_process(files, operation="extract_text",
    #                                progress_callback=progress_callback)
    #
    # for result in results:
    #     print(f"文件: {result['file_name']}")
    #     print(f"成功: {result['success']}")
    #     if result['success']:
    #         print(f"内容长度: {len(result['data'])}")
    #     else:
    #         print(f"错误: {result['error']}")


def example_convert_document():
    """示例：转换文档格式"""
    print("\n" + "=" * 60)
    print("示例：转换文档格式")
    print("=" * 60)

    engine = DocumentEngine()

    # 将Word转换为PDF
    # engine.convert("document.docx", DocumentType.PDF, "output.pdf")

    # 将Excel转换为CSV
    # engine.convert("data.xlsx", DocumentType.CSV, "output.csv")

    # 将PDF转换为文本
    # engine.convert("document.pdf", DocumentType.TXT, "output.txt")


def example_extract_content():
    """示例：提取完整内容"""
    print("\n" + "=" * 60)
    print("示例：提取完整内容")
    print("=" * 60)

    engine = DocumentEngine()

    # content = engine.extract_content("document.docx")
    # print(f"文本内容: {content.text[:500]}...")
    # print(f"段落数: {len(content.paragraphs)}")
    # print(f"表格数: {len(content.tables)}")
    # print(f"图片数: {len(content.images)}")


def example_with_context_manager():
    """示例：使用上下文管理器"""
    print("\n" + "=" * 60)
    print("示例：使用上下文管理器")
    print("=" * 60)

    # 引擎上下文管理器
    with DocumentEngine() as engine:
        # 文档上下文管理器
        # with engine.open("document.docx") as doc:
        #     text = doc.extract_text()
        #     metadata = doc.extract_metadata()
        #     print(f"文档类型: {doc.document_type}")
        #     print(f"文件大小: {doc.get_file_size()}")
        pass


def example_document_info():
    """示例：获取文档信息"""
    print("\n" + "=" * 60)
    print("示例：获取文档信息")
    print("=" * 60)

    engine = DocumentEngine()

    # info = engine.get_document_info("document.docx")
    # print(f"文件路径: {info['file_path']}")
    # print(f"文件大小: {info['file_size']}")
    # print(f"是否可处理: {info['can_handle']}")
    # print(f"文档类型: {info['document_type']}")


def example_async_processing():
    """示例：异步处理"""
    print("\n" + "=" * 60)
    print("示例：异步处理")
    print("=" * 60)

    import asyncio

    async def async_process():
        engine = DocumentEngine()

        # files = ["file1.docx", "file2.pdf", "file3.xlsx"]
        # results = await engine.batch_process_async(
        #     files,
        #     operation="extract_text"
        # )
        # return results

    # asyncio.run(async_process())


def main():
    """主函数"""
    print("DocMCP 文档处理引擎 - 基本使用示例")
    print("=" * 60)

    example_extract_text()
    example_extract_metadata()
    example_batch_process()
    example_convert_document()
    example_extract_content()
    example_with_context_manager()
    example_document_info()
    example_async_processing()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
