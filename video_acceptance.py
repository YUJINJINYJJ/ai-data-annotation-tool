import streamlit as st
import os
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from utils import create_csv_in_memory

# 教材默认验收标准
DEFAULT_ACCEPTANCE_STANDARDS = [
    {
        "id": "vot01_default",
        "video_name": "VOT01.mp4",
        "min_frames": 200,
        "min_targets": 1,
        "description": "猎豹视频跨帧追踪标注"
    },
    {
        "id": "vot02_default",
        "video_name": "VOT02.mp4",
        "min_frames": 200,
        "min_targets": 2,
        "description": "电动自行车视频跨帧追踪标注"
    },
    {
        "id": "vot03_default",
        "video_name": "VOT03.mp4",
        "min_frames": 200,
        "min_targets": 1,
        "description": "神舟十四号飞船视频跨帧追踪标注"
    }
]

# ------------------------------
# 安全初始化
# ------------------------------
def init_standards():
    if "acceptance_standards" not in st.session_state:
        st.session_state.acceptance_standards = DEFAULT_ACCEPTANCE_STANDARDS.copy()

def delete_standard(standard_id):
    new_list = []
    for s in st.session_state.acceptance_standards:
        if s.get("id") != standard_id:
            new_list.append(s)
    st.session_state.acceptance_standards = new_list
    st.rerun()

def add_new_standard():
    new_id = str(uuid.uuid4())
    st.session_state.acceptance_standards.append({
        "id": new_id,
        "video_name": "",
        "min_frames": 200,
        "min_targets": 1,
        "description": ""
    })
    st.rerun()

def reset_to_default():
    st.session_state.acceptance_standards = DEFAULT_ACCEPTANCE_STANDARDS.copy()
    st.rerun()

# ------------------------------
# JSON 解析
# ------------------------------
def parse_single_video_annotation(item, file_name):
    try:
        video_url = item.get("video_url", "")
        video_name = os.path.basename(video_url) if video_url else f"{file_name}_未知视频"
        box_list = item.get("box", [])
        total_targets = len(box_list)
        all_enabled_frames = []
        all_labels = []

        for box in box_list:
            sequence = box.get("sequence", [])
            enabled_count = sum(1 for frame in sequence if frame.get("enabled", True))
            all_enabled_frames.append(enabled_count)
            labels = box.get("labels", [])
            all_labels.extend(labels)

        max_enabled_frames = max(all_enabled_frames) if all_enabled_frames else 0
        total_frames = box_list[0].get("framesCount", 0) if box_list else 0
        duration = round(box_list[0].get("duration", 0), 2) if box_list else 0

        return {
            "status": "success",
            "video_name": video_name,
            "json_file_name": file_name,
            "total_frames": total_frames,
            "duration": duration,
            "total_targets": total_targets,
            "max_enabled_frames": max_enabled_frames,
            "labels": list(set(all_labels))
        }
    except Exception:
        return {"status": "error", "file_name": file_name}

def parse_video_annotation_json(file_obj):
    results = []
    try:
        file_obj.seek(0)
        json_data = json.load(file_obj)
        file_name = file_obj.name
        items = json_data if isinstance(json_data, list) else [json_data]
        for item in items:
            results.append(parse_single_video_annotation(item, file_name))
        return results
    except json.JSONDecodeError:
        return [{"status": "invalid_json", "file_name": file_obj.name}]
    except Exception:
        return [{"status": "error", "file_name": file_obj.name}]

# ------------------------------
# 主页面
# ------------------------------
def video_acceptance_page():
    st.title("✅ 视频标注自动验收工具")
    st.caption("支持带前缀视频名匹配，修改参数实时生效")
    init_standards()

    # 左侧边栏配置
    with st.sidebar:
        st.header("⚙️ 处理配置")
        max_workers = st.slider("⚡ 并行处理线程数", 2, 16, 8)
        st.divider()
        st.caption("💡 支持批量上传JSON文件")

    # --------------------------
    # 验收标准面板
    # --------------------------
    with st.expander("⚙️ 自定义验收标准", expanded=False):
        st.subheader("当前验收标准")
        for s in st.session_state.acceptance_standards:
            cols = st.columns([2, 1, 1, 2, 0.5])
            with cols[0]:
                s["video_name"] = st.text_input("视频名", value=s.get("video_name", ""), key=f"v_{s['id']}")
            with cols[1]:
                s["min_frames"] = st.number_input("最低帧数", min_value=1, value=s.get("min_frames", 200), key=f"f_{s['id']}")
            with cols[2]:
                s["min_targets"] = st.number_input("最低目标数", min_value=1, value=s.get("min_targets", 1), key=f"t_{s['id']}")
            with cols[3]:
                s["description"] = st.text_input("描述", value=s.get("description", ""), key=f"d_{s['id']}")
            with cols[4]:
                st.button("🗑️", key=f"del_{s['id']}", on_click=delete_standard, args=(s["id"],))

        c1, c2 = st.columns(2)
        with c1:
            st.button("➕ 添加新标准", use_container_width=True, on_click=add_new_standard)
        with c2:
            st.button("🔄 恢复默认", use_container_width=True, on_click=reset_to_default)

    # --------------------------
    # 上传 & 验收
    # --------------------------
    st.subheader("📤 上传JSON文件")
    uploaded_jsons = st.file_uploader(
        "选择JSON",
        type="json",
        accept_multiple_files=True,
        key="video_uploader"
    )
    # 一键清空上传文件
    if st.button("🗑️ 清空所有上传文件", use_container_width=True):
        if "video_uploader" in st.session_state:
            del st.session_state.video_uploader
        st.rerun()

    st.subheader("📝 验收信息")
    col1, col2 = st.columns(2)
    with col1:
        inspector = st.text_input("验收员")
    with col2:
        inspection_time = st.date_input("验收时间", value=datetime.now())

    if uploaded_jsons and st.button("🚀 开始自动验收", type="primary", use_container_width=True):
        if not inspector:
            st.error("请输入验收员！")
            st.stop()

        # 构建标准字典（用于后缀匹配）
        standard_list = []
        for s in st.session_state.acceptance_standards:
            vn = s.get("video_name", "").strip()
            if vn:
                standard_list.append({
                    "video_suffix": vn,
                    "min_frames": s.get("min_frames", 200),
                    "min_targets": s.get("min_targets", 1),
                    "description": s.get("description", "默认标准")
                })

        with st.spinner("解析中..."):
            all_parse_results = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(parse_video_annotation_json, f): f for f in uploaded_jsons}
                for future in as_completed(futures):
                    all_parse_results.extend(future.result())

        success_parses = [r for r in all_parse_results if r.get("status") == "success"]
        if not success_parses:
            st.error("无有效标注文件！")
            return

        acceptance_results = []
        for res in success_parses:
            vname = res.get("video_name", "")
            
            # 后缀模糊匹配：只要实际视频名以标准视频名结尾就匹配
            matched_std = None
            for std in standard_list:
                if vname.endswith(std["video_suffix"]):
                    matched_std = std
                    break
            
            # 没匹配到用默认
            if not matched_std:
                matched_std = {"min_frames":200, "min_targets":1, "description":"默认标准"}

            ok = True
            reason = []

            if res.get("max_enabled_frames", 0) < matched_std["min_frames"]:
                ok = False
                reason.append(f"帧数不足：实际{res.get('max_enabled_frames', 0)}帧，要求≥{matched_std['min_frames']}帧")
            if res.get("total_targets", 0) < matched_std["min_targets"]:
                ok = False
                reason.append(f"目标数不足：实际{res.get('total_targets', 0)}个，要求≥{matched_std['min_targets']}个")

            acceptance_results.append({
                "视频文件名": vname,
                "来源JSON": res.get("json_file_name", ""),
                "总帧数": res.get("total_frames", 0),
                "时长(秒)": res.get("duration", 0),
                "目标数": res.get("total_targets", 0),
                "最大有效帧数": res.get("max_enabled_frames", 0),
                "标签": "、".join(res.get("labels", [])),
                "验收标准": matched_std["description"],
                "结果": "✅ 合格" if ok else "❌ 不合格",
                "原因": "；".join(reason) if reason else "-"
            })

        total = len(acceptance_results)
        ok_cnt = len([x for x in acceptance_results if x["结果"] == "✅ 合格"])

        st.divider()
        st.subheader("📊 验收结果")
        cols = st.columns(4)
        cols[0].metric("总视频数", total)
        cols[1].metric("合格", ok_cnt)
        cols[2].metric("不合格", total - ok_cnt)
        cols[3].metric("合格率", f"{ok_cnt/total*100:.1f}%" if total>0 else 0)

        st.dataframe(acceptance_results, use_container_width=True, height=400)

        # 导出
        st.divider()
        st.subheader("📥 导出报告")
        rows = [["视频标注验收报告"],["验收员", inspector],["时间", inspection_time.strftime("%Y-%m-%d")],[]]
        if acceptance_results:
            rows.append(list(acceptance_results[0].keys()))
            for item in acceptance_results:
                rows.append([str(item[k]) for k in item.keys()])
        
        csv_file = create_csv_in_memory(None, rows)
        st.download_button("📄 下载报告", csv_file, f"验收报告_{inspection_time.strftime('%Y%m%d')}.csv", use_container_width=True)
        st.success("✅ 验收完成！")
