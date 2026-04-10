import streamlit as st
import os
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from utils import create_csv_in_memory

# 教材默认语音验收标准（完全匹配你上传的教材）
DEFAULT_SPEECH_STANDARDS = [
    {
        "id": "speech04_default",
        "audio_name": "speech04.mp3",
        "min_segments": 2,
        "max_silence_ratio": 10,
        "required_labels": ["碎裂声"],
        "description": "碎裂声事件检测标注"
    },
    {
        "id": "speech05_default",
        "audio_name": "speech05.mp3",
        "min_total_duration": 5,
        "max_other_sound_ratio": 10,
        "required_labels": ["安全警报"],
        "description": "安全警报声事件检测标注"
    },
    {
        "id": "speech06_default",
        "audio_name": "speech06.mp3",
        "min_segments_per_label": 2,
        "max_other_sound_ratio": 10,
        "required_labels": ["枪击声", "爆炸声", "叫喊声"],
        "description": "枪击/爆炸/叫喊声事件检测标注"
    },
    {
        "id": "speech07_default",
        "audio_name": "speech07.mp3",
        "min_segments_per_label": 2,
        "max_other_sound_ratio": 10,
        "required_labels": ["咳嗽声", "呼救声"],
        "description": "咳嗽/呼救声事件检测标注"
    }
]

# ------------------------------
# 安全初始化
# ------------------------------
def init_speech_standards():
    if "speech_acceptance_standards" not in st.session_state:
        st.session_state.speech_acceptance_standards = DEFAULT_SPEECH_STANDARDS.copy()

def delete_speech_standard(standard_id):
    new_list = []
    for s in st.session_state.speech_acceptance_standards:
        if s.get("id") != standard_id:
            new_list.append(s)
    st.session_state.speech_acceptance_standards = new_list
    st.rerun()

def add_new_speech_standard():
    new_id = str(uuid.uuid4())
    st.session_state.speech_acceptance_standards.append({
        "id": new_id,
        "audio_name": "",
        "min_segments": 1,
        "min_total_duration": 1,
        "min_segments_per_label": 1,
        "max_silence_ratio": 10,
        "max_other_sound_ratio": 10,
        "required_labels": "",
        "description": ""
    })
    st.rerun()

def reset_speech_to_default():
    st.session_state.speech_acceptance_standards = DEFAULT_SPEECH_STANDARDS.copy()
    st.rerun()

# ------------------------------
# 语音标注JSON解析
# ------------------------------
def parse_single_speech_annotation(item, file_name):
    try:
        # 从audio_url提取音频文件名
        audio_url = item.get("audio_url", "")
        audio_name = os.path.basename(audio_url) if audio_url else f"{file_name}_未知音频"
        
        # 解析segments数组（每个元素是一个标注片段）
        segments = item.get("segments", [])
        total_duration = item.get("duration", 0)
        
        # 统计各标签的片段数和总时长
        label_stats = {}
        total_enabled_duration = 0
        silence_duration = 0
        
        for seg in segments:
            if not seg.get("enabled", True):
                continue
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            seg_duration = end - start
            labels = seg.get("labels", [])
            
            for label in labels:
                if label not in label_stats:
                    label_stats[label] = {"count": 0, "duration": 0}
                label_stats[label]["count"] += 1
                label_stats[label]["duration"] += seg_duration
            
            total_enabled_duration += seg_duration
        
        # 计算无声时间比例
        silence_duration = max(0, total_duration - total_enabled_duration)
        silence_ratio = round((silence_duration / total_duration) * 100, 2) if total_duration > 0 else 0
        
        # 计算其他声音比例（非要求标签的声音占比）
        other_sound_duration = 0
        for label, stats in label_stats.items():
            if label not in ["碎裂声", "安全警报", "枪击声", "爆炸声", "叫喊声", "咳嗽声", "呼救声"]:
                other_sound_duration += stats["duration"]
        other_sound_ratio = round((other_sound_duration / total_enabled_duration) * 100, 2) if total_enabled_duration > 0 else 0

        return {
            "status": "success",
            "audio_name": audio_name,
            "json_file_name": file_name,
            "total_duration": round(total_duration, 2),
            "total_segments": len(segments),
            "label_stats": label_stats,
            "silence_ratio": silence_ratio,
            "other_sound_ratio": other_sound_ratio
        }
    except Exception:
        return {"status": "error", "file_name": file_name}

def parse_speech_annotation_json(file_obj):
    results = []
    try:
        file_obj.seek(0)
        json_data = json.load(file_obj)
        file_name = file_obj.name
        items = json_data if isinstance(json_data, list) else [json_data]
        for item in items:
            results.append(parse_single_speech_annotation(item, file_name))
        return results
    except json.JSONDecodeError:
        return [{"status": "invalid_json", "file_name": file_obj.name}]
    except Exception:
        return [{"status": "error", "file_name": file_obj.name}]

# ------------------------------
# 主页面
# ------------------------------
def speech_acceptance_page():
    st.title("🎙️ 语音标注自动验收工具")
    st.caption("完全匹配教材speech04~speech07验收标准，自动解析、自动验收")
    init_speech_standards()

    # --------------------------
    # 验收标准面板
    # --------------------------
    with st.expander("⚙️ 自定义验收标准", expanded=False):
        st.subheader("当前验收标准")
        for s in st.session_state.speech_acceptance_standards:
            cols = st.columns([2, 1, 1, 2, 0.5])
            with cols[0]:
                s["audio_name"] = st.text_input("音频名", value=s.get("audio_name", ""), key=f"a_{s['id']}")
            with cols[1]:
                s["description"] = st.text_input("标准描述", value=s.get("description", ""), key=f"desc_{s['id']}")
            with cols[2]:
                required = s.get("required_labels", [])
                if isinstance(required, list):
                    required = ",".join(required)
                s["required_labels"] = st.text_input("要求标签(逗号分隔)", value=required, key=f"lab_{s['id']}")
            with cols[3]:
                st.caption("参数配置")
                s["min_segments"] = st.number_input("最少片段数", min_value=1, value=s.get("min_segments", 1), key=f"seg_{s['id']}")
                s["min_total_duration"] = st.number_input("最少总时长(秒)", min_value=1, value=s.get("min_total_duration", 1), key=f"dur_{s['id']}")
                s["max_silence_ratio"] = st.number_input("最大无声比例(%)", min_value=0, max_value=100, value=s.get("max_silence_ratio", 10), key=f"sil_{s['id']}")
                s["max_other_sound_ratio"] = st.number_input("最大其他声音比例(%)", min_value=0, max_value=100, value=s.get("max_other_sound_ratio", 10), key=f"oth_{s['id']}")
            with cols[4]:
                st.button("🗑️", key=f"del_{s['id']}", on_click=delete_speech_standard, args=(s["id"],))

        c1, c2 = st.columns(2)
        with c1:
            st.button("➕ 添加新标准", use_container_width=True, on_click=add_new_speech_standard)
        with c2:
            st.button("🔄 恢复教材默认", use_container_width=True, on_click=reset_speech_to_default)

    # --------------------------
    # 上传 & 验收
    # --------------------------
    st.subheader("📤 上传JSON文件")
    uploaded_jsons = st.file_uploader(
        "选择语音标注JSON",
        type="json",
        accept_multiple_files=True,
        key="speech_uploader"
    )
    # 一键清空上传文件
    if st.button("🗑️ 清空所有上传文件", use_container_width=True):
        if "speech_uploader" in st.session_state:
            del st.session_state.speech_uploader
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

        # 构建标准字典（后缀匹配）
        standard_list = []
        for s in st.session_state.speech_acceptance_standards:
            an = s.get("audio_name", "").strip()
            if an:
                labels = s.get("required_labels", "")
                if isinstance(labels, str):
                    labels = [l.strip() for l in labels.split(",") if l.strip()]
                standard_list.append({
                    "audio_suffix": an,
                    "min_segments": s.get("min_segments", 1),
                    "min_total_duration": s.get("min_total_duration", 1),
                    "min_segments_per_label": s.get("min_segments_per_label", 1),
                    "max_silence_ratio": s.get("max_silence_ratio", 10),
                    "max_other_sound_ratio": s.get("max_other_sound_ratio", 10),
                    "required_labels": labels,
                    "description": s.get("description", "默认标准")
                })

        with st.spinner("解析中..."):
            all_parse_results = []
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {executor.submit(parse_speech_annotation_json, f): f for f in uploaded_jsons}
                for future in as_completed(futures):
                    all_parse_results.extend(future.result())

        success_parses = [r for r in all_parse_results if r.get("status") == "success"]
        if not success_parses:
            st.error("无有效标注文件！")
            return

        acceptance_results = []
        for res in success_parses:
            aname = res.get("audio_name", "")
            
            # 后缀模糊匹配
            matched_std = None
            for std in standard_list:
                if aname.endswith(std["audio_suffix"]):
                    matched_std = std
                    break
            
            if not matched_std:
                matched_std = {
                    "min_segments": 1,
                    "min_total_duration": 1,
                    "min_segments_per_label": 1,
                    "max_silence_ratio": 10,
                    "max_other_sound_ratio": 10,
                    "required_labels": [],
                    "description": "默认标准"
                }

            ok = True
            reason = []
            label_stats = res.get("label_stats", {})

            # 1. 检查总片段数
            if res.get("total_segments", 0) < matched_std["min_segments"]:
                ok = False
                reason.append(f"总片段数不足：实际{res.get('total_segments', 0)}个，要求≥{matched_std['min_segments']}个")

            # 2. 检查无声比例
            if res.get("silence_ratio", 0) > matched_std["max_silence_ratio"]:
                ok = False
                reason.append(f"无声比例过高：实际{res.get('silence_ratio', 0)}%，要求≤{matched_std['max_silence_ratio']}%")

            # 3. 检查其他声音比例
            if res.get("other_sound_ratio", 0) > matched_std["max_other_sound_ratio"]:
                ok = False
                reason.append(f"其他声音比例过高：实际{res.get('other_sound_ratio', 0)}%，要求≤{matched_std['max_other_sound_ratio']}%")

            # 4. 检查要求标签的片段数和总时长
            for label in matched_std["required_labels"]:
                stats = label_stats.get(label, {"count": 0, "duration": 0})
                if stats["count"] < matched_std["min_segments_per_label"]:
                    ok = False
                    reason.append(f"{label}片段数不足：实际{stats['count']}个，要求≥{matched_std['min_segments_per_label']}个")
                if stats["duration"] < matched_std["min_total_duration"]:
                    ok = False
                    reason.append(f"{label}总时长不足：实际{stats['duration']}秒，要求≥{matched_std['min_total_duration']}秒")

            # 生成标签统计字符串
            label_str = "；".join([f"{k}:{v['count']}个({v['duration']}秒)" for k, v in label_stats.items()])

            acceptance_results.append({
                "音频文件名": aname,
                "来源JSON": res.get("json_file_name", ""),
                "总时长(秒)": res.get("total_duration", 0),
                "总片段数": res.get("total_segments", 0),
                "标签统计": label_str,
                "无声比例(%)": res.get("silence_ratio", 0),
                "其他声音比例(%)": res.get("other_sound_ratio", 0),
                "验收标准": matched_std["description"],
                "结果": "✅ 合格" if ok else "❌ 不合格",
                "原因": "；".join(reason) if reason else "-"
            })

        total = len(acceptance_results)
        ok_cnt = len([x for x in acceptance_results if x["结果"] == "✅ 合格"])

        st.divider()
        st.subheader("📊 验收结果")
        cols = st.columns(4)
        cols[0].metric("总音频数", total)
        cols[1].metric("合格", ok_cnt)
        cols[2].metric("不合格", total - ok_cnt)
        cols[3].metric("合格率", f"{ok_cnt/total*100:.1f}%" if total>0 else 0)

        st.dataframe(acceptance_results, use_container_width=True, height=400)

        # 导出
        st.divider()
        st.subheader("📥 导出报告")
        rows = [["语音标注验收报告"],["验收员", inspector],["时间", inspection_time.strftime("%Y-%m-%d")],[]]
        if acceptance_results:
            rows.append(list(acceptance_results[0].keys()))
            for item in acceptance_results:
                rows.append([str(item[k]) for k in item.keys()])
        
        csv_file = create_csv_in_memory(None, rows)
        st.download_button("📄 下载报告", csv_file, f"语音标注验收报告_{inspection_time.strftime('%Y%m%d')}.csv", use_container_width=True)
        st.success("✅ 验收完成！")
