import streamlit as st
from keyword_search import json_keyword_search_page
from video_acceptance import video_acceptance_page

# 全局配置
st.set_page_config(
    page_title="数据标注工具集",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 顶部导航
st.sidebar.title("🛠️ 数据标注工具集")
page = st.sidebar.radio("选择功能页面", ["🔍 图片/视频JSON关键词匹配", "✅ 视频标注自动验收"])

# 页面路由
if page == "🔍 图片/视频JSON关键词匹配":
    json_keyword_search_page()
elif page == "✅ 视频标注自动验收":
    video_acceptance_page()

# 页脚
st.divider()
st.caption("💡 所有报告仅在点击下载时生成，不会自动保存到本地")