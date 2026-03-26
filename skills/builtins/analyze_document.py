"""
文档分析Skill

分析文档内容，提取关键信息、统计和摘要。
"""

import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..base import BaseSkill, SkillResult, SkillMetadata, SkillParameter
from ..decorators import skill, parameter, tag, category, require
from ..context import SkillContext


@skill(
    name="analyze_document",
    version="1.0.0",
    description="分析文档内容，提取关键信息和统计",
    author="DocMCP Team",
    category="document_processing",
    tags=["analysis", "statistics", "document"],
    dependencies=["extract_text"],
    timeout=180.0
)
@parameter("source", Union[str, Path, bytes], "文档来源", required=True)
@parameter("analysis_types", list, "分析类型列表", default=["basic", "keywords"])
@parameter("language", str, "文档语言", default="auto")
@parameter("max_keywords", int, "最大关键词数", default=20)
@parameter("summary_ratio", float, "摘要比例", default=0.2)
@tag("core", "analysis")
@category("document_processing")
class AnalyzeDocumentSkill(BaseSkill):
    """
    文档分析Skill
    
    提供多种文档分析功能：
    - 基础统计（字符数、词数、行数等）
    - 关键词提取
    - 文本摘要
    - 情感分析
    - 可读性分析
    - 实体识别
    
    示例:
        skill = AnalyzeDocumentSkill()
        result = skill.run(
            context,
            source="document.txt",
            analysis_types=["basic", "keywords", "readability"]
        )
    """
    
    # 停用词列表（简化版）
    STOP_WORDS = {
        "zh": set("的 了 在 是 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你 会 着 没有 看 好 自己 这 那 这些 那些 这个 那个 之 与 及 等 或 但 而 因为 所以 如果 虽然 但是 然而 而且 或者 还是 就是 即 便 即使 尽管 不管 无论 只要 只有 无论 不论 不管 尽管 即使 即便 哪怕 任凭"),
        "en": set("the a an and or but in on at to for of with by from as is was were be been being have has had do does did will would could should may might must can need shall"),
    }
    
    def execute(
        self,
        context: SkillContext,
        source: Union[str, Path, bytes],
        analysis_types: Optional[List[str]] = None,
        language: str = "auto",
        max_keywords: int = 20,
        summary_ratio: float = 0.2,
        **kwargs
    ) -> SkillResult:
        """
        执行文档分析
        
        Args:
            context: 执行上下文
            source: 文档来源
            analysis_types: 分析类型列表
            language: 文档语言
            max_keywords: 最大关键词数
            summary_ratio: 摘要比例
            
        Returns:
            分析结果
        """
        try:
            analysis_types = analysis_types or ["basic", "keywords"]
            
            # 首先提取文本
            extract_skill = context.get_dependency("extract_text")
            if extract_skill is None:
                return SkillResult.error_result("需要 extract_text Skill")
            
            extract_result = extract_skill.run(context, source=source)
            
            if not extract_result.success:
                return extract_result
            
            text_data = extract_result.data
            text = text_data.get("text", "")
            
            if not text.strip():
                return SkillResult.error_result("文档内容为空")
            
            # 自动检测语言
            if language == "auto":
                language = self._detect_language(text)
            
            # 执行分析
            results = {
                "language": language,
                "text_stats": text_data.get("stats", {}),
            }
            
            if "basic" in analysis_types:
                results["basic"] = self._analyze_basic(text, language)
            
            if "keywords" in analysis_types:
                results["keywords"] = self._extract_keywords(
                    text, language, max_keywords
                )
            
            if "summary" in analysis_types:
                results["summary"] = self._generate_summary(
                    text, language, summary_ratio
                )
            
            if "readability" in analysis_types:
                results["readability"] = self._analyze_readability(text, language)
            
            if "sentiment" in analysis_types:
                results["sentiment"] = self._analyze_sentiment(text, language)
            
            if "structure" in analysis_types:
                results["structure"] = self._analyze_structure(text)
            
            if "entities" in analysis_types:
                results["entities"] = self._extract_entities(text, language)
            
            context.log_info(
                f"文档分析完成: {len(analysis_types)} 种分析类型"
            )
            
            return SkillResult.success_result(data=results)
            
        except Exception as e:
            context.log_error(f"文档分析失败: {str(e)}")
            return SkillResult.error_result(f"文档分析失败: {str(e)}")
    
    def _detect_language(self, text: str) -> str:
        """检测文本语言"""
        # 简单检测：检查中文字符比例
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text)
        
        if total_chars == 0:
            return "en"
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return "zh"
        return "en"
    
    def _analyze_basic(self, text: str, language: str) -> Dict[str, Any]:
        """基础统计分析"""
        # 字符统计
        char_count = len(text)
        char_count_no_spaces = len(text.replace(" ", "").replace("\n", ""))
        
        # 行数
        lines = text.split("\n")
        line_count = len(lines)
        non_empty_lines = len([l for l in lines if l.strip()])
        
        # 段落数
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        paragraph_count = len(paragraphs)
        
        # 词数
        if language == "zh":
            # 中文按字符计数
            words = list(text.replace(" ", "").replace("\n", ""))
            word_count = len(words)
        else:
            # 英文按空格分词
            words = text.split()
            word_count = len(words)
        
        # 句子数
        sentences = re.split(r'[.!?。！？]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        # 平均词长/句长
        avg_word_length = char_count / word_count if word_count > 0 else 0
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
        
        return {
            "char_count": char_count,
            "char_count_no_spaces": char_count_no_spaces,
            "word_count": word_count,
            "line_count": line_count,
            "non_empty_lines": non_empty_lines,
            "paragraph_count": paragraph_count,
            "sentence_count": sentence_count,
            "avg_word_length": round(avg_word_length, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
        }
    
    def _extract_keywords(
        self,
        text: str,
        language: str,
        max_keywords: int
    ) -> Dict[str, Any]:
        """提取关键词"""
        # 预处理
        if language == "zh":
            # 中文分词（简化版）
            words = self._simple_chinese_tokenize(text)
        else:
            # 英文分词
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        # 过滤停用词和短词
        stop_words = self.STOP_WORDS.get(language, set())
        filtered_words = [
            w for w in words
            if len(w) > 1 and w.lower() not in stop_words
        ]
        
        # 统计词频
        word_freq = Counter(filtered_words)
        
        # 获取最频繁的词
        top_keywords = word_freq.most_common(max_keywords)
        
        # 计算TF-IDF（简化版）
        total_words = len(filtered_words)
        keyword_scores = [
            {
                "word": word,
                "frequency": freq,
                "tf": round(freq / total_words, 4),
                "score": round(freq / total_words * 100, 2)
            }
            for word, freq in top_keywords
        ]
        
        return {
            "keywords": keyword_scores,
            "unique_words": len(word_freq),
            "total_words": total_words,
        }
    
    def _simple_chinese_tokenize(self, text: str) -> List[str]:
        """简单中文分词"""
        # 移除标点
        text = re.sub(r'[^\u4e00-\u9fff\w]', ' ', text)
        
        words = []
        i = 0
        while i < len(text):
            if '\u4e00' <= text[i] <= '\u9fff':
                # 中文字符
                words.append(text[i])
                i += 1
            elif text[i].isalnum():
                # 英文/数字
                j = i
                while j < len(text) and text[j].isalnum():
                    j += 1
                words.append(text[i:j])
                i = j
            else:
                i += 1
        
        return words
    
    def _generate_summary(
        self,
        text: str,
        language: str,
        ratio: float
    ) -> Dict[str, Any]:
        """生成文本摘要"""
        # 分句
        if language == "zh":
            sentences = re.split(r'[。！？]+', text)
        else:
            sentences = re.split(r'[.!?]+', text)
        
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 3:
            return {
                "summary": text,
                "original_sentences": len(sentences),
                "summary_sentences": len(sentences),
                "method": "full_text"
            }
        
        # 简单摘要：选择前N句
        summary_length = max(1, int(len(sentences) * ratio))
        summary_sentences = sentences[:summary_length]
        
        # 尝试提取关键句（基于词频）
        try:
            keywords_result = self._extract_keywords(text, language, 20)
            keyword_words = {k["word"] for k in keywords_result["keywords"]}
            
            # 为每句打分
            sentence_scores = []
            for sent in sentences:
                score = sum(1 for kw in keyword_words if kw in sent)
                sentence_scores.append((sent, score))
            
            # 选择得分最高的句子
            sentence_scores.sort(key=lambda x: x[1], reverse=True)
            top_sentences = [s[0] for s in sentence_scores[:summary_length]]
            
            # 按原文顺序排列
            summary_sentences = [s for s in sentences if s in top_sentences]
        except Exception:
            pass
        
        if language == "zh":
            summary = "。".join(summary_sentences) + "。"
        else:
            summary = ". ".join(summary_sentences) + "."
        
        return {
            "summary": summary,
            "original_sentences": len(sentences),
            "summary_sentences": len(summary_sentences),
            "compression_ratio": round(len(summary) / len(text), 2),
            "method": "extractive"
        }
    
    def _analyze_readability(self, text: str, language: str) -> Dict[str, Any]:
        """分析可读性"""
        if language == "zh":
            return self._analyze_chinese_readability(text)
        else:
            return self._analyze_english_readability(text)
    
    def _analyze_chinese_readability(self, text: str) -> Dict[str, Any]:
        """分析中文可读性"""
        # 统计
        char_count = len(text)
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        sentences = len(re.findall(r'[。！？]+', text))
        
        if sentences == 0:
            sentences = 1
        
        # 平均句长
        avg_sentence_length = chinese_chars / sentences
        
        # 难度评估（简化版）
        if avg_sentence_length < 15:
            difficulty = "简单"
            grade = "小学"
        elif avg_sentence_length < 25:
            difficulty = "中等"
            grade = "初中"
        elif avg_sentence_length < 35:
            difficulty = "较难"
            grade = "高中"
        else:
            difficulty = "困难"
            grade = "大学及以上"
        
        return {
            "avg_sentence_length": round(avg_sentence_length, 2),
            "chinese_char_ratio": round(chinese_chars / char_count, 2) if char_count > 0 else 0,
            "difficulty": difficulty,
            "grade_level": grade,
            "score": max(0, min(100, 100 - avg_sentence_length * 2))
        }
    
    def _analyze_english_readability(self, text: str) -> Dict[str, Any]:
        """分析英文可读性"""
        # 统计
        sentences = len(re.findall(r'[.!?]+', text))
        words = len(text.split())
        syllables = self._count_syllables(text)
        
        if sentences == 0:
            sentences = 1
        if words == 0:
            words = 1
        
        # Flesch Reading Ease
        avg_sentence_length = words / sentences
        avg_syllables_per_word = syllables / words
        
        flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        flesch_score = max(0, min(100, flesch_score))
        
        # Flesch-Kincaid Grade Level
        fk_grade = (0.39 * avg_sentence_length) + (11.8 * avg_syllables_per_word) - 15.59
        
        # 难度等级
        if flesch_score >= 90:
            difficulty = "Very Easy"
            grade = "5th grade"
        elif flesch_score >= 80:
            difficulty = "Easy"
            grade = "6th grade"
        elif flesch_score >= 70:
            difficulty = "Fairly Easy"
            grade = "7th grade"
        elif flesch_score >= 60:
            difficulty = "Standard"
            grade = "8th-9th grade"
        elif flesch_score >= 50:
            difficulty = "Fairly Difficult"
            grade = "10th-12th grade"
        elif flesch_score >= 30:
            difficulty = "Difficult"
            grade = "College"
        else:
            difficulty = "Very Difficult"
            grade = "College Graduate"
        
        return {
            "flesch_score": round(flesch_score, 2),
            "flesch_kincaid_grade": round(fk_grade, 1),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "avg_syllables_per_word": round(avg_syllables_per_word, 2),
            "difficulty": difficulty,
            "grade_level": grade
        }
    
    def _count_syllables(self, text: str) -> int:
        """计算音节数"""
        words = text.lower().split()
        count = 0
        
        for word in words:
            # 简单音节计数
            vowels = "aeiouy"
            syllables = 0
            prev_was_vowel = False
            
            for char in word:
                if char in vowels:
                    if not prev_was_vowel:
                        syllables += 1
                    prev_was_vowel = True
                else:
                    prev_was_vowel = False
            
            # 处理e结尾
            if word.endswith('e') and syllables > 1:
                syllables -= 1
            
            count += max(1, syllables)
        
        return count
    
    def _analyze_sentiment(self, text: str, language: str) -> Dict[str, Any]:
        """情感分析"""
        # 简化版情感分析
        if language == "zh":
            positive_words = set("好 棒 优秀 喜欢 爱 快乐 幸福 成功 美丽 精彩 赞 完美 满意 开心 愉快 舒适 便捷 高效 优质 卓越".split())
            negative_words = set("坏 差 糟糕 讨厌 恨 悲伤 痛苦 失败 丑陋 错误 遗憾 失望 难过 愤怒 焦虑 麻烦 低效 劣质 平庸".split())
        else:
            positive_words = set("good great excellent love happy success beautiful amazing perfect best fantastic wonderful positive".split())
            negative_words = set("bad terrible awful hate sad fail ugly wrong worst horrible negative poor disappointing".split())
        
        # 统计
        positive_count = sum(1 for word in positive_words if word in text.lower())
        negative_count = sum(1 for word in negative_words if word in text.lower())
        
        total = positive_count + negative_count
        
        if total == 0:
            sentiment = "neutral"
            score = 0
        elif positive_count > negative_count:
            sentiment = "positive"
            score = positive_count / total
        elif negative_count > positive_count:
            sentiment = "negative"
            score = -negative_count / total
        else:
            sentiment = "neutral"
            score = 0
        
        return {
            "sentiment": sentiment,
            "score": round(score, 2),
            "positive_words": positive_count,
            "negative_words": negative_count,
            "confidence": round(total / len(text.split()) * 10, 2) if text.split() else 0
        }
    
    def _analyze_structure(self, text: str) -> Dict[str, Any]:
        """分析文档结构"""
        # 标题检测
        headers = []
        
        # Markdown风格标题
        md_headers = re.findall(r'^(#{1,6})\s+(.+)$', text, re.MULTILINE)
        for level, title in md_headers:
            headers.append({
                "level": len(level),
                "title": title.strip(),
                "type": "markdown"
            })
        
        # 下划线风格标题
        underline_headers = re.findall(r'^(.+)\n([=\-]+)\s*$', text, re.MULTILINE)
        for title, underline in underline_headers:
            level = 1 if underline[0] == '=' else 2
            headers.append({
                "level": level,
                "title": title.strip(),
                "type": "underline"
            })
        
        # 列表检测
        bullet_lists = len(re.findall(r'^\s*[-*+]\s', text, re.MULTILINE))
        numbered_lists = len(re.findall(r'^\s*\d+\.\s', text, re.MULTILINE))
        
        # 代码块检测
        code_blocks = len(re.findall(r'```[\s\S]*?```', text))
        inline_code = len(re.findall(r'`[^`]+`', text))
        
        # 表格检测
        tables = len(re.findall(r'\|[^\n]+\|', text))
        
        # 链接和图片
        links = len(re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text))
        images = len(re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', text))
        
        return {
            "headers": headers,
            "header_count": len(headers),
            "bullet_lists": bullet_lists,
            "numbered_lists": numbered_lists,
            "code_blocks": code_blocks,
            "inline_code": inline_code,
            "tables": tables,
            "links": links,
            "images": images,
            "structure_depth": max((h["level"] for h in headers), default=0)
        }
    
    def _extract_entities(self, text: str, language: str) -> Dict[str, List[str]]:
        """提取实体"""
        entities = {
            "emails": [],
            "urls": [],
            "phones": [],
            "dates": [],
            "numbers": [],
        }
        
        # 邮箱
        entities["emails"] = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        
        # URL
        entities["urls"] = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
        
        # 电话号码（简化版）
        if language == "zh":
            entities["phones"] = re.findall(r'1[3-9]\d{9}|\d{3,4}-\d{7,8}', text)
        else:
            entities["phones"] = re.findall(r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        
        # 日期
        date_patterns = [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
        ]
        for pattern in date_patterns:
            entities["dates"].extend(re.findall(pattern, text, re.IGNORECASE))
        
        # 数字
        entities["numbers"] = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text)
        
        # 去重
        for key in entities:
            entities[key] = list(set(entities[key]))
        
        return entities
