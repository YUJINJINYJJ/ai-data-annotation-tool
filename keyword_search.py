# 解析阈值
threshold_dict = {}
if enable_threshold and threshold_text.strip():
    for line in threshold_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # ✅ 自动将中文冒号转换为英文冒号
        line = line.replace('：', ':')
        if ":" not in line:
            st.warning(f"⚠️ 阈值格式错误：{line}，已跳过")
            continue
        kw, cnt = line.split(":", 1)
        kw = kw.strip()
        try:
            threshold_dict[kw] = int(cnt.strip())
        except ValueError:
            st.warning(f"⚠️ 阈值必须为数字：{line}，已跳过")
