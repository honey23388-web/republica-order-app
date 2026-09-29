import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="REPUBLICA B2B 발주 시스템", page_icon="👓", layout="centered")

SHEET_ID = "1FiP0FFJI8OdswJa_p6ejkOpLZGbVZx9j71UUSJ6zLN4"

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

# 사이드바 최신 데이터 새로고침 버튼
st.sidebar.markdown("### 👓 REPUBLICA B2B")
st.sidebar.markdown("---")
if st.sidebar.button("🔄 최신 데이터 새로고침", use_container_width=True):
    st.cache_data.clear()
    st.success("캐시가 초기화되었습니다!")
    st.rerun()

if df_models is None or df_models.empty:
    st.error("⚠️ 구글 시트 데이터를 불러오는 데 실패했습니다.")
    st.info("💡 해결 방법:\n1. 구글 시트 링크 및 공유 설정(링크가 있는 모든 사용자 보기 가능)을 확인해 주세요.\n2. 시트 하단의 탭 이름이 **model**, **color**, **client**로 정확히 입력되어 있는지 확인해 주세요.")
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

    # 공통 CSS 스타일 주입 (버튼 일체형 디자인 최적화)
    st.markdown("""
        <style>
        .main {
            background-color: #fcfcfc;
        }
        .brand-header {
            padding: 15px;
            background: linear-gradient(135deg, #111111, #333333);
            color: white;
            border-radius: 10px;
            text-align: center;
            margin-bottom: 20px;
        }
        .brand-header h1 {
            margin: 0;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: 1px;
        }
        .brand-header p {
            margin: 5px 0 0 0;
            font-size: 13px;
            color: #aaaaaa;
        }
        /* 모델 카드 내부 버튼 디자인을 깔끔하게 통일 */
        div.stButton > button {
            border-radius: 10px;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        </style>
    """, unsafe_allow_html=True)
    
    cart_count = sum(item['수량'] for item in st.session_state.cart)
    
    nav_choice = st.sidebar.radio(
        "메뉴 선택", 
        [
            "새주문", 
            f"장바구니 ({cart_count})", 
            "주문서", 
            "재고현황", 
            "매장별 히스토리 보기",
            "현황"
        ]
    )

    # -------------------------------------------------------------------------
    # 1. 새주문 메뉴
    # -------------------------------------------------------------------------
    if nav_choice == "새주문":
        if st.session_state.step == "input_client":
            st.markdown("""
                <div class="brand-header">
                    <h1>REPUBLICA</h1>
                    <p>B2B Professional Optical Order System</p>
                </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 📝 새주문 시작하기")
            st.markdown("발주를 진행할 거래처 유형을 선택해 주세요.")
            
            client_type = st.radio("거래처 유형", ["기존 거래처 선택", "신규 계약 매장"], horizontal=True)
            st.markdown("---")
            
            known_clients = []
            if df_clients is not None and not df_clients.empty:
                c_col = df_clients.columns[0]
                known_clients = df_clients[c_col].dropna().astype(str).tolist()
            
            selected_target = ""
            
            if client_type == "기존 거래처 선택":
                st.markdown("#### 🔍 구글 시트 연동 기존 거래처 선택")
                if known_clients:
                    client_list = ["-- 거래처를 선택하세요 --"] + sorted(known_clients)
                    selected_dropdown = st.selectbox("거래처 안경원 검색", client_list, label_visibility="collapsed")
                    if selected_dropdown != "-- 거래처를 선택하세요 --":
                        selected_target = selected_dropdown
                else:
                    st.warning("⚠️ 등록된 거래처가 없습니다. 구글 시트의 client 탭을 확인해 주세요.")
            else:
                st.markdown("#### ✍️ 신규 계약 매장명 입력")
                new_input = st.text_input("신규 매장명 입력", value="", placeholder="예: 스타안경원", label_visibility="collapsed")
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
            st.markdown("""
                <div class="brand-header">
                    <h1>REPUBLICA</h1>
                    <p>모델 선택 화면</p>
                </div>
            """, unsafe_allow_html=True)
            
            st.info(f"📍 **현재 거래처:** {st.session_state.current_client}")
            
            if st.button("🔄 거래처 다시 선택/입력"):
                st.session_state.step = "input_client"
                st.rerun()
                
            st.markdown("---")
            st.markdown("### 🔎 모델 직접 검색 (자동완성)")
            model_col = df_models.columns[0]
            material_col = df_models.columns[1] if len(df_models.columns) > 1 else None
            price_col = df_models.columns[2] if len(df_models.columns) > 2 else None

            all_model_names = df_models[model_col].astype(str).tolist()
            search_query = st.selectbox("모델명 검색 또는 선택", ["-- 모델을 검색하거나 아래에서 선택하세요 --"] + all_model_names)
            
            if search_query != "-- 모델을 검색하거나 아래에서 선택하세요 --":
                matched_row = df_models[df_models[model_col].astype(str) == search_query].iloc[0]
                model_name = str(matched_row[model_col])
                material = str(matched_row[material_col]).strip() if material_col else "기타"
                try:
                    price = int(matched_row[price_col]) if price_col else 33000
                except:
                    price = 33000
                
                st.success(f"선택된 모델: **{model_name}** ({material} / ₩ {price:,})")
                if st.button("🚀 이 모델 컬러 고르러 가기", type="primary", use_container_width=True):
                    st.session_state.selected_model = model_name
                    st.session_state.unit_price = price
                    st.session_state.step = "select_color"
                    st.rerun()

            st.markdown("---")
            st.markdown("### 📋 제품 모델 선택")
            st.markdown("<small style='color: gray;'>소재별 색상이 적용된 아래 카드 버튼을 터치하여 컬러 선택으로 넘어가세요.</small>", unsafe_allow_html=True)
            st.markdown("")

            # [핵심 개선] 제품 설명 카드와 선택 버튼을 하나의 완벽한 카드형 버튼으로 일체화
            for idx, row in df_models.iterrows():
                model_name = str(row[model_col])
                material = str(row[material_col]).strip() if material_col else "기타"
                try:
                    price = int(row[price_col]) if price_col else 33000
                except:
                    price = 33000

                mat_lower = material.lower()
                if "티타늄" in mat_lower or "아세테이트" in mat_lower:
                    box_bg = "#f7ebe1"
                    border_c = "#d9b89a"
                    badge_c = "#8c5830"
                elif "콤비" in mat_lower:
                    box_bg = "#daf2da"
                    border_c = "#87cb87"
                    badge_c = "#2d6a2d"
                else:
                    box_bg = "#eaeaea"
                    border_c = "#cccccc"
                    badge_c = "#555555"

                # Streamlit 버튼 안에 HTML 정보를 얹어 완벽하게 일체화된 카드 버튼 구현
                btn_caption = f"🕶️ {model_name}  [{material}]  |  단가: ₩ {price:,}"
                
                # 커스텀 스타일 마크다운 카드와 버튼을 타이트하게 밀착
                st.markdown(f"""
                <div style="padding: 10px 14px; background-color: {box_bg}; border: 2px solid {border_c}; border-radius: 10px 10px 0 0; margin-top: 10px; font-weight: 700; color: #111; display: flex; justify-content: space-between; align-items: center;">
                    <span>🕶️ {model_name}</span>
                    <span style="background-color: {badge_c}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{material}</span>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"👉 선택하기 (공급 단가: ₩ {price:,})", key=f"unified_card_{idx}", use_container_width=True, type="primary"):
                    st.session_state.selected_model = model_name
                    st.session_state.unit_price = price
                    st.session_state.step = "select_color"
                    st.rerun()

            if len(st.session_state.cart) > 0:
                st.markdown("---")
                if st.button("🛒 장바구니 확인 / 주문 완료로 이동", use_container_width=True):
                    st.session_state.step = "goto_cart_tab"
                    st.rerun()

        elif st.session_state.step == "select_color":
            st.markdown("""
                <div class="brand-header">
                    <h1>REPUBLICA</h1>
                    <p>컬러 및 재고 확인</p>
                </div>
            """, unsafe_allow_html=True)
            
            st.info(f"📍 **거래처:** {st.session_state.current_client} &nbsp;|&nbsp; 📌 **모델:** {st.session_state.selected_model}")
            
            if st.button("⬅️ 모델 목록으로 돌아가기"):
                st.session_state.step = "select_model"
                st.rerun()
                
            st.markdown("---")
            st.markdown(f"### [{st.session_state.selected_model}] 컬러별 재고 및 수량 지정")
            st.markdown("<small style='color: gray;'>재고가 0인 제품은 장바구니 담기 시 예약주문 여부를 확인합니다.</small>", unsafe_allow_html=True)

            selected_model_name = st.session_state.selected_model
            unit_price = st.session_state.unit_price
            
            clean_selected_model = selected_model_name.split('(')[0].strip().upper()
            color_model_col = df_colors.columns[0]
            
            matched_colors_df = df_colors[
                df_colors[color_model_col].astype(str)
                .apply(lambda x: x.split('(')[0].strip().upper() == clean_selected_model)
            ]

            if matched_colors_df.empty:
                matched_colors_df = df_colors[
                    df_colors[color_model_col].astype(str)
                    .apply(lambda x: clean_selected_model in x.upper() or x.upper() in clean_selected_model)
                ]

            if matched_colors_df.empty:
                st.warning(f"⚠️ '{selected_model_name}' 모델에 매칭되는 컬러 정보를 찾지 못했습니다.")
            else:
                if st.session_state.pending_reservation_items:
                    st.warning("⚠️ **재고가 없는 제품이 포함되어 있습니다!**")
                    st.write('재고가 없는 제품입니다. 예약주문으로 하시겠습니까?')
                    
                    with st.form("reservation_confirm_form"):
                        st.write("**[예약주문 대상 품목]**")
                        for p_item in st.session_state.pending_reservation_items:
                            st.markdown(f"- **{p_item['모델명']}** / {p_item['컬러']} (수량: {p_item['수량']}개)")
                        
                        r_col1, r_col2 = st.columns(2)
                        with r_col1:
                            yes_sub = st.form_submit_button("예 (예약주문 진행)", use_container_width=True, type="primary")
                        with r_col2:
                            no_sub = st.form_submit_button("취소", use_container_width=True)
                            
                        if yes_sub:
                            for p_item in st.session_state.pending_reservation_items:
                                p_item['비고'] = "예약주문"
                                existing = None
                                for c_item in st.session_state.cart:
                                    if (c_item["거래처"] == p_item["거래처"] and 
                                        c_item["모델명"] == p_item["모델명"] and 
                                        c_item["컬러"] == p_item["컬러"] and 
                                        c_item.get("비고") == "예약주문"):
                                        existing = c_item
                                        break
                                if existing:
                                    existing["수량"] += p_item["수량"]
                                    existing["금액"] = existing["수량"] * unit_price
                                else:
                                    st.session_state.cart.append(p_item)
                            st.session_state.pending_reservation_items = []
                            st.success("🎉 예약주문으로 정상 처리되어 장바구니에 담겼습니다!")
                            st.rerun()
                        elif no_sub:
                            st.session_state.pending_reservation_items = []
                            st.info("예약주문이 취소되었습니다.")
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
                                try:
                                    stock_qty = int(row.iloc[3])
                                except:
                                    stock_qty = 0
                            
                            c1, c2 = st.columns([3, 1])
                            with c1:
                                stock_color_style = "color: #cc0000;" if stock_qty == 0 else "color: #0066cc;"
                                st.markdown(f"**{color_label}** &nbsp; <span style='{stock_color_style} font-size: 13px;'>(재고: <b>{stock_qty}개</b>)</span>", unsafe_allow_html=True)
                                is_checked = st.checkbox("선택", key=f"chk_{clean_selected_model}_{idx}", label_visibility="collapsed")
                            with c2:
                                qty = st.number_input("수량", min_value=1, max_value=100, value=1, step=1, key=f"qty_{clean_selected_model}_{idx}", label_visibility="collapsed")
                            
                            if is_checked:
                                color_inputs.append({"컬러": color_label, "수량": qty, "재고": stock_qty})
                        
                        st.markdown("")
                        submitted = st.form_submit_button("🛒 장바구니에 담기", use_container_width=True, type="primary")
                        
                        if submitted:
                            if len(color_inputs) == 0:
                                st.warning("⚠️ 체크박스로 선택된 컬러가 없습니다.")
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
                                        if (cart_item["거래처"] == item["거래처"] and 
                                            cart_item["모델명"] == item["모델명"] and 
                                            cart_item["컬러"] == item["컬러"] and 
                                            cart_item.get("비고", "") == ""):
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
                                    st.success("🎉 성공적으로 장바구니에 담겼습니다!")
                                    st.rerun()
                            
                if len(st.session_state.cart) > 0:
                    st.markdown("---")
                    st.markdown("#### ✨ 다음 작업을 선택하세요:")
                    b_col1, b_col2 = st.columns(2)
                    with b_col1:
                        if st.button("➕ 다른 모델 계속 담기", use_container_width=True):
                            st.session_state.step = "select_model"
                            st.rerun()
                    with b_col2:
                        if st.button("🛒 장바구니 확인 / 주문 완료", type="primary", use_container_width=True):
                            st.session_state.step = "goto_cart_tab"
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
                    if st.button("🗑️ 삭제", key=f"step_del_{idx}"):
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
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip()
                    })
                    st.success("주문이 성공적으로 완료되었습니다!")
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.session_state.step = "input_client"
                    st.rerun()

    # -------------------------------------------------------------------------
    # 2. 장바구니 메뉴
    # -------------------------------------------------------------------------
    elif nav_choice.startswith("장바구니"):
        st.title("🛒 장바구니 및 임시저장")
        st.markdown(f"현재 거래처: **{st.session_state.current_client or '지정되지 않음'}**")
        st.markdown("---")
        
        if len(st.session_state.cart) > 0:
            for idx, item in enumerate(st.session_state.cart):
                c1, c2, c3 = st.columns([4, 2, 1])
                with c1:
                    memo_txt = f" [{item['비고']}]" if item.get('비고') else ""
                    st.write(f"**{item['모델명']}** / {item['컬러']}{memo_txt}")
                with c2:
                    st.write(f"수량: {item['수량']}개 (₩ {item['금액']:,})")
                with c3:
                    if st.button("🗑️ 삭제", key=f"cart_page_del_{idx}"):
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
                    st.success("임시저장되었습니다.")
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.rerun()
            with col2:
                if st.button("🚀 최종 주문 완료", type="primary", use_container_width=True):
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip()
                    })
                    st.success("주문이 성공적으로 전송 완료되었습니다!")
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.session_state.step = "input_client"
                    st.rerun()
            with col3:
                if st.button("🧹 장바구니 비우기", use_container_width=True):
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.rerun()
        else:
            st.info("장바구니가 비어 있습니다. '새주문' 메뉴에서 제품을 담아주세요.")

    # -------------------------------------------------------------------------
    # 3. 주문서 메뉴
    # -------------------------------------------------------------------------
    elif nav_choice == "주문서":
        st.title("📋 작성된 주문서 리스트")
        st.markdown("완료된 주문서 목록을 확인하고, **요청사항 확인·수량 변경·품목 삭제·모델 추가** 등으로 직접 수정하거나 취소할 수 있습니다.")
        st.markdown("---")
        
        if len(st.session_state.drafts) > 0:
            for i, draft in enumerate(st.session_state.drafts):
                time_key = '시간'
                t_str = draft.get(time_key, '시간정보없음')
                with st.expander(f"[{t_str}] 거래처: {draft['거래처']} (총 {draft['품목수']}개 품목)"):
                    
                    st.markdown("##### ✏️ 주문 품목 편집")
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
                    
                    st.markdown("---")
                    st.markdown("##### 📝 요청 (특이) 사항")
                    current_draft_memo = draft.get("요청사항", "")
                    edited_memo = st.text_area("요청사항 수정", value=current_draft_memo, key=f"edit_memo_{i}", label_visibility="collapsed")
                    draft["요청사항"] = edited_memo.strip()
                    
                    st.markdown("")
                    col_save, col_add, col_cancel = st.columns(3)
                    with col_save:
                        if st.button("💾 변경사항 저장", key=f"save_draft_{i}", use_container_width=True, type="primary"):
                            st.success("주문서 수정 내용이 저장되었습니다!")
                            st.rerun()
                    with col_add:
                        if st.button("➕ 모델 추가하기", key=f"add_more_to_draft_{i}", use_container_width=True):
                            st.session_state.current_client = draft['거래처']
                            st.session_state.cart = draft["내역"].copy()
                            st.session_state.cart_memo = draft.get("요청사항", "")
                            st.session_state.drafts.pop(i)
                            st.session_state.step = "select_model"
                            st.success("모델을 추가할 수 있도록 새주문 화면으로 이동합니다.")
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ 주문 취소(삭제)", key=f"del_draft_{i}", use_container_width=True):
                            st.session_state.drafts.pop(i)
                            st.success("주문서가 취소되었습니다.")
                            st.rerun()
        else:
            st.info("작성된 주문서 내역이 없습니다.")

    # -------------------------------------------------------------------------
    # 4. 재고현황 메뉴
    # -------------------------------------------------------------------------
    elif nav_choice == "재고현황":
        st.title("📦 실시간 재고 현황")
        st.markdown("이카운트 ERP(Ecount ERP API) 연동을 통해 실시간 제품별 재고 수량을 확인할 수 있습니다.")
        st.markdown("---")
        
        st.info("💡 현재 이카운트 ERP API 연동 대기 중입니다. (연동 시 실시간 재고 수량이 자동 표기됩니다)")
        
        if not df_colors.empty:
            st.dataframe(df_colors, use_container_width=True)
        else:
            st.warning("재고 데이터를 불러올 수 없습니다.")

    # -------------------------------------------------------------------------
    # 5. 매장별 히스토리 보기 메뉴
    # -------------------------------------------------------------------------
    elif nav_choice == "매장별 히스토리 보기":
        st.title("📊 매장별 거래 히스토리 & 채권 현황")
        st.markdown("구글 시트(`client` 탭) 및 주문 데이터를 기반으로 적립잔액, 미수금, 특이사항 및 예약출고를 조회합니다.")
        st.markdown("---")
        
        known_clients = []
        if df_clients is not None and not df_clients.empty:
            c_col = df_clients.columns[0]
            known_clients = df_clients[c_col].dropna().astype(str).tolist()
        
        if not known_clients:
            known_clients = ["등록된 거래처가 없습니다"]
            
        selected_client_history = st.selectbox("🔍 조회할 거래처(매장) 선택", sorted(known_clients))
        
        if selected_client_history and selected_client_history != "등록된 거래처가 없습니다":
            st.markdown(f"### 📍 [{selected_client_history}] 상세 현황")
            
            client_row = df_clients[df_clients[df_clients.columns[0]].astype(str).str.strip() == selected_client_history]
            
            ad_balance = "0"
            mi_suku = "0"
            sheet_memo = "특이사항 없음"
            sheet_res = "0"
            
            if not client_row.empty:
                r = client_row.iloc[0]
                try: ad_balance = str(r.iloc[1]) if len(r) > 1 else "0"
                except: pass
                try: mi_suku = str(r.iloc[2]) if len(r) > 2 else "0"
                except: pass
                try: sheet_memo = str(r.iloc[3]) if len(r) > 3 else "특이사항 없음"
                except: pass
                try: sheet_res = str(r.iloc[4]) if len(r) > 4 else "0"
                except: pass

            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                st.metric(label="💰 적립 잔액", value=f"{ad_balance}")
            with col_h2:
                st.metric(label="⚠️ 미수금 (채권)", value=f"{mi_suku}")
            with col_h3:
                st.metric(label="📦 미출고 예약제품(수량)", value=f"{sheet_res} 개")
                
            if sheet_memo and sheet_memo != "nan" and sheet_memo != "특이사항 없음":
                st.info(f"📝 **[시트 등록 특이사항]:** {sheet_memo}")
                
            st.markdown("---")
            st.subheader("📦 실시간 예약 및 미출고 제품 내역")
            
            reserved_items = []
            for draft in st.session_state.drafts:
                if draft['거래처'] == selected_client_history:
                    for item in draft['내역']:
                        if item.get('비고') == '예약주문':
                            res_copy = item.copy()
                            res_copy['주문시간'] = draft['시간']
                            reserved_items.append(res_copy)
                            
            if reserved_items:
                df_reserved = pd.DataFrame(reserved_items)[['주문시간', '모델명', '컬러', '수량', '금액']]
                st.dataframe(df_reserved, use_container_width=True)
            else:
                st.info("💡 현재 앱에서 작성된 미출고 예약주문 품목이 없습니다.")
                
            st.markdown("---")
            st.subheader("📜 과거 주문 판매 내역 및 특이사항 메모")
            
            client_drafts = [d for d in st.session_state.drafts if d['거래처'] == selected_client_history]
            if client_drafts:
                for cd in client_drafts:
                    memo_str = f" | 메모: {cd['요청사항']}" if cd.get('요청사항') else ""
                    with st.expander(f"🕒 주문일시: {cd['시간']} (총 {cd['품목수']}개){memo_str}"):
                        st.dataframe(pd.DataFrame(cd['내역']), use_container_width=True)
                        if cd.get('요청사항'):
                            st.info(f"📝 **매장 요청/특이사항 메모:** {cd['요청사항']}")
            else:
                st.info("📈 해당 거래처의 완료된 과거 주문 내역이 없습니다.")

    # -------------------------------------------------------------------------
    # 6. 현황 메뉴
    # -------------------------------------------------------------------------
    elif nav_choice == "현황":
        st.title("📊 매출 및 주문 현황")
        st.markdown("일별 주문, 주별 및 월별 판매 금액 현황을 한눈에 확인할 수 있습니다.")
        st.markdown("---")
        
        if len(st.session_state.drafts) == 0:
            st.info("📈 집계할 완료된 주문서 데이터가 아직 없습니다. 주문을 완료하면 통계가 자동 집계됩니다.")
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
            with m1:
                st.metric(label="💰 누적 총 판매금액", value=f"₩ {total_sales:,}")
            with m2:
                st.metric(label="👓 누적 총 판매수량", value=f"{total_qty:,} 개")
                
            st.markdown("---")
            st.subheader("📅 일별 판매 현황")
            daily_sales = df_orders_all.groupby('날짜')[['수량', '금액']].sum().reset_index()
            st.dataframe(daily_sales, use_container_width=True)
            
            st.subheader("🗓️ 거래처별 판매 현황")
            client_sales = df_orders_all.groupby('거래처')[['수량', '금액']].sum().reset_index()
            st.dataframe(client_sales, use_container_width=True)
