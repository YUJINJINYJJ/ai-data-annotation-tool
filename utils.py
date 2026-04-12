"""
工具函数模块
提供CSV生成、日志记录、配置管理等通用功能
"""
import csv
import logging
from io import StringIO, BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_csv_in_memory(headers: Optional[List[str]], rows: List[List[Any]]) -> BytesIO:
    """
    内存生成CSV，Excel打开不乱码
    
    Args:
        headers: 表头列表（可选）
        rows: 数据行列表
    
    Returns:
        BytesIO: CSV文件的字节流对象
    """
    string_buffer = StringIO()
    writer = csv.writer(string_buffer)
    if headers:
        writer.writerow(headers)
    writer.writerows(rows)
    csv_content = string_buffer.getvalue()
    # 添加 BOM 头，确保 Excel 正确识别 UTF-8 编码
    csv_bytes = b'\xef\xbb\xbf' + csv_content.encode('utf-8')
    output = BytesIO(csv_bytes)
    output.seek(0)
    return output


def create_dict_csv_in_memory(headers: List[str], dict_rows: List[Dict[str, Any]]) -> BytesIO:
    """
    生成字典格式CSV
    
    Args:
        headers: 表头列表
        dict_rows: 字典格式的数据行列表
    
    Returns:
        BytesIO: CSV文件的字节流对象
    """
    string_buffer = StringIO()
    writer = csv.DictWriter(string_buffer, fieldnames=headers)
    writer.writeheader()
    writer.writerows(dict_rows)
    csv_content = string_buffer.getvalue()
    csv_bytes = b'\xef\xbb\xbf' + csv_content.encode('utf-8')
    output = BytesIO(csv_bytes)
    output.seek(0)
    return output


def format_duration(seconds: float) -> str:
    """
    格式化时长显示
    
    Args:
        seconds: 秒数
    
    Returns:
        str: 格式化的时长字符串
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}分{secs:.1f}秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}时{minutes}分{secs:.1f}秒"


def format_file_size(size_bytes: int) -> str:
    """
    格式化文件大小显示
    
    Args:
        size_bytes: 字节数
    
    Returns:
        str: 格式化的文件大小字符串
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"


def get_timestamp_filename(prefix: str = "报告", suffix: str = "csv") -> str:
    """
    生成带时间戳的文件名
    
    Args:
        prefix: 文件名前缀
        suffix: 文件扩展名
    
    Returns:
        str: 格式化的文件名
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.{suffix}"


def safe_str(value: Any, default: str = "") -> str:
    """
    安全转换为字符串
    
    Args:
        value: 任意值
        default: 默认值
    
    Returns:
        str: 字符串结果
    """
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default


def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    截断文本
    
    Args:
        text: 原文本
        max_length: 最大长度
        suffix: 截断后缀
    
    Returns:
        str: 截断后的文本
    """
    if not text or len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def parse_keywords_input(keyword_input: str) -> List[str]:
    """
    解析关键词输入（支持中英文逗号分隔）
    
    Args:
        keyword_input: 关键词输入字符串
    
    Returns:
        List[str]: 关键词列表
    """
    if not keyword_input or not keyword_input.strip():
        return []
    
    # 统一分隔符
    clean_input = keyword_input.strip().replace("，", ",")
    keywords = [kw.strip() for kw in clean_input.split(",") if kw.strip()]
    return keywords


def parse_threshold_input(threshold_text: str) -> Dict[str, int]:
    """
    解析阈值输入
    
    Args:
        threshold_text: 阈值输入文本（格式：关键词:次数，每行一个）
    
    Returns:
        Dict[str, int]: 关键词到阈值的映射
    """
    threshold_dict = {}
    if not threshold_text or not threshold_text.strip():
        return threshold_dict
    
    for line in threshold_text.split("\n"):
        line = line.strip().replace("：", ":")
        if not line or ":" not in line:
            continue
        parts = line.split(":", 1)
        if len(parts) != 2:
            continue
        kw, cnt = parts[0].strip(), parts[1].strip()
        if not kw or not cnt:
            continue
        try:
            threshold_dict[kw] = int(cnt)
        except ValueError:
            logger.warning(f"阈值格式错误，已跳过: {line}")
    
    return threshold_dict


class ProcessingStats:
    """处理统计类"""
    
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.errors: List[str] = []
    
    def add_success(self):
        self.success += 1
        self.total += 1
    
    def add_failure(self, error_msg: str = ""):
        self.failed += 1
        self.total += 1
        if error_msg:
            self.errors.append(error_msg)
    
    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.success / self.total) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "success_rate": f"{self.success_rate:.1f}%"
        }