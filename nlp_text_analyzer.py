import streamlit as st
import pandas as pd
import json
import re
from utils import create_csv_in_memory, create_dict_csv_in_memory

def nlp_text_analyzer_page():
    st.title("📄 批量中文提取（按文件单独输出）")
    st.caption("每个文件独立提取中文，单独展示、单独导出")

    # 清空
    if st.button("🗑️ 清空所有文件与结果", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("nlp_"):
                del st.session_state[k]
        st.rerun()

    # 批量上传
    st.subheader("📤 上传多个 CSV / JSON 文件")
    uploaded_files = st.file_uploader(
        "可多选，上传后按文件单独输出中文",
        type=["csv", "json"],
        accept_multiple_files=True,
        key="nlp_uploader"
    )

    if not uploaded_files:
        st.info("请上传文件开始提取")
        return

    st.success(f"已上传 {len(uploaded_files)} 个文件")

    # 中文正则
    pattern = re.compile(r'[\u4e00-\u9fa5]+')

    # 逐个文件处理
    for idx, f in enumerate(uploaded_files):
        with st.container(border=True):
            st.subheader(f"📄 {f.name}")
            btn_key = f"extract_{idx}"

            if st.button(f"提取该文件中文", key=btn_key, use_container_width=True):
                try:
                    ext = f.name.split(".")[-1].lower()
                    lines = []

                    if ext == "csv":
                        df = pd.read_csv(f, encoding="utf-8-sig", dtype=str).fillna("")
                        for _, row in df.iterrows():
                            lines.append(" ".join(row.astype(str)))

                    elif ext == "json":
                        obj = json.load(f)
                        if isinstance(obj, list):
                            lines = [str(x) for x in obj]
                        else:
                            lines = [str(obj)]

                    # 提取中文
                    results = []
                    for raw in lines:
                        s = str(raw).strip()
                        cn = "".join(pattern.findall(s)).strip()
                        results.append({
                            "原文片段": s[:200] + ("..." if len(s) > 200 else ""),
                            "提取中文": cn if cn else "(无中文)"
                        })

                    df_out = pd.DataFrame(results)

                    # 展示
                    st.dataframe(df_out, use_container_width=True, height=300)

                    # 单独导出
                    csv_bytes = create_dict_csv_in_memory(
                        ["原文片段", "提取中文"],
                        df_out.to_dict("records")
                    )
                    fname_out = f"中文提取_{f.name}.csv"
                    st.download_button(
                        "💾 导出本文件中文结果",
                        csv_bytes,
                        file_name=fname_out,
                        mime="text/csv",
                        use_container_width=True
                    )

                except Exception as e:
                    st.error(f"失败：{str(e)[:50]}")

    st.divider()
    st.caption("✅ 每个文件独立输出，互不合并")
