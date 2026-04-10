import streamlit as st
import os
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import create_csv_in_memory, create_dict_csv_in_memory

# --------------------------
# 核心辅助函数（完整保留，无修改）
# --------------------------
def search_json_data(data, targets):
    matches = []
    if isinstance(data, dict):
        for v in data.values():
            matches.extend(search_json_data(v, targets))
    elif isinstance(data, list):
        for item in data:
            matches.extend(search_json_data(item, targets))
    else:
        s = str(data).lower()
        for t in targets:
            if t.lower() in s:
                matches.append({"value": str(data), "keyword": t})
                break
    return matches

def check_json_threshold(file_count, threshold_dict):
    is_pass = True
    fail = []
    for kw, m in threshold_dict.items():
        a = file_count.get(kw, 0)
        if a < m:
            is_pass = False
            fail.append(f"{kw}实际{a}次，要求≥{m}次")
    return is_pass, "; ".join(fail)

def generate_json_verification_report(success_results, targets, threshold_dict, total_files):
    if not threshold_dict:
        return None
    total = len(success_results)
    p = 0
    f = 0
    for r in success_results:
        r["is_pass"], r["fail_reason"] = check_json_threshold(r["keyword_count"], threshold_dict)
        p += 1 if r["is_pass"] else 0
        f += 1 if not r["is_pass"] else 0
    return {
        "global_stats": {
            "总扫描文件数": total_files,
            "有效JSON文件数": total,
            "达标文件数": p,
            "未达标文件数": f,
            "文件达标率": f"{p/total*100:.2f}%" if total > 0 else "0%"
        },
        "all_files": success_results
    }

def process_single_json(file_obj, targets, is_uploaded=True, split_array=False):
    results = []
    try:
        if is_uploaded:
            file_obj.seek(0)
            json_data = json.load(file_obj)
            file_name = file_obj.name
            file_path = f"上传文件/{file_name}"
        else:
            with open(file_obj, "r", encoding="utf-8") as f:
                json_data = json.load(f)
            file_name = os.path.basename(file_obj)
            file_path = file_obj

        if split_array and isinstance(json_data, list):
            for idx, item in enumerate(json_data):
                item_results = search_json_data(item, targets)
                file_count = {t: 0 for t in targets}
                match_values = []
                for res in item_results:
                    file_count[res["keyword"]] += 1
                    match_values.append(res["value"])
                results.append({
                    "status": "success",
                    "file_path": file_path,
                    "file_name": f"{file_name} (第{idx+1}个)",
                    "total_match": len(item_results),
                    "keyword_count": file_count,
                    "match_values": match_values
                })
        else:
            all_results = search_json_data(json_data, targets)
            file_count = {t: 0 for t in targets}
            match_values = []
            for res in all_results:
                file_count[res["keyword"]] += 1
                match_values.append(res["value"])
            results.append({
                "status": "success",
                "file_path": file_path,
                "file_name": file_name,
                "total_match": len(all_results),
                "keyword_count": file_count,
                "match_values": match_values
            })
        return results
    except json.JSONDecodeError:
        return [{"status": "invalid_json", "file_name": getattr(file_obj, "name", str(file_obj))}]
    except Exception as e:
        return [{"status": "error", "file_name": getattr(file_obj, "name", str(file_obj)), "error": str(e)}]

# --------------------------
# 主页面（配置左移+多线程完整保留）
# --------------------------
def json_keyword_search_page():
    st.title("🔍 图片/视频JSON关键词批量匹配")
    st.caption("配置项已移至左侧边栏，多线程并行处理完整保留")

    # ======================
    # 【所有配置100%移到左侧边栏】
    # ======================
    with st.sidebar:
        st.header("⚙️ 匹配配置")
        keyword_input = st.text_input(
            "🔑 查找关键词",
            placeholder="多个用逗号分隔，支持中文逗号",
            help="模糊匹配，输入'足'会匹配所有带'足'的内容"
        )
        
        st.subheader("✅ 达标检测配置")
        enable_threshold = st.checkbox("启用关键字数量达标检测", value=True)
        threshold_text = ""
        if enable_threshold:
            threshold_text = st.text_area(
                "📏 各关键字最低出现次数",
                placeholder="每行一个，格式：关键字:最低次数",
                height=150
            )
        
        st.divider()
        split_array = st.checkbox(
            "拆分JSON数组为独立条目",
            value=False,
            help="关闭：整个JSON作为整体统计；开启：数组每个元素独立统计"
        )
        
        # 【多线程配置完整保留】
        max_workers = st.slider("⚡ 并行处理线程数", 2, 16, 8, help="批量大文件时调大，提升处理速度")
        st.divider()
        st.caption("💡 支持批量上传JSON文件，多线程并行加速")

    # ======================
    # 【主界面仅保留上传+结果】
    # ======================
    st.subheader("📤 上传JSON文件")
    tab1, tab2 = st.tabs(["📤 上传JSON文件", "📂 本地文件夹（仅本地运行）"])

    with tab1:
        uploaded_files = st.file_uploader(
            "选择多个JSON文件（支持批量上传，多线程并行处理）",
            type="json",
            accept_multiple_files=True,
            key="keyword_uploader"
        )
        if st.button("🗑️ 清空所有上传文件", use_container_width=True):
            if "keyword_uploader" in st.session_state:
                del st.session_state.keyword_uploader
            st.rerun()

    with tab2:
        folder_path = st.text_input(
            "输入本地JSON文件夹绝对路径",
            placeholder="例如：D:\\data\\json_files"
        )

    # ======================
    # 【开始匹配（多线程完整执行）】
    # ======================
    if st.button("🚀 开始批量匹配", type="primary", use_container_width=True):
        if not keyword_input.strip():
            st.error("❌ 请输入查找关键词！")
            st.stop()
        
        # 处理关键词（自动中文逗号转英文）
        keyword_input_clean = keyword_input.strip().replace('，', ',')
        targets = [kw.strip() for kw in keyword_input_clean.split(",") if kw.strip()]
        if not targets:
            st.error("❌ 关键词不能为空！")
            st.stop()
        
        # 处理阈值
        threshold_dict = {}
        if enable_threshold and threshold_text.strip():
            for line in threshold_text.split("\n"):
                line = line.strip().replace('：', ':')
                if not line or ":" not in line:
                    continue
                kw, cnt = line.split(":", 1)
                try:
                    threshold_dict[kw.strip()] = int(cnt.strip())
                except:
                    st.warning(f"⚠️ 阈值格式错误：{line}，已跳过")
        
        # 收集待处理文件
        files_to_process = []
        if uploaded_files:
            files_to_process = [(f, True) for f in uploaded_files]
        if folder_path and os.path.isdir(folder_path):
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith(".json"):
                        files_to_process.append((os.path.join(root, f), False))
        
        if not files_to_process:
            st.error("❌ 未找到任何JSON文件！")
            st.stop()
        
        # 【多线程并行处理，完整保留】
        with st.spinner(f"🔍 正在多线程并行处理 {len(files_to_process)} 个文件..."):
            all_results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_single_json, f, targets, is_up, split_array): (f, is_up) 
                    for f, is_up in files_to_process
                }
                for future in as_completed(futures):
                    all_results.extend(future.result())
        
        # 结果分类
        success_results = [r for r in all_results if r["status"] == "success"]
        invalid_results = [r for r in all_results if r["status"] == "invalid_json"]
        error_results = [r for r in all_results if r["status"] == "error"]
        total_files = len(all_results)
        
        # 生成达标校验报告
        verification_report = None
        if enable_threshold and threshold_dict:
            verification_report = generate_json_verification_report(success_results, targets, threshold_dict, total_files)
        
        # 统计数据
        matched_files = len([r for r in success_results if r["total_match"] > 0])
        total_matches = sum(r["total_match"] for r in success_results)
        value_counter = Counter()
        for r in success_results:
            value_counter.update(r["match_values"])

        # ======================
        # 结果展示
        # ======================
        st.divider()
        st.subheader("📊 全局统计")
        cols = st.columns(6)
        cols[0].metric("总扫描文件数", total_files)
        cols[1].metric("有效JSON文件", len(success_results))
        cols[2].metric("匹配到关键词", matched_files)
        cols[3].metric("总匹配条数", total_matches)
        cols[4].metric("无效JSON", len(invalid_results))
        cols[5].metric("读取失败", len(error_results))
        
        # 达标统计
        if verification_report:
            st.divider()
            st.subheader("✅ 关键字达标检测统计")
            cols2 = st.columns(4)
            cols2[0].metric("达标文件数", verification_report["global_stats"]["达标文件数"])
            cols2[1].metric("未达标文件数", verification_report["global_stats"]["未达标文件数"])
            cols2[2].metric("文件达标率", verification_report["global_stats"]["文件达标率"])
            cols2[3].metric("校验关键字数", len(threshold_dict))
        
        # 分文件详情
        st.divider()
        st.subheader("📋 分文件匹配详情")
        detail_data = []
        if success_results:
            for r in success_results:
                row = {
                    "文件名": r["file_name"],
                    "文件路径": r["file_path"],
                    "总匹配数": r["total_match"]
                }
                for kw in targets:
                    row[f"{kw}出现次数"] = r["keyword_count"][kw]
                if verification_report:
                    row["校验状态"] = "✅ 达标" if r["is_pass"] else "❌ 未达标"
                    row["未达标原因"] = r["fail_reason"] if not r["is_pass"] else "-"
                row["匹配值预览"] = " | ".join(r["match_values"][:10]) + ("..." if len(r["match_values"]) > 10 else "")
                detail_data.append(row)
            
            # 筛选
            if verification_report:
                filter_option = st.radio("筛选显示：", ["全部文件", "仅达标文件", "仅未达标文件"], horizontal=True)
                display_data = []
                for d in detail_data:
                    if filter_option == "全部文件":
                        display_data.append(d)
                    elif filter_option == "仅达标文件" and d["校验状态"] == "✅ 达标":
                        display_data.append(d)
                    elif filter_option == "仅未达标文件" and d["校验状态"] == "❌ 未达标":
                        display_data.append(d)
            else:
                display_data = detail_data
            st.dataframe(display_data, use_container_width=True, height=400)
        
        # 异常文件
        if invalid_results or error_results:
            with st.expander("⚠️ 异常文件列表（已跳过）"):
                if invalid_results:
                    st.write("❌ 无效JSON文件：", [r["file_name"] for r in invalid_results])
                if error_results:
                    st.write("❌ 读取失败文件：", [f"{r['file_name']}: {r['error']}" for r in error_results])
        
        # 匹配值统计
        st.divider()
        st.subheader("🔢 匹配值出现次数统计（降序）")
        value_data = [{"匹配值": k, "出现次数": v} for k, v in sorted(value_counter.items(), key=lambda x: x[1], reverse=True)]
        if value_data:
            st.dataframe(value_data, use_container_width=True, height=300)
        
        # 导出报告
        st.divider()
        st.subheader("📥 报告导出")
        name_suffix = "_".join(targets)
        
        if verification_report:
            report_rows = [["【全局校验统计】"]]
            for k,v in verification_report["global_stats"].items():
                report_rows.append([k, v])
            report_rows.append([])
            report_headers = ["文件名","文件路径","总匹配数"] + [f"{kw}出现次数" for kw in targets] + ["校验状态","未达标原因","所有匹配值"]
            report_rows.append(report_headers)
            for r in verification_report["all_files"]:
                row = [r["file_name"],r["file_path"],str(r["total_match"])]
                row.extend([str(r["keyword_count"][kw]) for kw in targets])
                row.extend(["✅ 达标" if r["is_pass"] else "❌ 未达标", r["fail_reason"] if not r["is_pass"] else "-", " | ".join(r["match_values"])])
                report_rows.append(row)
            report_csv = create_csv_in_memory(None, report_rows)
            st.download_button("📄 下载完整校验报告", report_csv, f"JSON批量校验报告_{name_suffix}.csv", use_container_width=True, type="primary")
        
        if detail_data:
            result_csv = create_dict_csv_in_memory(list(detail_data[0].keys()), detail_data)
            st.download_button("📋 下载匹配结果CSV", result_csv, f"JSON匹配结果_{name_suffix}.csv", use_container_width=True)
        if value_data:
            count_csv = create_dict_csv_in_memory(["匹配值","出现次数"], value_data)
            st.download_button("📊 下载值统计CSV", count_csv, f"值出现次数统计_{name_suffix}.csv", use_container_width=True)
        
        st.success("✅ 多线程批量匹配完成！")
