"""
工具函数模块
提供CSV生成、日志记录、配置管理、文件处理等通用功能
"""
import csv
import logging
import os
import hashlib
from io import StringIO, BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path

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


# ------------------------------
# 文件处理工具函数
# ------------------------------

def calculate_file_hash(file_data: bytes, hash_algorithm: str = "sha256") -> str:
    """
    计算文件内容的哈希值
    
    Args:
        file_data: 文件内容字节流
        hash_algorithm: 哈希算法，默认 SHA256
    
    Returns:
        str: 十六进制哈希值
    """
    hash_obj = hashlib.new(hash_algorithm)
    hash_obj.update(file_data)
    return hash_obj.hexdigest()


def calculate_file_hash_from_path(file_path: str, hash_algorithm: str = "sha256") -> str:
    """
    从文件路径计算文件哈希值
    
    Args:
        file_path: 文件路径
        hash_algorithm: 哈希算法
    
    Returns:
        str: 十六进制哈希值
    """
    hash_obj = hashlib.new(hash_algorithm)
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except Exception as e:
        logger.error(f"计算文件哈希失败 [{file_path}]: {str(e)}")
        return ""


def scan_folder_recursively(folder_path: str, file_extensions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    递归扫描文件夹中的所有文件
    
    Args:
        folder_path: 文件夹路径
        file_extensions: 可选的文件扩展名过滤列表（如 [".json", ".txt"]）
    
    Returns:
        List[Dict]: 文件信息列表，包含 path, name, size, hash, relative_path
    """
    file_list = []
    
    try:
        # 检查路径是否存在
        if not os.path.exists(folder_path):
            logger.error(f"文件夹路径不存在: {folder_path}")
            return file_list
        
        # 检查是否有权限访问
        try:
            os.listdir(folder_path)
        except PermissionError:
            logger.error(f"没有权限访问文件夹: {folder_path}")
            return file_list
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 过滤文件扩展名
                if file_extensions:
                    ext = os.path.splitext(file)[1].lower()
                    if ext not in file_extensions:
                        continue
                
                file_path_full = os.path.join(root, file)
                relative_path = os.path.relpath(file_path_full, folder_path)
                
                try:
                    file_size = os.path.getsize(file_path_full)
                    file_hash = calculate_file_hash_from_path(file_path_full)
                    
                    file_list.append({
                        "path": file_path_full,
                        "name": file,
                        "size": file_size,
                        "hash": file_hash,
                        "relative_path": relative_path,
                        "folder_path": folder_path
                    })
                except PermissionError:
                    logger.warning(f"无法访问文件（权限不足）: {file_path_full}")
                except Exception as e:
                    logger.error(f"处理文件失败 [{file_path_full}]: {str(e)}")
    
    except Exception as e:
        logger.error(f"扫描文件夹失败 [{folder_path}]: {str(e)}")
    
    return file_list


# ------------------------------
# 重复检测工具函数
# ------------------------------

class DuplicateResult:
    """重复检测结果类"""
    def __init__(self):
        self.duplicate_groups: List[List[Dict[str, Any]]] = []  # 重复文件组
        self.unique_files: List[Dict[str, Any]] = []  # 唯一文件
    
    def add_duplicate_group(self, group: List[Dict[str, Any]]):
        """添加一个重复文件组"""
        if len(group) >= 2:
            self.duplicate_groups.append(group)
    
    def add_unique_file(self, file_info: Dict[str, Any]):
        """添加唯一文件"""
        self.unique_files.append(file_info)
    
    @property
    def total_duplicate_files(self) -> int:
        """总重复文件数"""
        return sum(len(group) for group in self.duplicate_groups)
    
    @property
    def total_unique_files(self) -> int:
        """总唯一文件数"""
        return len(self.unique_files)
    
    @property
    def has_duplicates(self) -> bool:
        """是否存在重复"""
        return len(self.duplicate_groups) > 0


def detect_duplicates(
    files: List[Dict[str, Any]],
    check_filename: bool = True,
    check_content: bool = True
) -> DuplicateResult:
    """
    检测重复文件
    
    Args:
        files: 文件信息列表
        check_filename: 是否按文件名检测重复
        check_content: 是否按内容哈希检测重复
    
    Returns:
        DuplicateResult: 重复检测结果
    """
    result = DuplicateResult()
    
    if not files:
        return result
    
    # 按文件名分组
    filename_groups: Dict[str, List[Dict[str, Any]]] = {}
    if check_filename:
        for file_info in files:
            filename = file_info["name"].lower()
            if filename not in filename_groups:
                filename_groups[filename] = []
            filename_groups[filename].append(file_info)
    
    # 按哈希分组
    hash_groups: Dict[str, List[Dict[str, Any]]] = {}
    if check_content:
        for file_info in files:
            file_hash = file_info.get("hash", "")
            if file_hash:
                if file_hash not in hash_groups:
                    hash_groups[file_hash] = []
                hash_groups[file_hash].append(file_info)
    
    # 找出重复的文件
    processed_files: Set[str] = set()
    
    # 先处理内容重复（更高优先级）
    for hash_val, group in hash_groups.items():
        if len(group) >= 2:
            # 标记这些文件为已处理
            for f in group:
                processed_files.add(f["path"])
            result.add_duplicate_group(group)
    
    # 再处理文件名重复（排除已处理的）
    if check_filename:
        for filename, group in filename_groups.items():
            filtered_group = [f for f in group if f["path"] not in processed_files]
            if len(filtered_group) >= 2:
                for f in filtered_group:
                    processed_files.add(f["path"])
                result.add_duplicate_group(filtered_group)
    
    # 剩余的是唯一文件
    for file_info in files:
        if file_info["path"] not in processed_files:
            result.add_unique_file(file_info)
    
    return result


def generate_duplicate_report(duplicate_result: DuplicateResult) -> str:
    """
    生成重复检测报告
    
    Args:
        duplicate_result: 重复检测结果
    
    Returns:
        str: 格式化的报告文本
    """
    if not duplicate_result.has_duplicates:
        return "✅ 未发现重复文件"
    
    report_lines = ["⚠️ 发现重复文件："]
    
    for idx, group in enumerate(duplicate_result.duplicate_groups, 1):
        first_file = group[0]
        report_lines.append(f"\n📦 重复组 #{idx}")
        report_lines.append(f"   文件名: {first_file['name']}")
        report_lines.append(f"   重复数量: {len(group)} 个")
        report_lines.append("   文件位置:")
        
        for file_info in group:
            report_lines.append(f"     - {file_info['path']}")
    
    return "\n".join(report_lines)