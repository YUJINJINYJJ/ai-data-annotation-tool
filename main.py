"""
数据标注工具集 - 主入口
提供视频标注验收、语音标注验收、JSON关键词匹配、中文文本分析等功能
"""
import streamlit as st
from keyword_search import json_keyword_search_page
from video_acceptance import video_acceptance_page
from speech_acceptance import speech_acceptance_page
from nlp_text_analyzer import nlp_text_analyzer_page

# 页面配置
st.set_page_config(
    page_title="数据标注工具集",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "数据标注工具集 - 批量验收与分析工具"
    }
)

# 自定义样式
CUSTOM_CSS = """
<style>
    /* 主色调（明暗模式通用） */
    :root {
        --primary-color: #1E88E5;
        --success-color: #4CAF50;
        --warning-color: #FF9800;
        --danger-color: #F44336;
    }
    
    /* 浅色模式 */
    @media (prefers-color-scheme: light) {
        :root {
            --bg-color: #FAFAFA;
            --card-bg-color: #F5F5F5;
            --text-primary-color: #212121;
            --text-secondary-color: #757575;
            --border-color: #E0E0E0;
            --hover-bg-color: #E3F2FD;
        }
    }
    
    /* 深色模式（核心修复） */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg-color: #0E1117;
            --card-bg-color: #262730;
            --text-primary-color: #FAFAFA;
            --text-secondary-color: #B0B0B0;
            --border-color: #3A3A3A;
            --hover-bg-color: #1E3A5F;
        }
    }
    
    /* 标题样式 */
    .stTitle {
        font-size: 2rem !important;
        font-weight: 600 !important;
        color: var(--primary-color) !important;
    }
    
    /* 副标题 */
    .stMarkdown h3 {
        color: var(--text-primary-color) !important;
        border-bottom: 2px solid var(--hover-bg-color);
        padding-bottom: 0.5rem;
    }
    
    /* 按钮样式 */
    .stButton > button[kind="primary"] {
        background-color: var(--primary-color) !important;
        border-color: var(--primary-color) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* 数据框样式 */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* 指标卡片 */
    .stMetric > div {
        background-color: var(--card-bg-color) !important;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .stMetric label {
        font-size: 0.9rem !important;
        color: var(--text-secondary-color) !important;
    }
    
    .stMetric [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 600 !important;
        color: var(--text-primary-color) !important;
    }
    
    /* 侧边栏（核心修复：动态背景色） */
    section[data-testid="stSidebar"] {
        background-color: var(--card-bg-color) !important;
    }
    
    /* 侧边栏文字颜色适配 */
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] .stCaption {
        color: var(--text-primary-color) !important;
    }
    
    /* 上传区域 */
    .stFileUploader {
        border: 2px dashed var(--border-color);
        border-radius: 8px;
        padding: 1rem;
        background-color: var(--card-bg-color);
    }
    
    /* 表格悬停效果 */
    .stDataFrame tbody tr:hover {
        background-color: var(--hover-bg-color) !important;
    }
    
    /* 成功提示 */
    .stSuccess {
        background-color: #E8F5E9 !important;
        border-left: 4px solid var(--success-color) !important;
        color: #1B5E20 !important;
    }
    
    /* 错误提示 */
    .stError {
        background-color: #FFEBEE !important;
        border-left: 4px solid var(--danger-color) !important;
        color: #B71C1C !important;
    }
    
    /* 警告提示 */
    .stWarning {
        background-color: #FFF3E0 !important;
        border-left: 4px solid var(--warning-color) !important;
        color: #E65100 !important;
    }
    
    /* 信息提示 */
    .stInfo {
        background-color: #E3F2FD !important;
        border-left: 4px solid var(--primary-color) !important;
        color: #0D47A1 !important;
    }
    
    /* 分隔线 */
    hr {
        border-color: var(--border-color) !important;
    }
    
    /* 页脚 */
    .footer {
        text-align: center;
        padding: 1rem;
        color: var(--text-secondary-color);
        font-size: 0.85rem;
    }
    
    /* 输入框样式适配 */
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea {
        background-color: var(--card-bg-color) !important;
        color: var(--text-primary-color) !important;
        border-color: var(--border-color) !important;
    }
    
    /* 滑块样式适配 */
    .stSlider [data-testid="stSliderThumb"] {
        background-color: var(--primary-color) !important;
    }
    
    .stSlider [data-testid="stSliderTrack"] {
        background-color: var(--border-color) !important;
    }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# 页面配置字典
PAGES = {
    "🔍 JSON 关键词匹配": {
        "function": json_keyword_search_page,
        "icon": "🔍",
        "description": "递归搜索 JSON 文件中的关键词，支持阈值校验"
    },
    "🎬 视频标注验收": {
        "function": video_acceptance_page,
        "icon": "🎬",
        "description": "批量验收视频标注质量，检查帧数和目标数"
    },
    "🎙️ 语音标注验收": {
        "function": speech_acceptance_page,
        "icon": "🎙️",
        "description": "批量验收语音标注质量，检查片段数和标签"
    },
    "📄 中文文本分析": {
        "function": nlp_text_analyzer_page,
        "icon": "📄",
        "description": "提取中文内容，统计关键词出现次数"
    }
}

# 侧边栏导航
with st.sidebar:
    st.title("🛠️ 数据标注工具集")
    st.caption("专业的标注数据验收与分析工具")
    
    st.divider()
    
    # 页面选择
    page_names = list(PAGES.keys())
    selected_page = st.radio(
        "选择功能",
        page_names,
        key="main_page_radio",
        label_visibility="collapsed"
    )
    
    # 显示当前页面描述
    if selected_page in PAGES:
        st.caption(f"📋 {PAGES[selected_page]['description']}")
    
    st.divider()
    
    # 快捷操作
    with st.expander("⚡ 快捷键", expanded=False):
        st.markdown("""
        - `Ctrl + Enter` - 提交表单
        - `Esc` - 关闭弹窗
        """)

# 主内容区
if selected_page in PAGES:
    PAGES[selected_page]["function"]()
else:
    st.error("❌ 页面不存在")

# 页脚
st.divider()
st.markdown(
    "<div class='footer'>💡 所有报告仅在点击下载时生成，不会自动保存到本地</div>",
    unsafe_allow_html=True
)
