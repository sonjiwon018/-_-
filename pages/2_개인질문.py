import streamlit as st
import requests
import pandas as pd
import re

st.set_page_config(
    page_title="칼로리가 높은 날에 반복되는 반찬",
    page_icon="🔥",
    layout="wide"
)

API_URL = "https://open.neis.go.kr/hub"


# =========================================================
# 급식 데이터 가져오기
# =========================================================
@st.cache_data(ttl=3600)
def get_meals(office_code, school_code, year, month):

    start_date = f"{year}{month:02d}01"

    if month == 12:
        next_month = f"{year + 1}0101"
    else:
        next_month = f"{year}{month + 1:02d}01"

    end_date = (
        pd.to_datetime(next_month)
        - pd.Timedelta(days=1)
    ).strftime("%Y%m%d")

    url = f"{API_URL}/mealServiceDietInfo"

    all_rows = []
    page = 1

    while True:

        params = {
            "Type": "json",
            "pIndex": page,
            "pSize": 1000,
            "ATPT_OFCDC_SC_CODE": office_code,
            "SD_SCHUL_CODE": school_code,
            "MLSV_FROM_YMD": start_date,
            "MLSV_TO_YMD": end_date
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        if "mealServiceDietInfo" not in data:
            break

        rows = data["mealServiceDietInfo"][1].get(
            "row",
            []
        )

        if not rows:
            break

        all_rows.extend(rows)

        if len(rows) < 1000:
            break

        page += 1

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    df["날짜"] = pd.to_datetime(
        df["MLSV_YMD"],
        format="%Y%m%d",
        errors="coerce"
    )

    df["메뉴"] = (
        df["DDISH_NM"]
        .fillna("")
        .astype(str)
    )

    # -----------------------------------------------------
    # CAL_INFO에서 숫자만 추출
    # 예: "712.4 Kcal" → 712.4
    # -----------------------------------------------------
    df["칼로리"] = (
        df["CAL_INFO"]
        .fillna("")
        .astype(str)
        .str.extract(
            r"([\d,]+(?:\.\d+)?)"
        )[0]
        .str.replace(",", "", regex=False)
    )

    df["칼로리"] = pd.to_numeric(
        df["칼로리"],
        errors="coerce"
    )

    return df


# =========================================================
# 메뉴 이름 정리
# =========================================================
def clean_menu(menu):

    menu = re.sub(
        r"<br\s*/?>",
        "\n",
        menu,
        flags=re.IGNORECASE
    )

    menu = re.sub(
        r"\(\s*\d+(?:\s*[.,]\s*\d+)*\s*\)",
        "",
        menu
    )

    menu = re.sub(
        r"<[^>]+>",
        "",
        menu
    )

    return menu


# =========================================================
# 메뉴 분리
# =========================================================
def make_menu_rows(df):

    rows = []

    for _, row in df.iterrows():

        menu_text = clean_menu(row["메뉴"])

        menus = menu_text.split("\n")

        for menu in menus:

            menu = menu.strip()

            if not menu:
                continue

            rows.append(
                {
                    "날짜": row["날짜"],
                    "반찬": menu
                }
            )

    return pd.DataFrame(rows)


# =========================================================
# 화면
# =========================================================
st.title(
    "🔥 칼로리가 높은 날에 반복해서 등장하는 반찬이 있을까?"
)

st.write(
    "선택한 달의 평균 칼로리보다 높은 날만 골라서 "
    "그날들의 메뉴를 비교합니다."
)

st.divider()


# =========================================================
# 학교 확인
# =========================================================
if "school_code" not in st.session_state:

    st.warning(
        "먼저 첫 화면에서 학교를 선택해 주세요."
    )

    st.stop()


school_name = st.session_state["school_name"]
office_code = st.session_state["office_code"]
school_code = st.session_state["school_code"]


st.info(
    f"현재 선택된 학교: **{school_name}**"
)


# =========================================================
# 월 선택
# =========================================================
col1, col2 = st.columns(2)

with col1:

    year = st.number_input(
        "연도",
        min_value=2020,
        max_value=2035,
        value=2026,
        step=1
    )

with col2:

    month = st.selectbox(
        "분석할 월",
        range(1, 13),
        index=0
    )


# =========================================================
# 분석
# =========================================================
if st.button(
    "🔎 칼로리가 높은 날 분석하기",
    type="primary"
):

    with st.spinner(
        "한 달 전체 급식 데이터를 분석하고 있습니다..."
    ):

        df = get_meals(
            office_code,
            school_code,
            year,
            month
        )


    if df.empty:

        st.warning(
            "선택한 달의 급식 데이터가 없습니다."
        )

        st.stop()


    # -----------------------------------------------------
    # 칼로리 데이터가 있는 행만 사용
    # -----------------------------------------------------
    calorie_df = df.dropna(
        subset=["칼로리"]
    ).copy()


    if calorie_df.empty:

        st.warning(
            "칼로리 정보가 있는 급식 데이터가 없습니다."
        )

        st.stop()


    # -----------------------------------------------------
    # 중요:
    # 한 달 전체 급식의 평균 칼로리 계산
    # -----------------------------------------------------
    monthly_average = calorie_df["칼로리"].mean()


    # -----------------------------------------------------
    # 평균보다 높은 날 찾기
    # -----------------------------------------------------
    high_calorie = calorie_df[
        calorie_df["칼로리"] > monthly_average
    ].copy()


    # =====================================================
    # 평균 칼로리 표시
    # =====================================================
    st.divider()

    st.header("📌 이 달의 칼로리 기준")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "월 평균 칼로리",
            f"{monthly_average:.1f} kcal"
        )

    with col2:
        st.metric(
            "평균보다 높은 급식",
            f"{len(high_calorie)}건"
        )

    with col3:
        st.metric(
            "전체 급식",
            f"{len(calorie_df)}건"
        )


    st.caption(
        "※ '칼로리가 높은 날'은 선택한 월의 전체 급식 평균 칼로리보다 "
        "높은 날로 정의했습니다."
    )


    # =====================================================
    # 높은 칼로리 날짜의 급식
    # =====================================================
    st.divider()

    st.header(
        "🔥 평균보다 칼로리가 높은 급식"
    )

    high_display = high_calorie[
        ["날짜", "급식구분", "칼로리"]
    ].copy()

    high_display["날짜"] = (
        high_display["날짜"]
        .dt.strftime("%Y-%m-%d")
    )

    high_display = high_display.sort_values(
        "날짜"
    )

    st.dataframe(
        high_display,
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 높은 칼로리 날짜의 메뉴만 추출
    # =====================================================
    menu_df = make_menu_rows(
        high_calorie
    )


    if menu_df.empty:

        st.warning(
            "높은 칼로리 날짜에서 분석할 메뉴를 찾지 못했습니다."
        )

        st.stop()


    # =====================================================
    # 메뉴별 등장 횟수
    # =====================================================
    result = (
        menu_df
        .groupby("반찬")
        .agg(
            등장횟수=("반찬", "size"),
            등장날짜=("날짜", "nunique")
        )
        .reset_index()
    )


    # -----------------------------------------------------
    # 실제 등장 날짜
    # -----------------------------------------------------
    date_map = (
        menu_df
        .groupby("반찬")["날짜"]
        .apply(
            lambda x: ", ".join(
                sorted(
                    x.dt.day.astype(str).unique(),
                    key=lambda v: int(v)
                )
            )
        )
        .reset_index(name="등장날짜")
    )


    result = (
        result
        .drop(columns=["등장날짜"])
        .merge(
            date_map,
            on="반찬"
        )
    )


    # -----------------------------------------------------
    # 등장 횟수 높은 순서
    # -----------------------------------------------------
    result = result.sort_values(
        ["등장횟수", "반찬"],
        ascending=[False, True]
    ).reset_index(drop=True)


    result.insert(
        0,
        "순위",
        range(1, len(result) + 1)
    )


    result["등장날짜"] = (
        result["등장날짜"]
        .apply(
            lambda x: ", ".join(
                f"{d}일"
                for d in x.split(", ")
            )
        )
    )


    # =====================================================
    # 결과 표
    # =====================================================
    st.divider()

    st.header(
        "🥗 칼로리가 높은 날에 등장한 메뉴"
    )

    st.dataframe(
        result[
            [
                "순위",
                "반찬",
                "등장횟수",
                "등장날짜"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )


    # =====================================================
    # 반복 등장 메뉴만
    # =====================================================
    repeated = result[
        result["등장횟수"] >= 2
    ].copy()


    st.divider()

    st.header(
        "🔁 칼로리가 높은 날에 중복 등장한 반찬"
    )


    if repeated.empty:

        st.info(
            "평균보다 칼로리가 높은 날들 사이에서 "
            "2번 이상 반복해서 등장한 메뉴가 없습니다."
        )

    else:

        chart_df = repeated.head(10).copy()

        chart_df = chart_df.sort_values(
            "등장횟수",
            ascending=True
        )

        st.bar_chart(
            chart_df.set_index("반찬")["등장횟수"]
        )


    # =====================================================
    # 해석
    # =====================================================
    st.divider()

    st.header(
        "💡 이 그래프로 알 수 있는 것"
    )


    if repeated.empty:

        st.write(
            f"{year}년 {month}월의 평균 칼로리는 "
            f"**{monthly_average:.1f} kcal**였습니다. "
            "이 평균보다 높은 날만 따로 비교했을 때, "
            "2번 이상 반복해서 등장한 메뉴는 없었습니다."
        )

    else:

        top = repeated.iloc[0]

        st.write(
            f"{year}년 {month}월의 평균 칼로리는 "
            f"**{monthly_average:.1f} kcal**였습니다."
        )

        st.write(
            f"이 평균보다 높은 날의 급식을 비교한 결과, "
            f"**{top['반찬']}**이 "
            f"**{top['등장횟수']}회**로 가장 많이 반복해서 "
            f"등장했습니다."
        )

        st.write(
            "따라서 이 결과를 통해 평균보다 칼로리가 높은 날의 "
            "급식에서 어떤 메뉴가 반복적으로 등장하는지 "
            "확인할 수 있습니다."
        )

    st.caption(
        "※ 이 분석은 '높은 칼로리'와 메뉴의 반복적인 등장 여부를 "
        "비교하는 것이며, 메뉴가 칼로리를 높이는 원인이라고 "
        "해석하는 것은 아닙니다."
    )
