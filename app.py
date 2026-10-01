import streamlit as st
import pandas as pd
import datetime
import requests
import json
import streamlit.components.v1 as components

st.set_page_config(page_title="REPUBLICA B2B 발주 시스템", page_icon="👓", layout="centered")

SHEET_ID = "1FiP0FFJI8OdswJa_p6ejkOpLZGbVZx9j71UUSJ6zLN4"
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyBmjN8f2UkUbL3TrRK7zvkESJ2g-ZUqquHwPPDatrieBcpUMOAXiQXjJv3rHf5JjaG-Q/exec"

# 🌟 이카운트 ERP API 연동 정보 세팅
ECOUNT_COM_CODE = st.secrets["ECOUNT_COM_CODE"]
ECOUNT_USER_ID = st.secrets["ECOUNT_USER_ID"]
ECOUNT_API_KEY = st.secrets["ECOUNT_API_KEY"]
ECOUNT_WH_CD = st.secrets.get("ECOUNT_WH_CD", "00009")

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
            df_clients = pd.DataFrame(columns=["거래처명", "적립잔액", "미수금", "특이사항", "미출고예약제품(수량)", "매장코드"])
            
        return df_models, df_colors, df_clients
    except Exception as e:
        return None, None, None

# 🌟 이카운트 ERP '판매주문서 입력' 전송 함수 (URL 경로 정돈 및 매장코드/품목코드 매핑 반영)
def send_order_to_ecount(cart_items, client_name, memo, df_colors, df_clients):
    try:
        # 1) 회사의 ECOUNT Zone 조회
        zone_res = requests.post(
            "https://sboapi.ecount.com/ECERP/OAPI/V2/Zone",
            json={"COM_CODE": ECOUNT_COM_CODE},
            timeout=10
        )
        zone_res.raise_for_status()
        zone_data = zone_res.json()
        zone_info = zone_data.get("Data") or {}

        zone = (
            zone_info.get("ZONE")
            or zone_info.get("Zone")
            or zone_info.get("zone")
        )
        if not zone:
            st.error(f"❌ 이카운트 Zone 조회 실패: {zone_data}")
            return False

        zone = str(zone).upper()

        # 2) 로그인하여 SESSION_ID 발급
        login_url = f"https://sboapi{zone.lower()}.ecount.com/OAPI/V2/OAPILogin"
        login_res = requests.post(
            login_url,
            json={
                "COM_CODE": ECOUNT_COM_CODE,
                "USER_ID": ECOUNT_USER_ID,
                "API_CERT_KEY": ECOUNT_API_KEY,
                "ZONE": zone,
                "LAN_TYPE": "ko-KR"
            },
            timeout=10
        )
        login_res.raise_for_status()
        login_data = login_res.json()

        login_block = login_data.get("Data") or {}
        datas_block = login_block.get("Datas") or {}
        session_id = (
            datas_block.get("SESSION_ID")
            or login_block.get("SESSION_ID")
            or login_block.get("Session_Id")
        )

        if not session_id:
            st.error(f"❌ 이카운트 로그인 실패: {login_data}")
            return False

        # 3) 선택한 거래처명을 ECOUNT 거래처코드로 변환
        cust_cd = ""
        clean_target = str(client_name).replace("[신규]", "").strip().upper()

        if df_clients is not None and not df_clients.empty:
            for _, r in df_clients.iterrows():
                sheet_c_name = str(r.iloc[0]).strip().upper()
