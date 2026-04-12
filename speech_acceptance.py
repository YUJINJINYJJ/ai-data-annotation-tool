"""
语音标注自动验收工具
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
    parse_keywords_input, ProcessingStats, logger
)

# 默认语音验收标准
DEFAULT_SPEECH_STANDARDS = [
    {
        "id": "speech04_default",
        "audio_name": "speech04.mp3",
        "min_segments": 2,
        "max_silence_ratio_in_segment": 10,
        "required_labels": ["碎裂声"],
        "description": "speech04.mp3 碎裂声事件检测标注"
    },
    {
        "id": "speech05_default",
        "audio_name": "speech05.mp3",
        "min_total_duration": 1.0,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": ["安全警报"],
        "description": "speech05.mp3 安全警报声事件检测标注"
    },
    {
        "id": "speech06_default",
        "audio_name": "speech06.mp3",
        "min_segments_per_label": 2,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": ["枪击声", "爆炸声", "叫喊声"],
        "description": "speech06.mp3 枪击/爆炸/叫喊声事件检测标注"
    },
    {
        "id": "speech07_default",
        "audio_name": "speech07.mp3",
        "min_segments_per_label": 2,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": ["咳嗽声", "呼救声"],
        "description": "speech07.mp3 咳嗽/呼救声事件检测标注"
    }
]

# 已知的有效声音标签（用于验证和提示）
KNOWN_SOUND_LABELS = [
    "碎裂声", "安全警报", "枪击声", "爆炸声", "叫喊声", 
    "咳嗽声", "呼救声", "玻璃破碎声", "汽车喇叭声", "狗叫声",
    "哭声", "笑声", "敲门声", "电话铃声", "警笛声"
]

# ------------------------------
# 会话状态管理
# ------------------------------
def init_speech_standards() -> None:
    """初始化语音验收标准到会话状态"""
    if "speech_acceptance_standards" not in st.session_state:
        st.session_state.speech_acceptance_standards = DEFAULT_SPEECH_STANDARDS.copy()

def get_speech_standards() -> List[Dict[str, Any]]:
    """获取当前语音验收标准"""
    return st.session_state.get("speech_acceptance_standards", [])

def delete_speech_standard(standard_id: str) -> None:
    """删除指定验收标准"""
    new_list = [s for s in get_speech_standards() if s.get("id") != standard_id]
    st.session_state.speech_acceptance_standards = new_list
    # 已删除 st.rerun()

def add_new_speech_standard() -> None:
    """添加新的验收标准"""
    new_id = str(uuid.uuid4())
    st.session_state.speech_acceptance_standards.append({
        "id": new_id,
        "audio_name": "",
        "min_segments": 1,
        "min_total_duration": 1.0,
        "min_segments_per_label": 1,
        "max_silence_ratio_in_segment": 10,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": [],
        "description": ""
    })
    # 已删除 st.rerun()

def reset_speech_to_default() -> None:
    """重置为默认验收标准"""
    st.session_state.speech_acceptance_standards = DEFAULT_SPEECH_STANDARDS.copy()
    # 已删除 st.rerun()

# ------------------------------
# JSON 解析与验证
# ------------------------------
def parse_single_speech_annotation(item: Dict[str, Any], file_name: str) -> Dict[str, Any]:
    """
    解析单个语音标注数据
    
    Args:
        item: 单条标注数据
        file_name: 来源文件名
    
    Returns:
        解析结果字典
    """
    try:
        # 从 audio_url 提取音频文件名
        audio_url = item.get("audio_url", "")
        audio_name = os.path.basename(audio_url) if audio_url else f"{file_name}_未知音频"
        
        # 解析 segments 数组
        segments = item.get("segments", [])
        total_duration = item.get("duration", 0)
        
        # 初始化统计数据
        label_stats: Dict[str, Dict[str, Any]] = {}
        total_segments = 0
        all_segment_silence_ratios: List[float] = []
        all_segment_other_ratios: List[float] = []
        
        # 收集所有出现的标签
        all_labels_found: set = set()
        for seg in segments:
            if not seg.get("enabled", True):
                continue
            
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            seg_total_duration = end - start
            
            if seg_total_duration <= 0:
                continue
            
            total_segments += 1
            labels = seg.get("labels", [])
            all_labels_found.update(labels)
            
            # 计算片段内的无声比例
            seg_silence_duration = 0 if labels else seg_total_duration
            seg_silence_ratio = round(
                (seg_silence_duration / seg_total_duration) * 100, 2
            ) if seg_total_duration > 0 else 0
            all_segment_silence_ratios.append(seg_silence_ratio)

            # 计算片段内的其他声音比例（非已知标签的声音）
            seg_other_duration = 0
            for label in labels:
                # 如果标签不在已知标签列表中，视为其他声音
                if label not in KNOWN_SOUND_LABELS:
                    seg_other_duration += seg_total_duration / len(labels) if labels else 0
            
            seg_other_ratio = round(
                (seg_other_duration / seg_total_duration) * 100, 2
            ) if seg_total_duration > 0 else 0
            all_segment_other_ratios.append(seg_other_ratio)

            # 更新标签统计
            for label in labels:
                if label not in label_stats:
                    label_stats[label] = {
                        "count": 0,
                        "total_duration": 0,
                        "max_silence_ratio": 0,
                        "max_other_ratio": 0
                    }
                label_stats[label]["count"] += 1
                label_stats[label]["total_duration"] += seg_total_duration
                label_stats[label]["max_silence_ratio"] = max(
                    label_stats[label]["max_silence_ratio"], seg_silence_ratio
                )
                label_stats[label]["max_other_ratio"] = max(
                    label_stats[label]["max_other_ratio"], seg_other_ratio
                )

        # 计算全局统计
        avg_silence_ratio = round(
            sum(all_segment_silence_ratios) / len(all_segment_silence_ratios), 2
        ) if all_segment_silence_ratios else 0
        avg_other_ratio = round(
            sum(all_segment_other_ratios) / len(all_segment_other_ratios), 2
        ) if all_segment_other_ratios else 0
        max_silence_ratio = max(all_segment_silence_ratios) if all_segment_silence_ratios else 0
        max_other_ratio = max(all_segment_other_ratios) if all_segment_other_ratios else 0

        return {
            "status": "success",
            "audio_name": audio_name,
            "json_file_name": file_name,
            "total_duration": round(total_duration, 2),
            "total_segments": total_segments,
            "label_stats": label_stats,
            "all_labels": list(all_labels_found),
            "avg_silence_ratio": avg_silence_ratio,
            "max_silence_ratio": max_silence_ratio,
            "avg_other_ratio": avg_other_ratio,
            "max_other_ratio": max_other_ratio
        }
        
    except Exception as e:
        logger.error(f"解析语音标注失败 [{file_name}]: {str(e)}")
        return {"status": "error", "file_name": file_name, "error": str(e)}

def parse_speech_annotation_json(file_obj) -> List[Dict[str, Any]]:
    """
    解析语音标注 JSON 文件
    
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
            results.append(parse_single_speech_annotation(item, file_name))
            
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
def validate_speech_annotation(
    parse_result: Dict[str, Any], 
    standard: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    验证语音标注是否符合标准
    
    Args:
        parse_result: 解析结果
        standard: 验收标准
    
    Returns:
        (是否合格, 不合格原因列表)
    """
    is_valid = True
    reasons = []
    label_stats = parse_result.get("label_stats", {})
    
    # 1. 检查总片段数
    min_segments = standard.get("min_segments", 1)
    if parse_result.get("total_segments", 0) < min_segments:
        is_valid = False
        reasons.append(
            f"总片段数不足：实际 {parse_result.get('total_segments', 0)} 个，"
            f"要求 ≥ {min_segments} 个"
        )

    # 2. 检查片段内最大无声比例
    max_silence_ratio = standard.get("max_silence_ratio", 10)
    if parse_result.get("max_silence_ratio", 0) > max_silence_ratio:
        is_valid = False
        reasons.append(
            f"片段内无声比例过高：最高 {parse_result.get('max_silence_ratio', 0)}%，"
            f"要求 ≤ {max_silence_ratio}%"
        )

    # 3. 检查片段内最大其他声音比例
    max_other_ratio = standard.get("max_other_ratio", 10)
    if parse_result.get("max_other_ratio", 0) > max_other_ratio:
        is_valid = False
        reasons.append(
            f"片段内其他声音比例过高：最高 {parse_result.get('max_other_ratio', 0)}%，"
            f"要求 ≤ {max_other_ratio}%"
        )

    # 4. 检查要求标签
    required_labels = standard.get("required_labels", [])
    min_segments_per_label = standard.get("min_segments_per_label", 1)
    min_total_duration = standard.get("min_total_duration", 1.0)
    
    for label in required_labels:
        stats = label_stats.get(label, {"count": 0, "total_duration": 0})
        
        # 检查每标签最少片段数
        if stats["count"] < min_segments_per_label:
            is_valid = False
            reasons.append(
                f"「{label}」片段数不足：实际 {stats['count']} 个，"
                f"要求 ≥ {min_segments_per_label} 个"
            )
        
        # 检查标签总时长
        if stats.get("total_duration", 0) < min_total_duration:
            is_valid = False
            reasons.append(
                f"「{label}」总时长不足：实际 {stats.get('total_duration', 0):.1f} 秒，"
                f"要求 ≥ {min_total_duration} 秒"
            )
        
        # 检查标签对应片段的无声/其他比例
        if stats.get("max_silence_ratio", 0) > max_silence_ratio:
            is_valid = False
            reasons.append(
                f"「{label}」片段无声比例过高：{stats['max_silence_ratio']}%，"
                f"要求 ≤ {max_silence_ratio}%"
            )
        if stats.get("max_other_ratio", 0) > max_other_ratio:
            is_valid = False
            reasons.append(
                f"「{label}」片段其他声音比例过高：{stats['max_other_ratio']}%，"
                f"要求 ≤ {max_other_ratio}%"
            )
    return is_valid, reasons

def match_standard(
    audio_name: str, 
    standards: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    根据音频名称匹配合适的验收标准（后缀匹配）
    
    Args:
        audio_name: 音频文件名
        standards: 标准列表
    
    Returns:
        匹配的标准，如果没有匹配则返回 None
    """
    for std in standards:
        suffix = std.get("audio_suffix", "").strip()
        if suffix and audio_name.endswith(suffix):
            return std
    return None

# ------------------------------
# 主页面
# ------------------------------
def speech_acceptance_page() -> None:
    """语音标注自动验收页面"""
    st.title("🎙️ 语音标注自动验收工具")
    st.markdown("**批量验证语音标注质量，支持自定义验收标准**")
    
    init_speech_standards()
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
            - **最少总片段数**：标注的片段总数下限
            - **每标签最少片段数**：每个要求标签的片段数下限
            - **最少总时长**：每个标签的累计时长下限
            - **最大无声比例**：片段内无标签部分的最大占比
            - **最大其他声音比例**：片段内非目标声音的最大占比
            
            **支持格式：** JSON 格式的语音标注文件
            """)

    # --------------------------
    # 验收标准面板
    # --------------------------
    with st.expander("⚙️ 验收标准配置", expanded=False):
        st.subheader("当前验收标准")
        
        # 显示标准表格
        for s in get_speech_standards():
            with st.container():
                cols = st.columns([2, 1.5, 1.5, 2, 0.5])
                
                with cols[0]:
                    s["audio_name"] = st.text_input(
                        "音频名称", 
                        value=s.get("audio_name", ""), 
                        key=f"audio_{s['id']}",
                        placeholder="例如：speech01.mp3"
                    )
                    s["description"] = st.text_input(
                        "标准描述", 
                        value=s.get("description", ""), 
                        key=f"desc_{s['id']}"
                    )
                
                with cols[1]:
                    required = s.get("required_labels", [])
                    if isinstance(required, list):
                        required = ",".join(required)
                    s["required_labels"] = st.text_input(
                        "要求标签（逗号分隔）", 
                        value=required, 
                        key=f"labels_{s['id']}",
                        placeholder="例如：碎裂声,爆炸声"
                    )
                
                with cols[2]:
                    s["min_segments"] = st.number_input(
                        "最少总片段数", 
                        min_value=1, 
                        value=s.get("min_segments", 1), 
                        key=f"min_seg_{s['id']}"
                    )
                    # 修复：统一float类型，无类型冲突
                    s["min_total_duration"] = st.number_input(
                        "最少总时长(秒)", 
                        min_value=0.1, 
                        value=float(s.get("min_total_duration", 1.0)),
                        step=0.1,
                        key=f"min_dur_{s['id']}"
                    )
                    s["min_segments_per_label"] = st.number_input(
                        "每标签最少片段数", 
                        min_value=1, 
                        value=s.get("min_segments_per_label", 1), 
                        key=f"min_seg_label_{s['id']}"
                    )
                
                with cols[3]:
                    s["max_silence_ratio_in_segment"] = st.number_input(
                        "最大无声比例(%)", 
                        min_value=0, 
                        max_value=100, 
                        value=s.get("max_silence_ratio_in_segment", 10), 
                        key=f"max_silence_{s['id']}"
                    )
                    s["max_other_sound_ratio_in_segment"] = st.number_input(
                        "最大其他声音比例(%)", 
                        min_value=0, 
                        max_value=100, 
                        value=s.get("max_other_sound_ratio_in_segment", 10), 
                        key=f"max_other_{s['id']}"
                    )
                
                with cols[4]:
                    st.button(
                        "🗑️", 
                        key=f"del_{s['id']}", 
                        on_click=delete_speech_standard, 
                        args=(s["id"],),
                        help="删除此标准"
                    )
                
                st.divider()
        # 操作按钮
        c1, c2 = st.columns(2)
        with c1:
            st.button("➕ 添加新标准", use_container_width=True, on_click=add_new_speech_standard)
        with c2:
            st.button("🔄 恢复默认标准", use_container_width=True, on_click=reset_speech_to_default)

    # --------------------------
    # 文件上传区
    # --------------------------
    st.subheader("📤 上传标注文件")
    
    uploaded_jsons = st.file_uploader(
        "选择语音标注 JSON 文件",
        type="json",
        accept_multiple_files=True,
        key="speech_uploader"
    )
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🗑️ 清空上传文件", use_container_width=True):
            if "speech_uploader" in st.session_state:
                del st.session_state.speech_uploader
            st.rerun()
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
    if uploaded_jsons and st.button("🚀 开始自动验收", type="primary", use_container_width=True):
        if not inspector:
            st.error("❌ 请输入验收员姓名！")
            st.stop()
        # 构建标准列表
        standard_list = []
        for s in get_speech_standards():
            audio_name = s.get("audio_name", "").strip()
            if not audio_name:
                continue
                
            labels = s.get("required_labels", "")
            if isinstance(labels, str):
                labels = parse_keywords_input(labels)
            
            standard_list.append({
                "audio_suffix": audio_name,
                "min_segments": s.get("min_segments", 1),
                "min_total_duration": float(s.get("min_total_duration", 1.0)),
                "min_segments_per_label": s.get("min_segments_per_label", 1),
                "max_silence_ratio": s.get("max_silence_ratio_in_segment", 10),
                "max_other_ratio": s.get("max_other_sound_ratio_in_segment", 10),
                "required_labels": labels,
                "description": s.get("description", "默认标准")
            })
        # 并行解析文件
        with st.spinner("⏳ 正在解析标注文件..."):
            progress_bar = st.progress(0)
            all_parse_results = []
            stats = ProcessingStats()
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(parse_speech_annotation_json, f): f 
                    for f in uploaded_jsons
                }
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
            audio_name = res.get("audio_name", "")
            
            # 匹配验收标准
            matched_std = match_standard(audio_name, standard_list)
            if not matched_std:
                matched_std = {
                    "min_segments": 1,
                    "min_total_duration": 1.0,
                    "min_segments_per_label": 1,
                    "max_silence_ratio": 10,
                    "max_other_ratio": 10,
                    "required_labels": [],
                    "description": "默认标准（未匹配到特定标准）"
                }
            # 验证
            is_valid, reasons = validate_speech_annotation(res, matched_std)
            # 格式化标签统计
            label_stats = res.get("label_stats", {})
            label_str = "；".join([
                f"{k}: {v['count']}个 ({v['total_duration']:.1f}秒)" 
                for k, v in label_stats.items()
            ]) if label_stats else "无标签"
            acceptance_results.append({
                "音频文件名": audio_name,
                "来源JSON": res.get("json_file_name", ""),
                "总时长(秒)": res.get("total_duration", 0),
                "总片段数": res.get("total_segments", 0),
                "标签统计": label_str,
                "片段内最高无声比例(%)": res.get("max_silence_ratio", 0),
                "片段内最高其他声音比例(%)": res.get("max_other_ratio", 0),
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
        cols[0].metric("📋 总音频数", total)
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
            key="speech_filter"
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
            ["语音标注验收报告"],
            ["验收员", inspector],
            ["验收时间", inspection_time.strftime("%Y-%m-%d")],
            ["总音频数", str(total)],
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
        filename = get_timestamp_filename("语音标注验收报告", "csv")
        
        st.download_button(
            "📄 下载验收报告 (CSV)", 
            csv_file, 
            filename, 
            mime="text/csv",
            use_container_width=True
        )
        
        st.success("✅ 验收完成！")