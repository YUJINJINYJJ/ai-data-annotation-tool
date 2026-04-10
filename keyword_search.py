import streamlit as st
import os
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import create_csv_in_memory, create_dict_csv_in_memory


def json_keyword_search_page():
    st.title("🔍 图片/视频JSON关键词批量匹配工具")
    st.caption("支持模糊匹配、多关键词统计、达标检测、手动下载报告")

    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 匹配配置")
        keyword_input = st.text_input(
            "🔑 查找关键词",
            placeholder="多个用英文逗号分隔，如：足,女足,足球",
            help="模糊匹配，输入'足'会匹配所有带'足'的内容"
        )

        st.subheader("✅ 达标检测配置")
        enable_threshold = st.checkbox("启用关键字数量达标检测", value=True)
        threshold_text = ""
        if enable_threshold:
            threshold_text = st.text_area(
                "📏 各关键字最低出现次数",
                placeholder="每行一个，格式：关键字:最低次数\n例如：\n足:3\n女足:2\n足球:1",
                height=150
            )

        max_workers = st.slider("⚡ 并行处理线程数", 2, 16, 8, help="数值越大处理越快")
        st.divider()
        st.caption("💡 支持批量上传JSON文件，本地运行可输入文件夹路径")

    # 输入方式选择
    tab1, tab2 = st.tabs(["📤 上传JSON文件", "📂 本地文件夹（仅本地运行）"])

    with tab1:
        uploaded_files = st.file_uploader(
            "选择多个JSON文件（支持百/千份批量上传）",
            type="json",
            accept_multiple_files=True,
            help="按住Ctrl可多选，支持拖拽上传"
        )

    with tab2:
        folder_path = st.text_input(
            "输入本地JSON文件夹绝对路径",
            placeholder="例如：D:\\data\\json_files 或 /home/user/json_files"
        )

    # 开始匹配按钮
    if st.button("🚀 开始批量匹配", type="primary", use_container_width=True):
        # 输入校验
        if not keyword_input.strip():
            st.error("❌ 请输入查找关键词！")
            st.stop()

        targets = [kw.strip() for kw in keyword_input.split(",") if kw.strip()]
        if not targets:
            st.error("❌ 关键词不能为空！")
            st.stop()

        # 解析阈值
        threshold_dict = {}
        if enable_threshold and threshold_text.strip():
            for line in threshold_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                if ":" not in line:
                    st.warning(f"⚠️ 阈值格式错误：{line}，已跳过")
                    continue
                kw, cnt = line.split(":", 1)
                kw = kw.strip()
                try:
                    threshold_dict[kw] = int(cnt.strip())
                except ValueError:
                    st.warning(f"⚠️ 阈值必须为数字：{line}，已跳过")

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

        # 多线程批量处理
        with st.spinner(f"🔍 正在批量处理 {len(files_to_process)} 个文件..."):
            all_results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_single_json, f, targets, is_up): (f, is_up) for f, is_up in
                           files_to_process}
                for future in as_completed(futures):
                    all_results.extend(future.result())

        # 分离结果
        success_results = [r for r in all_results if r["status"] == "success"]
        invalid_results = [r for r in all_results if r["status"] == "invalid_json"]
        error_results = [r for r in all_results if r["status"] == "error"]
        total_files = len(all_results)

        # 生成校验报告
        verification_report = None
        if enable_threshold and threshold_dict:
            verification_report = generate_json_verification_report(success_results, targets, threshold_dict,
                                                                    total_files)

        # 全局统计
        matched_files = len([r for r in success_results if r["total_match"] > 0])
        total_matches = sum(r["total_match"] for r in success_results)
        all_values = []
        for r in success_results:
            all_values.extend(r["match_values"])
        value_counter = Counter(all_values)

        # 展示结果
        st.divider()
        st.subheader("📊 全局统计")

        # 基础统计卡片
        cols = st.columns(6)
        cols[0].metric("总扫描文件数", total_files)
        cols[1].metric("有效JSON文件", len(success_results))
        cols[2].metric("匹配到关键词", matched_files)
        cols[3].metric("总匹配条数", total_matches)
        cols[4].metric("无效JSON", len(invalid_results))
        cols[5].metric("读取失败", len(error_results))

        # 达标检测统计
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

            if verification_report:
                filter_option = st.radio("筛选显示：", ["全部文件", "仅达标文件", "仅未达标文件"], horizontal=True)
                if filter_option == "仅达标文件":
                    display_data = [d for d in detail_data if d["校验状态"] == "✅ 达标"]
                elif filter_option == "仅未达标文件":
                    display_data = [d for d in detail_data if d["校验状态"] == "❌ 未达标"]
                else:
                    display_data = detail_data
            else:
                display_data = detail_data

            if display_data:
                st.dataframe(display_data, use_container_width=True, height=400)

        # 异常文件
        if invalid_results or error_results:
            with st.expander("⚠️ 异常文件列表（已跳过）"):
                if invalid_results:
                    st.write("❌ 无效JSON文件：")
                    st.write([r["file_name"] for r in invalid_results])
                if error_results:
                    st.write("❌ 读取失败文件：")
                    for r in error_results:
                        st.write(f"{r['file_name']}: {r['error']}")

        # 匹配值统计
        st.divider()
        st.subheader("🔢 匹配值出现次数统计（降序）")
        value_data = []
        if value_counter:
            value_data = [{"匹配值": k, "出现次数": v} for k, v in
                          sorted(value_counter.items(), key=lambda x: x[1], reverse=True)]
            if value_data:
                st.dataframe(value_data, use_container_width=True, height=300)

        # 结果导出
        st.divider()
        st.subheader("📥 报告导出")
        name_suffix = "_".join(targets)

        if verification_report:
            # 生成完整校验报告
            report_rows = []
            report_rows.append(["【全局校验统计】"])
            for k, v in verification_report["global_stats"].items():
                report_rows.append([k, str(v)])
            report_rows.append([])
            report_rows.append(["【分文件详细结果】"])
            report_headers = ["文件名", "文件路径", "总匹配数"]
            for kw in targets:
                report_headers.append(f"{kw}出现次数")
            report_headers.extend(["校验状态", "未达标原因", "所有匹配值"])
            report_rows.append(report_headers)
            for r in verification_report["all_files"]:
                row = [r["file_name"], r["file_path"], str(r["total_match"])]
                for kw in targets:
                    row.append(str(r["keyword_count"][kw]))
                row.extend([
                    "✅ 达标" if r["is_pass"] else "❌ 未达标",
                    r["fail_reason"] if not r["is_pass"] else "-",
                    " | ".join(r["match_values"])
                ])
                report_rows.append(row)

            report_csv = create_csv_in_memory(None, report_rows)
            st.download_button(
                "📄 下载完整校验报告",
                report_csv,
                file_name=f"JSON批量校验报告_{name_suffix}.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )

        if detail_data:
            result_headers = list(detail_data[0].keys())
            result_csv = create_dict_csv_in_memory(result_headers, detail_data)
            st.download_button(
                "📋 下载匹配结果CSV",
                result_csv,
                file_name=f"JSON匹配结果_{name_suffix}.csv",
                mime="text/csv",
                use_container_width=True
            )

        if value_data:
            count_headers = ["匹配值", "出现次数"]
            count_csv = create_dict_csv_in_memory(count_headers, value_data)
            st.download_button(
                "📊 下载值统计CSV",
                count_csv,
                file_name=f"值出现次数统计_{name_suffix}.csv",
                mime="text/csv",
                use_container_width=True
            )

        st.success("✅ 批量匹配完成！点击上方按钮下载需要的报告")


# JSON匹配辅助函数（支持数组根结构）
def process_single_json(file_obj, targets, is_uploaded=True):
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

        # 支持根为数组或单个对象
        items = json_data if isinstance(json_data, list) else [json_data]

        for idx, item in enumerate(items):
            item_results = search_json_data(item, targets)
            file_count = {t: 0 for t in targets}
            match_values = []
            for res in item_results:
                file_count[res["keyword"]] += 1
                match_values.append(res["value"])

            results.append({
                "status": "success",
                "file_path": file_path,
                "file_name": f"{file_name} (第{idx + 1}个)",
                "total_match": len(item_results),
                "keyword_count": file_count,
                "match_values": match_values
            })

        return results
    except json.JSONDecodeError:
        return [{"status": "invalid_json", "file_name": getattr(file_obj, "name", str(file_obj))}]
    except Exception as e:
        return [{"status": "error", "file_name": getattr(file_obj, "name", str(file_obj)), "error": str(e)}]


def search_json_data(data, targets):
    matches = []
    if isinstance(data, dict):
        for value in data.values():
            matches.extend(search_json_data(value, targets))
    elif isinstance(data, list):
        for item in data:
            matches.extend(search_json_data(item, targets))
    else:
        val_str = str(data).lower()
        for target in targets:
            if target.lower() in val_str:
                matches.append({
                    "value": str(data),
                    "keyword": target
                })
                break
    return matches


def check_json_threshold(file_count, threshold_dict):
    is_pass = True
    fail_reasons = []
    for kw, min_cnt in threshold_dict.items():
        actual = file_count.get(kw, 0)
        if actual < min_cnt:
            is_pass = False
            fail_reasons.append(f"{kw}：实际{actual}次，要求≥{min_cnt}次")
    return is_pass, "; ".join(fail_reasons)


def generate_json_verification_report(success_results, targets, threshold_dict, total_files):
    if not threshold_dict:
        return None

    total_valid = len(success_results)
    pass_count = 0
    fail_count = 0

    for r in success_results:
        r["is_pass"], r["fail_reason"] = check_json_threshold(r["keyword_count"], threshold_dict)
        if r["is_pass"]:
            pass_count += 1
        else:
            fail_count += 1

    pass_rate = (pass_count / total_valid) * 100 if total_valid > 0 else 0

    return {
        "global_stats": {
            "总扫描文件数": total_files,
            "有效JSON文件数": total_valid,
            "达标文件数": pass_count,
            "未达标文件数": fail_count,
            "文件达标率": f"{pass_rate:.2f}%"
        },
        "all_files": success_results
    }