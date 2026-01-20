# utils.py
from __future__ import annotations
import streamlit as st

DIRS = ["L", "C", "R"]

def safe_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def stage_from_kick_index(kick_index: int) -> str:
    # 1-10 脚（前5轮*2）视为 REG，之后 SD
    return "REG" if kick_index <= 10 else "SD"

def round_stage_from_kick_index(kick_index: int) -> str:
    # 压缩为 EARLY/MID/LATE（给模型用）
    # EARLY: 前2轮(1-4脚) MID: 3-4轮(5-8脚) LATE: 第5轮及以后(9+)
    if kick_index <= 4:
        return "EARLY"
    if kick_index <= 8:
        return "MID"
    return "LATE"

def kicker_for_kick_index(order_mode: str, kick_index: int) -> str:
    # order_mode: ME_FIRST / OPP_FIRST
    # kick_index 从 1 开始
    if order_mode == "ME_FIRST":
        return "ME" if kick_index % 2 == 1 else "OPP"
    else:
        return "OPP" if kick_index % 2 == 1 else "ME"

def round_number_from_kick_index(kick_index: int) -> int:
    # 1-2脚为第1轮，3-4脚为第2轮...
    return (kick_index + 1) // 2

def _inject_dir_button_css():
    st.markdown(
        """
<style>
/* 大号方向按钮 */
div.stButton > button[kind="secondary"]{
  font-size: 34px !important;
  height: 78px !important;
  width: 100% !important;
  border-radius: 14px !important;
  font-weight: 800 !important;
}
/* 选中态（用我们额外渲染的提示条来体现） */
.dir-selected {
  padding: 10px 14px;
  border-radius: 12px;
  font-weight: 700;
  font-size: 16px;
  background: rgba(0,0,0,0.06);
}
</style>
        """,
        unsafe_allow_html=True,
    )

def dir_pick_3buttons(label: str, key: str, default: str | None = None) -> str:
    """
    三个大按钮：⬅️ ⬆️ ➡️ 对应 L/C/R
    返回当前选择（L/C/R）
    """
    _inject_dir_button_css()

    state_key = f"{key}__val"
    if state_key not in st.session_state:
        st.session_state[state_key] = default if default in DIRS else None

    st.caption(label)
    c1, c2, c3 = st.columns(3)
    if c1.button("⬅️", key=f"{key}_L", type="secondary"):
        st.session_state[state_key] = "L"
        safe_rerun()
    if c2.button("⬆️", key=f"{key}_C", type="secondary"):
        st.session_state[state_key] = "C"
        safe_rerun()
    if c3.button("➡️", key=f"{key}_R", type="secondary"):
        st.session_state[state_key] = "R"
        safe_rerun()

    cur = st.session_state[state_key]
    show = cur if cur else "（未选择）"
    st.markdown(f'<div class="dir-selected">当前选择： <b>{show}</b></div>', unsafe_allow_html=True)
    return cur
