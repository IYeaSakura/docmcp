"""
文档合并Skill

将多个文档合并为一个文档。
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from ..base import BaseSkill, SkillResult, SkillMetadata, SkillParameter
from ..decorators import skill, parameter, tag, category, require
from ..context import SkillContext


@skill(
    name="merge_documents",
    version="1.0.0",
    description="将多个文档合并为一个文档",
    author="DocMCP Team",
    category="document_processing",
    tags=["merge", "combine", "document"],
    dependencies=["extract_text"],
    timeout=180.0
)
@parameter("sources", list, "文档来源列表", required=True)
@parameter("output_format", str, "输出格式", default="markdown")
@parameter("add_headers", bool, "添加文档标题", default=True)
@parameter("add_page_breaks", bool, "添加分页符", default=False)
@parameter("custom_header", str, "自定义标题模板", default=None)
@parameter("toc", bool, "生成目录", default=False)
@tag("core", "merge")
@category("document_processing")
class MergeDocumentsSkill(BaseSkill):
    """
    文档合并Skill
    
    将多个文档合并为一个统一的文档，支持：
    - 多种输入格式
    - 自定义输出格式
    - 添加标题和分隔
    - 生成目录
    
    示例:
        skill = MergeDocumentsSkill()
        result = skill.run(
            context,
            sources=["doc1.pdf", "doc2.docx", "doc3.txt"],
            output_format="markdown",
            add_headers=True
        )
    """
    
    OUTPUT_FORMATS = {
        "markdown": "md",
        "md": "md",
        "html": "html",
        "text": "txt",
        "txt": "txt",
        "json": "json",
    }
    
    def execute(
        self,
        context: SkillContext,
        sources: List[Union[str, Path, Dict[str, Any]]],
        output_format: str = "markdown",
        add_headers: bool = True,
        add_page_breaks: bool = False,
        custom_header: Optional[str] = None,
        toc: bool = False,
        **kwargs
    ) -> SkillResult:
        """
        执行文档合并
        
        Args:
            context: 执行上下文
            sources: 文档来源列表
            output_format: 输出格式
            add_headers: 是否添加文档标题
            add_page_breaks: 是否添加分页符
            custom_header: 自定义标题模板
            toc: 是否生成目录
            
        Returns:
            合并结果
        """
        try:
            if not sources:
                return SkillResult.error_result("文档列表为空")
            
            # 获取提取文本Skill
            extract_skill = context.get_dependency("extract_text")
            if extract_skill is None:
                return SkillResult.error_result("需要 extract_text Skill")
            
            # 提取所有文档内容
            documents = []
            for i, source in enumerate(sources):
                doc_info = self._process_source(
                    context, extract_skill, source, i + 1
                )
                if doc_info:
                    documents.append(doc_info)
            
            if not documents:
                return SkillResult.error_result("没有成功提取任何文档内容")
            
            # 规范化输出格式
            output_format = output_format.lower()
            if output_format not in self.OUTPUT_FORMATS:
                output_format = "markdown"
            
            # 根据格式生成输出
            if output_format in ["markdown", "md"]:
                merged_content = self._merge_as_markdown(
                    documents, add_headers, add_page_breaks, custom_header, toc
                )
            elif output_format == "html":
                merged_content = self._merge_as_html(
                    documents, add_headers, add_page_breaks, custom_header, toc
                )
            elif output_format in ["text", "txt"]:
                merged_content = self._merge_as_text(
                    documents, add_headers, add_page_breaks, custom_header
                )
            elif output_format == "json":
                merged_content = self._merge_as_json(documents)
            else:
                merged_content = self._merge_as_markdown(
                    documents, add_headers, add_page_breaks, custom_header, toc
                )
            
            # 构建结果
            result = {
                "content": merged_content,
                "format": output_format,
                "document_count": len(documents),
                "documents": [
                    {
                        "index": doc["index"],
                        "title": doc.get("title", f"Document {doc['index']}"),
                        "format": doc.get("format", "unknown"),
                        "char_count": len(doc.get("text", "")),
                    }
                    for doc in documents
                ],
                "total_chars": len(merged_content),
                "merged_at": datetime.now().isoformat(),
            }
            
            if toc:
                result["toc"] = self._generate_toc(documents)
            
            context.log_info(
                f"成功合并 {len(documents)} 个文档，共 {result['total_chars']} 字符"
            )
            
            return SkillResult.success_result(data=result)
            
        except Exception as e:
            context.log_error(f"文档合并失败: {str(e)}")
            return SkillResult.error_result(f"文档合并失败: {str(e)}")
    
    def _process_source(
        self,
        context: SkillContext,
        extract_skill: BaseSkill,
        source: Union[str, Path, Dict[str, Any]],
        index: int
    ) -> Optional[Dict[str, Any]]:
        """处理单个文档来源"""
        try:
            if isinstance(source, dict):
                # 字典格式
                source_path = source.get("source") or source.get("path")
                title = source.get("title")
                options = source.get("options", {})
            else:
                # 字符串或Path
                source_path = source
                title = None
                options = {}
            
            # 提取文本
            result = extract_skill.run(
                context,
                source=source_path,
                **options
            )
            
            if not result.success:
                context.log_warning(f"无法提取文档 {source_path}: {result.error}")
                return None
            
            data = result.data
            
            # 获取标题
            if title is None:
                if isinstance(source, dict):
                    title = source.get("title")
                if title is None:
                    title = data.get("metadata", {}).get("title")
                if title is None:
                    path = Path(str(source_path))
                    title = path.stem if hasattr(path, "stem") else f"Document {index}"
            
            return {
                "index": index,
                "source": str(source_path),
                "title": title,
                "text": data.get("text", ""),
                "format": data.get("format", "unknown"),
                "metadata": data.get("metadata", {}),
            }
            
        except Exception as e:
            context.log_warning(f"处理文档失败: {str(e)}")
            return None
    
    def _merge_as_markdown(
        self,
        documents: List[Dict[str, Any]],
        add_headers: bool,
        add_page_breaks: bool,
        custom_header: Optional[str],
        toc: bool
    ) -> str:
        """合并为Markdown格式"""
        parts = []
        
        # 添加目录
        if toc:
            parts.append("# 目录\n")
            for doc in documents:
                title = doc.get("title", f"Document {doc['index']}")
                parts.append(f"- [{title}](#{self._slugify(title)})")
            parts.append("\n---\n")
        
        # 合并文档
        for i, doc in enumerate(documents):
            if add_headers:
                title = doc.get("title", f"Document {doc['index']}")
                
                if custom_header:
                    header = custom_header.format(
                        index=doc["index"],
                        title=title,
                        source=doc.get("source", ""),
                        format=doc.get("format", "")
                    )
                else:
                    header = f"# {title}"
                
                parts.append(header)
                parts.append("")
            
            # 添加文档内容
            parts.append(doc.get("text", ""))
            
            # 添加分隔
            if i < len(documents) - 1:
                if add_page_breaks:
                    parts.append("\n<div style=\"page-break-after: always;\"></div>\n")
                else:
                    parts.append("\n---\n")
        
        return "\n\n".join(parts)
    
    def _merge_as_html(
        self,
        documents: List[Dict[str, Any]],
        add_headers: bool,
        add_page_breaks: bool,
        custom_header: Optional[str],
        toc: bool
    ) -> str:
        """合并为HTML格式"""
        parts = []
        
        # HTML头部
        parts.append("<!DOCTYPE html>")
        parts.append("<html>")
        parts.append("<head>")
        parts.append("<meta charset=\"UTF-8\">")
        parts.append("<title>合并文档</title>")
        parts.append("<style>")
        parts.append(self._default_html_css())
        parts.append("</style>")
        parts.append("</head>")
        parts.append("<body>")
        
        # 添加目录
        if toc:
            parts.append("<nav class=\"toc\">")
            parts.append("<h2>目录</h2>")
            parts.append("<ul>")
            for doc in documents:
                title = doc.get("title", f"Document {doc['index']}")
                parts.append(f'<li><a href="#doc-{doc["index"]}">{title}</a></li>')
            parts.append("</ul>")
            parts.append("</nav>")
        
        # 合并文档
        for i, doc in enumerate(documents):
            doc_id = f'doc-{doc["index"]}'
            parts.append(f'<section id="{doc_id}" class="document">')
            
            if add_headers:
                title = doc.get("title", f"Document {doc['index']}")
                
                if custom_header:
                    header = custom_header.format(
                        index=doc["index"],
                        title=title,
                        source=doc.get("source", ""),
                        format=doc.get("format", "")
                    )
                    parts.append(f"<h2>{header}</h2>")
                else:
                    parts.append(f"<h2>{title}</h2>")
            
            # 将Markdown转换为HTML（简化版）
            text = doc.get("text", "")
            html_content = self._markdown_to_html(text)
            parts.append(f'<div class="content">{html_content}</div>')
            
            parts.append("</section>")
            
            if i < len(documents) - 1 and add_page_breaks:
                parts.append('<div class="page-break"></div>')
        
        parts.append("</body>")
        parts.append("</html>")
        
        return "\n".join(parts)
    
    def _merge_as_text(
        self,
        documents: List[Dict[str, Any]],
        add_headers: bool,
        add_page_breaks: bool,
        custom_header: Optional[str]
    ) -> str:
        """合并为纯文本格式"""
        parts = []
        
        for i, doc in enumerate(documents):
            if add_headers:
                title = doc.get("title", f"Document {doc['index']}")
                
                if custom_header:
                    header = custom_header.format(
                        index=doc["index"],
                        title=title,
                        source=doc.get("source", ""),
                        format=doc.get("format", "")
                    )
                else:
                    header = f"{'=' * 50}\n{title}\n{'=' * 50}"
                
                parts.append(header)
                parts.append("")
            
            parts.append(doc.get("text", ""))
            
            if i < len(documents) - 1:
                if add_page_breaks:
                    parts.append("\n" + "=" * 50 + "\n")
                else:
                    parts.append("\n" + "-" * 50 + "\n")
        
        return "\n\n".join(parts)
    
    def _merge_as_json(self, documents: List[Dict[str, Any]]) -> str:
        """合并为JSON格式"""
        import json
        
        output = {
            "merged_at": datetime.now().isoformat(),
            "document_count": len(documents),
            "documents": []
        }
        
        for doc in documents:
            output["documents"].append({
                "index": doc["index"],
                "title": doc.get("title", f"Document {doc['index']}"),
                "source": doc.get("source", ""),
                "format": doc.get("format", "unknown"),
                "text": doc.get("text", ""),
                "metadata": doc.get("metadata", {}),
            })
        
        return json.dumps(output, indent=2, ensure_ascii=False)
    
    def _generate_toc(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成目录"""
        toc = []
        for doc in documents:
            toc.append({
                "index": doc["index"],
                "title": doc.get("title", f"Document {doc['index']}"),
                "anchor": self._slugify(doc.get("title", "")),
            })
        return toc
    
    def _slugify(self, text: str) -> str:
        """生成URL友好的锚点"""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')
    
    def _markdown_to_html(self, text: str) -> str:
        """简单Markdown转HTML"""
        import re
        
        html = text
        
        # 转义HTML
        html = html.replace("&", "&amp;")
        html = html.replace("<", "&lt;")
        html = html.replace(">", "&gt;")
        
        # 标题
        for i in range(6, 0, -1):
            pattern = f'^{"#" * i} (.+)$'
            html = re.sub(pattern, f'<h{i + 1}>\\1</h{i + 1}>', html, flags=re.MULTILINE)
        
        # 粗体和斜体
        html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        
        # 代码
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        html = re.sub(r'```[\s\S]*?```', lambda m: f'<pre><code>{m.group(0)[3:-3]}</code></pre>', html)
        
        # 链接
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
        
        # 段落
        paragraphs = html.split('\n\n')
        html = '\n'.join(f'<p>{p}</p>' if not p.startswith('<') else p for p in paragraphs)
        
        # 换行
        html = html.replace('\n', '<br>\n')
        
        return html
    
    def _default_html_css(self) -> str:
        """默认HTML样式"""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        .toc {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }
        .toc ul {
            list-style: none;
            padding-left: 0;
        }
        .toc li {
            margin: 5px 0;
        }
        .toc a {
            color: #0066cc;
            text-decoration: none;
        }
        .document {
            margin-bottom: 40px;
        }
        .document h2 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .content {
            margin-top: 20px;
        }
        .page-break {
            page-break-after: always;
            border-top: 2px dashed #ccc;
            margin: 40px 0;
        }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        pre {
            background: #f4f4f4;
            padding: 16px;
            border-radius: 5px;
            overflow-x: auto;
        }
        """
