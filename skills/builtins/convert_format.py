"""
格式转换Skill

在不同文档格式之间进行转换。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import io

from ..base import BaseSkill, SkillResult, SkillMetadata, SkillParameter
from ..decorators import skill, parameter, tag, category
from ..context import SkillContext


@skill(
    name="convert_format",
    version="1.0.0",
    description="在不同文档格式之间进行转换",
    author="DocMCP Team",
    category="document_processing",
    tags=["conversion", "format", "document"],
    timeout=120.0
)
@parameter("source", Union[str, bytes, Dict], "源内容", required=True)
@parameter("source_format", str, "源格式", required=True)
@parameter("target_format", str, "目标格式", required=True)
@parameter("options", dict, "转换选项", default={})
@tag("core", "conversion")
@category("document_processing")
class ConvertFormatSkill(BaseSkill):
    """
    格式转换Skill
    
    支持多种文档格式之间的转换：
    - Markdown <-> HTML
    - JSON <-> YAML
    - HTML <-> Text
    - CSV <-> JSON
    
    示例:
        skill = ConvertFormatSkill()
        result = skill.run(
            context,
            source="# Hello",
            source_format="markdown",
            target_format="html"
        )
        print(result.data)  # <h1>Hello</h1>
    """
    
    SUPPORTED_CONVERSIONS = {
        ("markdown", "html"): "_md_to_html",
        ("md", "html"): "_md_to_html",
        ("html", "markdown"): "_html_to_md",
        ("html", "md"): "_html_to_md",
        ("html", "text"): "_html_to_text",
        ("html", "txt"): "_html_to_text",
        ("json", "yaml"): "_json_to_yaml",
        ("yaml", "json"): "_yaml_to_json",
        ("csv", "json"): "_csv_to_json",
        ("json", "csv"): "_json_to_csv",
        ("text", "html"): "_text_to_html",
        ("txt", "html"): "_text_to_html",
    }
    
    def execute(
        self,
        context: SkillContext,
        source: Union[str, bytes, Dict, List],
        source_format: str,
        target_format: str,
        options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> SkillResult:
        """
        执行格式转换
        
        Args:
            context: 执行上下文
            source: 源内容
            source_format: 源格式
            target_format: 目标格式
            options: 转换选项
            
        Returns:
            转换结果
        """
        try:
            options = options or {}
            
            # 规范化格式名称
            source_format = source_format.lower().strip()
            target_format = target_format.lower().strip()
            
            # 检查是否支持转换
            conversion_key = (source_format, target_format)
            
            if conversion_key not in self.SUPPORTED_CONVERSIONS:
                # 检查是否为相同格式
                if source_format == target_format:
                    return SkillResult.success_result(
                        data={"content": source, "format": target_format}
                    )
                
                supported = [f"{s} -> {t}" for s, t in self.SUPPORTED_CONVERSIONS.keys()]
                return SkillResult.error_result(
                    f"不支持的转换: {source_format} -> {target_format}. "
                    f"支持的转换: {', '.join(supported)}"
                )
            
            # 执行转换
            converter_name = self.SUPPORTED_CONVERSIONS[conversion_key]
            converter = getattr(self, converter_name)
            
            result = converter(source, options)
            
            context.log_info(
                f"格式转换完成: {source_format} -> {target_format}"
            )
            
            return SkillResult.success_result(data={
                "content": result,
                "source_format": source_format,
                "target_format": target_format
            })
            
        except Exception as e:
            context.log_error(f"格式转换失败: {str(e)}")
            return SkillResult.error_result(f"格式转换失败: {str(e)}")
    
    def _md_to_html(self, source: Union[str, bytes], options: Dict) -> str:
        """Markdown转HTML"""
        try:
            import markdown
            
            if isinstance(source, bytes):
                source = source.decode("utf-8")
            
            # 配置选项
            extensions = options.get("extensions", [
                "tables",
                "fenced_code",
                "toc",
                "nl2br"
            ])
            
            md = markdown.Markdown(extensions=extensions)
            html = md.convert(source)
            
            # 添加样式
            if options.get("add_styles", False):
                css = options.get("css", self._default_markdown_css())
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <style>{css}</style>
                </head>
                <body>
                    {html}
                </body>
                </html>
                """
            
            return html
            
        except ImportError:
            # 简单转换
            if isinstance(source, bytes):
                source = source.decode("utf-8")
            
            # 基本Markdown转换
            html = source
            html = html.replace("&", "&amp;")
            html = html.replace("<", "&lt;")
            html = html.replace(">", "&gt;")
            
            # 标题
            for i in range(6, 0, -1):
                html = html.replace(f"{'#' * i} ", f"<h{i}>")
                html = html.replace(f"\n{'#' * i} ", f"</p>\n<h{i}>")
            
            # 段落
            html = "<p>" + html.replace("\n\n", "</p>\n<p>") + "</p>"
            
            return html
    
    def _html_to_md(self, source: Union[str, bytes], options: Dict) -> str:
        """HTML转Markdown"""
        try:
            from bs4 import BeautifulSoup
            import html2text
            
            if isinstance(source, bytes):
                source = source.decode("utf-8")
            
            h = html2text.HTML2Text()
            h.ignore_links = options.get("ignore_links", False)
            h.ignore_images = options.get("ignore_images", False)
            h.ignore_tables = options.get("ignore_tables", False)
            h.body_width = options.get("body_width", 0)
            
            markdown = h.handle(source)
            return markdown
            
        except ImportError:
            try:
                from bs4 import BeautifulSoup
                
                if isinstance(source, bytes):
                    source = source.decode("utf-8")
                
                soup = BeautifulSoup(source, "html.parser")
                
                # 简单转换
                md_parts = []
                
                # 标题
                for i in range(1, 7):
                    for header in soup.find_all(f"h{i}"):
                        md_parts.append(f"{'#' * i} {header.get_text().strip()}")
                
                # 段落
                for p in soup.find_all("p"):
                    md_parts.append(p.get_text().strip())
                
                # 列表
                for ul in soup.find_all("ul"):
                    for li in ul.find_all("li"):
                        md_parts.append(f"- {li.get_text().strip()}")
                
                for ol in soup.find_all("ol"):
                    for i, li in enumerate(ol.find_all("li"), 1):
                        md_parts.append(f"{i}. {li.get_text().strip()}")
                
                return "\n\n".join(md_parts)
                
            except ImportError:
                # 简单去除标签
                if isinstance(source, bytes):
                    source = source.decode("utf-8")
                import re
                return re.sub(r'<[^>]+>', '', source)
    
    def _html_to_text(self, source: Union[str, bytes], options: Dict) -> str:
        """HTML转纯文本"""
        try:
            from bs4 import BeautifulSoup
            
            if isinstance(source, bytes):
                source = source.decode("utf-8")
            
            soup = BeautifulSoup(source, "html.parser")
            
            # 移除script和style
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 获取文本
            text = soup.get_text(separator="\n")
            
            # 清理空白
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = "\n".join(chunk for chunk in chunks if chunk)
            
            return text
            
        except ImportError:
            if isinstance(source, bytes):
                source = source.decode("utf-8")
            import re
            return re.sub(r'<[^>]+>', '', source)
    
    def _text_to_html(self, source: Union[str, bytes], options: Dict) -> str:
        """纯文本转HTML"""
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        
        # 转义HTML特殊字符
        text = source
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        
        # 转换换行
        text = text.replace("\n", "<br>\n")
        
        # 包装
        if options.get("full_document", False):
            return f"""<!DOCTYPE html>
<html>
<head><title>Converted Text</title></head>
<body>
<p>{text}</p>
</body>
</html>"""
        else:
            return f"<p>{text}</p>"
    
    def _json_to_yaml(self, source: Union[str, bytes, Dict], options: Dict) -> str:
        """JSON转YAML"""
        try:
            import yaml
            
            # 解析JSON
            if isinstance(source, (str, bytes)):
                if isinstance(source, bytes):
                    source = source.decode("utf-8")
                data = json.loads(source)
            else:
                data = source
            
            # 转换为YAML
            default_flow_style = options.get("default_flow_style", False)
            allow_unicode = options.get("allow_unicode", True)
            
            yaml_str = yaml.dump(
                data,
                default_flow_style=default_flow_style,
                allow_unicode=allow_unicode,
                sort_keys=options.get("sort_keys", False)
            )
            
            return yaml_str
            
        except ImportError:
            # 简单YAML格式
            if isinstance(source, (str, bytes)):
                if isinstance(source, bytes):
                    source = source.decode("utf-8")
                data = json.loads(source)
            else:
                data = source
            
            return self._simple_yaml_dump(data)
    
    def _yaml_to_json(self, source: Union[str, bytes], options: Dict) -> str:
        """YAML转JSON"""
        try:
            import yaml
            
            if isinstance(source, bytes):
                source = source.decode("utf-8")
            
            data = yaml.safe_load(source)
            
            # 转换为JSON
            indent = options.get("indent", 2)
            ensure_ascii = options.get("ensure_ascii", False)
            sort_keys = options.get("sort_keys", False)
            
            return json.dumps(
                data,
                indent=indent,
                ensure_ascii=ensure_ascii,
                sort_keys=sort_keys
            )
            
        except ImportError:
            return SkillResult.error_result("需要安装PyYAML库")
    
    def _csv_to_json(self, source: Union[str, bytes], options: Dict) -> str:
        """CSV转JSON"""
        import csv
        import io
        
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        
        # 解析CSV
        delimiter = options.get("delimiter", ",")
        quotechar = options.get("quotechar", '"')
        
        csv_file = io.StringIO(source)
        reader = csv.DictReader(
            csv_file,
            delimiter=delimiter,
            quotechar=quotechar
        )
        
        rows = list(reader)
        
        return json.dumps(
            rows,
            indent=options.get("indent", 2),
            ensure_ascii=False
        )
    
    def _json_to_csv(self, source: Union[str, bytes, List], options: Dict) -> str:
        """JSON转CSV"""
        import csv
        import io
        
        # 解析JSON
        if isinstance(source, (str, bytes)):
            if isinstance(source, bytes):
                source = source.decode("utf-8")
            data = json.loads(source)
        else:
            data = source
        
        if not isinstance(data, list):
            return SkillResult.error_result("JSON必须是数组格式")
        
        if not data:
            return ""
        
        # 生成CSV
        delimiter = options.get("delimiter", ",")
        quotechar = options.get("quotechar", '"')
        
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=data[0].keys(),
            delimiter=delimiter,
            quotechar=quotechar
        )
        
        writer.writeheader()
        writer.writerows(data)
        
        return output.getvalue()
    
    def _simple_yaml_dump(self, data: Any, indent: int = 0) -> str:
        """简单YAML序列化"""
        lines = []
        prefix = "  " * indent
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    lines.append(f"{prefix}{key}:")
                    lines.append(self._simple_yaml_dump(value, indent + 1))
                else:
                    lines.append(f"{prefix}{key}: {value}")
        
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}-")
                    lines.append(self._simple_yaml_dump(item, indent + 1))
                else:
                    lines.append(f"{prefix}- {item}")
        
        else:
            lines.append(f"{prefix}{data}")
        
        return "\n".join(lines)
    
    def _default_markdown_css(self) -> str:
        """默认Markdown样式"""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #2c3e50;
            margin-top: 24px;
            margin-bottom: 16px;
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
        blockquote {
            border-left: 4px solid #ddd;
            padding-left: 16px;
            margin-left: 0;
            color: #666;
        }
        table {
            border-collapse: collapse;
            width: 100%;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background: #f4f4f4;
        }
        """
