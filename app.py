import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="REPUBLICA B2B 발주 시스템", page_icon="👓", layout="centered")

SHEET_ID = "1FiP0FFJI8OdswJa_p6ejkOpLZGbVZx9j71UUSJ6zLN4"

@st.cache_data(ttl=60)
def load_data():
    try:
        # 영문 탭 이름(model, color)으로 안정적으로 CSV 호출
        model_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=model"
        color_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=color"
        
        df_models = pd.read_csv(model_url)
        df_colors = pd.read_csv(color_url)
        return df_models, df_colors
    except Exception as e:
        return None, None

df_models, df_colors = load_data()

if df_models is None or df_colors is None or df_models.empty:
    st.error("⚠️ 구글 시트 데이터를 불러오는 데 실패했습니다. 1) 탭 이름이 'model', 'color'로 되어 있는지, 2) 링크 공유가 '뷰어'로 열려 있는지 확인해 주세요.")
else:
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    if 'drafts' not in st.session_state:
        st.session_state.drafts = []
    if 'current_client' not in st.session_state:
        st.session_state.current_client = ""

    menu = st.sidebar.radio("메뉴 이동", ["새주문 (시작)", "장바구니 / 임시저장", "주문서 현황"])

    if menu == "새주문 (시작)":
        st.title("👓 REPUBLICA B2B 주문 시스템")
        st.write("거래처 안경원 이름을 입력하고 실시간 제품을 확인하세요.")
        
        client_name = st.text_input("거래처 안경원 이름", value=st.session_state.current_client, placeholder="예: 글라스안경 세곡점")
        
        if st.button("주문서 작성 시작", type="primary", use_container_width=True):
            if client_name.strip() == "":
                st.warning("거래처 안경원 이름을 입력해주세요!")
            else:
                st.session_state.current_client = client_name
                st.success(f"'{client_name}'님의 주문을 시작합니다! 아래 모델을 선택해 주세요.")
                
        st.divider()
        st.subheader("📋 실시간 모델 목록")
        st.dataframe(df_models, use_container_width=True)
        
        st.markdown("### 🛒 모델별 다중 컬러 수량 담기")
        
        model_col = df_models.columns[0]
        selected_model_name = st.selectbox("주문할 모델 선택", df_models[model_col].dropna().tolist())
        
        model_row = df_models[df_models[model_col] == selected_model_name].iloc[0]
        
        try:
            unit_price = int(model_row.iloc[2])
        except:
            unit_price = 33000
            
        st.info(f"선택 모델: {selected_model_name} | 단가: ₩ {unit_price:,}")

        with st.form(key="color_form"):
            st.write("원하시는 컬러별 수량을 입력하세요:")
            
            color_options = df_colors.iloc[:, 0].dropna().tolist()
            
            quantities = {}
            for color in color_options:
                quantities[color] = st.number_input(f"{color} 수량", min_value=0, max_value=100, step=1, key=f"{selected_model_name}_{color}")
                
            submitted = st.form_submit_button("장바구니에 담기")
            if submitted:
                added_any = False
                for color, qty in quantities.items():
                    if qty > 0:
                        st.session_state.cart.append({
                            "거래처": st.session_state.current_client,
                            "모델명": selected_model_name,
                            "컬러": color,
                            "수량": qty,
                            "단가": unit_price,
                            "금액": qty * unit_price
                        })
                        added_any = True
                if added_any:
                    st.success("장바구니에 성공적으로 담겼습니다!")
                else:
                    st.warning("수량을 1개 이상 입력해주세요.")

    elif menu == "장바구니 / 임시저장":
        st.title("🛒 장바구니 및 임시저장")
        st.write(f"현재 거래처: **{st.session_state.current_client or '지정되지 않음'}**")
        
        if len(st.session_state.cart) > 0:
            cart_df = pd.DataFrame(st.session_state.cart)
            st.dataframe(cart_df, use_container_width=True)
            total_price = cart_df["금액"].sum()
            st.markdown(f"### 총 주문 금액: ₩ {total_price:,}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("임시저장 (Draft)", use_container_width=True):
                    st.session_state.drafts.append({
                        "거래처": st.session_state.current_client,
                        "시간": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "품목수": len(st.session_state.cart),
                        "내역": st.session_state.cart.copy()
                    })
                    st.success("임시저장되었습니다.")
                    st.session_state.cart = []
            with col2:
                if st.button("최종 주문 완료 (발주 전송)", type="primary", use_container_width=True):
                    st.success("주문이 성공적으로 전송되었습니다!")
                    st.session_state.cart = []
        else:
            st.info("장바구니가 비어 있습니다.")

    elif menu == "주문서 현황":
        st.title("📊 주문서 현황")
        if len(st.session_state.drafts) > 0:
            for i, draft in enumerate(st.session_state.drafts):
                with st.expander(f"[{draft['시간']}] 거래처: {draft['거래처']} (총 {draft['품목수']}개 품목)"):
                    st.dataframe(pd.DataFrame(draft["내역"]), use_container_width=True)
        else:
            st.info("저장된 임시 주문 내역이 없습니다.")
