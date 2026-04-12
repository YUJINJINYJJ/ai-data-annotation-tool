"""
中文文本分析与关键词统计工具
支持批量处理 CSV/JSON 文件，提取中文并统计关键词
"""
import streamlit as st
import pandas as pd
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
from utils import (
    create_dict_csv_in_memory, get_timestamp_filename,
    parse_keywords_input, ProcessingStats, logger
)


# 中文正则表达式
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fa5]+")


# ------------------------------
# 核心处理函数
# ------------------------------
def extract_chinese(text: str) -> List[str]:
    """
    从文本中提取所有中文片段
    
    Args:
        text: 输入文本
    
    Returns:
        中文片段列表
    """
    if not text:
        return []
    return CHINESE_PATTERN.findall(text)


def count_keywords(text: str, keywords: List[str]) -> Dict[str, int]:
    """
    统计关键词在文本中的出现次数
    
    Args:
        text: 输入文本
        keywords: 关键词列表
    
    Returns:
        关键词计数字典
    """
    count_dict = {}
    for kw in keywords:
        count_dict[kw] = text.count(kw)
    return count_dict


def process_single_file(
    file_obj,
    keywords: List[str],
    enable_keywords: bool
) -> Dict[str, Any]:
    """
    处理单个文件
    
    Args:
        file_obj: 文件对象
        keywords: 关键词列表
        enable_keywords: 是否启用关键词统计
    
    Returns:
        处理结果字典
    """
    file_name = getattr(file_obj, 'name', '未知文件')
    
    try:
        ext = file_name.split(".")[-1].lower()
        full_text = ""
        
        # 读取文件内容
        if ext == "csv":
            df = pd.read_csv(file_obj, encoding="utf-8-sig", dtype=str).fillna("")
            full_text = " ".join(df.stack().astype(str).tolist())
        elif ext == "json":
            file_obj.seek(0)
            json_data = json.load(file_obj)
            full_text = str(json_data)
        else:
            return {
                "status": "error",
                "file_name": file_name,
                "error": f"不支持的文件格式: {ext}"
            }
        
        # 提取中文
        chinese_list = extract_chinese(full_text)
        chinese_text = "、".join(chinese_list) if chinese_list else "(无中文)"
        
        # 关键词统计
        keyword_info = {}
        if enable_keywords and keywords:
            count_dict = count_keywords(full_text, keywords)
            hit_keywords = [kw for kw in keywords if count_dict[kw] > 0]
            total_hits = sum(count_dict.values())
            
            keyword_info = {
                "是否命中": "是" if hit_keywords else "否",
                "命中关键词": " | ".join(hit_keywords) if hit_keywords else "无",
                "各关键词次数": " | ".join([f"{k}:{v}" for k, v in count_dict.items()]),
                "总命中次数": total_hits
            }
        
        # 构建结果
        result = {
            "status": "success",
            "文件名": file_name,
            "中文片段数": len(chinese_list),
            "提取全部中文": chinese_text[:2000] + ("..." if len(chinese_text) > 2000 else "")
        }
        
        if enable_keywords:
            result.update(keyword_info)
        
        return result
        
    except pd.errors.EmptyDataError:
        logger.error(f"空文件 [{file_name}]")
        return {"status": "error", "file_name": file_name, "error": "文件为空"}
    except json.JSONDecodeError:
        logger.error(f"JSON 解析错误 [{file_name}]")
        return {"status": "error", "file_name": file_name, "error": "JSON 格式无效"}
    except Exception as e:
        logger.error(f"文件处理错误 [{file_name}]: {str(e)}")
        return {"status": "error", "file_name": file_name, "error": str(e)}


# ------------------------------
# 主页面
# ------------------------------
def nlp_text_analyzer_page() -> None:
    """中文文本分析页面"""
    st.title("📄 中文文本分析工具")
    st.markdown("**批量提取中文内容、统计关键词出现次数**")
    
    # 初始化会话状态
    if "nlp_result" not in st.session_state:
        st.session_state["nlp_result"] = None

    # 左侧边栏配置
    with st.sidebar:
        st.header("⚙️ 处理配置")
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
            - 自动提取文件中的所有中文字符
            - 可选统计指定关键词出现次数
            - 支持 CSV 和 JSON 格式
            
            **输出格式：**
            - 一个文件一行
            - 中文内容用顿号分隔显示
            """)

    # 清空按钮
    if st.button("🗑️ 清空所有结果", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("nlp_"):
                del st.session_state[k]
        st.rerun()

    # --------------------------
    # 文件上传区
    # --------------------------
    st.subheader("📤 上传文件")
    
    uploaded_files = st.file_uploader(
        "选择 CSV 或 JSON 文件",
        type=["csv", "json"],
        accept_multiple_files=True,
        key="nlp_uploader"
    )
    
    if not uploaded_files:
        st.info("👆 请上传 CSV 或 JSON 文件开始分析")
        return

    # 显示上传文件信息
    with st.expander(f"📁 已上传 {len(uploaded_files)} 个文件", expanded=False):
        for f in uploaded_files:
            st.write(f"- {f.name}")

    # --------------------------
    # 关键词配置
    # --------------------------
    st.subheader("🔑 关键词匹配（可选）")
    
    enable_keywords = st.checkbox(
        "启用关键词统计", 
        value=False,
        help="开启后将统计指定关键词在各文件中的出现次数"
    )
    
    keyword_input = ""
    if enable_keywords:
        keyword_input = st.text_input(
            "关键词（逗号分隔，支持中文逗号）",
            placeholder="例如：人工智能,教育,历史",
            help="输入要统计的关键词，多个关键词用逗号分隔"
        )
        
        # 显示解析后的关键词
        if keyword_input.strip():
            parsed_keywords = parse_keywords_input(keyword_input)
            if parsed_keywords:
                st.caption(f"📝 已识别 {len(parsed_keywords)} 个关键词：{', '.join(parsed_keywords)}")

    # --------------------------
    # 执行处理
    # --------------------------
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        # 解析关键词
        keywords = []
        if enable_keywords and keyword_input.strip():
            keywords = parse_keywords_input(keyword_input)
        
        # 并行处理
        with st.spinner("⏳ 正在处理文件..."):
            progress_bar = st.progress(0)
            results = []
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_single_file, f, keywords, enable_keywords): f 
                    for f in uploaded_files
                }
                
                completed = 0
                total = len(futures)
                
                for future in as_completed(futures):
                    results.append(future.result())
                    completed += 1
                    progress_bar.progress(completed / total)
            
            progress_bar.empty()

        # 分类结果
        success_results = [r for r in results if r.get("status") == "success"]
        error_results = [r for r in results if r.get("status") == "error"]
        
        if not success_results:
            st.error("❌ 没有成功处理的文件！")
            if error_results:
                with st.expander("⚠️ 查看错误详情"):
                    for r in error_results:
                        st.write(f"- {r.get('file_name', '未知')}: {r.get('error', '未知错误')}")
            return

        # 构建结果表格
        rows = []
        for r in success_results:
            row = {
                "文件名": r["文件名"],
                "中文片段数": r["中文片段数"],
                "提取全部中文": r["提取全部中文"]
            }
            if enable_keywords:
                row.update({
                    "是否命中": r.get("是否命中", "否"),
                    "命中关键词": r.get("命中关键词", "无"),
                    "各关键词次数": r.get("各关键词次数", ""),
                    "总命中次数": r.get("总命中次数", 0)
                })
            rows.append(row)
        
        st.session_state["nlp_result"] = pd.DataFrame(rows)

    # --------------------------
    # 结果展示
    # --------------------------
    if st.session_state["nlp_result"] is not None:
        st.divider()
        st.subheader("📊 分析结果")
        
        df = st.session_state["nlp_result"]
        
        # 统计信息
        cols = st.columns(4)
        cols[0].metric("📁 文件数", len(df))
        cols[1].metric("📝 总中文片段", df["中文片段数"].sum())
        
        if "总命中次数" in df.columns:
            cols[2].metric("🔍 总命中次数", df["总命中次数"].sum())
            hit_files = len(df[df["是否命中"] == "是"])
            cols[3].metric("🎯 命中文件数", hit_files)
        
        # 结果表格
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
        
        # --------------------------
        # 导出
        # --------------------------
        st.divider()
        st.subheader("📥 导出结果")
        
        csv_bytes = create_dict_csv_in_memory(
            list(df.columns), 
            df.to_dict("records")
        )
        
        filename = get_timestamp_filename("中文分析结果", "csv")
        
        st.download_button(
            "💾 下载分析结果 (CSV)",
            csv_bytes,
            filename,
            mime="text/csv",
            use_container_width=True
        )
        
        st.success("✅ 分析完成！")