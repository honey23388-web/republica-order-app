import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="REPUBLICA B2B 발주 시스템", page_icon="👓", layout="centered")

SHEET_ID = "1FiP0FFJI8OdswJa_p6ejkOpLZGbVZx9j71UUSJ6zLN4"

# ⚡ 캐시 시간을 1시간(3600초)으로 늘려 매번 구글 시트를 부르지 않고 속도를 대폭 향상시킵니다.
@st.cache_data(ttl=3600)
def load_data():
    try:
        model_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=model"
        color_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=color"
        client_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=client"
        
        df_models = pd.read_csv(model_url)
        df_colors = pd.read_csv(color_url)
        
        try:
            df_clients = pd.read_csv(client_url)
        except:
            df_clients = pd.DataFrame(columns=["거래처명", "적립잔액", "미수금", "특이사항", "미출고예약제품(수량)"])
            
        return df_models, df_colors, df_clients
    except Exception as e:
        return None, None, None

df_models, df_colors, df_clients = load_data()

# 사이드바에 수동 캐시 초기화(새로고침) 버튼 추가
st.sidebar.markdown("---")
if st.sidebar.button("🔄 최신 데이터 새로고침", use_container_width=True):
    st.cache_data.clear()
    st.success("캐시가 초기화되었습니다!")
    st.rerun()
