import streamlit as st
import pandas as pd
import json
import re
from utils import create_csv_in_memory, create_dict_csv_in_memory

def nlp_text_analyzer_page():
    if "nlp_results" not in st.session_state:
        st.session_state["nlp_results"] = None

    st.title("📄 批量文件中文提取工具")
    st.caption("自动从 CSV / JSON 中提取所有中文，支持批量上传")

    # 清空
    if st.button("🗑️ 清空所有", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("nlp_"):
                del st.session_state[k]
        st.rerun()

    # 批量上传
    st.subheader("📤 批量上传 CSV / JSON（可多选）")
    uploaded_files = st.file_uploader(
        "选择多个文件",
        type=["csv", "json"],
        accept_multiple_files=True,
        key="nlp_uploader"
    )

    if not uploaded_files:
        st.info("ℹ️ 请上传文件开始提取中文")
        return

    st.success(f"✅ 已选择 {len(uploaded_files)} 个文件")

    # 开始提取
    if st.button("🚀 批量提取中文", type="primary", use_container_width=True):
        results = []
        error_list = []

        # 中文正则
        pattern = re.compile(r'[\u4e00-\u9fa5]+')

        with st.spinner("正在提取中文..."):
            for f in uploaded_files:
                try:
                    ext = f.name.split(".")[-1].lower()
                    data_rows = []

                    if ext == "csv":
                        df = pd.read_csv(f, encoding="utf-8-sig", dtype=str).fillna("")
                        for _, row in df.iterrows():
                            data_rows.append(" ".join(row.astype(str)))

                    elif ext == "json":
                        obj = json.load(f)
                        if isinstance(obj, list):
                            data_rows = [str(item) for item in obj]
                        else:
                            data_rows = [str(obj)]

                    # 逐行提取中文
                    for raw in data_rows:
                        raw_str = str(raw).strip()
                        chinese_parts = pattern.findall(raw_str)
                        chinese_text = "".join(chinese_parts).strip()

                        results.append({
                            "来源文件": f.name,
                            "原文片段": raw_str[:200] + ("..." if len(raw_str) > 200 else ""),
                            "提取中文": chinese_text if chinese_text else "(无中文)"
                        })

                except Exception as e:
                    error_list.append(f"{f.name} | 错误：{str(e)[:30]}")

            if not results:
                st.warning("⚠️ 未提取到任何内容")
                return

            final_df = pd.DataFrame(results)
            st.session_state["nlp_results"] = final_df

        # 展示
        st.divider()
        st.subheader("📊 提取结果")
        st.metric("总行数", len(final_df))
        st.dataframe(final_df, use_container_width=True, height=450)

        if error_list:
            with st.expander("⚠️ 失败文件"):
                for e in error_list:
                    st.write(e)

        # 导出
        st.divider()
        st.subheader("📥 导出结果")
        csv_bytes = create_dict_csv_in_memory(
            list(final_df.columns),
            final_df.to_dict("records")
        )
        st.download_button(
            "💾 下载中文提取结果",
            csv_bytes,
            file_name="批量中文提取结果.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.success("✅ 提取完成！")

    # 历史结果
    elif st.session_state["nlp_results"] is not None:
        st.divider()
        st.subheader("📊 历史提取结果")
        st.dataframe(st.session_state["nlp_results"], use_container_width=True, height=400)
