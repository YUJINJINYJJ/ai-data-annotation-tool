import streamlit as st
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import create_csv_in_memory

def process_speech_json(f):
    try:
        f.seek(0)
        data = json.load(f)
        return {"文件名": f.name, "片段数": len(data.get("segments", [])), "状态": "正常"}
    except:
        return {"文件名": f.name, "片段数": 0, "状态": "读取失败"}

def speech_acceptance_page():
    st.title("🎙️ 语音标注自动验收")

    with st.sidebar:
        st.header("⚙️ 配置")
        max_workers = st.slider("多线程数", 2, 16, 8)

    st.subheader("📤 上传语音标注JSON")
    uploaded_files = st.file_uploader("批量上传", type="json", accept_multiple_files=True)

    if uploaded_files and st.button("🚀 开始验收", type="primary"):
        with st.spinner("多线程并行处理..."):
            results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_speech_json, f): f for f in uploaded_files}
                for future in as_completed(futures):
                    results.append(future.result())

        st.dataframe(results, use_container_width=True)
        st.success("✅ 多线程处理完成")
