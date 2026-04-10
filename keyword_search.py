import streamlit as st
import json
from collections import Counter

# 主页面函数
def json_keyword_search_page():
    st.title("🔍 图片/视频JSON关键词批量匹配")

    # ======================
    # 配置项 = 左侧边栏
    # ======================
    with st.sidebar:
        st.header("⚙️ 匹配设置")
        keyword_input = st.text_input("关键词（逗号分隔）")
        split_array = st.checkbox("拆分JSON数组", value=False)

    # ======================
    # 主界面：上传
    # ======================
    st.subheader("📤 上传JSON文件")
    uploaded_files = st.file_uploader(
        "批量上传JSON", type="json", accept_multiple_files=True
    )

    if not uploaded_files:
        st.info("请上传文件继续")
        return

    # 处理按钮
    if st.button("🚀 开始匹配", type="primary"):
        if not keyword_input:
            st.error("请输入关键词")
            return

        # 处理关键词
        keywords = [k.strip() for k in keyword_input.replace("，", ",").split(",") if k.strip()]
        results = []

        # 遍历文件
        for file in uploaded_files:
            try:
                data = json.load(file)
                text = str(data)
                count = {k: text.count(k) for k in keywords}
                total = sum(count.values())

                results.append({
                    "文件名": file.name,
                    "总匹配数": total,
                    **{f"{k}次数": v for k, v in count.items()}
                })
            except:
                results.append({"文件名": f"{file.name}（错误）", "总匹配数": 0})

        # 展示结果
        st.dataframe(results, use_container_width=True)

        # 导出
        csv = "\n".join([",".join(map(str, r.values())) for r in results])
        st.download_button("导出结果", csv, "匹配结果.csv", "text/csv")
