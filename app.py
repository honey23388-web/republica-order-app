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

if df_models is None or df_models.empty:
    st.error("⚠️️ 구글 시트 데이터를 불러오는 데 실패했습니다.")
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

    # 모바일 최적화 CSS 주입
    st.markdown("""
        <style>
        .block-container {
            padding-top: 2.8rem !important;
            padding-bottom: 6rem !important;
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
            margin-bottom: 12px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        div.stButton > button {
            border-radius: 8px;
            font-weight: 700;
            height: 48px;
            font-size: 15px;
            transition: all 0.2s ease-in-out;
        }
        div.stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .fixed-bottom-dock {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background-color: #ffffff;
            border-top: 1px solid #e0e0e0;
            padding: 8px 12px 12px 12px;
            z-index: 999999;
            box-shadow: 0 -4px 15px rgba(0,0,0,0.08);
        }
        </style>
    """, unsafe_allow_html=True)
    
    cart_count = sum(item['수량'] for item in st.session_state.cart)

    # -------------------------------------------------------------------------
    # 왼쪽 상단 사이드바
    # -------------------------------------------------------------------------
    st.sidebar.markdown("### 👓 REPUBLICA B2B")
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🔄 최신 데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.success("캐시가 초기화되었습니다!")
        st.rerun()
        
    st.sidebar.markdown("#### 📂 추가 조회 메뉴")
    sub_menu = st.sidebar.radio(
        "조회 메뉴 선택", 
        [
            "선택 안함 (메인 화면 유지)",
            "📦 재고현황", 
            "📊 매장별 히스토리 보기", 
            "📈 실적현황"
        ],
        label_visibility="collapsed"
    )
    
    if sub_menu != "선택 안함 (메인 화면 유지)":
        if "재고현황" in sub_menu:
            active_view = "재고현황"
        elif "매장별 히스토리" in sub_menu:
            active_view = "매장별 히스토리"
        elif "실적현황" in sub_menu:
            active_view = "실적현황"
    else:
        active_view = st.session_state.active_tab

    # -------------------------------------------------------------------------
    # 메인 화면 라우팅
    # -------------------------------------------------------------------------
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

            all_model_names = df_models[model_col].astype(str).tolist()
            search_query = st.selectbox("모델 검색", ["-- 모델명 검색 또는 선택 --"] + all_model_names, label_visibility="collapsed")
            
            if search_query != "-- 모델명 검색 또는 선택 --":
                matched_row = df_models[df_models[model_col].astype(str) == search_query].iloc[0]
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
                material = str(row[material_col]).strip() if material_col else "기타"
                try:
                    price = int(row[price_col]) if price_col else 33000
                except:
                    price = 33000

                mat_lower = material.lower()
                if "티타늄" in mat_lower:
                    icon_prefix = "🔩"
                elif "아세테이트" in mat_lower:
                    icon_prefix = "🏷️"
                elif "콤비" in mat_lower:
                    icon_prefix = "🔗"
                else:
                    icon_prefix = "🕶️"

                btn_label = f"{icon_prefix} {model_name}"
                if st.button(btn_label, key=f"mat_icon_btn_{idx}", use_container_width=True):
                    st.session_state.selected_model = model_name
                    st.session_state.unit_price = price
                    st.session_state.step = "select_color"
                    st.rerun()

            if len(st.session_state.cart) > 0:
                st.markdown("---")
                if st.button("🛒 장바구니 확인 / 주문 완료", use_container_width=True):
                    st.session_state.active_tab = "장바구니"
                    st.session_state.step = "goto_cart_tab"
                    st.rerun()

        elif st.session_state.step == "select_color":
            st.markdown(f"""
                <div class="client-highlight-box">
                    📍 {st.session_state.current_client}<br>📌 {st.session_state.selected_model}
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("⬅️ 모델 다시 고르기", use_container_width=True):
                st.session_state.step = "select_model"
                st.rerun()
                
            # 🔥 불필요한 구분선과 '컬러별 수량 지정' 텍스트를 완전히 제거하여 여백 압축

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
                st.warning(f"⚠️ 매칭되는 컬러 정보를 찾지 못했습니다.")
            else:
                if st.session_state.pending_reservation_items:
                    st.warning("⚠️ **재고가 없는 제품(예약주문 대상)이 포함되어 있습니다!**")
                    
                    with st.form("reservation_confirm_form"):
                        st.write("재고가 없는 제품입니다. 예약주문으로 하시겠습니까?")
                        for p_item in st.session_state.pending_reservation_items:
                            st.markdown(f"- **{p_item['모델명']}** / {p_item['컬러']} ({p_item['수량']}개)")
                        
                        r_col1, r_col2 = st.columns(2)
                        with r_col1:
                            yes_sub = st.form_submit_button("예 (예약진행)", use_container_width=True, type="primary")
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
                                try:
                                    stock_qty = int(row.iloc[3])
                                except:
                                    stock_qty = 0
                            
                            checkbox_label = f"{color_label} (재고: {stock_qty})"
                            
                            col_chk, col_qty = st.columns([2.5, 1])
                            with col_chk:
                                st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                                is_checked = st.checkbox(checkbox_label, key=f"chk_{clean_selected_model}_{idx}")
                            with col_qty:
                                qty = st.number_input("수량", min_value=1, max_value=100, value=1, step=1, key=f"qty_{clean_selected_model}_{idx}")
                            
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
                                    st.success("🎉 장바구니 담기 성공!")
                                    st.rerun()
                            
                if len(st.session_state.cart) > 0:
                    st.markdown("---")
                    b_col1, b_col2 = st.columns(2)
                    with b_col1:
                        if st.button("➕ 다른 모델 담기", use_container_width=True):
                            st.session_state.step = "select_model"
                            st.rerun()
                    with b_col2:
                        if st.button("🛒 장바구니 확인", type="primary", use_container_width=True):
                            st.session_state.active_tab = "장바구니"
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

    # 장바구니 화면
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
                    if st.button("🗑️", key=f"cart_page_del_{idx}"):
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
                    st.success("임시저장됨")
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.rerun()
            with col2:
                if st.button("🚀 주문완료", type="primary", use_container_width=True):
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy(),
                        "요청사항": st.session_state.cart_memo.strip()
                    })
                    st.success("주문 완료됨!")
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.session_state.step = "input_client"
                    st.rerun()
            with col3:
                if st.button("🧹 비우기", use_container_width=True):
                    st.session_state.cart = []
                    st.session_state.cart_memo = ""
                    st.rerun()
        else:
            st.info("장바구니가 비어 있습니다.")

    # 주문서 화면
    elif active_view == "주문서":
        st.title("📋 주문서 리스트")
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
                        if st.button("💾 저장", key=f"save_draft_{i}", use_container_width=True, type="primary"):
                            st.success("저장됨!")
                            st.rerun()
                    with col_add:
                        if st.button("➕ 모델추가", key=f"add_more_to_draft_{i}", use_container_width=True):
                            st.session_state.current_client = draft['거래처']
                            st.session_state.cart = draft["내역"].copy()
                            st.session_state.cart_memo = draft.get("요청사항", "")
                            st.session_state.drafts.pop(i)
                            st.session_state.step = "select_model"
                            st.session_state.active_tab = "새주문"
                            st.rerun()
                    with col_cancel:
                        if st.button("❌ 취소", key=f"del_draft_{i}", use_container_width=True):
                            st.session_state.drafts.pop(i)
                            st.rerun()
        else:
            st.info("작성된 주문서가 없습니다.")

    # 재고현황 화면
    elif active_view == "재고현황":
        st.title("📦 재고 현황")
        st.markdown("---")
        if not df_colors.empty:
            st.dataframe(df_colors, use_container_width=True)
        else:
            st.warning("재고 데이터를 불러올 수 없습니다.")

    # 매장별 히스토리 화면
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
            
            ad_balance, mi_suku, sheet_memo, sheet_res = "0", "0", "없음", "0"
            if not client_row.empty:
                r = client_row.iloc[0]
                try: ad_balance = str(r.iloc[1]) if len(r) > 1 else "0"
                except: pass
                try: mi_suku = str(r.iloc[2]) if len(r) > 2 else "0"
                except: pass
                try: sheet_memo = str(r.iloc[3]) if len(r) > 3 else "없음"
                except: pass
                try: sheet_res = str(r.iloc[4]) if len(r) > 4 else "0"
                except: pass

            col_h1, col_h2, col_h3 = st.columns(3)
            with col_h1:
                st.metric(label="적립잔액", value=ad_balance)
            with col_h2:
                st.metric(label="미수금", value=mi_suku)
            with col_h3:
                st.metric(label="미출고", value=f"{sheet_res}개")
                
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
                            
            if reserved_items:
                st.dataframe(pd.DataFrame(reserved_items)[['주문시간', '모델명', '컬러', '수량']], use_container_width=True)
            else:
                st.info("미출고 예약 내역 없음")

    # 실적현황 화면
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
            with m1:
                st.metric(label="총 매출액", value=f"₩ {total_sales:,}")
            with m2:
                st.metric(label="총 판매수량", value=f"{total_qty:,}개")

    # -------------------------------------------------------------------------
    # [하단 고정 가로배치 탭 바]
    # -------------------------------------------------------------------------
    cart_badge = f" ({cart_count})" if cart_count > 0 else ""
    
    st.markdown(f"""
        <div class="fixed-bottom-dock">
            <div id="dock-target" style="display: flex; gap: 6px; justify-content: space-between;">
            </div>
        </div>
    """, unsafe_allow_html=True)

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        if st.button("📝 새주문", use_container_width=True):
            st.session_state.active_tab = "새주문"
            st.session_state.step = "input_client"
            st.rerun()
    with d2:
        cart_label = f"🛒 장바구니{cart_badge}"
        if st.button(cart_label, use_container_width=True):
            st.session_state.active_tab = "장바구니"
            st.session_state.step = "goto_cart_tab"
            st.rerun()
    with d3:
        if st.button("📋 주문서", use_container_width=True):
            st.session_state.active_tab = "주문서"
            st.rerun()
    with d4:
        if st.button("🔄 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.success("데이터 갱신 완료!")
            st.rerun()
