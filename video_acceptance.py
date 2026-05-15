"""
视频标注自动验收工具
支持自定义验收标准、批量处理、报告导出
"""
import streamlit as st
import os
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from utils import (
    create_csv_in_memory, format_duration, get_timestamp_filename,
    ProcessingStats, logger
)
from folder_uploader import folder_uploader
# 默认视频验收标准
DEFAULT_VIDEO_STANDARDS = [
    {
        "id": "vot01_default",
        "video_name": "VOT01.mp4",
        "min_frames": 200,
        "min_targets": 1,
        "description": "猎豹视频跨帧追踪标注"
    },
    {
        "id": "vot02_default",
        "video_name": "VOT02.mp4",
        "min_frames": 200,
        "min_targets": 2,
        "description": "电动自行车视频跨帧追踪标注"
    },
    {
        "id": "vot03_default",
        "video_name": "VOT03.mp4",
        "min_frames": 200,
        "min_targets": 1,
        "description": "神舟十四号飞船视频跨帧追踪标注"
    }
]
# ------------------------------
# 会话状态管理
# ------------------------------
def init_video_standards() -> None:
    """初始化视频验收标准到会话状态"""
    if "video_acceptance_standards" not in st.session_state:
        st.session_state.video_acceptance_standards = DEFAULT_VIDEO_STANDARDS.copy()
def get_video_standards() -> List[Dict[str, Any]]:
    """获取当前视频验收标准"""
    return st.session_state.get("video_acceptance_standards", [])
def delete_video_standard(standard_id: str) -> None:
    """删除指定验收标准"""
    new_list = [s for s in get_video_standards() if s.get("id") != standard_id]
    st.session_state.video_acceptance_standards = new_list
    # 已删除 st.rerun()
def add_new_video_standard() -> None:
    """添加新的验收标准"""
    new_id = str(uuid.uuid4())
    st.session_state.video_acceptance_standards.append({
        "id": new_id,
        "video_name": "",
        "min_frames": 200,
        "min_targets": 1,
        "description": ""
    })
    # 已删除 st.rerun()
def reset_video_to_default() -> None:
    """重置为默认验收标准"""
    st.session_state.video_acceptance_standards = DEFAULT_VIDEO_STANDARDS.copy()
    # 已删除 st.rerun()
# ------------------------------
# JSON 解析与验证
# ------------------------------
def parse_single_video_annotation(item: Dict[str, Any], file_name: str) -> Dict[str, Any]:
    """
    解析单个视频标注数据
    
    支持两种数据格式：
    格式1: 包含 video_url 和 box 数组的格式
    格式2: 包含 video_name、total_frames 和 annotations 的格式
    
    Args:
        item: 单条标注数据
        file_name: 来源文件名
    
    Returns:
        解析结果字典
    """
    try:
        # 尝试格式2：包含 video_name、total_frames 和 annotations 的格式
        video_name = item.get("video_name", "")
        
        if video_name:
            # 使用格式2解析
            total_frames = item.get("total_frames", 0)
            annotations = item.get("annotations", [])
            metadata = item.get("metadata", {})
            duration = metadata.get("duration", 0.0)
            
            # 统计目标数量和有效帧数
            target_ids = set()
            enabled_frames = set()
            all_labels = []
            
            for annotation in annotations:
                frame_id = annotation.get("frame_id", 0)
                targets = annotation.get("targets", [])
                
                for target in targets:
                    target_id = target.get("id", "")
                    if target_id:
                        target_ids.add(target_id)
                        enabled_frames.add(frame_id)
                    
                    label = target.get("label", "")
                    if label:
                        all_labels.append(label)
            
            total_targets = len(target_ids)
            max_enabled_frames = len(enabled_frames)
            
        else:
            # 格式1：从 video_url 提取视频文件名
            video_url = item.get("video_url", "")
            video_name = os.path.basename(video_url) if video_url else f"{file_name}_未知视频"
            
            # 解析 box 数组（每个 box 是一个追踪目标）
            box_list = item.get("box", [])
            total_targets = len(box_list)
            
            all_enabled_frames: List[int] = []
            all_labels: List[str] = []
            total_frames = 0
            duration = 0.0
            for idx, box in enumerate(box_list):
                sequence = box.get("sequence", [])
                
                # 统计启用的帧数
                enabled_count = sum(1 for frame in sequence if frame.get("enabled", True))
                all_enabled_frames.append(enabled_count)
                
                # 收集标签
                labels = box.get("labels", [])
                all_labels.extend(labels)
                
                # 从第一个 box 获取视频信息
                if idx == 0:
                    total_frames = box.get("framesCount", 0)
                    duration = box.get("duration", 0)
            max_enabled_frames = max(all_enabled_frames) if all_enabled_frames else 0
        
        return {
            "status": "success",
            "video_name": video_name,
            "json_file_name": file_name,
            "total_frames": total_frames,
            "duration": round(duration, 2),
            "total_targets": total_targets,
            "max_enabled_frames": max_enabled_frames,
            "labels": list(set(all_labels))
        }
        
    except Exception as e:
        logger.error(f"解析视频标注失败 [{file_name}]: {str(e)}")
        return {"status": "error", "file_name": file_name, "error": str(e)}
def parse_video_annotation_json(file_obj) -> List[Dict[str, Any]]:
    """
    解析视频标注 JSON 文件
    
    Args:
        file_obj: 上传的文件对象
    
    Returns:
        解析结果列表
    """
    results = []
    file_name = getattr(file_obj, 'name', '未知文件')
    
    try:
        file_obj.seek(0)
        json_data = json.load(file_obj)
        items = json_data if isinstance(json_data, list) else [json_data]
        
        for item in items:
            results.append(parse_single_video_annotation(item, file_name))
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误 [{file_name}]: {str(e)}")
        return [{"status": "invalid_json", "file_name": file_name, "error": "JSON格式错误"}]
    except Exception as e:
        logger.error(f"文件处理错误 [{file_name}]: {str(e)}")
        return [{"status": "error", "file_name": file_name, "error": str(e)}]
    
    return results


def parse_video_annotation_json_from_path(file_path: str) -> List[Dict[str, Any]]:
    """
    解析视频标注 JSON 文件（从文件路径）
    
    Args:
        file_path: 文件路径
    
    Returns:
        解析结果列表
    """
    results = []
    file_name = os.path.basename(file_path)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        items = json_data if isinstance(json_data, list) else [json_data]
        
        for item in items:
            results.append(parse_single_video_annotation(item, file_name))
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误 [{file_name}]: {str(e)}")
        return [{"status": "invalid_json", "file_name": file_name, "error": "JSON格式错误"}]
    except Exception as e:
        logger.error(f"文件处理错误 [{file_name}]: {str(e)}")
        return [{"status": "error", "file_name": file_name, "error": str(e)}]
    
    return results

# ------------------------------
# 验收逻辑
# ------------------------------
def validate_video_annotation(
    parse_result: Dict[str, Any], 
    standard: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    验证视频标注是否符合标准
    
    Args:
        parse_result: 解析结果
        standard: 验收标准
    
    Returns:
        (是否合格, 不合格原因列表)
    """
    is_valid = True
    reasons = []
    
    # 检查帧数
    min_frames = standard.get("min_frames", 200)
    actual_frames = parse_result.get("max_enabled_frames", 0)
    if actual_frames < min_frames:
        is_valid = False
        reasons.append(
            f"有效帧数不足：实际 {actual_frames} 帧，要求 ≥ {min_frames} 帧"
        )
    
    # 检查目标数
    min_targets = standard.get("min_targets", 1)
    actual_targets = parse_result.get("total_targets", 0)
    if actual_targets < min_targets:
        is_valid = False
        reasons.append(
            f"目标数不足：实际 {actual_targets} 个，要求 ≥ {min_targets} 个"
        )
    return is_valid, reasons
def match_video_standard(
    video_name: str, 
    standards: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    根据视频名称匹配合适的验收标准（后缀匹配）
    
    Args:
        video_name: 视频文件名
        standards: 标准列表
    
    Returns:
        匹配的标准，如果没有匹配则返回 None
    """
    for std in standards:
        suffix = std.get("video_suffix", "").strip()
        if suffix and video_name.endswith(suffix):
            return std
    return None
# ------------------------------
# 主页面
# ------------------------------
def video_acceptance_page() -> None:
    """视频标注自动验收页面"""
    st.title("🎬 视频标注自动验收工具")
    st.markdown("**批量验证视频标注质量，支持跨帧追踪标注验收**")
    
    init_video_standards()
    # 左侧边栏配置
    with st.sidebar:
        st.header("⚙️ 处理配置")
        max_workers = st.slider(
            "⚡ 并行处理线程数", 
            min_value=2, 
            max_value=16, 
            value=8,
            help="增加线程数可提高处理速度，但会占用更多系统资源"
        )
        st.divider()
        
        # 帮助信息
        with st.expander("💡 使用帮助", expanded=False):
            st.markdown("""
            **验收标准说明：**
            - **最低帧数**：目标追踪的有效帧数下限
            - **最低目标数**：需要追踪的目标数量下限
            
            **支持格式：** JSON 格式的视频标注文件
            
            **验收流程：**
            1. 配置验收标准（可使用默认标准）
            2. 上传 JSON 标注文件
            3. 填写验收员信息
            4. 点击开始验收
            5. 查看结果并导出报告
            """)
    # --------------------------
    # 验收标准面板
    # --------------------------
    with st.expander("⚙️ 验收标准配置", expanded=False):
        st.subheader("当前验收标准")
        
        # 使用表格形式展示标准
        for s in get_video_standards():
            with st.container():
                cols = st.columns([2, 1, 1, 2, 0.5])
                
                with cols[0]:
                    s["video_name"] = st.text_input(
                        "视频名称", 
                        value=s.get("video_name", ""), 
                        key=f"vname_{s['id']}",
                        placeholder="例如：VOT01.mp4"
                    )
                
                with cols[1]:
                    s["min_frames"] = st.number_input(
                        "最低帧数", 
                        min_value=1, 
                        value=s.get("min_frames", 200), 
                        key=f"frames_{s['id']}"
                    )
                
                with cols[2]:
                    s["min_targets"] = st.number_input(
                        "最低目标数", 
                        min_value=1, 
                        value=s.get("min_targets", 1), 
                        key=f"targets_{s['id']}"
                    )
                
                with cols[3]:
                    s["description"] = st.text_input(
                        "标准描述", 
                        value=s.get("description", ""), 
                        key=f"vdesc_{s['id']}"
                    )
                
                with cols[4]:
                    st.button(
                        "🗑️", 
                        key=f"vdel_{s['id']}", 
                        on_click=delete_video_standard, 
                        args=(s["id"],),
                        help="删除此标准"
                    )
                
                st.divider()
        # 操作按钮
        c1, c2 = st.columns(2)
        with c1:
            st.button("➕ 添加新标准", use_container_width=True, on_click=add_new_video_standard)
        with c2:
            st.button("🔄 恢复默认标准", use_container_width=True, on_click=reset_video_to_default)
    # --------------------------
    # 文件上传区
    # --------------------------
    st.subheader("📤 上传标注文件")
    
    # 使用文件夹上传组件
    uploaded_files = folder_uploader(
        label="选择视频标注文件夹",
        key="video_folder_uploader",
        file_extensions=[".json"],
        max_file_size_mb=100
    )
    
    # 将选中的文件保存到会话状态供后续处理
    if uploaded_files:
        st.session_state["video_selected_files"] = uploaded_files
    # 验收信息
    st.subheader("📝 验收信息")
    col1, col2 = st.columns(2)
    with col1:
        inspector = st.text_input("验收员", placeholder="请输入验收员姓名")
    with col2:
        inspection_time = st.date_input("验收时间", value=datetime.now())
    # --------------------------
    # 执行验收
    # --------------------------
    selected_files = st.session_state.get("video_selected_files", [])
    
    # 显示已选择的文件数
    if selected_files:
        st.info(f"✅ 已选择 {len(selected_files)} 个文件")
    
    if (selected_files or uploaded_files) and st.button("🚀 开始自动验收", type="primary", use_container_width=True):
        if not inspector:
            st.error("❌ 请输入验收员姓名！")
            st.stop()
        
        # 使用选中的文件
        files_to_process = selected_files if selected_files else uploaded_files
        
        # 构建标准列表
        standard_list = []
        for s in get_video_standards():
            video_name = s.get("video_name", "").strip()
            if not video_name:
                continue
            
            standard_list.append({
                "video_suffix": video_name,
                "min_frames": s.get("min_frames", 200),
                "min_targets": s.get("min_targets", 1),
                "description": s.get("description", "默认标准")
            })
        # 并行解析文件
        with st.spinner("⏳ 正在解析标注文件..."):
            progress_bar = st.progress(0)
            all_parse_results = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for file_info in files_to_process:
                    file_path = file_info["path"]
                    # 打开文件并创建类文件对象
                    futures[executor.submit(parse_video_annotation_json_from_path, file_path)] = file_path
                
                completed = 0
                total = len(futures)
                
                for future in as_completed(futures):
                    all_parse_results.extend(future.result())
                    completed += 1
                    progress_bar.progress(completed / total)
            
            progress_bar.empty()
        # 筛选有效解析结果
        success_parses = [r for r in all_parse_results if r.get("status") == "success"]
        invalid_parses = [r for r in all_parse_results if r.get("status") == "invalid_json"]
        error_parses = [r for r in all_parse_results if r.get("status") == "error"]
        if not success_parses:
            st.error("❌ 没有找到有效的标注文件！")
            if invalid_parses:
                st.warning(f"⚠️ {len(invalid_parses)} 个文件 JSON 格式无效")
            if error_parses:
                st.warning(f"⚠️ {len(error_parses)} 个文件解析出错")
            return
        # 执行验收
        acceptance_results = []
        for res in success_parses:
            video_name = res.get("video_name", "")
            
            # 匹配验收标准
            matched_std = match_video_standard(video_name, standard_list)
            if not matched_std:
                matched_std = {
                    "min_frames": 200,
                    "min_targets": 1,
                    "description": "默认标准（未匹配到特定标准）"
                }
            # 验证
            is_valid, reasons = validate_video_annotation(res, matched_std)
            # 格式化时长
            duration_str = format_duration(res.get("duration", 0))
            acceptance_results.append({
                "视频文件名": video_name,
                "来源JSON": res.get("json_file_name", ""),
                "总帧数": res.get("total_frames", 0),
                "时长": duration_str,
                "目标数": res.get("total_targets", 0),
                "最大有效帧数": res.get("max_enabled_frames", 0),
                "标签": "、".join(res.get("labels", [])) or "无",
                "验收标准": matched_std["description"],
                "结果": "✅ 合格" if is_valid else "❌ 不合格",
                "原因": "；".join(reasons) if reasons else "-"
            })
        # --------------------------
        # 结果展示
        # --------------------------
        st.divider()
        st.subheader("📊 验收结果统计")
        
        total = len(acceptance_results)
        ok_cnt = len([x for x in acceptance_results if x["结果"] == "✅ 合格"])
        
        # 统计卡片
        cols = st.columns(4)
        cols[0].metric("🎬 总视频数", total)
        cols[1].metric("✅ 合格", ok_cnt, delta_color="normal")
        cols[2].metric("❌ 不合格", total - ok_cnt, delta_color="inverse")
        cols[3].metric("📈 合格率", f"{ok_cnt/total*100:.1f}%" if total > 0 else "0%")
        # 详细结果表格
        st.subheader("📋 详细结果")
        
        # 筛选选项
        filter_option = st.radio(
            "筛选显示：", 
            ["全部", "仅合格", "仅不合格"], 
            horizontal=True,
            key="video_filter"
        )
        
        if filter_option == "仅合格":
            display_data = [x for x in acceptance_results if x["结果"] == "✅ 合格"]
        elif filter_option == "仅不合格":
            display_data = [x for x in acceptance_results if x["结果"] == "❌ 不合格"]
        else:
            display_data = acceptance_results
        
        st.dataframe(display_data, use_container_width=True, hide_index=True)
        # 异常文件提示
        if invalid_parses or error_parses:
            with st.expander("⚠️ 异常文件列表", expanded=False):
                if invalid_parses:
                    st.warning(f"**JSON 格式无效的文件 ({len(invalid_parses)} 个)：**")
                    for p in invalid_parses:
                        st.write(f"- {p.get('file_name', '未知')}")
                if error_parses:
                    st.warning(f"**解析出错的文件 ({len(error_parses)} 个)：**")
                    for p in error_parses:
                        st.write(f"- {p.get('file_name', '未知')}: {p.get('error', '未知错误')}")
        # --------------------------
        # 导出报告
        # --------------------------
        st.divider()
        st.subheader("📥 导出报告")
        
        # 构建报告内容
        report_rows = [
            ["视频标注验收报告"],
            ["验收员", inspector],
            ["验收时间", inspection_time.strftime("%Y-%m-%d")],
            ["总视频数", str(total)],
            ["合格数", str(ok_cnt)],
            ["不合格数", str(total - ok_cnt)],
            ["合格率", f"{ok_cnt/total*100:.1f}%" if total > 0 else "0%"],
            []
        ]
        
        if acceptance_results:
            report_rows.append(list(acceptance_results[0].keys()))
            for item in acceptance_results:
                report_rows.append([str(item[k]) for k in item.keys()])
        
        csv_file = create_csv_in_memory(None, report_rows)
        filename = get_timestamp_filename("视频标注验收报告", "csv")
        
        st.download_button(
            "📄 下载验收报告 (CSV)", 
            csv_file, 
            filename, 
            mime="text/csv",
            use_container_width=True
        )
        
        st.success("✅ 验收完成！")