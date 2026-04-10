import streamlit as st
import pandas as pd
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import create_dict_csv_in_memory

def extract_one_file(f):
    try:
        ext = f.name.split(".")[-1].lower()
        all_text = ""
        if ext == "csv":
            df = pd.read_csv(f, encoding="utf-8-sig", dtype=str).fillna("")
            all_text = " ".join(df.stack().tolist())
        elif ext == "json":
            all_text = str(json.load(f))
        cn = "".join(re.findall(r"[\u4e00-\u9fa5]+", all_text))
        return {"来源文件": f.name, "提取中文": cn}
    except:
        return {"来源文件": f.name, "提取中文": "读取失败"}

def nlp_text_analyzer_page():
    st.title("📄 批量中文提取（含关键词）")

    with st.sidebar:
        st.header("⚙️ 配置")
        enable_key = st.checkbox("开启关键词匹配")
        keyword_input = st.text_input("关键词") if enable_key else ""
        max_workers = st.slider("多线程数", 2, 16, 8)

    st.subheader("📤 上传CSV/JSON")
    uploaded_files = st.file_uploader("批量上传", type=["csv","json"], accept_multiple_files=True)

    if uploaded_files and st.button("🚀 开始提取", type="primary"):
        with st.spinner("多线程提取中..."):
            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(extract_one_file, f): f for f in uploaded_files}
                for future in as_completed(futures):
                    results.append(future.result())

        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        st.success("✅ 多线程中文提取完成")
