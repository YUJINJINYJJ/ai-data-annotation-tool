import streamlit as st
import pandas as pd
import json
from utils import create_csv_in_memory, create_dict_csv_in_memory

def nlp_text_analyzer_page():
    if "nlp_results" not in st.session_state:
        st.session_state["nlp_results"] = None

    st.title("📄 中文自然语言批量分析（多文件）")
    st.caption("支持批量上传 CSV / JSON，统一关键词匹配，汇总统计+导出")

    # 一键清空
    if st.button("🗑️ 清空所有上传与结果", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("nlp_"):
                del st.session_state[k]
        st.rerun()

    # ======================
    # 批量上传
    # ======================
    st.subheader("📤 批量上传文件（可多选 CSV / JSON）")
    uploaded_files = st.file_uploader(
        "选择多个文件",
        type=["csv", "json"],
        accept_multiple_files=True,
        key="nlp_uploader"
    )

    if not uploaded_files:
        st.info("ℹ️ 请批量上传 CSV 或 JSON 文件开始分析")
        with st.expander("💡 使用说明"):
            st.markdown("""
            1. 可同时上传 **多个 .csv / .json**
            2. 所有文件共用同一套关键词规则
            3. 自动合并结果、统一统计命中率
            4. 一键导出 **总汇总报告**
            """)
        return

    st.success(f"✅ 已选择 {len(uploaded_files)} 个文件")

    # ======================
    # 统一配置（所有文件共用）
    # ======================
    st.subheader("🔍 统一配置")
    text_col = st.text_input(
        "文本列名（所有文件必须相同）",
        value="content",
        help="例如：content / text / 内容 / 文本"
    )

    st.subheader("🔑 关键词匹配（可选）")
    enable_keyword = st.checkbox("启用关键词匹配", value=False)
    keyword_input = ""
    match_type = "包含（模糊）"

    if enable_keyword:
        keyword_input = st.text_input(
            "关键词（逗号分隔，支持中文逗号）",
            placeholder="人工智能,教育,大数据"
        )
        match_type = st.radio(
            "匹配方式",
            ["包含（模糊）", "完全相等（精确）"],
            horizontal=True
        )

    # ======================
    # 开始批量分析
    # ======================
    if st.button("🚀 批量分析所有文件", type="primary", use_container_width=True):
        if not text_col.strip():
            st.error("请输入文本列名！")
            return

        all_dfs = []
        error_files = []

        # 处理关键词
        keywords = []
        if enable_keyword and keyword_input.strip():
            clean_input = keyword_input.strip().replace("，", ",")
            keywords = [k.strip() for k in clean_input.split(",") if k.strip()]

        with st.spinner(f"正在处理 {len(uploaded_files)} 个文件..."):
            for f in uploaded_files:
                try:
                    ext = f.name.split(".")[-1].lower()
                    if ext == "csv":
                        df = pd.read_csv(f, encoding="utf-8-sig", on_bad_lines="skip")
                    elif ext == "json":
                        data = json.load(f)
                        df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame([data])
                    else:
                        continue

                    # 检查列是否存在
                    if text_col not in df.columns:
                        error_files.append(f"{f.name}（无列：{text_col}）")
                        continue

                    # 加来源文件名
                    df["_来源文件"] = f.name
                    df["_文本内容"] = df[text_col].fillna("").astype(str).str.strip()

                    # 匹配
                    hit_list = []
                    hit_key_list = []
                    for txt in df["_文本内容"]:
                        hit = False
                        hit_keys = []
                        if keywords:
                            for kw in keywords:
                                if match_type == "完全相等（精确）":
                                    if txt == kw:
                                        hit = True
                                        hit_keys.append(kw)
                                else:
                                    if kw in txt:
                                        hit = True
                                        hit_keys.append(kw)
                        hit_list.append("✅ 命中" if hit else "❌ 未命中")
                        hit_key_list.append(" | ".join(hit_keys) if hit_keys else "-")

                    df["是否命中"] = hit_list
                    df["命中关键词"] = hit_key_list
                    all_dfs.append(df)

                except Exception as e:
                    error_files.append(f"{f.name}（错误：{str(e)[:50]}）")

            # 汇总
            if not all_dfs:
                st.error("❌ 无有效文件可分析")
                return

            final_df = pd.concat(all_dfs, ignore_index=True)
            st.session_state["nlp_results"] = final_df

        # ======================
        # 结果展示
        # ======================
        st.divider()
        st.subheader("📊 批量汇总结果")

        total = len(final_df)
        hit_cnt = len(final_df[final_df["是否命中"] == "✅ 命中"]) if enable_keyword else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总文件数", len(uploaded_files))
        col2.metric("总行数", total)
        col3.metric("命中行数", hit_cnt)
        col4.metric("命中率", f"{hit_cnt/total*100:.1f}%" if total else 0)

        # 显示表格
        st.subheader("📋 完整结果（含来源文件）")
        show_cols = ["_来源文件", text_col, "是否命中", "命中关键词"]
        st.dataframe(final_df[show_cols], use_container_width=True, height=400)

        # 错误文件
        if error_files:
            with st.expander("⚠️ 处理失败的文件"):
                for e in error_files:
                    st.write(e)

        # ======================
        # 导出总报告
        # ======================
        st.divider()
        st.subheader("📥 导出批量汇总报告")
        out_df = final_df.drop(columns=["_文本内容"], errors="ignore")
        csv_data = create_dict_csv_in_memory(list(out_df.columns), out_df.to_dict("records"))

        st.download_button(
            "💾 下载全部结果 CSV",
            csv_data,
            file_name="批量文本分析总报告.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.success("✅ 批量分析完成！")

    # 显示历史结果
    elif st.session_state["nlp_results"] is not None:
        st.divider()
        st.subheader("📊 历史批量结果")
        df = st.session_state["nlp_results"]
        show_cols = ["_来源文件"] + [c for c in df.columns if c not in ["_来源文件","_文本内容"]]
        st.dataframe(df[show_cols], use_container_width=True, height=400)
