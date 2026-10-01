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


# 기준 데이터는 GitHub 저장소의 database.xlsx에서 직접 읽습니다.
# Google Spreadsheet는 더 이상 제품/컬러/거래처 DB로 사용하지 않습니다.
DATABASE_FILE = "database.xlsx"
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyBmjN8f2UkUbL3TrRK7zvkESJ2g-ZUqquHwPPDatrieBcpUMOAXiQXjJv3rHf5JjaG-Q/exec"

# 🌟 이카운트 ERP API 연동 정보 세팅
ECOUNT_COM_CODE = st.secrets["ECOUNT_COM_CODE"]
ECOUNT_USER_ID = st.secrets["ECOUNT_USER_ID"]
ECOUNT_API_KEY = st.secrets["ECOUNT_API_KEY"]
ECOUNT_WH_CD = st.secrets.get("ECOUNT_WH_CD", "100")
ECOUNT_EMP_CD = LOGIN_EMP_CD

@st.cache_data
def load_data():
    """GitHub 저장소에 함께 둔 database.xlsx의 MODEL/COLOR/CLIENT 시트를 읽습니다."""
    try:
        df_models = pd.read_excel(DATABASE_FILE, sheet_name="MODEL", engine="openpyxl")
        df_colors = pd.read_excel(DATABASE_FILE, sheet_name="COLOR", engine="openpyxl")
        df_clients = pd.read_excel(DATABASE_FILE, sheet_name="CLIENT", engine="openpyxl")

        # 셀 앞뒤 공백 때문에 매칭이 실패하지 않도록 기본 정리
        for df in (df_models, df_colors, df_clients):
            df.columns = [str(c).strip() for c in df.columns]

        return df_models, df_colors, df_clients
    except Exception as e:
        st.error(f"❌ 내장 데이터베이스(database.xlsx) 로딩 실패: {e}")
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
            return False, ""

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
            return False, ""

        # 3) 선택한 거래처명을 ECOUNT 거래처코드로 변환
        cust_cd = ""
        clean_target = str(client_name).replace("[신규]", "").strip().upper()

        if df_clients is not None and not df_clients.empty:
            for _, r in df_clients.iterrows():
                sheet_c_name = str(r.iloc[0]).strip().upper()
                if sheet_c_name == clean_target:
                    if "매장코드" in df_clients.columns and pd.notna(r.get("매장코드")):
                        cust_cd = str(r.get("매장코드")).strip()
                    break

        if not cust_cd:
            st.error(
                f"❌ '{client_name}'의 ECOUNT 거래처코드를 찾지 못했습니다. "
                "database.xlsx의 CLIENT 시트 '매장코드'를 확인해주세요."
            )
            return False, ""

        today_str = datetime.datetime.now().strftime("%Y%m%d")
        sale_order_list = []

        # 요청사항은 예약/반품 행을 피해서 마지막 일반 판매상품의 빈 적요에만 기록합니다.
        # 주문 전체가 예약/반품뿐이면 ECOUNT 적요에는 요청사항을 넣지 않고 앱 주문내역에만 보존합니다.
        memo_target_idx = None
        if str(memo).strip() and cart_items:
            normal_indexes = [
                i for i, x in enumerate(cart_items)
                if x.get("비고", "") not in ("예약주문", "반품")
            ]
            memo_target_idx = normal_indexes[-1] if normal_indexes else None

        # 4) ECOUNT 공식 SaleOrderList -> BulkDatas 형식으로 주문 품목 구성
        for idx, item in enumerate(cart_items):
            # 장바구니에 실제 ECOUNT 품목코드가 저장되어 있으면 그것을 최우선 사용합니다.
            # 특히 REFUND 품목은 화면 표시명이 '반품 - 33,000'처럼 변환되므로 재검색하면 매칭되지 않습니다.
            prod_cd = str(item.get("ECOUNT 품목코드", "") or "").strip()
            prod_des = str(item.get("모델명", "")).strip()
            color_des = str(item.get("컬러", "")).strip()

            try:
                m_clean = prod_des.split("(")[0].strip().upper()
                c_clean = color_des.upper()

                # 코드가 장바구니에 없는 기존/일반 품목만 기존 방식으로 재검색합니다.
                for _, r in ([] if prod_cd else df_colors.iterrows()):
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
                        if "이카운트코드" in df_colors.columns and pd.notna(r.get("이카운트코드")):
                            prod_cd = str(r.get("이카운트코드")).strip()
                        break
            except Exception:
                pass

            if not prod_cd:
                st.error(
                    f"❌ ECOUNT 품목코드를 찾지 못했습니다: "
                    f"{prod_des} / {color_des}"
                )
                return False, ""

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
                "REMARKS": (
                    " / ".join(filter(None, [
                        "[예약 주문]" if item.get("비고") == "예약주문" else ("반품" if item.get("비고") == "반품" else ""),
                        str(memo).strip() if idx == memo_target_idx else ""
                    ]))
                ),
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
            return False, ""

        if order_data.get("Error"):
            st.error(f"❌ 이카운트 오류: {order_data.get('Error')}")
            return False, ""

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
            return False, ""

        slip_nos = data.get("SlipNos") or []
        slip_no = ", ".join(map(str, slip_nos)) if slip_nos else ""
        if slip_no:
            st.info("📄 ECOUNT 주문번호: " + slip_no)

        return True, slip_no

    except requests.RequestException as e:
        st.error(f"❌ 이카운트 HTTP 통신 오류: {e}")
        return False, ""
    except Exception as e:
        st.error(f"❌ 이카운트 처리 오류: {e}")
        return False, ""


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
    """내장 COLOR DB의 이카운트코드로 본사창고 실재고를 조회합니다."""
    # database.xlsx의 COLOR 시트는
    # 모델명 / 컬러명(영문) / 컬러명 / 이카운트코드 의 4개 열입니다.
    # 기존 Google Sheet 버전은 E열(row.iloc[4])을 사용했기 때문에
    # 내장 DB 전환 후에는 항상 '재고 확인 불가'가 표시되었습니다.
    try:
        if "이카운트코드" in row.index:
            value = row["이카운트코드"]
        elif len(row) > 3:
            value = row.iloc[3]
        else:
            return None, "ECOUNT 품목코드 없음"

        if pd.isna(value) or not str(value).strip():
            return None, "ECOUNT 품목코드 없음"

        prod_cd = str(value).strip()
        return get_ecount_stock(prod_cd, ECOUNT_WH_CD)
    except Exception as e:
        return None, f"ECOUNT 품목코드 확인 실패: {e}"


df_models, df_colors, df_clients = load_data()

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
            
    ecount_success, ecount_slip_no = send_order_to_ecount(cart_items, client_name, memo, df_colors, df_clients)
    return google_success, ecount_success, ecount_slip_no

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
    if 'pending_return_items' not in st.session_state:
        st.session_state.pending_return_items = []
    if 'cart_memo' not in st.session_state:
        st.session_state.cart_memo = ""
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "새주문"
    if 'cart_added_feedback' not in st.session_state:
        st.session_state.cart_added_feedback = False
    if 'reset_color_widgets' not in st.session_state:
        st.session_state.reset_color_widgets = False

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

            # 장바구니 담기 완료 후에는 다음 rerun 시작 시, 위젯이 만들어지기 전에
            # 이전 체크박스/수량 위젯 상태를 삭제합니다.
            # (Streamlit은 이미 생성된 위젯의 session_state 값을 같은 실행 중 직접 변경하면 오류가 납니다.)
            if st.session_state.get('reset_color_widgets', False):
                widget_prefix_chk = f"chk_{clean_selected_model}_"
                widget_prefix_qty = f"qty_{clean_selected_model}_"
                for state_key in list(st.session_state.keys()):
                    if str(state_key).startswith(widget_prefix_chk) or str(state_key).startswith(widget_prefix_qty):
                        del st.session_state[state_key]
                st.session_state.reset_color_widgets = False

            # 반품 품목 판정: MODEL 시트의 표시명이 "반품 - 33,000"처럼 REFUND 코드가 아닐 수 있으므로
            # 표시명 + 단가를 함께 봅니다. REFUND 코드 / '반품' 표시명 / 음수단가 중 하나면 반품입니다.
            def _is_refund_item(model_name, price=None):
                model_text = str(model_name or "").split('(')[0].strip().upper()
                if model_text.startswith("REFUND") or "반품" in model_text:
                    return True
                try:
                    return float(price) < 0
                except (TypeError, ValueError):
                    return False

            is_refund_model = _is_refund_item(selected_model_name, unit_price)

            # 배포 전 세션에 반품이 '예약대기'로 남아 있어도 즉시 반품대기로 교정합니다.
            if st.session_state.pending_reservation_items:
                still_reservation = []
                moved_to_return = []
                for pending in st.session_state.pending_reservation_items:
                    if _is_refund_item(pending.get("모델명", ""), pending.get("단가")):
                        pending["비고"] = "반품"
                        moved_to_return.append(pending)
                    else:
                        still_reservation.append(pending)
                if moved_to_return:
                    st.session_state.pending_reservation_items = still_reservation
                    st.session_state.pending_return_items.extend(moved_to_return)

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
                if st.session_state.pending_return_items:
                    st.info("🔄 **반품 항목이 선택되었습니다.**")
                    with st.form("return_confirm_form"):
                        st.write("반품을 진행하시겠습니까?")
                        for p_item in st.session_state.pending_return_items:
                            st.markdown(f"- **{p_item['모델명']}** ({p_item['수량']}개)")

                        r_col1, r_col2 = st.columns(2)
                        with r_col1: yes_return = st.form_submit_button("반품 진행", use_container_width=True, type="primary")
                        with r_col2: no_return = st.form_submit_button("취소", use_container_width=True)

                        if yes_return:
                            for p_item in st.session_state.pending_return_items:
                                p_item['비고'] = "반품"
                                existing = None
                                for c_item in st.session_state.cart:
                                    if (c_item["거래처"] == p_item["거래처"] and c_item["모델명"] == p_item["모델명"] and c_item["컬러"] == p_item["컬러"] and c_item.get("비고") == "반품"):
                                        existing = c_item
                                        break
                                if existing:
                                    existing["수량"] += p_item["수량"]
                                    existing["금액"] = existing["수량"] * unit_price
                                else:
                                    st.session_state.cart.append(p_item)
                            st.session_state.pending_return_items = []
                            st.session_state.reset_color_widgets = True
                            st.session_state.cart_added_feedback = True
                            st.rerun()
                        elif no_return:
                            st.session_state.pending_return_items = []
                            st.info("취소되었습니다.")
                            st.rerun()
                elif st.session_state.pending_reservation_items:
                    st.warning("⚠️ **재고가 부족한 제품(예약주문 대상)이 포함되어 있습니다!**")
                    with st.form("reservation_confirm_form"):
                        st.write("현재고를 초과한 수량은 예약주문으로 처리됩니다. 예약주문으로 진행하시겠습니까?")
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
                            st.session_state.reset_color_widgets = True
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
                            col_code = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
                            col_name = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ""
                            color_label = f"{col_code} / {col_name}".strip(" /")
                            
                            # REFUND 품목은 재고/예약 개념을 적용하지 않습니다.
                            if is_refund_model:
                                stock_qty = None
                                if not color_label:
                                    color_label = "반품"
                                checkbox_label = "반품수량 입력"
                            else:
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
                                # 선택 시점의 실제 ECOUNT 품목코드를 함께 보관합니다.
                                # REFUND도 이후 표시명으로 다시 찾지 않고 이 코드를 그대로 전송합니다.
                                row_prod_cd = ""
                                if "이카운트코드" in matched_colors_df.columns and pd.notna(row.get("이카운트코드")):
                                    row_prod_cd = str(row.get("이카운트코드")).strip()
                                elif len(row) > 4 and pd.notna(row.iloc[4]):
                                    row_prod_cd = str(row.iloc[4]).strip()
                                color_inputs.append({"컬러": color_label, "수량": qty, "재고": stock_qty, "ECOUNT 품목코드": row_prod_cd})
                        
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
                                        "비고": "",
                                        "ECOUNT 품목코드": item.get("ECOUNT 품목코드", "")
                                    }
                                    # REFUND 품목은 재고조회/예약판정 없이 반품 확인 대상으로 보냅니다.
                                    if is_refund_model:
                                        item_data["비고"] = "반품"
                                        zero_stock_items.append(item_data)
                                        continue

                                    # 재고보다 주문수량이 많으면 재고분은 일반주문, 초과분만 예약주문으로 분리합니다.
                                    # 이미 장바구니에 담긴 같은 품목의 일반주문 수량도 현재 재고에서 차감해 계산합니다.
                                    if item["재고"] is not None:
                                        already_normal = sum(
                                            int(c.get("수량", 0))
                                            for c in st.session_state.cart
                                            if c.get("거래처") == item_data["거래처"]
                                            and c.get("모델명") == item_data["모델명"]
                                            and c.get("컬러") == item_data["컬러"]
                                            and c.get("비고", "") != "예약주문"
                                        )
                                        available = max(int(item["재고"]) - already_normal, 0)
                                        normal_qty = min(int(item["수량"]), available)
                                        reserve_qty = int(item["수량"]) - normal_qty

                                        if normal_qty > 0:
                                            normal_part = item_data.copy()
                                            normal_part["수량"] = normal_qty
                                            normal_part["금액"] = normal_qty * unit_price
                                            normal_items.append(normal_part)

                                        if reserve_qty > 0:
                                            reserve_part = item_data.copy()
                                            reserve_part["수량"] = reserve_qty
                                            reserve_part["금액"] = reserve_qty * unit_price
                                            zero_stock_items.append(reserve_part)
                                    else:
                                        # 조회 실패(None)는 품절로 오판하지 않고 기존처럼 일반주문 처리합니다.
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
                                    if is_refund_model:
                                        st.session_state.pending_return_items = zero_stock_items
                                    else:
                                        st.session_state.pending_reservation_items = zero_stock_items
                                    st.rerun()
                                else:
                                    # 다음 rerun에서 위젯 생성 전에 선택값을 초기화합니다.
                                    st.session_state.reset_color_widgets = True

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
                    g_ok, e_ok, e_slip_no = process_final_order(st.session_state.cart, st.session_state.current_client, st.session_state.cart_memo.strip())
                    
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip(),
                        "ECOUNT주문번호": e_slip_no if e_ok else ""
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
                        "요청사항": st.session_state.cart_memo.strip(),
                        "ECOUNT주문번호": ""
                    })
                    st.success("앱 내부에 임시저장됨")
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.rerun()
            with col2:
                if st.button("🚀 주문완료", type="primary", use_container_width=True):
                    g_ok, e_ok, e_slip_no = process_final_order(st.session_state.cart, st.session_state.current_client, st.session_state.cart_memo.strip())
                    
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip(),
                        "ECOUNT주문번호": e_slip_no if e_ok else ""
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
        st.caption("완료된 주문서는 조회만 가능합니다. ECOUNT 전표와 혼선을 막기 위해 수정·삭제할 수 없습니다.")
        st.markdown("---")

        if len(st.session_state.drafts) > 0:
            for i, draft in enumerate(reversed(st.session_state.drafts)):
                t_str = draft.get("시간", "시간없음")
                item_count = draft.get("품목수", 0)
                with st.expander(f"[{t_str}] {draft.get('거래처', '')} ({item_count}개)"):
                    slip_no = draft.get("ECOUNT주문번호", "")
                    if slip_no:
                        st.info(f"📄 ECOUNT 주문번호: {slip_no}")
                    else:
                        st.caption("ECOUNT 주문번호 없음 (임시저장 또는 이전 주문)")

                    for item in draft.get("내역", []):
                        memo_lbl = f" [{item.get('비고')}]" if item.get("비고") else ""
                        qty = int(item.get("수량", 0))
                        price = int(item.get("단가", 0))
                        amount = int(item.get("금액", qty * price))
                        st.write(f"**{item.get('모델명', '')}**{memo_lbl}")
                        st.write(f"{item.get('컬러', '')} · {qty}개 · ₩{amount:,}")

                    order_memo = draft.get("요청사항", "")
                    if order_memo:
                        st.markdown("##### 📝 요청(특이)사항")
                        st.write(order_memo)

                    total_amount = sum(int(x.get("금액", 0)) for x in draft.get("내역", []))
                    st.markdown(f"**총 금액: ₩{total_amount:,}**")
                    st.caption("🔒 ECOUNT에 전송된 주문서는 앱에서 수정하거나 삭제할 수 없습니다.")
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
                # 현재 내장 CLIENT DB는 거래처명/매장코드만 보관합니다.
                # 잔액/미수금/특이사항/미출고 데이터는 없으므로 기본값을 유지합니다.

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