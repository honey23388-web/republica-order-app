import streamlit as st
import pandas as pd
import datetime
import requests
import json
import hashlib
import streamlit.components.v1 as components

st.set_page_config(page_title="REPUBLICA B2B 발주 시스템", page_icon="👓", layout="centered")

# ============================================================
# 사용자 로그인
# 비밀번호는 Streamlit Secrets의 [APP_USERS]에 저장합니다.
# ECOUNT 마스터 인증정보는 기존 Secrets에 그대로 유지되며 사용자에게 노출하지 않습니다.
# ============================================================

# ============================================================
# ECOUNT 규격 컬러코드 -> 앱 표시용 한국어 컬러명
# ECOUNT의 SIZE_DES(예: C02 - BROWN)를 원본으로 사용하고,
# 한국어명만 앱 내부에서 보완합니다.
# ============================================================
COLOR_KR = {
    "C01": "블랙",
    "C01M": "매트블랙",
    "C02": "브라운",
    "C03": "골드",
    "C03M": "너겟골드",
    "C04": "건메탈",
    "C04M": "매트건메탈",
    "C05": "크롬실버",
    "C05M": "매트실버",
    "C06": "로즈골드",
}

def _parse_ecount_spec(size_des):
    text = str(size_des or "").strip()
    if not text:
        return "", ""
    if " - " in text:
        code, eng = text.split(" - ", 1)
    elif "-" in text:
        code, eng = text.split("-", 1)
    else:
        code, eng = text, ""
    code = code.strip().upper()
    eng = eng.strip().upper()
    kr = COLOR_KR.get(code, "")
    display = f"{eng} / {kr}" if eng and kr else (kr or eng)
    return code, display

APP_USER_PROFILES = {
    "teon":     {"name": "김태헌", "emp_cd": "00001"},
    "jinheeus": {"name": "김진희", "emp_cd": "00002"},
    "funtime":  {"name": "김현우", "emp_cd": "00003"},
    "hjsim":    {"name": "심현종", "emp_cd": "00005"},
}

def _password_matches(entered_password, stored_value):
    """평문 Secrets도 지원하고 sha256:... 형식도 지원합니다."""
    entered_password = str(entered_password)
    stored_value = str(stored_value)

    if stored_value.startswith("sha256:"):
        entered_hash = hashlib.sha256(entered_password.encode("utf-8")).hexdigest()
        return entered_hash == stored_value.split(":", 1)[1]

    # Secrets 자체는 GitHub에 노출되지 않으므로 초기 설정 편의를 위해 평문도 허용
    return entered_password == stored_value

def _get_app_password(user_id):
    try:
        return st.secrets["APP_USERS"][user_id]
    except Exception:
        return None

def require_login():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "login_user_id" not in st.session_state:
        st.session_state.login_user_id = None

    if st.session_state.authenticated and st.session_state.login_user_id in APP_USER_PROFILES:
        profile = APP_USER_PROFILES[st.session_state.login_user_id]
        return st.session_state.login_user_id, profile

    st.markdown("## 🔐 REPUBLICA B2B 로그인")
    st.caption("발주 시스템을 이용하려면 로그인하세요.")

    with st.form("login_form"):
        login_id = st.text_input("아이디")
        login_pw = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)

    if submitted:
        login_id = login_id.strip()
        profile = APP_USER_PROFILES.get(login_id)
        stored_pw = _get_app_password(login_id)

        if profile is not None and stored_pw is not None and _password_matches(login_pw, stored_pw):
            st.session_state.authenticated = True
            st.session_state.login_user_id = login_id
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    st.stop()

LOGIN_USER_ID, LOGIN_PROFILE = require_login()
LOGIN_USER_NAME = LOGIN_PROFILE["name"]
LOGIN_EMP_CD = LOGIN_PROFILE["emp_cd"]


SHEET_ID = "1FiP0FFJI8OdswJa_p6ejkOpLZGbVZx9j71UUSJ6zLN4"
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyBmjN8f2UkUbL3TrRK7zvkESJ2g-ZUqquHwPPDatrieBcpUMOAXiQXjJv3rHf5JjaG-Q/exec"

# 🌟 이카운트 ERP API 연동 정보 세팅
ECOUNT_COM_CODE = st.secrets["ECOUNT_COM_CODE"]
ECOUNT_USER_ID = st.secrets["ECOUNT_USER_ID"]
ECOUNT_API_KEY = st.secrets["ECOUNT_API_KEY"]
ECOUNT_WH_CD = st.secrets.get("ECOUNT_WH_CD", "100")
ECOUNT_EMP_CD = LOGIN_EMP_CD

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
                if sheet_c_name == clean_target:
                    if len(r) > 5 and pd.notna(r.iloc[5]):
                        cust_cd = str(r.iloc[5]).strip()
                    break

        if not cust_cd:
            st.error(
                f"❌ '{client_name}'의 ECOUNT 거래처코드를 찾지 못했습니다. "
                "client 시트의 매장코드(F열)를 확인해주세요."
            )
            return False

        today_str = datetime.datetime.now().strftime("%Y%m%d")
        sale_order_list = []

        # 4) ECOUNT 공식 SaleOrderList -> BulkDatas 형식으로 주문 품목 구성
        for idx, item in enumerate(cart_items):
            prod_cd = ""
            prod_des = str(item.get("모델명", "")).strip()
            color_des = str(item.get("컬러", "")).strip()

            try:
                m_clean = prod_des.split("(")[0].strip().upper()
                c_clean = color_des.upper()

                for _, r in df_colors.iterrows():
                    row_model = str(r.iloc[0]).split("(")[0].strip().upper()
                    row_col_code = str(r.iloc[1]).strip().upper() if len(r) > 1 else ""
                    row_col_name = str(r.iloc[2]).strip().upper() if len(r) > 2 else ""
                    row_full_col = f"{row_col_code} / {row_col_name}".strip(" /")

                    if (
                        row_model == m_clean
                        and (
                            row_col_code in c_clean
                            or row_col_name in c_clean
                            or row_full_col in c_clean
                        )
                    ):
                        if len(r) > 4 and pd.notna(r.iloc[4]):
                            prod_cd = str(r.iloc[4]).strip()
                        break
            except Exception:
                pass

            if not prod_cd:
                st.error(
                    f"❌ ECOUNT 품목코드를 찾지 못했습니다: "
                    f"{prod_des} / {color_des}"
                )
                return False

            qty = item.get("수량", 1)
            price = item.get("단가", "")
            supply_amt = item.get("금액", "")

            bulk = {
                "IO_DATE": today_str,
                "UPLOAD_SER_NO": "1",
                "CUST": str(cust_cd),
                "CUST_DES": "",
                "EMP_CD": str(ECOUNT_EMP_CD),
                "WH_CD": str(ECOUNT_WH_CD),
                "IO_TYPE": "",
                "EXCHANGE_TYPE": "",
                "EXCHANGE_RATE": "",
                "PJT_CD": "",
                "DOC_NO": "",
                "TTL_CTT": "",
                "REF_DES": "",
                "COLL_TERM": "",
                "AGREE_TERM": "",
                "TIME_DATE": "",
                "REMARKS_WIN": "",
                "U_MEMO1": "",
                "U_MEMO2": "",
                "U_MEMO3": "",
                "U_MEMO4": "",
                "U_MEMO5": "",
                "ADD_TXT_01_T": "",
                "ADD_TXT_02_T": "",
                "ADD_TXT_03_T": "",
                "ADD_TXT_04_T": "",
                "ADD_TXT_05_T": "",
                "ADD_TXT_06_T": "",
                "ADD_TXT_07_T": "",
                "ADD_TXT_08_T": "",
                "ADD_TXT_09_T": "",
                "ADD_TXT_10_T": "",
                "ADD_NUM_01_T": "",
                "ADD_NUM_02_T": "",
                "ADD_NUM_03_T": "",
                "ADD_NUM_04_T": "",
                "ADD_NUM_05_T": "",
                "ADD_CD_01_T": "",
                "ADD_CD_02_T": "",
                "ADD_CD_03_T": "",
                "ADD_DATE_01_T": "",
                "ADD_DATE_02_T": "",
                "ADD_DATE_03_T": "",
                "U_TXT1": "",
                "ADD_LTXT_01_T": "",
                "ADD_LTXT_02_T": "",
                "ADD_LTXT_03_T": "",
                "PROD_CD": str(prod_cd),
                "PROD_DES": "",
                "SIZE_DES": "",
                "UQTY": "",
                "QTY": str(qty),
                "PRICE": str(price) if price not in (None, "") else "",
                "USER_PRICE_VAT": "",
                "SUPPLY_AMT": str(supply_amt) if supply_amt not in (None, "") else "",
                "SUPPLY_AMT_F": "",
                "VAT_AMT": "",
                "ITEM_TIME_DATE": "",
                "REMARKS": (f"[예약 주문] {memo}".strip() if item.get("비고") == "예약주문" else str(memo)),
                "ITEM_CD": "",
                "P_REMARKS1": "",
                "P_REMARKS2": "",
                "P_REMARKS3": "",
                "ADD_TXT_01": "",
                "ADD_TXT_02": "",
                "ADD_TXT_03": "",
                "ADD_TXT_04": "",
                "ADD_TXT_05": "",
                "ADD_TXT_06": "",
                "REL_DATE": "",
                "REL_NO": "",
                "P_AMT1": "",
                "P_AMT2": "",
                "ADD_NUM_01": "",
                "ADD_NUM_02": "",
                "ADD_NUM_03": "",
                "ADD_NUM_04": "",
                "ADD_NUM_05": "",
                "ADD_CD_01": "",
                "ADD_CD_02": "",
                "ADD_CD_03": "",
                "ADD_CD_NM_01": "",
                "ADD_CD_NM_02": "",
                "ADD_CD_NM_03": "",
                "ADD_CDNM_01": "",
                "ADD_CDNM_02": "",
                "ADD_CDNM_03": "",
                "ADD_DATE_01": "",
                "ADD_DATE_02": "",
                "ADD_DATE_03": ""
            }

            sale_order_list.append({"BulkDatas": bulk})

        order_payload = {"SaleOrderList": sale_order_list}

        # 5) 공식 Request URL
        order_url = (
            f"https://sboapi{zone.lower()}.ecount.com/"
            f"OAPI/V2/SaleOrder/SaveSaleOrder?SESSION_ID={session_id}"
        )

        order_res = requests.post(
            order_url,
            json=order_payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        order_res.raise_for_status()
        order_data = order_res.json()

        # HTTP/Status 200이어도 품목별 Validation 실패가 있을 수 있음
        if str(order_data.get("Status")) != "200":
            st.error(f"❌ 이카운트 전송 실패: {order_data}")
            return False

        if order_data.get("Error"):
            st.error(f"❌ 이카운트 오류: {order_data.get('Error')}")
            return False

        data = order_data.get("Data") or {}
        fail_cnt = int(data.get("FailCnt") or 0)
        success_cnt = int(data.get("SuccessCnt") or 0)

        if fail_cnt > 0 or success_cnt < len(sale_order_list):
            result_details = data.get("ResultDetails") or []
            messages = []
            for result in result_details:
                if not result.get("IsSuccess", False):
                    total_error = result.get("TotalError")
                    if total_error:
                        messages.append(str(total_error))
                    for err in result.get("Errors") or []:
                        col = err.get("ColCd", "")
                        msg = err.get("Message", "")
                        messages.append(f"{col}: {msg}".strip(": "))

            st.error(
                "❌ 이카운트 주문서 입력 실패\n\n"
                + ("\n".join(messages) if messages else str(order_data))
            )
            return False

        slip_nos = data.get("SlipNos") or []
        if slip_nos:
            st.info("📄 ECOUNT 주문번호: " + ", ".join(map(str, slip_nos)))

        return True

    except requests.RequestException as e:
        st.error(f"❌ 이카운트 HTTP 통신 오류: {e}")
        return False
    except Exception as e:
        st.error(f"❌ 이카운트 처리 오류: {e}")
        return False


@st.cache_data(ttl=300)
def get_ecount_inventory_session():
    """ECOUNT 재고조회용 ZONE / SESSION_ID를 5분간 캐시합니다."""
    zone_res = requests.post(
        "https://sboapi.ecount.com/ECERP/OAPI/V2/Zone",
        json={"COM_CODE": ECOUNT_COM_CODE},
        timeout=10
    )
    zone_res.raise_for_status()
    zone_data = zone_res.json()
    zone_info = zone_data.get("Data") or {}
    zone = zone_info.get("ZONE") or zone_info.get("Zone") or zone_info.get("zone")

    if not zone:
        raise RuntimeError(f"Zone 조회 실패: {zone_data}")

    zone = str(zone).upper()

    login_res = requests.post(
        f"https://sboapi{zone.lower()}.ecount.com/OAPI/V2/OAPILogin",
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
        raise RuntimeError(f"ECOUNT 로그인 실패: {login_data}")

    return zone, session_id


@st.cache_data(ttl=300)
def get_ecount_stock(prod_cd, wh_cd):
    """품목 1개의 ECOUNT BAL_QTY 조회. 조회 실패(None)와 실제 0재고를 구분."""
    prod_cd = str(prod_cd).strip()
    wh_cd = str(wh_cd).strip()
    if not prod_cd:
        return None, "품목코드 없음"

    try:
        zone, session_id = get_ecount_inventory_session()
        inventory_url = (
            f"https://sboapi{zone.lower()}.ecount.com/"
            f"OAPI/V2/InventoryBalance/ViewInventoryBalanceStatus"
            f"?SESSION_ID={session_id}"
        )
        payload = {
            "PROD_CD": prod_cd,
            "WH_CD": wh_cd,
            "BASE_DATE": datetime.datetime.now().strftime("%Y%m%d")
        }
        res = requests.post(
            inventory_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        res.raise_for_status()
        response_data = res.json()

        if str(response_data.get("Status")) != "200" or response_data.get("Error"):
            return None, str(response_data.get("Error") or response_data.get("Errors") or response_data)

        data = response_data.get("Data") or {}
        if data.get("IsSuccess") is False:
            return None, str(response_data)

        results = data.get("Result") or []
        if not results:
            return 0.0, None

        matched = next(
            (r for r in results if str(r.get("PROD_CD", "")).strip() == prod_cd),
            results[0]
        )
        raw_qty = matched.get("BAL_QTY")
        if raw_qty in (None, ""):
            return None, "BAL_QTY 없음"

        return float(raw_qty), None

    except requests.RequestException as e:
        return None, f"재고 API 통신 실패: {e}"
    except Exception as e:
        return None, f"재고 조회 실패: {e}"


def get_live_stock_for_color_row(row):
    """color 시트 E열의 ECOUNT 품목코드로 본사창고 실재고를 조회합니다."""
    if len(row) <= 4 or pd.isna(row.iloc[4]):
        return None, "ECOUNT 품목코드 없음"

    prod_cd = str(row.iloc[4]).strip()
    return get_ecount_stock(prod_cd, ECOUNT_WH_CD)


@st.cache_data(ttl=300)
def get_ecount_basic_products(prod_codes, prod_type=""):
    """ECOUNT 품목조회 API로 지정 품목의 기본정보를 조회합니다."""
    codes = [str(x).strip() for x in prod_codes if str(x).strip()]
    if not codes:
        return [], "조회할 품목코드가 없습니다."

    try:
        zone, session_id = get_ecount_inventory_session()
        url = (
            f"https://sboapi{zone.lower()}.ecount.com/"
            f"OAPI/V2/InventoryBasic/GetBasicProductsList"
            f"?SESSION_ID={session_id}"
        )
        payload = {"PROD_CD": "/".join(codes), "COMMA_FLAG": "N"}
        if str(prod_type).strip():
            payload["PROD_TYPE"] = str(prod_type).strip()

        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        res.raise_for_status()
        response_data = res.json()

        if str(response_data.get("Status")) != "200" or response_data.get("Error"):
            return [], str(response_data.get("Error") or response_data.get("Errors") or response_data)

        data = response_data.get("Data") or {}
        result = data.get("Result") or []
        # 이 API의 Result는 문서 예시처럼 JSON 문자열로 오는 경우가 있습니다.
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                return [], f"Result JSON 해석 실패: {result[:300]}"
        if isinstance(result, dict):
            result = [result]
        return result or [], None
    except requests.RequestException as e:
        return [], f"품목조회 API 통신 실패: {e}"
    except Exception as e:
        return [], f"품목조회 실패: {e}"


# ECOUNT 규격정보의 컬러코드를 앱 표시용 한글명으로 변환합니다.
COLOR_KR = {
    "C01M": "매트블랙", "C01": "블랙", "C02": "브라운",
    "C03M": "너겟골드", "C03": "골드", "C04M": "매트건메탈",
    "C04": "건메탈", "C05M": "매트실버", "C05": "크롬실버",
    "C06": "로즈골드",
}


def build_ecount_product_catalog(sheet_colors):
    """기존 Sheet 구조를 유지하면서 품목명/규격/가격을 ECOUNT 값으로 덮어씁니다.
    API 실패 시 호출부가 기존 Sheet 데이터로 폴백할 수 있도록 error를 반환합니다.
    """
    if sheet_colors is None or sheet_colors.empty:
        return pd.DataFrame(), pd.DataFrame(), "Google Sheet color 데이터가 없습니다."

    try:
        # 현재 앱에서 ECOUNT 품목코드는 color 시트의 5번째 열(E열)에 있습니다.
        prod_codes = (
            sheet_colors.iloc[:, 4].dropna().astype(str).str.strip().tolist()
            if len(sheet_colors.columns) > 4 else []
        )
        prod_codes = list(dict.fromkeys([x for x in prod_codes if x and x.lower() != "nan"]))
        if not prod_codes:
            return pd.DataFrame(), pd.DataFrame(), "ECOUNT 품목코드가 없습니다."

        # 문서상 PROD_CD는 '/'로 여러 품목을 묶어 조회할 수 있으므로 과도하게 긴 요청만 분할합니다.
        products = []
        for start in range(0, len(prod_codes), 150):
            rows, err = get_ecount_basic_products(prod_codes[start:start + 150])
            if err:
                return pd.DataFrame(), pd.DataFrame(), err
            products.extend(rows)

        by_code = {str(x.get("PROD_CD", "")).strip(): x for x in products if str(x.get("PROD_CD", "")).strip()}
        if not by_code:
            return pd.DataFrame(), pd.DataFrame(), "ECOUNT 품목조회 결과가 비어 있습니다."

        # color DataFrame은 기존 열 개수/순서를 그대로 유지해야 주문/재고 로직이 깨지지 않습니다.
        ec_colors = sheet_colors.copy()
        model_price = {}

        for idx, row in ec_colors.iterrows():
            if len(row) <= 4 or pd.isna(row.iloc[4]):
                continue
            prod_cd = str(row.iloc[4]).strip()
            item = by_code.get(prod_cd)
            if not item:
                continue

            prod_des = str(item.get("PROD_DES") or "").strip()
            size_des = str(item.get("SIZE_DES") or "").strip()

            # ECOUNT SIZE_DES 예: 'C02 - BROWN'
            color_code = ""
            english_color = size_des
            if "-" in size_des:
                left, right = size_des.split("-", 1)
                color_code = left.strip()
                english_color = right.strip()
            elif size_des:
                color_code = size_des.split()[0].strip()

            kr = COLOR_KR.get(color_code.upper(), "")
            display_color = english_color
            if kr:
                display_color = f"{english_color} / {kr}" if english_color else kr

            if prod_des:
                ec_colors.iat[idx, 0] = prod_des
            if len(ec_colors.columns) > 1 and color_code:
                ec_colors.iat[idx, 1] = color_code
            if len(ec_colors.columns) > 2 and display_color:
                ec_colors.iat[idx, 2] = display_color

            try:
                out_price = float(item.get("OUT_PRICE") or 0)
                if prod_des and out_price > 0:
                    model_price.setdefault(prod_des, int(round(out_price)))
            except Exception:
                pass

        # 모델 목록은 기존 Sheet의 재질 등 앱 전용 정보를 보존하고, ECOUNT 모델명/가격만 반영합니다.
        sheet_models = globals().get("_sheet_models")
        if sheet_models is None or sheet_models.empty:
            # 호출 시점에는 _sheet_models가 아직 없을 수 있으므로 color에서 최소 모델표를 만듭니다.
            names = [x for x in ec_colors.iloc[:, 0].dropna().astype(str).unique().tolist() if x and x != "nan"]
            ec_models = pd.DataFrame({"모델명": names, "재질": [""] * len(names), "출고단가": [model_price.get(x, 33000) for x in names]})
        else:
            ec_models = sheet_models.copy()
            # 기존 모델행과 ECOUNT PROD_DES가 같은 경우 가격만 최신화
            for idx, row in ec_models.iterrows():
                name = str(row.iloc[0]).strip()
                if len(ec_models.columns) > 2 and name in model_price:
                    ec_models.iat[idx, 2] = model_price[name]

        return ec_models, ec_colors, None
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"ECOUNT 품목 카탈로그 구성 실패: {e}"


df_models, df_colors, df_clients = load_data()

# ECOUNT 품목정보를 우선 사용합니다. 실패하면 기존 Google Sheet 데이터로 안전하게 폴백합니다.
_sheet_models = df_models
_sheet_colors = df_colors
_ec_models, _ec_colors, _ec_catalog_error = build_ecount_product_catalog(_sheet_colors)
if _ec_catalog_error is None:
    df_models = _ec_models
    df_colors = _ec_colors
else:
    df_models = _sheet_models
    df_colors = _sheet_colors


# 구글 시트 + 이카운트 주문서 전송 동시 진행 함수
def process_final_order(cart_items, client_name, memo):
    google_success = False
    if WEBHOOK_URL:
        order_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_payload = []
        for item in cart_items:
            order_payload.append([
                order_time,
                client_name,
                item['모델명'],
                item['컬러'],
                item['수량'],
                item['단가'],
                item['금액'],
                memo
            ])
        try:
            res = requests.post(WEBHOOK_URL, data=json.dumps(order_payload))
            if res.status_code == 200:
                google_success = True
        except:
            pass
            
    ecount_success = send_order_to_ecount(cart_items, client_name, memo, df_colors, df_clients)
    return google_success, ecount_success

if df_models is None or df_models.empty:
    st.error("⚠️ 구글 시트 데이터를 불러오는 데 실패했습니다.")
    st.info("💡 해결 방법:\n1. 구글 시트 링크 및 공유 설정을 확인해 주세요.\n2. 탭 이름이 **model**, **color**, **client**인지 확인해 주세요.")
else:
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    if 'drafts' not in st.session_state:
        st.session_state.drafts = []
    if 'current_client' not in st.session_state:
        st.session_state.current_client = ""
    if 'step' not in st.session_state:
        st.session_state.step = "input_client"
    if 'pending_reservation_items' not in st.session_state:
        st.session_state.pending_reservation_items = []
    if 'cart_memo' not in st.session_state:
        st.session_state.cart_memo = ""
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "새주문"
    if 'cart_added_feedback' not in st.session_state:
        st.session_state.cart_added_feedback = False

    components.html(
        """
        <script>
            function forceScrollTop() {
                try {
                    window.parent.scrollTo(0, 0);
                    var mainContainer = window.parent.document.querySelector('.main');
                    if (mainContainer) { mainContainer.scrollTo(0, 0); }
                    var stContainer = window.parent.document.querySelector('.stMain');
                    if (stContainer) { stContainer.scrollTo(0, 0); }
                    if (window.parent.document.activeElement) {
                        window.parent.document.activeElement.blur();
                    }
                } catch(e) {}
            }
            forceScrollTop();
            setTimeout(forceScrollTop, 50);
            setTimeout(forceScrollTop, 150);
            setTimeout(forceScrollTop, 300);
        </script>
        """,
        height=0
    )

    st.markdown("""
        <style>
        .block-container {
            padding-top: 2.8rem !important;
            padding-bottom: 3rem !important;
        }
        .main {
            background-color: #fcfcfc;
        }
        .brand-header {
            padding: 8px;
            background: linear-gradient(135deg, #111111, #333333);
            color: white;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 10px;
        }
        .brand-header h1 {
            margin: 0;
            font-size: 19px;
            font-weight: 700;
            letter-spacing: 1px;
        }
        .brand-header p {
            margin: 2px 0 0 0;
            font-size: 11px;
            color: #aaaaaa;
        }
        .client-highlight-box {
            background-color: #111111;
            color: #ffffff;
            padding: 14px 16px;
            border-radius: 10px;
            text-align: center;
            font-size: 18px;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        div.stButton > button {
            border-radius: 8px;
            font-weight: 700;
            height: 52px;
            font-size: 16px;
            transition: all 0.2s ease-in-out;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        </style>
    """, unsafe_allow_html=True)
    
    cart_count = sum(item['수량'] for item in st.session_state.cart)

    # 사이드바 메뉴
    st.sidebar.markdown("### 👓 REPUBLICA B2B")
    st.sidebar.markdown("#### 📌 메인 메뉴")
    if st.sidebar.button("📝 새주문 작성", use_container_width=True):
        st.session_state.active_tab = "새주문"
        st.session_state.step = "input_client"
        st.rerun()
        
    if st.sidebar.button("📋 주문서 내역", use_container_width=True):
        st.session_state.active_tab = "주문서"
        st.rerun()
        
    if st.sidebar.button("🔄 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.success("최신 데이터 갱신 완료!")
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📂 추가 조회 메뉴")
    if st.sidebar.button("📦 재고현황", use_container_width=True):
        st.session_state.active_tab = "재고현황"
        st.rerun()

    if st.sidebar.button("🧪 ECOUNT 품목조회 테스트", use_container_width=True):
        st.session_state.active_tab = "품목조회테스트"
        st.rerun()
        
    if st.sidebar.button("📊 매장별 히스토리", use_container_width=True):
        st.session_state.active_tab = "매장별 히스토리"
        st.rerun()
        
    if st.sidebar.button("📈 실적현황", use_container_width=True):
        st.session_state.active_tab = "실적현황"
        st.rerun()

    active_view = st.session_state.active_tab

    if active_view == "새주문":
        if st.session_state.step == "input_client":
            st.markdown("""
                <div class="brand-header">
                    <h1>REPUBLICA</h1>
                    <p>B2B Order System</p>
                </div>
            """, unsafe_allow_html=True)
            
            client_type = st.radio("거래처 유형 선택", ["기존 거래처", "신규 계약"], horizontal=True, label_visibility="collapsed")
            
            known_clients = []
            if df_clients is not None and not df_clients.empty:
                c_col = df_clients.columns[0]
                known_clients = df_clients[c_col].dropna().astype(str).tolist()
            
            selected_target = ""
            if client_type == "기존 거래처":
                if known_clients:
                    client_list = ["-- 거래처를 선택하세요 --"] + sorted(known_clients)
                    selected_dropdown = st.selectbox("거래처 선택", client_list, label_visibility="collapsed")
                    if selected_dropdown != "-- 거래처를 선택하세요 --":
                        selected_target = selected_dropdown
                else:
                    st.warning("⚠️ 등록된 거래처가 없습니다.")
            else:
                new_input = st.text_input("신규 매장명 입력", value="", placeholder="신규 매장명 입력 (예: 스타안경원)", label_visibility="collapsed")
                if new_input.strip():
                    selected_target = f"[신규] {new_input.strip()}"
            
            st.markdown("")
            if st.button("👉 주문서 작성 시작", type="primary", use_container_width=True):
                if not selected_target or selected_target.strip() == "":
                    st.warning("⚠️ 거래처 안경원 이름을 선택하거나 입력해주세요!")
                else:
                    st.session_state.current_client = selected_target
                    st.session_state.step = "select_model"
                    st.rerun()

        elif st.session_state.step == "select_model":
            st.markdown(f"""
                <div class="client-highlight-box">
                    📍 {st.session_state.current_client}
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("🔄 거래처 다시 선택/입력", use_container_width=True):
                st.session_state.step = "input_client"
                st.rerun()
                
            st.markdown("---")
            
            model_col = df_models.columns[0]
            material_col = df_models.columns[1] if len(df_models.columns) > 1 else None
            price_col = df_models.columns[2] if len(df_models.columns) > 2 else None

            all_model_names = df_models[model_col].fillna("").astype(str).tolist()
            search_query = st.selectbox("모델 검색", ["-- 모델명 검색 또는 선택 --"] + all_model_names, label_visibility="collapsed")
            
            if search_query != "-- 모델명 검색 또는 선택 --":
                matched_row = df_models[df_models[model_col].fillna("").astype(str) == search_query].iloc[0]
                model_name = str(matched_row[model_col])
                try:
                    price = int(matched_row[price_col]) if price_col else 33000
                except:
                    price = 33000
                
                st.success(f"선택: **{model_name}** (₩ {price:,})")
                if st.button("🚀 이 모델 컬러 고르러 가기", type="primary", use_container_width=True):
                    st.session_state.selected_model = model_name
                    st.session_state.unit_price = price
                    st.session_state.cart_added_feedback = False
                    st.session_state.step = "select_color"
                    st.rerun()

            st.markdown("---")
            st.markdown("<p style='font-size: 13px; font-weight: 700; color: #666; margin-bottom: 8px; letter-spacing: 1px;'>ALL MODELS</p>", unsafe_allow_html=True)
            
            for idx, row in df_models.iterrows():
                model_name = str(row[model_col])
                if model_name == "nan" or not model_name.strip():
                    continue
                    
                material = str(row[material_col]).strip() if material_col else "기타"
                try:
                    price = int(row[price_col]) if price_col else 33000
                except:
                    price = 33000

                mat_lower = material.lower()
                if "티타늄" in mat_lower: icon_prefix = "🔩"
                elif "아세테이트" in mat_lower: icon_prefix = "🏷️"
                elif "콤비" in mat_lower: icon_prefix = "🔗"
                else: icon_prefix = "🕶️"

                btn_label = f"{icon_prefix} {model_name}"
                if st.button(btn_label, key=f"mat_icon_btn_{idx}", use_container_width=True):
                    st.session_state.selected_model = model_name
                    st.session_state.unit_price = price
                    st.session_state.cart_added_feedback = False
                    st.session_state.step = "select_color"
                    st.rerun()

        elif st.session_state.step == "select_color":
            components.html(
                """
                <script>
                    function goTop() {
                        try {
                            window.parent.scrollTo({top: 0, left: 0, behavior: 'instant'});
                            const main = window.parent.document.querySelector('.stMain');
                            if (main) main.scrollTo({top: 0, left: 0, behavior: 'instant'});
                            const section = window.parent.document.querySelector('section.main');
                            if (section) section.scrollTo({top: 0, left: 0, behavior: 'instant'});
                        } catch(e) {}
                    }
                    goTop();
                    setTimeout(goTop, 50);
                    setTimeout(goTop, 150);
                    setTimeout(goTop, 350);
                    setTimeout(goTop, 700);
                </script>
                """,
                height=0
            )
            st.markdown(f"""
                <div class="client-highlight-box">
                    📍 {st.session_state.current_client}
                </div>
                <div style="font-size: 16px; font-weight: 800; color: #111111; margin-bottom: 10px; text-align: center;">
                    📌 {st.session_state.selected_model}
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("⬅️ 모델 다시 고르기", use_container_width=True):
                st.session_state.cart_added_feedback = False
                st.session_state.step = "select_model"
                st.rerun()

            selected_model_name = st.session_state.selected_model
            unit_price = st.session_state.unit_price
            
            clean_selected_model = str(selected_model_name).split('(')[0].strip().upper()
            color_model_col = df_colors.columns[0]
            safe_color_series = df_colors[color_model_col].fillna("").astype(str)
            
            matched_colors_df = df_colors[
                safe_color_series.apply(lambda x: str(x).split('(')[0].strip().upper() == clean_selected_model)
            ]

            if matched_colors_df.empty:
                matched_colors_df = df_colors[
                    safe_color_series.apply(lambda x: clean_selected_model in str(x).upper() or str(x).upper() in clean_selected_model)
                ]

            if matched_colors_df.empty:
                st.warning(f"⚠️ 매칭되는 컬러 정보를 찾지 못했습니다.")
            else:
                if st.session_state.pending_reservation_items:
                    st.warning("⚠️ **재고가 없는 제품(예약주문 대상)이 포함되어 있습니다!**")
                    with st.form("reservation_confirm_form"):
                        st.write("재고가 없는 제품입니다. 예약주문으로 하시겠습니까?")
                        for p_item in st.session_state.pending_reservation_items:
                            st.markdown(f"- **{p_item['모델명']}** / {p_item['컬러']} ({p_item['수량']}개)")
                        
                        r_col1, r_col2 = st.columns(2)
                        with r_col1: yes_sub = st.form_submit_button("예 (예약진행)", use_container_width=True, type="primary")
                        with r_col2: no_sub = st.form_submit_button("취소", use_container_width=True)
                            
                        if yes_sub:
                            for p_item in st.session_state.pending_reservation_items:
                                p_item['비고'] = "예약주문"
                                existing = None
                                for c_item in st.session_state.cart:
                                    if (c_item["거래처"] == p_item["거래처"] and c_item["모델명"] == p_item["모델명"] and c_item["컬러"] == p_item["컬러"] and c_item.get("비고") == "예약주문"):
                                        existing = c_item
                                        break
                                if existing:
                                    existing["수량"] += p_item["수량"]
                                    existing["금액"] = existing["수량"] * unit_price
                                else:
                                    st.session_state.cart.append(p_item)
                            st.session_state.pending_reservation_items = []
                            st.session_state.cart_added_feedback = True
                            st.rerun()
                        elif no_sub:
                            st.session_state.pending_reservation_items = []
                            st.info("취소되었습니다.")
                            st.rerun()
                else:
                    with st.form(key=f"multi_color_form_{selected_model_name}"):
                        color_inputs = []
                        for idx, row in matched_colors_df.iterrows():
                            col_code = str(row.iloc[1]) if len(row) > 1 else ""
                            col_name = str(row.iloc[2]) if len(row) > 2 else ""
                            color_label = f"{col_code} / {col_name}".strip(" /")
                            
                            # 선택한 모델의 컬러만 ECOUNT 실재고를 조회합니다.
                            # 같은 품목은 5분간 캐시되어 반복 호출을 줄입니다.
                            live_stock, stock_error = get_live_stock_for_color_row(row)
                            if live_stock is None:
                                stock_qty = None
                                checkbox_label = f"{color_label} (재고 확인 불가)"
                            else:
                                stock_qty = int(live_stock) if float(live_stock).is_integer() else live_stock
                                checkbox_label = f"{color_label} (재고: {stock_qty})"
                            
                            col_chk, col_qty = st.columns([2.5, 1])
                            with col_chk:
                                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                                is_checked = st.checkbox(checkbox_label, key=f"chk_{clean_selected_model}_{idx}")
                            with col_qty:
                                qty = st.number_input("수량", min_value=1, max_value=100, value=1, step=1, key=f"qty_{clean_selected_model}_{idx}", label_visibility="collapsed")
                            
                            st.markdown("<hr style='margin: 4px 0; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
                            
                            if is_checked:
                                color_inputs.append({"컬러": color_label, "수량": qty, "재고": stock_qty})
                        
                        st.markdown("")
                        if st.session_state.cart_added_feedback:
                            st.success("✅ 장바구니에 추가되었습니다.")
                        submitted = st.form_submit_button(
                            "🛒 장바구니에 담기",
                            use_container_width=True,
                            type="secondary" if st.session_state.cart_added_feedback else "primary"
                        )
                        
                        if submitted:
                            if len(color_inputs) == 0:
                                st.warning("⚠️ 선택된 컬러가 없습니다.")
                            else:
                                zero_stock_items = []
                                normal_items = []
                                
                                for item in color_inputs:
                                    item_data = {
                                        "거래처": st.session_state.current_client,
                                        "모델명": selected_model_name,
                                        "컬러": item["컬러"],
                                        "수량": item["수량"],
                                        "단가": unit_price,
                                        "금액": item["수량"] * unit_price,
                                        "비고": ""
                                    }
                                    # 실제 재고가 0 이하인 경우에만 예약주문.
                                    # 조회 실패(None)는 품절로 오판하지 않습니다.
                                    if item["재고"] is not None and item["재고"] <= 0:
                                        zero_stock_items.append(item_data)
                                    else:
                                        normal_items.append(item_data)
                                        
                                for item in normal_items:
                                    existing_item = None
                                    for cart_item in st.session_state.cart:
                                        if (cart_item["거래처"] == item["거래처"] and cart_item["모델명"] == item["모델명"] and cart_item["컬러"] == item["컬러"] and cart_item.get("비고", "") == ""):
                                            existing_item = cart_item
                                            break
                                    if existing_item:
                                        existing_item["수량"] += item["수량"]
                                        existing_item["금액"] = existing_item["수량"] * unit_price
                                    else:
                                        st.session_state.cart.append(item)
                                        
                                if zero_stock_items:
                                    st.session_state.pending_reservation_items = zero_stock_items
                                    st.rerun()
                                else:
                                    st.session_state.cart_added_feedback = True
                                    st.rerun()
                            
                if len(st.session_state.cart) > 0:
                    st.markdown("---")
                    if st.button("➕ 다른 모델 추가로 담기", type="primary", use_container_width=True):
                        st.session_state.cart_added_feedback = False
                        st.session_state.step = "select_model"
                        st.rerun()

        if st.session_state.step == "goto_cart_tab":
            st.title("🛒 장바구니 현황")
            st.markdown(f"현재 거래처: **{st.session_state.current_client}**")
            
            for idx, item in enumerate(st.session_state.cart):
                c1, c2, c3 = st.columns([4, 2, 1])
                with c1:
                    memo_txt = f" [{item['비고']}]" if item.get('비고') else ""
                    st.write(f"**{item['모델명']}** / {item['컬러']}{memo_txt}")
                with c2:
                    st.write(f"수량: {item['수량']}개 (₩ {item['금액']:,})")
                with c3:
                    if st.button("🗑 삭제", key=f"step_del_{idx}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
                        
            st.markdown("---")
            total_price = sum(item['금액'] for item in st.session_state.cart)
            st.markdown(f"### 💰 총 주문 금액: **₩ {total_price:,}**")
            
            st.markdown("")
            st.markdown("##### 📝 요청 (특이) 사항")
            st.session_state.cart_memo = st.text_area(
                "특이사항 입력", 
                value=st.session_state.cart_memo, 
                placeholder="매장별 전달사항이나 특이사항을 입력해 주세요.",
                label_visibility="collapsed"
            )
            
            st.markdown("")
            sc1, sc2 = st.columns(2)
            with sc1:
                if st.button("➕ 모델 추가로 담으러 가기", use_container_width=True):
                    st.session_state.step = "select_model"
                    st.rerun()
            with sc2:
                if st.button("🚀 최종 주문 완료하기", type="primary", use_container_width=True):
                    g_ok, e_ok = process_final_order(st.session_state.cart, st.session_state.current_client, st.session_state.cart_memo.strip())
                    
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip()
                    })
                    
                    msg = "🎉 주문 완료! "
                    if g_ok: msg += "[구글시트 저장 성공] "
                    if e_ok: msg += "[이카운트 주문서 전송 성공] "
                    if not g_ok and not e_ok: msg = "⚠️ 외부 전송 실패. 앱 내부에만 임시 저장되었습니다."
                    
                    st.success(msg)
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.session_state.step = "input_client"

    elif active_view == "장바구니":
        st.title("🛒 장바구니")
        st.markdown(f"**{st.session_state.current_client or '미지정'}**")
        st.markdown("---")
        
        if len(st.session_state.cart) > 0:
            for idx, item in enumerate(st.session_state.cart):
                c1, c2, c3 = st.columns([4, 2, 1])
                with c1:
                    memo_txt = f" [{item['비고']}]" if item.get('비고') else ""
                    st.write(f"**{item['모델명']}** / {item['컬러']}{memo_txt}")
                with c2:
                    st.write(f"{item['수량']}개 (₩ {item['금액']:,})")
                with c3:
                    if st.button("🗑", key=f"cart_page_del_{idx}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
                        
            st.markdown("---")
            total_price = sum(item['금액'] for item in st.session_state.cart)
            st.markdown(f"### 총 금액: **₩ {total_price:,}**")
            
            st.markdown("##### 📝 요청(특이)사항")
            st.session_state.cart_memo = st.text_area(
                "특이사항", 
                value=st.session_state.cart_memo, 
                placeholder="전달사항 입력",
                label_visibility="collapsed"
            )
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 임시저장", use_container_width=True):
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip()
                    })
                    st.success("앱 내부에 임시저장됨")
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.rerun()
            with col2:
                if st.button("🚀 주문완료", type="primary", use_container_width=True):
                    g_ok, e_ok = process_final_order(st.session_state.cart, st.session_state.current_client, st.session_state.cart_memo.strip())
                    
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip()
                    })
                    
                    msg = "🎉 주문 완료! "
                    if g_ok: msg += "[구글시트 저장 성공] "
                    if e_ok: msg += "[이카운트 주문서 전송 성공] "
                    if not g_ok and not e_ok: msg = "⚠️ 외부 전송 실패. 앱 내부에만 임시 저장되었습니다."
                    
                    st.success(msg)
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.session_state.step = "input_client"
                    
            with col3:
                if st.button("🧹 비우기", use_container_width=True):
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.rerun()
        else:
            st.info("장바구니가 비어 있습니다.")

    elif active_view == "주문서":
        st.markdown("#### 📋 작성된 주문서 리스트")
        st.markdown("---")
        
        if len(st.session_state.drafts) > 0:
            for i, draft in enumerate(st.session_state.drafts):
                t_str = draft.get('시간', '시간없음')
                with st.expander(f"[{t_str}] {draft['거래처']} ({draft['품목수']}개)"):
                    
                    updated_items = []
                    for item_idx, item in enumerate(draft["내역"]):
                        col_m, col_c, col_q, col_del = st.columns([3, 2, 2, 1])
                        with col_m:
                            memo_lbl = f" [{item['비고']}]" if item.get('비고') else ""
                            st.write(f"**{item['모델명']}**{memo_lbl}")
                        with col_c:
                            st.write(f"{item['컬러']}")
                        with col_q:
                            new_qty = st.number_input("수량", min_value=1, max_value=100, value=int(item['수량']), key=f"edit_q_{i}_{item_idx}", label_visibility="collapsed")
                        with col_del:
                            remove_item = st.button("🗑️", key=f"del_item_{i}_{item_idx}")
                        
                        if not remove_item:
                            updated_items.append({
                                "거래처": draft['거래처'],
                                "모델명": item['모델명'],
                                "컬러": item['컬러'],
                                "수량": new_qty,
                                "단가": item['단가'],
                                "금액": new_qty * item['단가'],
                                "비고": item.get('비고', '')
                            })
                    
                    draft["내역"] = updated_items
                    draft["품목수"] = sum(x['수량'] for x in updated_items)
                    
                    st.markdown("##### 메모")
                    current_draft_memo = draft.get("요청사항", "")
                    edited_memo = st.text_area("메모 수정", value=current_draft_memo, key=f"edit_memo_{i}", label_visibility="collapsed")
                    draft["요청사항"] = edited_memo.strip()
                    
                    col_save, col_add, col_cancel = st.columns(3)
                    with col_save:
                        if st.button("💾 변경사항저장", key=f"save_draft_{i}", use_container_width=True, type="primary"):
                            st.success("변경사항이 저장되었습니다!")
                            st.rerun()
                    with col_add:
                        if st.button("➕ 제품추가", key=f"add_more_to_draft_{i}", use_container_width=True):
                            st.session_state.current_client = draft['거래처']
                            st.session_state.cart = draft["내역"].copy()
                            st.session_state.cart_memo = draft.get("요청사항", "")
                            st.session_state.drafts.pop(i)
                            st.session_state.step = "select_model"
                            st.session_state.active_tab = "새주문"
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ 주문취소", key=f"del_draft_{i}", use_container_width=True):
                            st.session_state.drafts.pop(i)
                            st.rerun()
        else:
            st.info("작성된 주문서가 없습니다.")

    elif active_view == "재고현황":
        st.title("📦 ECOUNT 실재고 현황")
        st.caption(f"출하창고 코드: {ECOUNT_WH_CD} · 선택한 품목만 조회하며 결과는 5분간 캐시됩니다.")
        st.info("API 전송량 보호를 위해 전체 품목 자동조회는 중지했습니다. 모델을 선택한 뒤 필요한 품목만 조회하세요.")
        st.markdown("---")

        if not df_colors.empty:
            model_options = sorted(df_colors.iloc[:, 0].dropna().astype(str).unique().tolist())
            selected_stock_model = st.selectbox(
                "모델 선택",
                ["-- 모델을 선택하세요 --"] + model_options,
                key="inventory_model_select"
            )

            if selected_stock_model != "-- 모델을 선택하세요 --":
                model_rows = df_colors[df_colors.iloc[:, 0].astype(str) == selected_stock_model].copy()

                display_options = []
                row_map = {}
                for idx, row in model_rows.iterrows():
                    color_code = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                    color_name = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ""
                    prod_cd = str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else ""
                    label = f"{color_code} / {color_name} / {prod_cd}".strip(" /")
                    display_options.append(label)
                    row_map[label] = row

                selected_stock_items = st.multiselect(
                    "조회할 컬러/품목 선택",
                    display_options,
                    key="inventory_item_select"
                )

                st.caption("처음에는 1개 품목만 선택해서 테스트하는 것을 권장합니다.")

                if st.button("🔎 선택 품목 실재고 조회", type="primary", use_container_width=True):
                    if not selected_stock_items:
                        st.warning("조회할 품목을 하나 이상 선택하세요.")
                    else:
                        inventory_rows = []
                        for label in selected_stock_items:
                            row = row_map[label]
                            model_name = str(row.iloc[0]) if len(row) > 0 else ""
                            color_code = str(row.iloc[1]) if len(row) > 1 else ""
                            color_name = str(row.iloc[2]) if len(row) > 2 else ""
                            prod_cd = str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else ""

                            live_stock, stock_error = get_live_stock_for_color_row(row)
                            inventory_rows.append({
                                "모델명": model_name,
                                "컬러코드": color_code,
                                "컬러명": color_name,
                                "ECOUNT 품목코드": prod_cd,
                                "실재고": live_stock if live_stock is not None else "조회실패",
                                "조회상태": "정상" if stock_error is None else stock_error
                            })

                        st.session_state.inventory_lookup_result = inventory_rows

                if st.session_state.get("inventory_lookup_result"):
                    st.dataframe(
                        pd.DataFrame(st.session_state.inventory_lookup_result),
                        use_container_width=True
                    )
        else:
            st.warning("⚠️ 품목 데이터를 불러올 수 없습니다.")

    elif active_view == "품목조회테스트":
        st.title("🧪 ECOUNT 품목조회 테스트")
        st.caption("현재 Google Sheet color 시트의 ECOUNT 품목코드를 이용해 ECOUNT 품목 기본정보를 직접 조회합니다.")
        st.info("기존 주문/재고 로직은 변경하지 않았습니다. 우선 조회 결과만 확인하는 테스트 화면입니다.")
        st.markdown("---")

        if df_colors is None or df_colors.empty:
            st.warning("color 시트 데이터를 불러올 수 없습니다.")
        else:
            code_rows = []
            for _, row in df_colors.iterrows():
                model = str(row.iloc[0]).strip() if len(row) > 0 and pd.notna(row.iloc[0]) else ""
                color_code = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                color_name = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""
                prod_cd = str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else ""
                if prod_cd:
                    label = f"{model} / {color_code} / {color_name} / {prod_cd}"
                    code_rows.append((label, prod_cd))

            if not code_rows:
                st.warning("color 시트 E열에서 ECOUNT 품목코드를 찾지 못했습니다.")
            else:
                options = [x[0] for x in code_rows]
                selected = st.multiselect("테스트할 품목 선택", options, max_selections=10)
                st.caption("처음에는 1~3개만 선택해서 테스트하는 것을 권장합니다.")

                if st.button("🔎 ECOUNT에서 품목정보 조회", type="primary", use_container_width=True):
                    if not selected:
                        st.warning("품목을 하나 이상 선택하세요.")
                    else:
                        lookup = dict(code_rows)
                        prod_codes = [lookup[x] for x in selected]
                        rows, err = get_ecount_basic_products(prod_codes)
                        if err:
                            st.error(f"❌ 품목조회 실패: {err}")
                        elif not rows:
                            st.warning("조회는 성공했지만 반환된 품목이 없습니다.")
                        else:
                            st.success(f"✅ ECOUNT 품목조회 성공: {len(rows)}개")
                            preferred = ["PROD_CD", "PROD_DES", "PROD_TYPE", "UNIT", "WH_CD", "OUT_PRICE", "BAR_CODE", "REMARKS", "CLASS_CD"]
                            df_result = pd.DataFrame(rows)
                            cols = [c for c in preferred if c in df_result.columns]
                            extra = [c for c in df_result.columns if c not in cols]
                            st.dataframe(df_result[cols + extra], use_container_width=True)

    elif active_view == "매장별 히스토리":
        st.title("📊 매장별 히스토리")
        st.markdown("---")
        
        known_clients = []
        if df_clients is not None and not df_clients.empty:
            c_col = df_clients.columns[0]
            known_clients = df_clients[c_col].dropna().astype(str).tolist()
        
        if not known_clients:
            known_clients = ["등록된 거래처 없음"]
            
        selected_client_history = st.selectbox("거래처 선택", sorted(known_clients))
        
        if selected_client_history and selected_client_history != "등록된 거래처 없음":
            client_row = df_clients[df_clients[df_clients.columns[0]].astype(str).str.strip() == selected_client_history]
            
            ad_balance, mi_suku, sheet_memo, sky_res = "0", "0", "없음", "0"
            if not client_row.empty:
                r = client_row.iloc[0]
                try: ad_balance = str(r.iloc[1]) if len(r) > 1 else "0"
                except: pass
                try: mi_suku = str(r.iloc[2]) if len(r) > 2 else "0"
                except: pass
                try: sheet_memo = str(r.iloc[3]) if len(r) > 3 else "없음"
                except: pass
                try: sky_res = str(r.iloc[4]) if len(r) > 4 else "0"
                except: pass

            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1: st.metric(label="적립잔액", value=ad_balance)
            with col_h2: st.metric(label="미수금", value=mi_suku)
            with col_h3: st.metric(label="미출고", value=f"{sky_res}개")
                
            if sheet_memo and sheet_memo != "nan" and sheet_memo != "없음":
                st.info(f"📝 {sheet_memo}")
                
            st.markdown("---")
            st.subheader("예약주문 내역")
            reserved_items = []
            for draft in st.session_state.drafts:
                if draft['거래처'] == selected_client_history:
                    for item in draft['내역']:
                        if item.get('비고') == '예약주문':
                            res_copy = item.copy()
                            res_copy['주문시간'] = draft['시간']
                            reserved_items.append(res_copy)
                            
            if res_items := reserved_items:
                st.dataframe(pd.DataFrame(res_items)[['주문시간', '모델명', '컬러', '수량']], use_container_width=True)
            else:
                st.info("미출고 예약 내역 없음")

    elif active_view == "실적현황":
        st.title("📈 실적현황")
        st.markdown("---")
        
        if len(st.session_state.drafts) == 0:
            st.info("완료된 주문서가 없습니다.")
        else:
            all_orders = []
            for draft in st.session_state.drafts:
                order_time = draft['시간']
                for item in draft['내역']:
                    item_copy = item.copy()
                    item_copy['주문시각'] = order_time
                    item_copy['날짜'] = order_time.split()[0]
                    all_orders.append(item_copy)
            
            df_orders_all = pd.DataFrame(all_orders)
            total_sales = df_orders_all['금액'].sum()
            total_qty = df_orders_all['수량'].sum()
            
            m1, m2 = st.columns(2)
            with m1: st.metric(label="총 매출액", value=f"₩ {total_sales:,}")
            with m2: st.metric(label="총 판매수량", value=f"{total_qty:,}개")

    cart_badge_str = f" ({cart_count}개)" if cart_count > 0 else ""
    st.markdown("<br>", unsafe_allow_html=True) 
    st.markdown("---")
    
    if st.button(f"🛒 장바구니 확인하기{cart_badge_str}", use_container_width=True):
        st.session_state.active_tab = "장바구니"
        st.session_state.step = "goto_cart_tab"
        st.rerun()