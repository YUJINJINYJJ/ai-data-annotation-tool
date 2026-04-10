import streamlit as st
import pandas as pd
import json
import re
from collections import Counter
from utils import create_csv_in_memory, create_dict_csv_in_memory

def nlp_text_analyzer_page():
    if "nlp_result" not in st.session_state:
        st.session_state["nlp_result"] = None

    st.title("📄 批量中文提取 & 关键词统计（一行一个文件）")
    st.caption("中文分段分隔显示 | 关键词可开关 | 自动统计次数")

    # 清空
    if st.button("🗑️ 清空所有", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("nlp_"):
                del st.session_state[k]
        st.rerun()

    # 批量上传
    st.subheader("📤 上传多个 CSV / JSON")
    uploaded_files = st.file_uploader(
        "可多选，最终输出一个汇总表",
        type=["csv", "json"],
        accept_multiple_files=True,
        key="nlp_uploader"
    )

    if not uploaded_files:
        st.info("请上传文件")
        return

    # 可选关键词匹配 + 统计
    st.subheader("🔑 关键词匹配与统计（可选）")
    enable_key = st.checkbox("开启关键词匹配与统计", value=False)
    keyword_input = ""
    if enable_key:
        keyword_input = st.text_input(
            "关键词（逗号分隔，支持中文逗号）",
            placeholder="例如：人工智能,教育,历史"
        )

    # 开始处理
    if st.button("🚀 生成汇总表", type="primary", use_container_width=True):
        # 中文正则
        cn_pattern = re.compile(r"[\u4e00-\u9fa5]+")
        rows = []
        keywords = []

        # 处理关键词
        if enable_key and keyword_input.strip():
            clean_input = keyword_input.strip().replace("，", ",")
            keywords = [k.strip() for k in clean_input.split(",") if k.strip()]

        with st.spinner("正在提取中文并统计..."):
            for f in uploaded_files:
                try:
                    ext = f.name.split(".")[-1].lower()
                    full_text = ""

                    # 读取整个文件内容
                    if ext == "csv":
                        df = pd.read_csv(f, encoding="utf-8-sig", dtype=str).fillna("")
                        full_text = " ".join(df.stack().astype(str).tolist())
                    elif ext == "json":
                        full_text = str(json.load(f))

                    # 1. 提取所有中文 → 分隔显示
                    cn_list = cn_pattern.findall(full_text)
                    chinese_text = "、".join(cn_list) if cn_list else "(无中文)"

                    # 2. 关键词统计（只有开启才计算）
                    hit_info = {}
                    if enable_key and keywords:
                        # 统计每个关键词出现次数
                        count_dict = Counter()
                        for kw in keywords:
                            count_dict[kw] = full_text.count(kw)
                        # 命中的词
                        hit_kws = [kw for kw in keywords if count_dict[kw] > 0]
                        total_hit = sum(count_dict.values())

                        hit_info = {
                            "是否命中": "是" if hit_kws else "否",
                            "命中关键词": " | ".join(hit_kws) if hit_kws else "无",
                            "各关键词出现次数": " | ".join([f"{k}:{v}" for k, v in count_dict.items()]),
                            "总命中次数": total_hit
                        }

                    # 构造一行（一个文件一行）
                    row = {
                        "文件名": f.name,
                        "提取全部中文（分隔）": chinese_text
                    }
                    if enable_key:
                        row.update(hit_info)

                    rows.append(row)

                except Exception as e:
                    row = {"文件名": f.name + "（读取失败）", "提取全部中文（分隔）": ""}
                    if enable_key:
                        row.update({"是否命中": "", "命中关键词": "", "各关键词出现次数": "", "总命中次数": ""})
                    rows.append(row)

            st.session_state["nlp_result"] = pd.DataFrame(rows)

    # 展示结果
    if st.session_state["nlp_result"] is not None:
        st.divider()
        st.subheader("📊 汇总结果（一个文件一行）")
        st.dataframe(st.session_state["nlp_result"], use_container_width=True, height=400)

        # 导出一个总表
        st.subheader("📥 导出完整汇总表")
        csv_bytes = create_dict_csv_in_memory(
            list(st.session_state["nlp_result"].columns),
            st.session_state["nlp_result"].to_dict("records")
        )
        st.download_button(
            "💾 下载全部结果.csv",
            csv_bytes,
            file_name="中文提取&关键词统计汇总表.csv",
            mime="text/csv",
            use_container_width=True
        )
        st.success("✅ 处理完成！")
