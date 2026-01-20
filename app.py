# app.py
from __future__ import annotations

import pandas as pd
import streamlit as st

from auth import admin_login_ui, is_admin
from storage import (
    load_db,
    clear_db,
    delete_match,
    delete_last_n,
    export_csv_bytes,
)
from ui_record import record_page
from ui_live import live_page

st.set_page_config(page_title="点球大战 Penalty AI", layout="wide")


def _match_summary(df_match: pd.DataFrame) -> dict:
    df_match = df_match.sort_values("kick_index")
    me_goals = int(df_match.loc[df_match["who_kicked"] == "ME", "is_goal"].sum())
    opp_goals = int(df_match.loc[df_match["who_kicked"] == "OPP", "is_goal"].sum())
    me_k = int((df_match["who_kicked"] == "ME").sum())
    opp_k = int((df_match["who_kicked"] == "OPP").sum())
    order_mode = df_match["order_mode"].iloc[0] if len(df_match) else ""
    return {
        "match_id": df_match["match_id"].iloc[0] if len(df_match) else "",
        "score": f"{me_goals}-{opp_goals}",
        "kicks": f"{me_k}/{opp_k}",
        "order_mode": order_mode,
        "rows": len(df_match),
    }


def db_page(me_name: str, opp_name: str):
    st.subheader("数据库（按比赛汇总展示，可展开查看每脚）")

    df = load_db()

    m1, m2, m3 = st.columns([1.2, 1.2, 2.6])
    m1.metric("累计记录（脚）", int(len(df)))
    m2.metric("累计比赛（场）", int(df["match_id"].nunique()) if len(df) else 0)
    m3.metric("权限", "管理员 ✅" if is_admin() else "普通用户")

    # Admin-only download full DB
    if is_admin():
        st.download_button(
            "下载全库 CSV（管理员）",
            data=export_csv_bytes(admin_only=True),
            file_name="penalties.csv",
            mime="text/csv",
            key="db_download_admin",
        )
    else:
        st.info("普通用户可以查看与使用功能，但不能下载/删除/清空数据库。")

    st.divider()

    if len(df) == 0:
        st.info("数据库为空。")
        return

    # match list
    st.write("比赛列表（点击展开查看每脚明细）：")
    for mid, g in df.groupby("match_id"):
        info = _match_summary(g)
        title = (
            f"match_id={info['match_id']} | 比分({me_name}-{opp_name})={info['score']} | "
            f"脚数(我/对手)={info['kicks']} | 先后手={('我先发' if info['order_mode']=='ME_FIRST' else '我后发')} | 记录行={info['rows']}"
        )
        with st.expander(title, expanded=False):
            gg = g.sort_values("kick_index").copy()
            st.dataframe(gg, use_container_width=True)

            if is_admin():
                c1, c2 = st.columns([1, 3])
                with c1:
                    if st.button(f"删除该场 {mid}", type="primary", key=f"db_del_{mid}"):
                        delete_match(mid)
                        st.success(f"已删除 match_id={mid}")
                        st.rerun()
                with c2:
                    st.caption("删除后不可恢复。")
            else:
                st.caption("普通用户无删除权限。")

    st.divider()

    if is_admin():
        st.subheader("管理员：删减/清空")
        st.write("删除最后 N 脚（按追加顺序）：")
        n = st.number_input("N", min_value=1, value=10, step=1, key="db_last_n")
        if st.button("删除最后 N 脚", key="db_del_last_n"):
            delete_last_n(int(n))
            st.success(f"已删除最后 {int(n)} 脚")
            st.rerun()

        st.divider()
        st.write("危险：清空数据库（不可恢复）")
        if st.button("清空数据库", key="db_clear", type="primary"):
            clear_db()
            st.success("数据库已清空")
            st.rerun()


def main():
    st.title("⚽ 点球大战 Penalty AI（在线版：管理员权限控制）")

    # --- Sidebar config ---
    st.sidebar.header("配置")
    me_name = st.sidebar.text_input("我方名称", value="ME", key="sb_me")
    opp_name = st.sidebar.text_input("对手名称", value="OPP", key="sb_opp")

    order_mode = st.sidebar.radio(
        "先后手",
        ["ME_FIRST", "OPP_FIRST"],
        format_func=lambda x: "我先发" if x == "ME_FIRST" else "我后发",
        key="sb_order",
    )

    alpha = st.sidebar.slider("平滑 alpha", 0.0, 5.0, 1.0, 0.1, key="sb_alpha")
    k = st.sidebar.slider("序列阶数 K", 0, 4, 2, 1, key="sb_k")
    match_weight = st.sidebar.slider("本场权重", 0.0, 10.0, 2.0, 0.5, key="sb_mw")

    # --- Admin gate (sidebar) ---
    admin_login_ui()

    # quick stats
    df = load_db()
    st.sidebar.caption(f"数据库：{len(df)} 脚 / {df['match_id'].nunique() if len(df) else 0} 场")

    tab_live, tab_record, tab_db = st.tabs(["实时模式", "录入数据（按整场）", "数据库（按比赛）"])

    with tab_live:
        live_page(
            me_name=me_name,
            opp_name=opp_name,
            alpha=alpha,
            k=k,
            match_weight=match_weight,
            order_mode=order_mode,
        )

    with tab_record:
        record_page(me_name=me_name, opp_name=opp_name)

    with tab_db:
        db_page(me_name=me_name, opp_name=opp_name)


if __name__ == "__main__":
    main()
