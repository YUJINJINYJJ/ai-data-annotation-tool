"""
JSON 关键词批量匹配工具
支持递归搜索、阈值校验、报告导出
"""
import streamlit as st
import os
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple
from utils import (
    create_csv_in_memory, create_dict_csv_in_memory,
    get_timestamp_filename, parse_keywords_input, parse_threshold_input,
    ProcessingStats, logger
)
from folder_uploader import folder_uploader


# ------------------------------
# 核心搜索函数
# ------------------------------
def search_json_recursive(data: Any, targets: List[str]) -> List[Dict[str, str]]:
    """
    递归搜索 JSON 数据中匹配关键词的值
    
    Args:
        data: JSON 数据（任意类型）
        targets: 目标关键词列表
    
    Returns:
        匹配结果列表，每项包含 value 和 keyword
    """
    matches = []
    
    if isinstance(data, dict):
        for value in data.values():
            matches.extend(search_json_recursive(value, targets))
    elif isinstance(data, list):
        for item in data:
            matches.extend(search_json_recursive(item, targets))
    else:
        # 叶节点：检查是否包含关键词
        str_value = str(data).lower()
        for target in targets:
            if target.lower() in str_value:
                matches.append({"value": str(data), "keyword": target})
                break  # 一个值只匹配一次
    
    return matches


# ------------------------------
# 阈值校验
# ------------------------------
def check_threshold(
    keyword_count: Dict[str, int], 
    threshold_dict: Dict[str, int]
) -> Tuple[bool, str]:
    """
    检查关键词计数是否满足阈值要求
    
    Args:
        keyword_count: 关键词计数字典
        threshold_dict: 阈值字典
    
    Returns:
        (是否达标, 失败原因)
    """
    if not threshold_dict:
        return True, ""
    
    is_pass = True
    fail_reasons = []
    
    for keyword, min_count in threshold_dict.items():
        actual_count = keyword_count.get(keyword, 0)
        if actual_count < min_count:
            is_pass = False
            fail_reasons.append(f"「{keyword}」实际 {actual_count} 次，要求 ≥ {min_count} 次")
    
    return is_pass, "；".join(fail_reasons)


def generate_verification_report(
    success_results: List[Dict[str, Any]],
    targets: List[str],
    threshold_dict: Dict[str, int],
    total_files: int
) -> Dict[str, Any]:
    """
    生成阈值校验报告
    
    Args:
        success_results: 成功解析的结果列表
        targets: 关键词列表
        threshold_dict: 阈值字典
        total_files: 总文件数
    
    Returns:
        校验报告字典
    """
    if not threshold_dict:
        return None
    
    passed_count = 0
    failed_count = 0
    
    for result in success_results:
        is_pass, fail_reason = check_threshold(result["keyword_count"], threshold_dict)
        result["is_pass"] = is_pass
        result["fail_reason"] = fail_reason
        if is_pass:
            passed_count += 1
        else:
            failed_count += 1
    
    return {
        "global_stats": {
            "总扫描文件数": total_files,
            "有效JSON文件数": len(success_results),
            "达标文件数": passed_count,
            "未达标文件数": failed_count,
            "文件达标率": f"{passed_count/len(success_results)*100:.2f}%" if success_results else "0%"
        },
        "all_files": success_results
    }


# ------------------------------
# 文件处理
# ------------------------------
def process_single_json(
    file_obj,
    targets: List[str],
    is_uploaded: bool = True,
    split_array: bool = False
) -> List[Dict[str, Any]]:
    """
    处理单个 JSON 文件
    
    Args:
        file_obj: 文件对象或文件路径
        targets: 目标关键词列表
        is_uploaded: 是否为上传文件
        split_array: 是否拆分数组为独立条目
    
    Returns:
        处理结果列表
    """
    results = []
    file_name = getattr(file_obj, 'name', str(file_obj)) if is_uploaded else os.path.basename(file_obj)
    file_path = f"上传文件/{file_name}" if is_uploaded else str(file_obj)
    
    try:
        # 读取 JSON 数据
        if is_uploaded:
            file_obj.seek(0)
            json_data = json.load(file_obj)
        else:
            with open(file_obj, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        
        # 处理数据
        if split_array and isinstance(json_data, list):
            for idx, item in enumerate(json_data):
                item_matches = search_json_recursive(item, targets)
                keyword_count = {t: 0 for t in targets}
                match_values = []
                
                for match in item_matches:
                    keyword_count[match["keyword"]] += 1
                    match_values.append(match["value"])
                
                results.append({
                    "status": "success",
                    "file_path": file_path,
                    "file_name": f"{file_name} (第{idx+1}条)",
                    "total_match": len(item_matches),
                    "keyword_count": keyword_count,
                    "match_values": match_values
                })
        else:
            all_matches = search_json_recursive(json_data, targets)
            keyword_count = {t: 0 for t in targets}
            match_values = []
            
            for match in all_matches:
                keyword_count[match["keyword"]] += 1
                match_values.append(match["value"])
            
            results.append({
                "status": "success",
                "file_path": file_path,
                "file_name": file_name,
                "total_match": len(all_matches),
                "keyword_count": keyword_count,
                "match_values": match_values
            })
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误 [{file_name}]: {str(e)}")
        return [{"status": "invalid_json", "file_name": file_name, "error": "JSON格式错误"}]
    except Exception as e:
        logger.error(f"文件处理错误 [{file_name}]: {str(e)}")
        return [{"status": "error", "file_name": file_name, "error": str(e)}]
    
    return results


# ------------------------------
# 主页面
# ------------------------------
def json_keyword_search_page() -> None:
    """JSON 关键词批量匹配页面"""
    st.title("🔍 JSON 关键词批量匹配工具")
    st.markdown("**递归搜索 JSON 文件中的关键词，支持阈值校验和统计报告**")

    # 左侧边栏配置
    with st.sidebar:
        st.header("⚙️ 匹配配置")
        
        keyword_input = st.text_input(
            "🔑 查找关键词",
            placeholder="多个用逗号分隔",
            help="模糊匹配，输入'足'会匹配所有包含'足'的内容"
        )
        
        st.subheader("✅ 阈值校验")
        enable_threshold = st.checkbox("启用关键字数量阈值校验", value=True)
        
        threshold_text = ""
        if enable_threshold:
            threshold_text = st.text_area(
                "📏 各关键字最低出现次数",
                placeholder="每行一个，格式：关键字:最低次数\n例如：\n足球:3\n篮球:2",
                height=120
            )
        
        st.divider()
        
        split_array = st.checkbox(
            "拆分 JSON 数组为独立条目",
            value=False,
            help="关闭：整个 JSON 作为整体统计；开启：数组每个元素独立统计"
        )
        
        max_workers = st.slider(
            "⚡ 并行处理线程数", 
            min_value=2, 
            max_value=16, 
            value=8
        )
        
        st.divider()
        
        with st.expander("💡 使用帮助", expanded=False):
            st.markdown("""
            **功能说明：**
            - 递归搜索 JSON 中所有字段的值
            - 支持模糊匹配（包含即匹配）
            - 可设置阈值进行达标校验
            
            **输入格式：**
            - 关键词：逗号分隔，支持中英文逗号
            - 阈值：每行一个，格式 `关键词:次数`
            """)

    # --------------------------
    # 文件上传区
    # --------------------------
    st.subheader("📤 上传 JSON 文件")
    
    # 使用文件夹上传组件
    selected_files = folder_uploader(
        "选择包含 JSON 文件的文件夹",
        file_extensions=[".json"],
        max_file_size_mb=100,
        key="keyword_search_folder_uploader"
    )
    
    # 保存到会话状态
    if selected_files:
        st.session_state["keyword_selected_files"] = selected_files

    # 获取选中的文件
    keyword_selected_files = st.session_state.get("keyword_selected_files", [])
    
    # 显示已选择文件数量
    if keyword_selected_files:
        st.info(f"✅ 已选择 {len(keyword_selected_files)} 个文件")
    
    # --------------------------
    # 执行匹配
    # --------------------------
    has_files = (keyword_selected_files and len(keyword_selected_files) > 0) or (selected_files and len(selected_files) > 0)
    if has_files and st.button("🚀 开始批量匹配", type="primary", use_container_width=True):
        # 验证关键词输入
        if not keyword_input.strip():
            st.error("❌ 请输入查找关键词！")
            st.stop()
        
        targets = parse_keywords_input(keyword_input)
        if not targets:
            st.error("❌ 关键词格式无效！")
            st.stop()
        
        # 解析阈值
        threshold_dict = {}
        if enable_threshold and threshold_text.strip():
            threshold_dict = parse_threshold_input(threshold_text)
            if threshold_dict:
                st.info(f"📊 已设置 {len(threshold_dict)} 个关键词的阈值")
        
        # 使用选中的文件（优先从会话状态获取）
        files_to_process = keyword_selected_files if keyword_selected_files else selected_files
        
        if not files_to_process:
            st.error("❌ 未找到任何 JSON 文件！")
            st.stop()
        
        # 提取文件路径（folder_uploader返回的是字典，需要提取path字段）
        files_to_process = [f["path"] if isinstance(f, dict) else f for f in files_to_process]
        
        # 并行处理
        with st.spinner(f"🔍 正在处理 {len(files_to_process)} 个文件..."):
            progress_bar = st.progress(0)
            all_results = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        process_single_json, file_path, targets, False, split_array
                    ): file_path 
                    for file_path in files_to_process
                }
                
                completed = 0
                total = len(futures)
                
                for future in as_completed(futures):
                    all_results.extend(future.result())
                    completed += 1
                    progress_bar.progress(completed / total)
            
            progress_bar.empty()

        # 分类结果
        success_results = [r for r in all_results if r["status"] == "success"]
        invalid_results = [r for r in all_results if r["status"] == "invalid_json"]
        error_results = [r for r in all_results if r["status"] == "error"]
        total_files = len(all_results)
        
        # 生成校验报告
        verification_report = None
        if enable_threshold and threshold_dict:
            verification_report = generate_verification_report(
                success_results, targets, threshold_dict, total_files
            )
        
        # 统计数据
        matched_files = len([r for r in success_results if r["total_match"] > 0])
        total_matches = sum(r["total_match"] for r in success_results)
        value_counter = Counter()
        for r in success_results:
            value_counter.update(r["match_values"])

        # --------------------------
        # 结果展示
        # --------------------------
        st.divider()
        st.subheader("📊 全局统计")
        
        cols = st.columns(6)
        cols[0].metric("📁 总文件数", total_files)
        cols[1].metric("✅ 有效文件", len(success_results))
        cols[2].metric("🔍 匹配文件", matched_files)
        cols[3].metric("📊 总匹配数", total_matches)
        cols[4].metric("⚠️ 无效JSON", len(invalid_results))
        cols[5].metric("❌ 读取失败", len(error_results))
        
        # 阈值校验统计
        if verification_report:
            st.divider()
            st.subheader("✅ 阈值校验统计")
            
            stats = verification_report["global_stats"]
            cols = st.columns(4)
            cols[0].metric("✅ 达标文件", stats["达标文件数"])
            cols[1].metric("❌ 未达标文件", stats["未达标文件数"])
            cols[2].metric("📈 达标率", stats["文件达标率"])
            cols[3].metric("🔢 校验关键词", len(threshold_dict))

        # 详细结果表格
        st.divider()
        st.subheader("📋 分文件匹配详情")
        
        detail_data = []
        if success_results:
            for r in success_results:
                row = {
                    "文件名": r["file_name"],
                    "文件路径": r["file_path"],
                    "总匹配数": r["total_match"]
                }
                
                # 添加各关键词计数
                for kw in targets:
                    row[f"「{kw}」出现次数"] = r["keyword_count"][kw]
                
                # 添加校验状态
                if verification_report:
                    row["校验状态"] = "✅ 达标" if r["is_pass"] else "❌ 未达标"
                    row["未达标原因"] = r["fail_reason"] if not r["is_pass"] else "-"
                
                # 匹配值预览
                preview_values = r["match_values"][:5]
                preview_str = " | ".join(preview_values)
                if len(r["match_values"]) > 5:
                    preview_str += f" ... (共{len(r['match_values'])}个)"
                row["匹配值预览"] = preview_str
                
                detail_data.append(row)
            
            # 筛选
            if verification_report:
                filter_option = st.radio(
                    "筛选显示：", 
                    ["全部文件", "仅达标文件", "仅未达标文件"], 
                    horizontal=True,
                    key="keyword_filter"
                )
                
                if filter_option == "仅达标文件":
                    display_data = [d for d in detail_data if d["校验状态"] == "✅ 达标"]
                elif filter_option == "仅未达标文件":
                    display_data = [d for d in detail_data if d["校验状态"] == "❌ 未达标"]
                else:
                    display_data = detail_data
            else:
                display_data = detail_data
            
            st.dataframe(display_data, use_container_width=True, hide_index=True)
        
        # 异常文件
        if invalid_results or error_results:
            with st.expander("⚠️ 异常文件列表", expanded=False):
                if invalid_results:
                    st.warning(f"**JSON 格式无效的文件 ({len(invalid_results)} 个)：**")
                    for p in invalid_results:
                        st.write(f"- {p.get('file_name', '未知')}")
                
                if error_results:
                    st.warning(f"**读取失败的文件 ({len(error_results)} 个)：**")
                    for p in error_results:
                        st.write(f"- {p.get('file_name', '未知')}: {p.get('error', '未知错误')}")

        # 值统计
        st.divider()
        st.subheader("🔢 匹配值出现次数统计（Top 50）")
        
        value_data = [
            {"匹配值": k, "出现次数": v} 
            for k, v in sorted(value_counter.items(), key=lambda x: x[1], reverse=True)[:50]
        ]
        
        if value_data:
            st.dataframe(value_data, use_container_width=True, hide_index=True)
        
        # --------------------------
        # 导出报告
        # --------------------------
        st.divider()
        st.subheader("📥 导出报告")
        
        name_suffix = "_".join(targets[:3]) + ("..." if len(targets) > 3 else "")
        
        # 校验报告
        if verification_report:
            report_rows = [["【全局校验统计】"]]
            for k, v in verification_report["global_stats"].items():
                report_rows.append([k, v])
            report_rows.append([])
            
            report_headers = (
                ["文件名", "文件路径", "总匹配数"] + 
                [f"「{kw}」出现次数" for kw in targets] + 
                ["校验状态", "未达标原因", "所有匹配值"]
            )
            report_rows.append(report_headers)
            
            for r in verification_report["all_files"]:
                row = [
                    r["file_name"],
                    r["file_path"],
                    str(r["total_match"])
                ]
                row.extend([str(r["keyword_count"][kw]) for kw in targets])
                row.extend([
                    "✅ 达标" if r["is_pass"] else "❌ 未达标",
                    r["fail_reason"] if not r["is_pass"] else "-",
                    " | ".join(r["match_values"])
                ])
                report_rows.append(row)
            
            report_csv = create_csv_in_memory(None, report_rows)
            filename = get_timestamp_filename(f"JSON校验报告_{name_suffix}", "csv")
            
            st.download_button(
                "📄 下载完整校验报告", 
                report_csv, 
                filename, 
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )
        
        # 匹配结果
        if detail_data:
            result_csv = create_dict_csv_in_memory(
                list(detail_data[0].keys()), 
                detail_data
            )
            filename = get_timestamp_filename(f"JSON匹配结果_{name_suffix}", "csv")
            
            st.download_button(
                "📋 下载匹配结果详情", 
                result_csv, 
                filename, 
                mime="text/csv",
                use_container_width=True
            )
        
        # 值统计
        if value_data:
            count_csv = create_dict_csv_in_memory(
                ["匹配值", "出现次数"], 
                value_data
            )
            filename = get_timestamp_filename(f"匹配值统计_{name_suffix}", "csv")
            
            st.download_button(
                "📊 下载值统计表", 
                count_csv, 
                filename, 
                mime="text/csv",
                use_container_width=True
            )
        
        st.success("✅ 批量匹配完成！")