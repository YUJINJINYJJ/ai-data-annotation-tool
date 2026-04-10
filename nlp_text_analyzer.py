import streamlit as st
import pandas as pd
import json
import os
from utils import create_csv_in_memory, create_dict_csv_in_memory

def nlp_text_analyzer_page():
    st.title("📄 中文自然语言 & 关键词匹配分析")
    st.caption("支持 CSV / JSON 上传，自动识别文本列，可选关键词匹配")

    # 一键清空（保持统一）
    if st.button("🗑️ 清空所有上传与结果", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k in ["nlp_uploader", "nlp_df", "nlp_results"]:
                del st.session_state[k]
        st.rerun()

    # ----------------------
    # 上传区
    # ----------------------
    st.subheader("📤 上传文件（CSV / JSON）")
    uploaded_file = st.file_uploader(
        "选择单个 CSV 或 JSON 文件",
        type=["csv", "json"],
        key="nlp_uploader"
    )

    if uploaded_file is None:
        st.info("请上传 CSV 或 JSON 文件开始分析")
        return

    # ----------------------
    # 自动读取文件
    # ----------------------
    try:
        ext = uploaded_file.name.split(".")[-1].lower()

        if ext == "csv":
            df = pd.read_csv(uploaded_file)
        elif ext == "json":
            data = json.load(uploaded_file)
            if isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame([data])
        else:
            st.error("不支持的文件格式")
            return
    except Exception as e:
        st.error(f"读取失败：{e}")
        return

    st.success(f"✅ 读取成功：共 {len(df)} 行")
    st.dataframe(df.head(5), use_container_width=True)

    # ----------------------
    # 自动识别可能的文本列
    # ----------------------
    st.subheader("🔍 选择要分析的中文文本列")
    text_cols = list(df.columns)
    text_col = st.selectbox("选择文本列", text_cols)

    # ----------------------
    # 关键词匹配（可选）
    # ----------------------
    st.subheader("🔑 关键词匹配（可选）")
    enable_keyword = st.checkbox("启用关键词匹配筛选", value=False)

    keyword_input = ""
    match_type = "包含（模糊）"
    if enable_keyword:
        keyword_input = st.text_input(
            "输入关键词（多个用逗号分隔）",
            placeholder="例如：人工智能,教育,大数据（支持中文逗号）"
        )
        match_type = st.radio("匹配方式", ["包含（模糊）", "完全相等"], horizontal=True)

    # ----------------------
    # 开始分析
    # ----------------------
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        with st.spinner("分析中..."):
            # 复制一份用于结果
            res_df = df.copy()

            # 统一文本
            res_df["_文本内容"] = res_df[text_col].astype(str).str.strip()

            # 关键词处理（自动中文逗号 → 英文）
            keywords = []
            if enable_keyword and keyword_input.strip():
                clean_input = keyword_input.strip().replace("，", ",")
                keywords = [k.strip() for k in clean_input.split(",") if k.strip()]

            # 匹配
            hit_col = []
            hit_key_col = []

            for txt in res_df["_文本内容"]:
                hit = False
                hit_keys = []

                if keywords:
                    for kw in keywords:
                        if match_type == "完全相等":
                            if txt == kw:
                                hit = True
                                hit_keys.append(kw)
                        else:
                            if kw in txt:
                                hit = True
                                hit_keys.append(kw)

                hit_col.append("是" if hit else "否")
                hit_key_col.append(" | ".join(hit_keys))

            res_df["是否命中关键词"] = hit_col
            res_df["命中关键词"] = hit_key_col

            # 保存结果
            st.session_state["nlp_results"] = res_df

        # ----------------------
        # 结果展示
        # ----------------------
        st.divider()
        st.subheader("📊 分析结果")

        total = len(res_df)
        hit_count = len(res_df[res_df["是否命中关键词"] == "是"]) if enable_keyword else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("总行数", total)
        if enable_keyword:
            col2.metric("命中行数", hit_count)
            col3.metric("命中率", f"{hit_count/total*100:.1f}%" if total>0 else "0%")

        st.dataframe(
            res_df[[text_col, "是否命中关键词", "命中关键词"]],
            use_container_width=True,
            height=400
        )

        # ----------------------
        # 导出
        # ----------------------
        st.divider()
        st.subheader("📥 导出结果")
        out_df = res_df.drop(columns=["_文本内容"], errors="ignore")

        csv_bytes = create_dict_csv_in_memory(
            list(out_df.columns),
            out_df.to_dict("records")
        )

        st.download_button(
            "💾 下载完整结果 CSV",
            csv_bytes,
            file_name=f"文本分析结果_{uploaded_file.name}.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.success("✅ 分析完成！")
