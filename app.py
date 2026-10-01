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

# 🌟 이카운트 ERP '판매주문서 입력' 전송 함수
def send_order_to_ecount(cart_items, client_name, memo, df_colors, df_clients):
    try:
        # 1단계: ZONE 조회
        zone_res = requests.post(
            "https://sboapi.ecount.com/ECERP/OAPI/V2/Zone",
            json={"COM_CODE": ECOUNT_COM_CODE},
            timeout=5
        )

        zone_data = zone_res.json()
        zone_info = zone_data.get("Data")

        if not zone_info or "ZONE" not in zone_info:
            st.error(f"이카운트 Zone 조회 실패: {zone_data}")
            return False

        zone = str(zone_info.get("ZONE", "CC")).lower()

        # 2단계: 로그인 (SESSION_ID 발급)
        login_url = f"https://sboapi{zone}.ecount.com/ECERP/OAPI/V2/OAPILogin"

        login_res = requests.post(
            login_url,
            json={
                "COM_CODE": ECOUNT_COM_CODE,
                "USER_ID": ECOUNT_USER_ID,
                "API_CERT_KEY": ECOUNT_API_KEY,
                "ZONE": zone.upper(),
                "LAN_TYPE": "ko-KR"
            },
            timeout=5
        )

        login_data = login_res.json()
        login_data_block = login_data.get("Data", {})

        session_id = (
            login_data_block.get("Datas", {}).get("SESSION_ID")
            or login_data_block.get("SESSION_ID")
            or login_data_block.get("Session_Id")
        )

        if not session_id:
            st.error(f"이카운트 로그인 실패: {login_data}")
            return False

        # 3단계: 거래처명 → ECOUNT 거래처코드 변환
        cust_cd = client_name

        try:
            clean_target = (
                str(client_name)
                .replace("[신규]", "")
                .strip()
                .upper()
            )

            if df_clients is not None and not df_clients.empty:
                for _, r in df_clients.iterrows():

                    sheet_c_name = str(r.iloc[0]).strip().upper()

                    if sheet_c_name == clean_target:

                        # client 시트 F열 = ECOUNT 거래처코드
                        if len(r) > 5 and pd.notna(r.iloc[5]):
                            cust_cd = str(r.iloc[5]).strip()

                        break

        except Exception:
            pass

        # 4단계: 주문 상세 데이터 생성
        today_str = datetime.datetime.now().strftime("%Y%m%d")

        details = []

        for idx, item in enumerate(cart_items):

            # 기본값은 모델명
            prod_cd = item["모델명"]

            # Google Sheet color 데이터에서
            # ECOUNT 품목코드 찾기
            try:
                m_clean = (
                    str(item["모델명"])
                    .split("(")[0]
                    .strip()
                    .upper()
                )

                c_clean = str(item["컬러"]).strip().upper()

                for _, r in df_colors.iterrows():

                    row_model = (
                        str(r.iloc[0])
                        .split("(")[0]
                        .strip()
                        .upper()
                    )

                    row_col_code = str(r.iloc[1]).strip().upper()
                    row_col_name = str(r.iloc[2]).strip().upper()

                    row_full_col = (
                        f"{row_col_code} / {row_col_name}"
                        .strip(" /")
                    )

                    if (
                        row_model == m_clean
                        and (
                            row_col_code in c_clean
                            or row_col_name in c_clean
                            or row_full_col in c_clean
                        )
                    ):
                        # color 시트 E열 = ECOUNT 품목코드
                        if len(r) > 4 and pd.notna(r.iloc[4]):
                            prod_cd = str(r.iloc[4]).strip()

                        break

            except Exception:
                pass

            details.append({
                "LineNo": idx + 1,
                "ProdCd": str(prod_cd),
                "ProdDes": str(item["컬러"]),
                "Qty": float(item["수량"]),
                "Price": float(item["단가"]),
                "SupplyAmt": float(item["금액"]),
                "Remarks": str(memo)
            })

        # 5단계: ECOUNT 주문 데이터 구성
        order_payload = {
            "SESSION_ID": session_id,
            "Remote_IP": "",
            "SvcType": "A",
            "Data": {
                "UID": "",
                "IO_Date": today_str,
                "CustCd": str(cust_cd),
                "Remarks": str(memo),
                "Details": details
            }
        }

        # 6단계: ECOUNT 판매주문서 입력
        # ECOUNT 공식 Request URL
        order_url = (
            f"https://oapi{zone}.ecount.com"
            f"/OAPI/V2/SaleOrder/SaveSaleOrder"
            f"?SESSION_ID={session_id}"
        )

        order_res = requests.post(
            order_url,
            json=order_payload,
            timeout=10
        )

        # JSON 응답 확인
        try:
            order_data = order_res.json()
        except Exception:
            st.error(
                f"❌ 이카운트 응답 해석 실패 "
                f"(HTTP {order_res.status_code}): "
                f"{order_res.text}"
            )
            return False

        # 성공 여부 확인
        if (
            str(order_data.get("Status")) == "200"
            or str(order_data.get("Code")) == "200"
        ):
            return True

        # ECOUNT가 Errors를 빈 값으로 반환하는 경우도 고려
        if (
            not order_data.get("Errors")
            and order_data.get("Data")
            and str(order_data.get("Status", "")) == "200"
        ):
            return True

        st.error(
            f"❌ 이카운트 거부 사유: "
            f"{order_data.get('Errors') "
            f"or order_data.get('Message') "
            f"or order_data}"
        )

        return False

    except Exception as e:
        st.error(f"❌ 이카운트 통신 에러: {str(e)}")
        return False

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
                    st.session_state.step = "select_color"
                    st.rerun()

        elif st.session_state.step == "select_color":
            st.markdown(f"""
                <div class="client-highlight-box">
                    📍 {st.session_state.current_client}
                </div>
                <div style="font-size: 16px; font-weight: 800; color: #111111; margin-bottom: 10px; text-align: center;">
                    📌 {st.session_state.selected_model}
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("⬅️ 모델 다시 고르기", use_container_width=True):
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
                            st.success("🎉 예약주문 완료!")
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
                            
                            stock_qty = 0
                            if len(row) > 3:
                                try: stock_qty = int(row.iloc[3])
                                except: stock_qty = 0
                            
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
                        submitted = st.form_submit_button("🛒 장바구니에 담기", use_container_width=True, type="primary")
                        
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
                                    if item["재고"] == 0:
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
                                    st.success("🎉 장바구니 담기 성공!")
                                    st.rerun()
                            
                if len(st.session_state.cart) > 0:
                    st.markdown("---")
                    if st.button("➕ 다른 모델 추가로 담기", use_container_width=True):
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
        st.title("📦 재고 현황")
        st.markdown("---")
        if not df_colors.empty:
            st.dataframe(df_colors, use_container_width=True)
        else:
            st.warning("⚠️ 재고 데이터를 불러올 수 없습니다.")

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
