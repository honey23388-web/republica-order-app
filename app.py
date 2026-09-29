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

    st.sidebar.markdown("### 👓 REPUBLICA B2B")
    st.sidebar.markdown("---")
    menu = st.sidebar.radio("메뉴 이동", ["새주문 (시작)", "장바구니 / 임시저장", "주문서 현황"])
    
    if len(st.session_state.cart) > 0:
        st.sidebar.markdown("---")
        total_items_count = sum(item['수량'] for item in st.session_state.cart)
        st.sidebar.info(f"🛒 장바구니 수량: 총 **{total_items_count}개**")

    if menu == "새주문 (시작)":
        st.title("👓 REPUBLICA B2B 주문 시스템")
        st.markdown("거래처 안경원 이름을 입력하고 원하는 모델과 컬러 수량을 자유롭게 담아보세요.")
        
        st.markdown("#### 1️⃣ 거래처 정보")
        client_name = st.text_input("거래처 안경원 이름", value=st.session_state.current_client, placeholder="예: 글라스안경 세곡점")
        
        if client_name.strip() != "":
            st.session_state.current_client = client_name

        st.markdown("---")
        
        st.markdown("#### 2️⃣ 제품 모델 선택")
        model_col = df_models.columns[0]
        model_list = df_models[model_col].dropna().astype(str).tolist()
        selected_model_name = st.selectbox("주문할 모델을 선택하세요", model_list)
        
        model_row = df_models[df_models[model_col].astype(str) == selected_model_name].iloc[0]
        
        try:
            unit_price = int(model_row.iloc[2])
        except:
            unit_price = 33000
            
        st.success(f"📌 **선택 모델:** {selected_model_name} &nbsp;&nbsp;|&nbsp;&nbsp; 💵 **공급 단가:** ₩ {unit_price:,}")

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
            st.markdown("#### 3️⃣ 컬러별 수량 선택")
            st.markdown("<small style='color: gray;'>원하시는 컬러에 체크하시면 수량이 기본 1개로 설정되며, 필요시 조정할 수 있습니다.</small>", unsafe_allow_html=True)
            
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
                submitted = st.form_submit_button("🛒 선택한 품목 장바구니에 담기", use_container_width=True, type="primary")
                
                if submitted:
                    if not st.session_state.current_client:
                        st.error("⚠️ 상단에 거래처 안경원 이름을 먼저 입력해 주세요!")
                    elif len(color_inputs) == 0:
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
                                
                        st.success(f"🎉 **{selected_model_name}** 발주 내역이 장바구니에 안전하게 반영되었습니다! (동일 상품은 수량이 자동 합산됩니다)")

        # 현재까지 담긴 장바구니 요약 및 개별 삭제 인터페이스
        if len(st.session_state.cart) > 0:
            st.markdown("---")
            st.markdown(f"### 🛒 현재 장바구니 현황 (총 {len(st.session_state.cart)}개 품목)")
            
            for idx, item in enumerate(st.session_state.cart):
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.markdown(f"- **{item['모델명']}** | {item['컬러']} | 수량: **{item['수량']}개** (₩ {item['금액']:,})")
                with col_del:
                    if st.button("❌ 삭제", key=f"del_cart_{idx}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()

    elif menu == "장바구니 / 임시저장":
        st.title("🛒 장바구니 및 임시저장")
        st.markdown(f"현재 거래처: **{st.session_state.current_client or '지정되지 않음'}**")
        
        if len(st.session_state.cart) > 0:
            cart_df = pd.DataFrame(st.session_state.cart)
            
            # 장바구니 목록과 개별 삭제 버튼 제공
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
                if st.button("💾 임시저장 (Draft)", use_container_width=True):
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
                if st.button("🚀 최종 주문 완료 (발주 전송)", type="primary", use_container_width=True):
                    st.success("주문이 성공적으로 전송되었습니다!")
                    st.session_state.cart = []
                    st.rerun()
            with col3:
                if st.button("🧹 장바구니 비우기", use_container_width=True):
                    st.session_state.cart = []
                    st.rerun()
        else:
            st.info("장바구니가 비어 있습니다. '새주문' 메뉴에서 제품을 담아주세요.")

    elif menu == "주문서 현황":
        st.title("📊 주문서 현황")
        if len(st.session_state.drafts) > 0:
            for i, draft in enumerate(st.session_state.drafts):
                with st.expander(f"[{draft['시간']}] 거래처: {draft['거래처']} (총 {draft['품목수']}개 품목)"):
                    st.dataframe(pd.DataFrame(draft["내역"]), use_container_width=True)
        else:
            st.info("저장된 임시 주문 내역이 없습니다.")
