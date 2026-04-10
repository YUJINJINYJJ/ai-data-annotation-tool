import streamlit as st
import os
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from utils import create_csv_in_memory

# 教材默认语音验收标准（完全匹配教材5.3.4要求）
DEFAULT_SPEECH_STANDARDS = [
    {
        "id": "speech04_default",
        "audio_name": "speech04.mp3",
        "min_segments": 2,
        "max_silence_ratio_in_segment": 10,
        "required_labels": ["碎裂声"],
        "description": "speech04.mp3 碎裂声事件检测标注"
    },
    {
        "id": "speech05_default",
        "audio_name": "speech05.mp3",
        "min_total_duration": 5,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": ["安全警报"],
        "description": "speech05.mp3 安全警报声事件检测标注"
    },
    {
        "id": "speech06_default",
        "audio_name": "speech06.mp3",
        "min_segments_per_label": 2,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": ["枪击声", "爆炸声", "叫喊声"],
        "description": "speech06.mp3 枪击/爆炸/叫喊声事件检测标注"
    },
    {
        "id": "speech07_default",
        "audio_name": "speech07.mp3",
        "min_segments_per_label": 2,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": ["咳嗽声", "呼救声"],
        "description": "speech07.mp3 咳嗽/呼救声事件检测标注"
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
        "max_silence_ratio_in_segment": 10,
        "max_other_sound_ratio_in_segment": 10,
        "required_labels": "",
        "description": ""
    })
    st.rerun()

def reset_speech_to_default():
    st.session_state.speech_acceptance_standards = DEFAULT_SPEECH_STANDARDS.copy()
    st.rerun()

# ------------------------------
# 语音标注JSON解析（修正后逻辑）
# ------------------------------
def parse_single_speech_annotation(item, file_name):
    try:
        # 从audio_url提取音频文件名
        audio_url = item.get("audio_url", "")
        audio_name = os.path.basename(audio_url) if audio_url else f"{file_name}_未知音频"
        
        # 解析segments数组（每个元素是一个标注片段）
        segments = item.get("segments", [])
        total_duration = item.get("duration", 0)
        
        # 统计各标签的片段数、总时长、片段内无声/其他声音比例
        label_stats = {}
        total_segments = len(segments)
        all_segment_silence_ratios = []
        all_segment_other_ratios = []

        for seg in segments:
            if not seg.get("enabled", True):
                continue
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            seg_total_duration = end - start
            if seg_total_duration <= 0:
                continue
            
            labels = seg.get("labels", [])
            # 计算片段内的无声时长（标注为无标签的部分，这里简化为：如果标签为空则为无声）
            # 实际标注中，无声片段不会打标签，所以有标签的片段内无声比例为0
            seg_silence_duration = 0 if labels else seg_total_duration
            seg_silence_ratio = round((seg_silence_duration / seg_total_duration) * 100, 2) if seg_total_duration > 0 else 0
            all_segment_silence_ratios.append(seg_silence_ratio)

            # 计算片段内的其他声音比例（非要求标签的声音）
            seg_other_duration = 0
            # 假设标注的标签是目标声音，非目标标签为其他声音
            # 实际使用中，会根据标准的required_labels过滤，这里先统计所有非目标标签的时长
            for label in labels:
                if label not in ["碎裂声", "安全警报", "枪击声", "爆炸声", "叫喊声", "咳嗽声", "呼救声"]:
                    seg_other_duration += seg_total_duration / len(labels) if labels else 0
            seg_other_ratio = round((seg_other_duration / seg_total_duration) * 100, 2) if seg_total_duration > 0 else 0
            all_segment_other_ratios.append(seg_other_ratio)

            # 更新标签统计
            for label in labels:
                if label not in label_stats:
                    label_stats[label] = {
                        "count": 0,
                        "total_duration": 0,
                        "max_silence_ratio": 0,
                        "max_other_ratio": 0
                    }
                label_stats[label]["count"] += 1
                label_stats[label]["total_duration"] += seg_total_duration
                label_stats[label]["max_silence_ratio"] = max(label_stats[label]["max_silence_ratio"], seg_silence_ratio)
                label_stats[label]["max_other_ratio"] = max(label_stats[label]["max_other_ratio"], seg_other_ratio)

        # 计算全局统计
        avg_silence_ratio = round(sum(all_segment_silence_ratios) / len(all_segment_silence_ratios), 2) if all_segment_silence_ratios else 0
        avg_other_ratio = round(sum(all_segment_other_ratios) / len(all_segment_other_ratios), 2) if all_segment_other_ratios else 0
        max_silence_ratio = max(all_segment_silence_ratios) if all_segment_silence_ratios else 0
        max_other_ratio = max(all_segment_other_ratios) if all_segment_other_ratios else 0

        return {
            "status": "success",
            "audio_name": audio_name,
            "json_file_name": file_name,
            "total_duration": round(total_duration, 2),
            "total_segments": total_segments,
            "label_stats": label_stats,
            "avg_silence_ratio": avg_silence_ratio,
            "max_silence_ratio": max_silence_ratio,
            "avg_other_ratio": avg_other_ratio,
            "max_other_ratio": max_other_ratio
        }
    except Exception as e:
        return {"status": "error", "file_name": file_name, "error": str(e)}

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
    except Exception as e:
        return [{"status": "error", "file_name": file_obj.name, "error": str(e)}]

# ------------------------------
# 主页面
# ------------------------------
def speech_acceptance_page():
    st.title("🎙️ 语音标注自动验收工具")

    init_speech_standards()

    # --------------------------
    # 验收标准面板
    # --------------------------
    with st.expander("⚙️ 自定义验收标准", expanded=False):
        st.subheader("当前验收标准（完全匹配教材5.3.4）")
        for s in st.session_state.speech_acceptance_standards:
            cols = st.columns([2, 1.5, 1.5, 2, 0.5])
            with cols[0]:
                s["audio_name"] = st.text_input("音频名", value=s.get("audio_name", ""), key=f"a_{s['id']}")
                s["description"] = st.text_input("标准描述", value=s.get("description", ""), key=f"desc_{s['id']}")
            with cols[1]:
                required = s.get("required_labels", [])
                if isinstance(required, list):
                    required = ",".join(required)
                s["required_labels"] = st.text_input("要求标签(逗号分隔)", value=required, key=f"lab_{s['id']}")
            with cols[2]:
                s["min_segments"] = st.number_input("最少总片段数", min_value=1, value=s.get("min_segments", 1), key=f"seg_{s['id']}")
                s["min_total_duration"] = st.number_input("最少总时长(秒)", min_value=1, value=s.get("min_total_duration", 1), key=f"dur_{s['id']}")
                s["min_segments_per_label"] = st.number_input("每标签最少片段数", min_value=1, value=s.get("min_segments_per_label", 1), key=f"seg_lab_{s['id']}")
            with cols[3]:
                s["max_silence_ratio_in_segment"] = st.number_input("片段内最大无声比例(%)", min_value=0, max_value=100, value=s.get("max_silence_ratio_in_segment", 10), key=f"sil_{s['id']}")
                s["max_other_sound_ratio_in_segment"] = st.number_input("片段内最大其他声音比例(%)", min_value=0, max_value=100, value=s.get("max_other_sound_ratio_in_segment", 10), key=f"oth_{s['id']}")
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
                    "max_silence_ratio": s.get("max_silence_ratio_in_segment", 10),
                    "max_other_ratio": s.get("max_other_sound_ratio_in_segment", 10),
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
                    "max_other_ratio": 10,
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

            # 2. 检查片段内最大无声比例（所有标注片段中，无声比例最高的那个不能超标）
            if res.get("max_silence_ratio", 0) > matched_std["max_silence_ratio"]:
                ok = False
                reason.append(f"片段内无声比例过高：最高{res.get('max_silence_ratio', 0)}%，要求≤{matched_std['max_silence_ratio']}%")

            # 3. 检查片段内最大其他声音比例
            if res.get("max_other_ratio", 0) > matched_std["max_other_ratio"]:
                ok = False
                reason.append(f"片段内其他声音比例过高：最高{res.get('max_other_ratio', 0)}%，要求≤{matched_std['max_other_ratio']}%")

            # 4. 检查要求标签的片段数和总时长
            for label in matched_std["required_labels"]:
                stats = label_stats.get(label, {"count": 0, "total_duration": 0, "max_silence_ratio": 0, "max_other_ratio": 0})
                # 检查每标签最少片段数
                if stats["count"] < matched_std["min_segments_per_label"]:
                    ok = False
                    reason.append(f"{label}片段数不足：实际{stats['count']}个，要求≥{matched_std['min_segments_per_label']}个")
                # 检查标签总时长
                if stats["total_duration"] < matched_std["min_total_duration"]:
                    ok = False
                    reason.append(f"{label}总时长不足：实际{stats['total_duration']}秒，要求≥{matched_std['min_total_duration']}秒")
                # 检查标签对应片段的无声/其他比例
                if stats["max_silence_ratio"] > matched_std["max_silence_ratio"]:
                    ok = False
                    reason.append(f"{label}片段无声比例过高：{stats['max_silence_ratio']}%，要求≤{matched_std['max_silence_ratio']}%")
                if stats["max_other_ratio"] > matched_std["max_other_ratio"]:
                    ok = False
                    reason.append(f"{label}片段其他声音比例过高：{stats['max_other_ratio']}%，要求≤{matched_std['max_other_ratio']}%")

            # 生成标签统计字符串
            label_str = "；".join([
                f"{k}:{v['count']}个({v['total_duration']}秒，无声最高{v['max_silence_ratio']}%)" 
                for k, v in label_stats.items()
            ])

            acceptance_results.append({
                "音频文件名": aname,
                "来源JSON": res.get("json_file_name", ""),
                "总时长(秒)": res.get("total_duration", 0),
                "总片段数": res.get("total_segments", 0),
                "标签统计": label_str,
                "片段内最高无声比例(%)": res.get("max_silence_ratio", 0),
                "片段内最高其他声音比例(%)": res.get("max_other_ratio", 0),
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
