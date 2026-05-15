"""
文件夹上传组件
提供文件夹选择、递归扫描、重复检测和交互处理功能
"""
import os
import streamlit as st
from typing import List, Dict, Any, Optional, Callable

from utils import (
    scan_folder_recursively,
    detect_duplicates,
    DuplicateResult,
    format_file_size,
    logger
)

# 重复处理选项
DUPLICATE_ACTIONS = {
    "skip": "跳过重复",
    "replace": "替换",
    "keep_both": "保留两份"
}


class FolderUploader:
    """文件夹上传器类"""
    
    def __init__(
        self,
        key: str = "folder_uploader",
        file_extensions: Optional[List[str]] = None,
        max_file_size_mb: int = 100,
        on_upload_callback: Optional[Callable] = None
    ):
        """
        初始化文件夹上传器
        
        Args:
            key: Streamlit组件唯一标识
            file_extensions: 允许的文件扩展名列表
            max_file_size_mb: 最大文件大小限制（MB）
            on_upload_callback: 上传完成后的回调函数
        """
        self.key = key
        self.file_extensions = file_extensions or []
        self.max_file_size_mb = max_file_size_mb
        self.on_upload_callback = on_upload_callback
        
        # 初始化会话状态
        if f"{key}_selected_folder" not in st.session_state:
            st.session_state[f"{key}_selected_folder"] = ""
        if f"{key}_scanned_files" not in st.session_state:
            st.session_state[f"{key}_scanned_files"] = []
        if f"{key}_duplicate_result" not in st.session_state:
            st.session_state[f"{key}_duplicate_result"] = None
        if f"{key}_duplicate_actions" not in st.session_state:
            st.session_state[f"{key}_duplicate_actions"] = {}
        if f"{key}_upload_ready" not in st.session_state:
            st.session_state[f"{key}_upload_ready"] = False
    
    def _scan_folder(self, folder_path: str) -> List[Dict[str, Any]]:
        """扫描文件夹并返回文件列表"""
        if not folder_path or not os.path.isdir(folder_path):
            return []
        
        return scan_folder_recursively(folder_path, self.file_extensions)
    
    def _check_file_size(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """检查文件大小限制，返回超出限制的文件"""
        max_size_bytes = self.max_file_size_mb * 1024 * 1024
        oversized_files = []
        
        for file_info in files:
            if file_info["size"] > max_size_bytes:
                oversized_files.append(file_info)
        
        return oversized_files
    
    def _display_duplicate_group(self, group_idx: int, group: List[Dict[str, Any]]):
        """显示单个重复文件组"""
        first_file = group[0]
        
        with st.expander(f"📦 重复组 #{group_idx + 1} - {first_file['name']}"):
            st.write(f"**重复数量**: {len(group)} 个")
            
            # 显示每个文件的详细信息
            for file_idx, file_info in enumerate(group):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**文件 {file_idx + 1}**:")
                    st.write(f"   路径: `{file_info['path']}`")
                    st.write(f"   大小: {format_file_size(file_info['size'])}")
                    if file_info.get("hash"):
                        st.write(f"   哈希: `{file_info['hash'][:16]}...`")
                
                with col2:
                    action_key = f"{self.key}_action_{group_idx}_{file_idx}"
                    if action_key not in st.session_state[f"{self.key}_duplicate_actions"]:
                        st.session_state[f"{self.key}_duplicate_actions"][action_key] = "skip"
                    
                    st.selectbox(
                        "处理方式",
                        options=list(DUPLICATE_ACTIONS.keys()),
                        format_func=lambda x: DUPLICATE_ACTIONS[x],
                        key=action_key,
                        index=0
                    )
    
    def _process_duplicates(self) -> List[Dict[str, Any]]:
        """根据用户选择处理重复文件"""
        result = st.session_state[f"{self.key}_duplicate_result"]
        if not result or not result.has_duplicates:
            return st.session_state[f"{self.key}_scanned_files"]
        
        # 收集用户选择保留的文件
        selected_files = []
        processed_paths = set()
        
        for group_idx, group in enumerate(result.duplicate_groups):
            # 获取用户对每个文件的处理选择
            actions = []
            for file_idx, file_info in enumerate(group):
                action_key = f"{self.key}_action_{group_idx}_{file_idx}"
                action = st.session_state[f"{self.key}_duplicate_actions"].get(action_key, "skip")
                actions.append((file_info, action))
            
            # 根据处理方式决定保留哪些文件
            if all(a[1] == "skip" for a in actions):
                # 全部跳过
                continue
            
            elif any(a[1] == "replace" for a in actions):
                # 替换模式：保留最后一个选择"替换"的文件
                replace_files = [a[0] for a in actions if a[1] == "replace"]
                if replace_files:
                    selected_files.append(replace_files[-1])
                    processed_paths.add(replace_files[-1]["path"])
            
            elif any(a[1] == "keep_both" for a in actions):
                # 保留两份模式：保留所有选择"保留两份"的文件
                for file_info, action in actions:
                    if action == "keep_both":
                        selected_files.append(file_info)
                        processed_paths.add(file_info["path"])
            
            else:
                # 默认保留第一个文件
                selected_files.append(group[0])
                processed_paths.add(group[0]["path"])
        
        # 添加唯一文件
        for file_info in result.unique_files:
            if file_info["path"] not in processed_paths:
                selected_files.append(file_info)
        
        return selected_files
    
    def render(self) -> Optional[List[Dict[str, Any]]]:
        """渲染文件夹上传组件"""
        key = self.key
        
        # 选择上传方式：文件夹扫描或文件上传
        tab1, tab2 = st.tabs(["📂 扫描文件夹", "📁 上传文件"])
        
        with tab1:
            st.subheader("扫描文件夹")
            
            # 使用Streamlit的文件夹选择组件（支持拖拽和点击选择）
            folder_path = st.text_input(
                "文件夹路径",
                value=st.session_state[f"{key}_selected_folder"],
                key=f"{key}_folder_input",
                placeholder="请输入文件夹路径或直接粘贴（例如：C:\\Users\\xxx\\Documents）",
                help="输入要扫描的文件夹完整路径"
            )
            
            # 添加操作提示
            st.info("💡 提示：可以在文件资源管理器中复制文件夹路径，然后粘贴到上方输入框中")
            
            # 保存路径到会话状态
            if folder_path != st.session_state[f"{key}_selected_folder"]:
                st.session_state[f"{key}_selected_folder"] = folder_path
                # 重置扫描状态
                st.session_state[f"{key}_scanned_files"] = []
                st.session_state[f"{key}_duplicate_result"] = None
                st.session_state[f"{key}_upload_ready"] = False
            
            # 扫描按钮
            scan_col, clear_col = st.columns([1, 1])
            with scan_col:
                scan_button = st.button("🔍 扫描文件夹", key=f"{key}_scan_btn")
            
            with clear_col:
                clear_button = st.button("🗑️ 清除选择", key=f"{key}_clear_btn")
            
            if clear_button:
                st.session_state[f"{key}_selected_folder"] = ""
                st.session_state[f"{key}_scanned_files"] = []
                st.session_state[f"{key}_duplicate_result"] = None
                st.session_state[f"{key}_upload_ready"] = False
                st.session_state[f"{key}_duplicate_actions"] = {}
                st.rerun()
            
            # 扫描文件夹
            if scan_button and folder_path:
                # 清理前后的空格
                folder_path = folder_path.strip()
                
                # 检查路径是否存在
                if not os.path.exists(folder_path):
                    st.error(f"❌ 路径不存在: {folder_path}")
                    return None
                
                # 检查是否是文件夹
                if not os.path.isdir(folder_path):
                    st.error(f"❌ 路径不是文件夹: {folder_path}")
                    return None
                
                # 检查是否有权限访问
                try:
                    os.listdir(folder_path)
                except PermissionError:
                    st.error(f"❌ 没有权限访问该文件夹: {folder_path}")
                    return None
                
                with st.spinner("正在扫描文件夹..."):
                    try:
                        files = self._scan_folder(folder_path)
                        
                        if not files:
                            # 检查文件夹中是否有文件（不考虑扩展名过滤）
                            all_files = []
                            for root, dirs, files_in_dir in os.walk(folder_path):
                                all_files.extend(files_in_dir)
                            
                            if not all_files:
                                st.warning(f"⚠️ 文件夹是空的: {folder_path}")
                            else:
                                st.warning(f"⚠️ 文件夹中没有找到匹配扩展名的文件（期望: {self.file_extensions}）")
                            return None
                    except Exception as e:
                        st.error(f"❌ 扫描文件夹时发生错误: {str(e)}")
                        logger.error(f"扫描文件夹失败 [{folder_path}]: {str(e)}")
                        return None
                    
                    # 检查文件大小
                    oversized_files = self._check_file_size(files)
                    if oversized_files:
                        st.error(f"❌ 发现 {len(oversized_files)} 个文件超出大小限制 ({self.max_file_size_mb}MB):")
                        for f in oversized_files:
                            st.write(f"   - {f['name']} ({format_file_size(f['size'])})")
                        return None
                    
                    # 检测重复
                    st.session_state[f"{key}_scanned_files"] = files
                    st.session_state[f"{key}_duplicate_result"] = detect_duplicates(files)
                    st.session_state[f"{key}_upload_ready"] = True
                    
                    # 初始化重复处理操作
                    duplicate_result = st.session_state[f"{key}_duplicate_result"]
                    if duplicate_result.has_duplicates:
                        st.session_state[f"{key}_duplicate_actions"] = {}
                        for group_idx, group in enumerate(duplicate_result.duplicate_groups):
                            st.session_state[f"{key}_duplicate_actions"][group_idx] = "keep_both"
        
        with tab2:
            st.subheader("上传文件")
            
            # 文件上传组件
            uploaded_files = st.file_uploader(
                "选择文件",
                type=self.file_extensions if self.file_extensions else None,
                accept_multiple_files=True,
                key=f"{key}_file_uploader",
                help=f"支持多选，{f'仅支持 {self.file_extensions}' if self.file_extensions else '支持所有类型'}"
            )
            
            if uploaded_files:
                st.success(f"✅ 已选择 {len(uploaded_files)} 个文件")
                
                # 转换上传文件为统一格式
                files = []
                for uploaded_file in uploaded_files:
                    file_info = {
                        "name": uploaded_file.name,
                        "path": uploaded_file.name,  # 上传文件没有完整路径
                        "size": uploaded_file.size,
                        "hash": "",
                        "uploaded": True  # 标记为上传文件
                    }
                    files.append(file_info)
                
                # 检查文件大小
                oversized_files = self._check_file_size(files)
                if oversized_files:
                    st.error(f"❌ 发现 {len(oversized_files)} 个文件超出大小限制 ({self.max_file_size_mb}MB):")
                    for f in oversized_files:
                        st.write(f"   - {f['name']} ({format_file_size(f['size'])})")
                    return None
                
                # 检测重复
                st.session_state[f"{key}_scanned_files"] = files
                st.session_state[f"{key}_duplicate_result"] = detect_duplicates(files)
                st.session_state[f"{key}_upload_ready"] = True
                
                # 初始化重复处理操作
                duplicate_result = st.session_state[f"{key}_duplicate_result"]
                if duplicate_result.has_duplicates:
                    st.session_state[f"{key}_duplicate_actions"] = {}
                    for group_idx, group in enumerate(duplicate_result.duplicate_groups):
                        st.session_state[f"{key}_duplicate_actions"][group_idx] = "keep_both"
        

        
        # 显示扫描结果
        if st.session_state[f"{key}_upload_ready"]:
            files = st.session_state[f"{key}_scanned_files"]
            duplicate_result = st.session_state[f"{key}_duplicate_result"]
            
            # 显示统计信息
            st.subheader("📊 扫描结果")
            col1, col2, col3 = st.columns(3)
            col1.metric("总文件数", len(files))
            col2.metric("唯一文件", duplicate_result.total_unique_files)
            col3.metric("重复文件", duplicate_result.total_duplicate_files)
            
            # 显示重复文件
            if duplicate_result.has_duplicates:
                st.warning(f"⚠️ 发现 {len(duplicate_result.duplicate_groups)} 组重复文件")
                
                # 显示重复处理选项
                st.subheader("🔄 重复文件处理")
                st.info("""
                    **处理方式说明**:
                    - **跳过重复**: 跳过该文件，不上传
                    - **替换**: 替换已存在的同名/同内容文件（仅保留最后一个选择"替换"的文件）
                    - **保留两份**: 保留该文件，即使有重复
                """)
                
                for group_idx, group in enumerate(duplicate_result.duplicate_groups):
                    self._display_duplicate_group(group_idx, group)
            
            # 显示文件列表
            with st.expander("📋 文件列表"):
                for file_info in files:
                    st.write(f"- `{file_info['relative_path']}` ({format_file_size(file_info['size'])})")
            
            # 上传按钮
            if st.button("🚀 开始上传", key=f"{key}_upload_btn"):
                with st.spinner("正在处理文件..."):
                    final_files = self._process_duplicates()
                    st.success(f"✅ 已选择 {len(final_files)} 个文件准备上传")
                    
                    if self.on_upload_callback:
                        self.on_upload_callback(final_files)
                    
                    return final_files
        
        return None


def folder_uploader(
    label: str = "选择文件夹",
    key: str = "folder_uploader",
    file_extensions: Optional[List[str]] = None,
    max_file_size_mb: int = 100,
    on_upload_callback: Optional[Callable] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    快捷函数：创建并渲染文件夹上传组件
    
    Args:
        label: 组件标签
        key: Streamlit组件唯一标识
        file_extensions: 允许的文件扩展名列表
        max_file_size_mb: 最大文件大小限制（MB）
        on_upload_callback: 上传完成后的回调函数
    
    Returns:
        List[Dict]: 选中的文件信息列表，包含 path, name, size, hash, relative_path, folder_path
    """
    uploader = FolderUploader(
        key=key,
        file_extensions=file_extensions,
        max_file_size_mb=max_file_size_mb,
        on_upload_callback=on_upload_callback
    )
    return uploader.render()