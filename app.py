            
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
