import streamlit as st
import pandas as pd
import json
import re
from utils import create_csv_in_memory, create_dict_csv_in_memory

def nlp_text_analyzer_page():
    if "nlp_final" not in st.session_state:
        st.session_state["nlp_final"] = None

    st.title("📄 批量文件中文汇总 + 可选关键词匹配")
    st.caption("每个文件一行，全部结果合并输出，关键词可开可关")

    # 清空
    if st.button("🗑️ 清空所有", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("nlp_"):
                del st.session_state[k]
        st.rerun()

    # 上传
    st.subheader("📤 批量上传 CSV / JSON")
    uploaded_files = st.file_uploader(
        "可多选，最终输出一个汇总表",
        type=["csv", "json"],
        accept_multiple_files=True,
        key="nlp_uploader"
    )

    if not uploaded_files:
        st.info("请上传文件")
        return

    # 可选关键词匹配
    st.subheader("🔑 关键词匹配（可选）")
    enable_key = st.checkbox("开启关键词匹配", value=False)
    keyword_input = ""
    if enable_key:
        keyword_input = st.text_input(
            "关键词（逗号分隔，支持中文逗号）"
        )

    # 开始处理
    if st.button("🚀 生成汇总表", type="primary", use_container_width=True):
        pattern = re.compile(r"[\u4e00-\u9fa5]+")
        rows = []

        # 处理关键词
        keywords = []
        if enable_key and keyword_input.strip():
            clean = keyword_input.strip().replace("，", ",")
            keywords = [k.strip() for k in clean.split(",") if k.strip()]

        with st.spinner("处理中..."):
            for f in uploaded_files:
                try:
                    ext = f.name.split(".")[-1].lower()
                    all_text = ""

                    # 读取整个文件所有内容
                    if ext == "csv":
                        df = pd.read_csv(f, encoding="utf-8-sig", dtype=str).fillna("")
                        all_text = " ".join(df.astype(str).stack().tolist())
                    elif ext == "json":
                        all_text = str(json.load(f))

                    # 提取全部中文
                    chinese_all = "".join(pattern.findall(all_text)).strip()

                    # 关键词匹配（可选）
                    hit = ""
                    hit_keys = ""
                    if enable_key and keywords:
                        found = [k for k in keywords if k in chinese_all]
                        hit = "是" if found else "否"
                        hit_keys = " | ".join(found) if found else ""

                    # 每个文件只加一行
                    row = {
                        "来源文件名": f.name,
                        "文件全部中文汇总": chinese_all if chinese_all else "(无中文)"
                    }
                    if enable_key:
                        row["是否命中关键词"] = hit
                        row["命中关键词"] = hit_keys

                    rows.append(row)

                except Exception as e:
                    row = {
                        "来源文件名": f.name + "（读取失败）",
                        "文件全部中文汇总": ""
                    }
                    if enable_key:
                        row["是否命中关键词"] = ""
                        row["命中关键词"] = ""
                    rows.append(row)

            final_df = pd.DataFrame(rows)
            st.session_state["nlp_final"] = final_df

    # 展示结果
    if st.session_state["nlp_final"] is not None:
        st.divider()
        st.subheader("📊 汇总结果（一个文件一行）")
        st.dataframe(
            st.session_state["nlp_final"],
            use_container_width=True,
            height=400
        )

        # 导出一个总表
        st.subheader("📥 导出全部结果（单个文件）")
        csv_bytes = create_dict_csv_in_memory(
            list(st.session_state["nlp_final"].columns),
            st.session_state["nlp_final"].to_dict("records")
        )
        st.download_button(
            "💾 下载汇总表",
            csv_bytes,
            file_name="中文汇总&关键词结果.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.success("✅ 完成！所有文件合并成一个表，每个文件一行")
