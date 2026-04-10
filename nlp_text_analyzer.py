import streamlit as st
import pandas as pd
import json
import os
from utils import create_csv_in_memory, create_dict_csv_in_memory

def nlp_text_analyzer_page():
    # 页面初始化，确保session_state正常
    if "nlp_results" not in st.session_state:
        st.session_state["nlp_results"] = None

    st.title("📄 中文自然语言&关键词匹配分析")
    st.caption("支持 CSV / JSON 上传，自动识别文本列，可选关键词匹配")

    # 一键清空按钮（放在最前面，确保加载正常）
    if st.button("🗑️ 清空所有上传与结果", use_container_width=True):
        # 清空相关session_state
        for k in list(st.session_state.keys()):
            if k.startswith("nlp_"):
                del st.session_state[k]
        st.rerun()

    # ----------------------
    # 上传区
    # ----------------------
    st.subheader("📤 上传文件（CSV / JSON）")
    uploaded_file = st.file_uploader(
        "选择单个 CSV 或 JSON 文件",
        type=["csv", "json"],
        key="nlp_uploader"
    )

    # 如果没有上传文件，显示提示+使用说明，避免页面空白
    if uploaded_file is None:
        st.info("ℹ️ 请上传 CSV 或 JSON 文件开始分析")
        with st.expander("💡 使用说明", expanded=True):
            st.markdown("""
            1.  上传 **CSV** 或 **JSON** 格式的文本文件
            2.  选择要分析的**中文文本列**
            3.  （可选）开启关键词匹配，输入要查找的关键词
            4.  点击「开始分析」，自动统计命中结果并导出
            """)
        return

    # ----------------------
    # 自动读取文件（加完整异常处理）
    # ----------------------
    try:
        ext = uploaded_file.name.split(".")[-1].lower()
        st.info(f"正在读取 {ext.upper()} 文件...")

        if ext == "csv":
            # 读取CSV，自动识别编码，跳过错误行
            df = pd.read_csv(uploaded_file, encoding="utf-8-sig", on_bad_lines="skip")
        elif ext == "json":
            data = json.load(uploaded_file)
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                st.error("❌ JSON格式错误：仅支持数组或对象格式")
                return
        else:
            st.error("❌ 不支持的文件格式，仅支持 CSV / JSON")
            return

        # 检查是否为空
        if df.empty:
            st.error("❌ 文件内容为空，请重新上传")
            return

        st.success(f"✅ 读取成功！共 {len(df)} 行数据，{len(df.columns)} 列")
        st.subheader("📋 文件预览（前5行）")
        st.dataframe(df.head(5), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"❌ 文件读取失败：{str(e)}")
        return

    # ----------------------
    # 选择要分析的中文文本列
    # ----------------------
    st.subheader("🔍 选择分析列")
    text_cols = list(df.columns)
    if not text_cols:
        st.error("❌ 未检测到有效列，请检查文件格式")
        return

    text_col = st.selectbox("选择要分析的中文文本列", text_cols, help="选择包含中文自然语言的列")

    # ----------------------
    # 关键词匹配（可选）
    # ----------------------
    st.subheader("🔑 关键词匹配配置（可选）")
    enable_keyword = st.checkbox("✅ 启用关键词匹配筛选", value=False, help="开启后可按关键词筛选文本")

    keyword_input = ""
    match_type = "包含（模糊）"
    if enable_keyword:
        keyword_input = st.text_input(
            "输入关键词（多个用逗号分隔，支持中文逗号）",
            placeholder="例如：人工智能,教育,大数据",
            help="自动将中文逗号转换为英文逗号"
        )
        match_type = st.radio(
            "匹配方式",
            ["包含（模糊匹配）", "完全相等（精确匹配）"],
            horizontal=True,
            help="包含：只要文本中有关键词即命中；完全相等：文本必须和关键词完全一致"
        )

    # ----------------------
    # 开始分析按钮
    # ----------------------
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        with st.spinner("🔍 正在分析文本..."):
            try:
                # 复制数据，避免修改原数据
                res_df = df.copy()
                # 统一文本格式，处理空值
                res_df["_分析文本"] = res_df[text_col].fillna("").astype(str).str.strip()

                # 处理关键词
                keywords = []
                if enable_keyword and keyword_input.strip():
                    # 自动转换中文逗号为英文逗号
                    clean_input = keyword_input.strip().replace("，", ",")
                    keywords = [kw.strip() for kw in clean_input.split(",") if kw.strip()]

                # 执行匹配
                hit_list = []
                hit_key_list = []

                for txt in res_df["_分析文本"]:
                    hit = False
                    hit_keys = []

                    if keywords:
                        for kw in keywords:
                            if not kw:
                                continue
                            # 根据匹配方式判断
                            if match_type == "完全相等（精确匹配）":
                                if txt == kw:
                                    hit = True
                                    hit_keys.append(kw)
                            else:  # 包含（模糊匹配）
                                if kw in txt:
                                    hit = True
                                    hit_keys.append(kw)

                    hit_list.append("✅ 命中" if hit else "❌ 未命中")
                    hit_key_list.append(" | ".join(hit_keys) if hit_keys else "-")

                # 写入结果
                res_df["是否命中关键词"] = hit_list
                res_df["命中关键词"] = hit_key_list

                # 保存到session_state
                st.session_state["nlp_results"] = res_df

            except Exception as e:
                st.error(f"❌ 分析失败：{str(e)}")
                return

        # ----------------------
        # 结果展示
        # ----------------------
        st.divider()
        st.subheader("📊 分析结果")
        res_df = st.session_state["nlp_results"]

        if res_df is None or res_df.empty:
            st.warning("⚠️ 无有效分析结果")
            return

        # 统计数据
        total = len(res_df)
        hit_count = len(res_df[res_df["是否命中关键词"] == "✅ 命中"]) if enable_keyword else 0

        # 统计卡片
        col1, col2, col3 = st.columns(3)
        col1.metric("📄 总行数", total)
        if enable_keyword:
            col2.metric("🎯 命中行数", hit_count)
            col3.metric("📈 命中率", f"{hit_count/total*100:.1f}%" if total > 0 else "0%")

        # 结果表格
        st.subheader("📋 详细结果")
        display_cols = [col for col in res_df.columns if col != "_分析文本"]
        st.dataframe(
            res_df[display_cols],
            use_container_width=True,
            height=400,
            hide_index=True
        )

        # ----------------------
        # 导出结果
        # ----------------------
        st.divider()
        st.subheader("📥 导出结果")
        out_df = res_df.drop(columns=["_分析文本"], errors="ignore")

        # 生成CSV
        csv_bytes = create_dict_csv_in_memory(
            list(out_df.columns),
            out_df.to_dict("records")
        )

        st.download_button(
            "💾 下载完整分析结果 CSV",
            csv_bytes,
            file_name=f"文本分析结果_{uploaded_file.name}",
            mime="text/csv",
            use_container_width=True,
            type="primary"
        )

        st.success("✅ 分析完成！可点击上方按钮下载结果")

    # 刷新后保留历史结果
    elif st.session_state["nlp_results"] is not None:
        st.divider()
        st.subheader("📊 历史分析结果")
        res_df = st.session_state["nlp_results"]
        display_cols = [col for col in res_df.columns if col != "_分析文本"]
        st.dataframe(
            res_df[display_cols],
            use_container_width=True,
            height=400,
            hide_index=True
        )
