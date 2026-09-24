"""Home: avvio rapido di una sessione."""
import streamlit as st

import db

conn = db.connetti()
st.title("Cruscotto")

for f in db.fronti(conn):
    c1, c2, c3 = st.columns([4, 1, 1])
    c1.markdown(f"**{f['nome']}**")
    if c2.button("90 min", key=f"a90_{f['id']}"):
        st.session_state["avvia"] = (f["id"], 90)
        st.switch_page("pages/sessione.py")
    if c3.button("10 min", key=f"a10_{f['id']}"):
        st.session_state["avvia"] = (f["id"], 10)
        st.switch_page("pages/sessione.py")
