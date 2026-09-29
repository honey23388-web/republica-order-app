import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="REPUBLICA 발주 시스템", page_icon="👓", layout="centered")

if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'drafts' not in st.session_state:
    st.session_state.drafts = []
if 'current_client' not in st.session_state:
    st.session_state.current_client = ""

if 'models_df' not in st.session_state:
    st.session_state.models_df = pd.DataFrame([
        {"모델명": "REP403LOREN", "소재": "Acetate", "재고수량": 15, "단가": 33000, "컬러목록": ["C01 - BLACK", "C02 - CLEAR", "C03M - NUGGET GOLD"]},
        {"모델명": "REP402ENZO", "소재": "Titanium", "재고수량": 8, "단가": 33000, "컬러목록": ["C01 - SILVER", "C04 - GUN METAL"]},
        {"모델명": "REP411GON", "소재": "Acetate/Metal", "재고수량": 20, "단가": 33000, "컬러목록": ["C01 - BLACK", "C02 - BROWN"]}
    ])

menu = st.sidebar.radio("메뉴 이동", ["새주문 (시작)", "장바구니 / 임시저장", "주문서 현황"])

if menu == "새주문 (시작)":
    st.title("새주문")
    st.write("거래처 안경원 이름을 입력하고 주문을 시작하세요.")
    
    client_name = st.text_input("거래처 안경원 이름", value=st.session_state.current_client, placeholder="예: 글라스안경 세곡점")
    
    if st.button("주문서 작성 시작", type="primary", use_container_width=True):
        if client_name.strip() == "":
            st.warning("거래처 안경원 이름을 입력해주세요!")
        else:
            st.session_state.current_client = client_name
            st.success(f"'{client_name}'님의 주문을 시작합니다! 아래 모델을 골라주세요.")
            
    st.divider()
    st.subheader("모델 목록 및 재고 현황")
    st.dataframe(st.session_state.models_df[["모델명", "소재", "재고수량", "단가"]], use_container_width=True)
    
    st.markdown("### 🛒 모델별 다중 컬러 수량 담기")
    selected_model_name = st.selectbox("주문할 모델 선택", st.session_state.models_df["모델명"].tolist())
    
    model_info = st.session_state.models_df[st.session_state.models_df["모델명"] == selected_model_name].iloc[0]
    st.write(f"**선택한 모델:** {model_info['모델명']} (소재: {model_info['소재']})")
    
    with st.form(key="color_form"):
        st.write("원하시는 컬러별 수량을 입력하세요:")
        quantities = {}
        for color in model_info["컬러목록"]:
            quantities[color] = st.number_input(f"{color} 수량", min_value=0, max_value=100, step=1, key=color)
            
        submitted = st.form_submit_button("장바구니에 담기")
        if submitted:
            added_any = False
            for color, qty in quantities.items():
                if qty > 0:
                    st.session_state.cart.append({
                        "거래처": st.session_state.current_client,
                        "모델명": model_info["모델명"],
                        "컬러": color,
                        "수량": qty,
                        "단가": model_info["단가"],
                        "금액": qty * model_info["단가"]
                    })
                    added_any = True
            if added_any:
                st.success("장바구니에 누적되었습니다!")
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
                st.success("주문이 완료되었습니다!")
                st.session_state.cart = []
    else:
        st.info("장바구니가 비어 있습니다.")

elif menu == "주문서 현황":
    st.title("📊 주문서 현황")
    st.info("아직 완료된 주문 내역이 없습니다.")
