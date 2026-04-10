import streamlit as st
import os
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import create_csv_in_memory, create_dict_csv_in_memory

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

def json_keyword_search_page():
    st.title("🔍 图片/视频JSON关键词批量匹配")

    with st.sidebar:
        st.header("⚙️ 配置")
        keyword_input = st.text_input("关键词（逗号分隔）")
        enable_threshold = st.checkbox("启用达标检测")
        threshold_text = st.text_area("最低次数（关键字:次数）") if enable_threshold else ""
        split_array = st.checkbox("拆分数组")
        max_workers = st.slider("多线程数", 2, 16, 8)

    st.subheader("📤 上传JSON")
    uploaded_files = st.file_uploader("批量上传", type="json", accept_multiple_files=True)

    if uploaded_files and st.button("🚀 开始匹配", type="primary"):
        if not keyword_input:
            st.error("请输入关键词")
            return

        keyword_input_clean = keyword_input.strip().replace('，', ',')
        targets = [kw.strip() for kw in keyword_input_clean.split(",") if kw.strip()]
        threshold_dict = {}
        if enable_threshold and threshold_text:
            for line in threshold_text.split("\n"):
                line = line.strip().replace('：', ':')
                if ":" in line:
                    k, v = line.split(":", 1)
                    try:
                        threshold_dict[k.strip()] = int(v.strip())
                    except:
                        pass

        with st.spinner("多线程处理中..."):
            all_results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_single_json, f, targets, True, split_array): f
                    for f in uploaded_files
                }
                for future in as_completed(futures):
                    all_results.extend(future.result())

        success_results = [r for r in all_results if r["status"] == "success"]
        st.dataframe(success_results, use_container_width=True)
        st.success("✅ 多线程处理完成")
