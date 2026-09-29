import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="REPUBLICA B2B 발주 시스템", page_icon="👓", layout="centered")

SHEET_ID = "1FiP0FFJI8OdswJa_p6ejkOpLZGbVZx9j71UUSJ6zLN4"

@st.cache_data(ttl=60)
def load_data():
    try:
        model_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=model"
        color_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=color"
        
        df_models = pd.read_csv(model_url)
        df_colors = pd.read_csv(color_url)
        return df_models, df_colors
    except Exception as e:
        return None, None

df_models, df_colors = load_data()

if df_models is None or df_colors is None or df_models.empty:
    st.error("⚠️ 구글 시트 데이터를 불러오는 데 실패했습니다. 탭 이름과 공유 설정을 확인해 주세요.")
else:
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    if 'drafts' not in st.session_state:
        st.session_state.drafts = []
    if 'current_client' not in st.session_state:
        st.session_state.current_client = ""
    if 'step' not in st.session_state:
        st.session_state.step = "input_client"

    st.sidebar.markdown("### 👓 REPUBLICA B2B")
    st.sidebar.markdown("---")
    
    cart_count = sum(item['수량'] for item in st.session_state.cart)
    
    nav_choice = st.sidebar.radio(
        "메뉴 선택", 
        [
            "새주문", 
            f"장바구니 ({cart_count})", 
            "주문서", 
            "재고현황", 
            "현황"
        ]
    )

    # -------------------------------------------------------------------------
    # 1. 새주문 메뉴
    # -------------------------------------------------------------------------
    if nav_choice == "새주문":
        
        # [단계 1] 매장명 입력 화면
        if st.session_state.step == "input_client":
            st.title("👓 REPUBLICA B2B")
            st.markdown("### 새주문")
            st.markdown("#### 거래처 안경원 이름")
            
            client_input = st.text_input("거래처 입력", value=st.session_state.current_client, placeholder="예: 글라스안경 세곡점", label_visibility="collapsed")
            
            st.markdown("")
            if st.button("주문서 작성 시작", type="primary", use_container_width=True):
                if client_input.strip() == "":
                    st.warning("⚠️ 거래처 안경원 이름을 입력해주세요!")
                else:
                    st.session_state.current_client = client_input.strip()
                    st.session_state.step = "select_model"
                    st.rerun()

        # [단계 2] 모델 선택 화면 (소재별 박스 색상 적용)
        elif st.session_state.step == "select_model":
            st.title("👓 REPUBLICA B2B 주문 시스템")
            st.info(f"📍 **현재 거래처:** {st.session_state.current_client}")
            
            if st.button("🔄 거래처 다시 입력"):
                st.session_state.step = "input_client"
                st.rerun()
                
            st.markdown("---")
            st.markdown("### 제품 모델 선택")
            st.markdown("<small style='color: gray;'>소재별로 색상이 구분된 모델 박스를 확인하고 선택하세요.</small>", unsafe_allow_html=True)
            st.markdown("")
            
            model_col = df_models.columns[0]
            material_col = df_models.columns[1] if len(df_models.columns) > 1 else None
            price_col = df_models.columns[2] if len(df_models.columns) > 2 else None

            for idx, row in df_models.iterrows():
                model_name = str(row[model_col])
                material = str(row[material_col]).strip() if material_col else "기타"
                try:
                    price = int(row[price_col]) if price_col else 33000
                except:
                    price = 33000

                # [소재별 박스 배경색 및 테두리 설정]
                mat_lower = material.lower()
                if "티타늄" in mat_lower or "아세테이트" in mat_lower:
                    bg_color = "#fbf6f0"  # 옅은 브라운색
                    border_color = "#e6d5c3"
                elif "콤비" in mat_lower:
                    bg_color = "#f0f7f0"  # 옅은 그린색
                    border_color = "#cce3cc"
                else:
                    bg_color = "#f4f4f4"  # 옅은 회색
                    border_color = "#e0e0e0"

                # HTML 카드 박스 렌더링
                st.markdown(f"""
                <div style="padding: 12px 16px; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px 8px 0 0; margin-top: 10px;">
                    <b style="font-size: 16px; color: #222;">🕶️ {model_name}</b><br>
                    <span style="font-size: 13px; color: #555;">소재: <b>{material}</b> &nbsp;|&nbsp; 단가: <b>₩ {price:,}</b></span>
                </div>
                """, unsafe_allow_html=True)
                
                # 선택 버튼
                if st.button(f"👉 [{model_name}] 선택하기", key=f"btn_model_{idx}", use_container_width=True, type="primary"):
                    st.session_state.selected_model = model_name
                    st.session_state.unit_price = price
                    st.session_state.step = "select_color"
                    st.rerun()

            if len(st.session_state.cart) > 0:
                st.markdown("---")
                if st.button("🛒 장바구니 확인 / 주문 완료로 이동", use_container_width=True):
                    st.session_state.step = "goto_cart_tab"
                    st.rerun()

        # [단계 3] 컬러 및 수량 선택 화면
        elif st.session_state.step == "select_color":
            st.title("👓 REPUBLICA B2B 주문 시스템")
            st.info(f"📍 **거래처:** {st.session_state.current_client} &nbsp;|&nbsp; 📌 **모델:** {st.session_state.selected_model}")
            
            if st.button("⬅️ 모델 목록으로 돌아가기"):
                st.session_state.step = "select_model"
                st.rerun()
                
            st.markdown("---")
            st.markdown(f"### [{st.session_state.selected_model}] 컬러 및 수량 선택")
            st.markdown("<small style='color: gray;'>원하시는 컬러에 체크하시면 수량이 기본 1개로 설정되며, 필요시 조정할 수 있습니다.</small>", unsafe_allow_html=True)

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
                with st.form(key=f"multi_color_form_{selected_model_name}"):
                    color_inputs = []
                    for idx, row in matched_colors_df.iterrows():
                        col_code = str(row.iloc[1]) if len(row) > 1 else ""
                        col_name = str(row.iloc[2]) if len(row) > 2 else ""
                        color_label = f"{col_code} / {col_name}".strip(" /")
                        
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            is_checked = st.checkbox(f"**{color_label}**", key=f"chk_{clean_selected_model}_{idx}")
                        with c2:
                            qty = st.number_input("수량", min_value=1, max_value=100, value=1, step=1, key=f"qty_{clean_selected_model}_{idx}", label_visibility="collapsed")
                        
                        if is_checked:
                            color_inputs.append({"컬러": color_label, "수량": qty})
                    
                    st.markdown("")
                    submitted = st.form_submit_button("🛒 장바구니에 담기", use_container_width=True, type="primary")
                    
                    if submitted:
                        if len(color_inputs) == 0:
                            st.warning("⚠️ 체크박스로 선택된 컬러가 없습니다.")
                        else:
                            for item in color_inputs:
                                existing_item = None
                                for cart_item in st.session_state.cart:
                                    if (cart_item["거래처"] == st.session_state.current_client and 
                                        cart_item["모델명"] == selected_model_name and 
                                        cart_item["컬러"] == item["컬러"]):
                                        existing_item = cart_item
                                        break
                                
                                if existing_item:
                                    existing_item["수량"] += item["수량"]
                                    existing_item["금액"] = existing_item["수량"] * unit_price
                                else:
                                    st.session_state.cart.append({
                                        "거래처": st.session_state.current_client,
                                        "모델명": selected_model_name,
                                        "컬러": item["컬러"],
                                        "수량": item["수량"],
                                        "단가": unit_price,
                                        "금액": item["수량"] * unit_price
                                    })
                                    
                            st.success(f"🎉 성공적으로 장바구니에 담겼습니다!")
                            
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

        # 장바구니 바로가기 상태 처리
        if st.session_state.step == "goto_cart_tab":
            st.title("🛒 장바구니 현황")
            st.markdown(f"현재 거래처: **{st.session_state.current_client}**")
            
            for idx, item in enumerate(st.session_state.cart):
                c1, c2, c3 = st.columns([4, 2, 1])
                with c1:
                    st.write(f"**{item['모델명']}** / {item['컬러']}")
                with c2:
                    st.write(f"수량: {item['수량']}개 (₩ {item['금액']:,})")
                with c3:
                    if st.button("🗑️ 삭제", key=f"step_del_{idx}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
                        
            st.markdown("---")
            total_price = sum(item['금액'] for item in st.session_state.cart)
            st.markdown(f"### 💰 총 주문 금액: **₩ {total_price:,}**")
            
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
                        "내역": st.session_state.cart.copy()
                    })
                    st.success("주문이 성공적으로 완료되었습니다!")
                    st.session_state.cart = []
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
                    st.write(f"**{item['모델명']}** / {item['컬러']}")
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
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💾 임시저장", use_container_width=True):
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy()
                    })
                    st.success("임시저장되었습니다.")
                    st.session_state.cart = []
                    st.rerun()
            with col2:
                if st.button("🚀 최종 주문 완료", type="primary", use_container_width=True):
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy()
                    })
                    st.success("주문이 성공적으로 전송 완료되었습니다!")
                    st.session_state.cart = []
                    st.session_state.step = "input_client"
                    st.rerun()
            with col3:
                if st.button("🧹 장바구니 비우기", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()
        else:
            st.info("장바구니가 비어 있습니다. '새주문' 메뉴에서 제품을 담아주세요.")

    # -------------------------------------------------------------------------
    # 3. 주문서 메뉴
    # -------------------------------------------------------------------------
    elif nav_choice == "주문서":
        st.title("📋 작성된 주문서 리스트")
        st.markdown("완료된 주문서 목록을 확인하고, 필요시 주문을 취소할 수 있습니다.")
        st.markdown("---")
        
        if len(st.session_state.drafts) > 0:
            for i, draft in enumerate(st.session_state.drafts):
                col_exp, col_btn = st.columns([5, 1])
                with col_exp:
                    with st.expander(f"[{draft['시간']}] 거래처: {draft['거래처']} (총 {draft['품목수']}개 품목)"):
                        st.dataframe(pd.DataFrame(draft["내역"]), use_container_width=True)
                with col_btn:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("❌ 취소", key=f"del_draft_{i}"):
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
        
        if not df_models.empty:
            inventory_preview = df_models.copy()
            inventory_preview['실시간 재고'] = "확인 중 (ERP 연동)"
            st.dataframe(inventory_preview, use_container_width=True)
        else:
            st.warning("재고 데이터를 불러올 수 없습니다.")

    # -------------------------------------------------------------------------
    # 5. 현황 메뉴
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
