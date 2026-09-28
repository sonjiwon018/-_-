import streamlit as st
import requests
import pandas as pd
import re
import calendar
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="칼로리가 높은 날의 공통 메뉴",
    page_icon="🔥",
    layout="wide"
)

st.title("🔥 칼로리가 높은 날의 급식에 공통적으로 등장하는 메뉴가 있을까?")

st.write(
    "선택한 학교와 월의 급식 데이터를 분석하여 "
    "평균 칼로리보다 높은 날에 어떤 메뉴가 자주 등장하는지 알아봅니다."
)

MEAL_URL = (
    "https://open.neis.go.kr/hub/mealServiceDietInfo"
)


# ==================================================
# 한국 시간
# ==================================================
KST = timezone(
    timedelta(hours=9)
)

today = datetime.now(KST).date()


# ==================================================
# 학교 선택 여부 확인
# ==================================================
if "selected_school" not in st.session_state:

    st.info(
        "먼저 첫 화면에서 학교를 검색하고 선택해 주세요."
    )

    st.stop()


school = st.session_state["selected_school"]

school_name = school.get(
    "SCHUL_NM",
    ""
)

region = school.get(
    "LCTN_SC_NM",
    ""
)


st.success(
    f"🏫 분석할 학교: **{school_name} ({region})**"
)


# ==================================================
# 연도 / 월 선택
# ==================================================
st.subheader("📅 분석할 달")

col1, col2 = st.columns(2)


with col1:

    year = st.number_input(
        "연도",
        min_value=2020,
        max_value=today.year,
        value=today.year,
        step=1
    )


with col2:

    if year == today.year:

        month_range = range(
            1,
            today.month + 1
        )

    else:

        month_range = range(
            1,
            13
        )

    month = st.selectbox(
        "월",
        month_range,
        format_func=lambda x: f"{x}월"
    )


# ==================================================
# 날짜 계산
# ==================================================
last_day = calendar.monthrange(
    int(year),
    int(month)
)[1]

start_date = datetime(
    int(year),
    int(month),
    1
).date()

end_date = datetime(
    int(year),
    int(month),
    last_day
).date()


# 미래 날짜 방지
if end_date > today:
    end_date = today


# ==================================================
# 한 달 급식 데이터 가져오기
#
# 인증키 없이 사용할 수 있도록
# 5일씩 나누어 요청
# ==================================================
@st.cache_data(ttl=3600)
def get_month_meals(
    atpt_code,
    school_code,
    start_date,
    end_date
):

    all_rows = []

    current_date = start_date

    while current_date <= end_date:

        chunk_end = min(
            current_date + timedelta(days=4),
            end_date
        )

        from_ymd = current_date.strftime(
            "%Y%m%d"
        )

        to_ymd = chunk_end.strftime(
            "%Y%m%d"
        )

        params = {
            "Type": "json",

            "ATPT_OFCDC_SC_CODE":
                atpt_code,

            "SD_SCHUL_CODE":
                school_code,

            "MMEAL_SC_CODE":
                "2",

            "MLSV_FROM_YMD":
                from_ymd,

            "MLSV_TO_YMD":
                to_ymd
        }

        try:

            response = requests.get(
                MEAL_URL,
                params=params,
                timeout=15
            )

            response.raise_for_status()

            data = response.json()

        except Exception:

            current_date = (
                chunk_end +
                timedelta(days=1)
            )

            continue


        if "mealServiceDietInfo" in data:

            if len(
                data["mealServiceDietInfo"]
            ) >= 2:

                rows = data[
                    "mealServiceDietInfo"
                ][1].get(
                    "row",
                    []
                )

                all_rows.extend(rows)


        current_date = (
            chunk_end +
            timedelta(days=1)
        )


    return all_rows


# ==================================================
# 데이터 가져오기
# ==================================================
with st.spinner(
    "한 달 동안의 급식 데이터를 가져오는 중..."
):

    rows = get_month_meals(
        school[
            "ATPT_OFCDC_SC_CODE"
        ],
        school[
            "SD_SCHUL_CODE"
        ],
        start_date,
        end_date
    )


# ==================================================
# 데이터 없음
# ==================================================
if not rows:

    st.info(
        f"{year}년 {month}월에는 "
        "등록된 중식 정보가 없어요."
    )

    st.stop()


# ==================================================
# 데이터프레임
# ==================================================
df = pd.DataFrame(rows)


df["MLSV_YMD"] = pd.to_datetime(
    df["MLSV_YMD"],
    format="%Y%m%d"
)


# ==================================================
# 칼로리 숫자로 변환
#
# CAL_INFO 예:
# "856.2 Kcal"
# ==================================================
df["칼로리"] = (
    df["CAL_INFO"]
    .astype(str)
    .str.extract(
        r"([\d.]+)"
    )[0]
)

df["칼로리"] = pd.to_numeric(
    df["칼로리"],
    errors="coerce"
)


# 칼로리 없는 날 제거
df = df.dropna(
    subset=["칼로리"]
)


# 같은 날짜 중복 제거
df = df.drop_duplicates(
    subset=["MLSV_YMD"]
)


df = df.sort_values(
    "MLSV_YMD"
)


# ==================================================
# 데이터 확인
# ==================================================
if df.empty:

    st.info(
        "칼로리 정보가 있는 급식 데이터를 찾지 못했어요."
    )

    st.stop()


# ==================================================
# 월 평균 칼로리 계산
# ==================================================
average_calorie = df["칼로리"].mean()


# ==================================================
# 높은 칼로리 기준
#
# 평균보다 높은 날
# ==================================================
high_calorie_df = df[
    df["칼로리"] > average_calorie
].copy()


# ==================================================
# 기본 정보
# ==================================================
st.divider()

st.subheader(
    f"📊 {year}년 {month}월 칼로리 분석"
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "평균 칼로리",
        f"{average_calorie:.1f} Kcal"
    )


with col2:

    st.metric(
        "전체 급식일",
        f"{len(df)}일"
    )


with col3:

    st.metric(
        "평균보다 높은 날",
        f"{len(high_calorie_df)}일"
    )


st.caption(
    "※ 칼로리가 선택한 월의 평균보다 높은 날을 "
    "'칼로리가 높은 날'로 정의했습니다."
)


# ==================================================
# 평균 칼로리와 날짜별 칼로리 그래프
# ==================================================
st.divider()

st.subheader(
    "📈 날짜별 급식 칼로리"
)

chart_df = df[
    ["MLSV_YMD", "칼로리"]
].copy()

chart_df = chart_df.set_index(
    "MLSV_YMD"
)

st.line_chart(
    chart_df
)


st.caption(
    f"점선 대신 기준값을 확인하기 쉽도록 "
    f"평균 칼로리는 **{average_calorie:.1f} Kcal**입니다."
)


# ==================================================
# 높은 칼로리 날짜
# ==================================================
st.divider()

st.subheader(
    "🔥 평균보다 칼로리가 높은 날"
)


high_display = high_calorie_df[
    ["MLSV_YMD", "칼로리"]
].copy()

high_display["날짜"] = high_display[
    "MLSV_YMD"
].dt.strftime(
    "%Y-%m-%d"
)

high_display = high_display[
    ["날짜", "칼로리"]
].sort_values(
    "칼로리",
    ascending=False
)


st.dataframe(
    high_display,
    use_container_width=True,
    hide_index=True
)


# ==================================================
# 높은 칼로리 날의 메뉴 분리
# ==================================================
menu_list = []


for _, row in high_calorie_df.iterrows():

    date = row["MLSV_YMD"]

    menu_text = str(
        row.get(
            "DDISH_NM",
            ""
        )
    )

    # <br/>, <br>, <br /> 처리
    items = re.split(
        r"<br\s*/?>",
        menu_text,
        flags=re.IGNORECASE
    )


    for item in items:

        item = item.strip()

        item = re.sub(
            r"\s+",
            " ",
            item
        )

        if item:

            menu_list.append({
                "날짜": date,
                "원래메뉴": item
            })


menu_df = pd.DataFrame(
    menu_list
)


if menu_df.empty:

    st.info(
        "평균보다 높은 날의 메뉴 정보를 찾지 못했어요."
    )

    st.stop()


# ==================================================
# 메뉴 이름 정리
# ==================================================
def clean_menu(menu):

    menu = str(menu)

    # 알레르기 번호 제거
    # 예: 김치(5,6,9) → 김치
    menu = re.sub(
        r"\([^)]*\)",
        "",
        menu
    )

    # 앞뒤 기호 제거
    menu = menu.strip(
        " -•·"
    )

    # 여러 공백 정리
    menu = re.sub(
        r"\s+",
        " ",
        menu
    )

    return menu.strip()


menu_df["메뉴"] = menu_df[
    "원래메뉴"
].apply(
    clean_menu
)


# ==================================================
# 의미 없는 메뉴 제거
# ==================================================
menu_df = menu_df[
    menu_df["메뉴"].str.len() >= 2
]


menu_df = menu_df[
    ~menu_df["메뉴"].str.fullmatch(
        r"\d+"
    )
]


# ==================================================
# 메뉴별 등장 횟수 계산
# ==================================================
common_menu_df = (
    menu_df
    .groupby("메뉴")
    .agg(
        등장횟수=(
            "메뉴",
            "count"
        ),

        등장한날짜=(
            "날짜",
            "nunique"
        )
    )
    .reset_index()
)


common_menu_df = common_menu_df.sort_values(
    ["등장횟수", "메뉴"],
    ascending=[
        False,
        True
    ]
).reset_index(
    drop=True
)


# ==================================================
# 결과
# ==================================================
st.divider()

st.subheader(
    "🥗 칼로리가 높은 날에 공통적으로 등장한 메뉴"
)


if len(high_calorie_df) == 0:

    st.info(
        "월 평균보다 높은 칼로리의 급식이 없어요."
    )

    st.stop()


# 상위 메뉴
top_menu = common_menu_df.iloc[0]

top_menu_name = top_menu["메뉴"]
top_menu_count = int(
    top_menu["등장횟수"]
)


col1, col2 = st.columns(2)


with col1:

    st.metric(
        "가장 자주 등장한 메뉴",
        top_menu_name
    )


with col2:

    st.metric(
        "등장 횟수",
        f"{top_menu_count}회"
    )


# ==================================================
# 공통 메뉴 그래프
# ==================================================
st.subheader(
    "📊 높은 칼로리 날의 메뉴 등장 횟수"
)

graph_df = common_menu_df.head(
    15
).copy()

graph_df = graph_df.sort_values(
    "등장횟수",
    ascending=True
)


st.bar_chart(
    graph_df.set_index(
        "메뉴"
    )["등장횟수"]
)


st.caption(
    "※ 평균보다 높은 칼로리의 날에 등장한 메뉴 중 "
    "상위 15개를 표시했습니다."
)


# ==================================================
# 전체 결과표
# ==================================================
st.divider()

st.subheader(
    "📋 메뉴별 등장 횟수"
)


display_df = common_menu_df.copy()

display_df.insert(
    0,
    "순위",
    range(
        1,
        len(display_df) + 1
    )
)


st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ==================================================
# 질문에 대한 해석
# ==================================================
st.divider()

st.subheader(
    "💡 이 그래프로 알 수 있는 것"
)


st.write(
    f"""
{year}년 {month}월의 전체 급식 평균 칼로리는
**{average_calorie:.1f} Kcal**입니다.

따라서 이보다 높은 날을 '칼로리가 높은 날'로 정하고
메뉴를 비교했습니다.

칼로리가 높은 날에는 **{top_menu_name}**이
총 **{top_menu_count}번** 등장했습니다.

따라서 이 메뉴가 해당 월의 높은 칼로리 급식에서
얼마나 자주 등장했는지 확인할 수 있습니다.
"""
)

st.caption(
    "※ 이 분석은 메뉴의 등장 빈도를 보여주는 것이며, "
    "특정 메뉴가 칼로리를 높였다는 인과관계를 의미하지 않습니다."
)
