# auth.py
from __future__ import annotations
import hmac
import streamlit as st


def _consteq(a: str, b: str) -> bool:
    if a is None or b is None:
        return False
    return hmac.compare_digest(str(a), str(b))


def is_admin() -> bool:
    return bool(st.session_state.get("is_admin", False))


def admin_login_ui():
    """
    Sidebar login gate. Sets st.session_state['is_admin'].
    """
    st.sidebar.subheader("🔐 管理员")
    # Already admin
    if is_admin():
        st.sidebar.success("已解锁管理员权限")
        if st.sidebar.button("退出管理员", key="admin_logout"):
            st.session_state["is_admin"] = False
            try:
                st.rerun()
            except Exception:
                pass
        return

    # Not admin yet
    pwd = st.sidebar.text_input("管理员密码", type="password", key="admin_pwd")
    if st.sidebar.button("解锁", key="admin_unlock"):
        real = st.secrets.get("ADMIN_PASSWORD", "")
        if _consteq(pwd, real) and real != "":
            st.session_state["is_admin"] = True
            st.sidebar.success("管理员权限已开启")
            try:
                st.rerun()
            except Exception:
                pass
        else:
            st.sidebar.error("密码错误")


def require_admin():
    """
    Call inside dangerous operations to ensure admin.
    """
    if not is_admin():
        raise PermissionError("Admin permission required.")
