import streamlit as st
from keyword_search import json_keyword_search_page
from video_acceptance import video_acceptance_page
from speech_acceptance import speech_acceptance_page
from nlp_text_analyzer import nlp_text_analyzer_page  # 确保导入路径正确

# 全局配置
st.set_page_config(
    page_title="数据标注工具集",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 侧边栏导航
st.sidebar.title("🛠️ 数据标注工具集")
page = st.sidebar.radio(
    "选择功能页面",
    [
        "🔍 图片/视频JSON关键词匹配",
        "✅ 视频标注自动验收",
        "🎙️ 语音标注自动验收",
        "📄 中文自然语言匹配分析"  # 确保名称和路由完全一致
    ],
    key="main_page_radio"
)

# 页面路由
if page == "🔍 图片/视频JSON关键词匹配":
    json_keyword_search_page()
elif page == "✅ 视频标注自动验收":
    video_acceptance_page()
elif page == "🎙️ 语音标注自动验收":
    speech_acceptance_page()
elif page == "📄 中文自然语言匹配分析":
    nlp_text_analyzer_page()
else:
    st.error("❌ 页面不存在")

# 页脚
st.divider()
st.caption("💡 所有报告仅在点击下载时生成，不会自动保存到本地")
