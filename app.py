# 🌟 이카운트 ERP '판매주문서 입력' 전송 함수 (에러 메시지 출력 기능 추가)
def send_order_to_ecount(cart_items, client_name, memo, df_colors):
    try:
        # 1단계: ZONE 조회
        zone_res = requests.post(
            "https://oapi.ecount.com/OAPI/V2/Common/GetZone",
            json={"COM_CODE": ECOUNT_COM_CODE},
            timeout=5
        )
        zone_data = zone_res.json()
        if zone_data.get("Status") != "200" and zone_data.get("Code") != "200":
            st.error(f"이카운트 Zone 조회 실패: {zone_data}")
            return False
        zone = zone_data.get("Data", {}).get("ZONE", "1")
        
        # 2단계: 로그인 (세션 발급)
        login_res = requests.post(
            f"https://oapi{zone}.ecount.com/OAPI/V2/OAPILogin",
            json={
                "COM_CODE": ECOUNT_COM_CODE,
                "USER_ID": ECOUNT_USER_ID,
                "API_CERT_KEY": ECOUNT_API_KEY,
                "LAN_TYPE": "ko-KR"
            },
            timeout=5
        )
        login_data = login_res.json()
        if login_data.get("Status") != "200" and login_data.get("Code") != "200":
            st.error(f"이카운트 로그인 실패: {login_data}")
            return False
        session_id = login_data.get("Data", {}).get("SESSION_ID")
        if not session_id:
            st.error("이카운트 세션 ID를 받지 못했습니다.")
            return False
            
        # 3단계: 판매주문서 입력 데이터 구성
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        details = []
        
        for idx, item in enumerate(cart_items):
            prod_cd = item['모델명']
            try:
                m_clean = str(item['모델명']).split('(')[0].strip().upper()
                c_clean = str(item['컬러']).strip().upper()
                
                for _, r in df_colors.iterrows():
                    row_model = str(r.iloc[0]).split('(')[0].strip().upper()
                    row_col_code = str(r.iloc[1]).strip().upper()
                    row_col_name = str(r.iloc[2]).strip().upper()
                    row_full_col = f"{row_col_code} / {row_col_name}".strip(" /")
                    
                    if row_model == m_clean and (row_col_code in c_clean or row_col_name in c_clean or row_full_col in c_clean):
                        if len(r) > 4 and pd.notna(r.iloc[4]):
                            prod_cd = str(r.iloc[4]).strip()
                            break
            except:
                pass

            details.append({
                "LineNo": idx + 1,
                "ProdCd": str(prod_cd),
                "ProdDes": str(item['컬러']),
                "Qty": float(item['수량']),
                "Price": float(item['단가']),
                "SupplyAmt": float(item['금액']),
                "Remarks": str(memo)
            })
            
        order_payload = {
            "SESSION_ID": session_id,
            "Remote_IP": "",
            "SvcType": "A",
            "Data": {
                "UID": "",
                "IO_Date": today_str,
                "CustCd": str(client_name),
                "Remarks": str(memo),
                "Details": details
            }
        }
        
        order_res = requests.post(
            f"https://oapi{zone}.ecount.com/OAPI/V2/Sale/SaveSalesOrder?SESSION_ID={session_id}",
            json=order_payload,
            timeout=10
        )
        order_data = order_res.json()
        
        # 💡 이카운트가 거부했을 때 구체적인 에러 사유를 화면에 띄움
        if order_data.get("Status") == "200" or order_data.get("Code") == "200":
            return True
        else:
            st.error(f"❌ 이카운트 거부 사유: {order_data.get('Errors') or order_data.get('Message') or order_data}")
            return False
    except Exception as e:
        st.error(f"❌ 이카운트 통신 에러: {str(e)}")
        return False
