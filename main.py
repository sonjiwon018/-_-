import streamlit as st
import requests
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="학교 급식 찾아보기",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 학교 급식 찾아보기")
st.write("학교를 검색하고 원하는 날짜의 중식 메뉴를 확인해 보세요.")

SCHOOL_URL = "https://open.neis.go.kr/hub/schoolInfo"
MEAL_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# ==================================================
# 학교 검색
# ==================================================
@st.cache_data(ttl=3600)
def search_schools(keyword):

    def request_school(name):

        params = {
            "Type": "json",
            "SCHUL_NM": name
        }

        try:
            response = requests.get(
                SCHOOL_URL,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            return response.json()

        except Exception:
            return None

    # ----------------------------------------------
    # 1차 검색
    # ----------------------------------------------
    data = request_school(keyword)

    schools = []

    if data and "schoolInfo" in data:

        if len(data["schoolInfo"]) >= 2:

            schools = data["schoolInfo"][1].get(
                "row",
                []
            )

    # ----------------------------------------------
    # 줄임말 보완 검색
    # ----------------------------------------------
    if not schools:

        expanded_keyword = keyword

        # OO여고 → OO여자고등학교
        if expanded_keyword.endswith("여고"):

            expanded_keyword = (
                expanded_keyword[:-2]
                + "여자고등학교"
            )

        # OO고 → OO고등학교
        elif expanded_keyword.endswith("고"):

            expanded_keyword = (
                expanded_keyword[:-1]
                + "고등학교"
            )

        # 보완한 이름이 원래 검색어와 다를 때만 재검색
        if expanded_keyword != keyword:

            data = request_school(
                expanded_keyword
            )

            if data and "schoolInfo" in data:

                if len(data["schoolInfo"]) >= 2:

                    schools = data["schoolInfo"][1].get(
                        "row",
                        []
                    )

    return schools


# ==================================================
# 오늘 날짜 - 한국 시간
# ==================================================
KST = timezone(
    timedelta(hours=9)
)

today = datetime.now(KST).date()


# ==================================================
# 학교 검색 화면
# ==================================================
st.subheader("🏫 학교 찾기")

keyword = st.text_input(
    "학교 이름을 입력하세요",
    placeholder="예: 서울고등학교, 수도여고, 경기고"
)


if keyword:

    keyword = keyword.strip()

    if len(keyword) < 2:

        st.warning(
            "학교 이름을 두 글자 이상 입력해 주세요."
        )

    else:

        schools = search_schools(keyword)

        if not schools:

            st.info(
                "입력한 이름으로 학교를 찾지 못했어요. "
                "학교 이름을 다시 확인해 주세요."
            )

            # 이전 선택 학교 제거
            if "selected_school" in st.session_state:
                del st.session_state["selected_school"]

        else:

            st.success(
                f"{len(schools)}개의 학교를 찾았습니다."
            )

            # --------------------------------------
            # 학교 선택 목록
            # --------------------------------------
            school_labels = []

            for school in schools:

                school_name = school.get(
                    "SCHUL_NM",
                    ""
                )

                region = school.get(
                    "LCTN_SC_NM",
                    ""
                )

                school_labels.append(
                    f"{school_name} ({region})"
                )

            selected_label = st.selectbox(
                "학교를 선택하세요",
                school_labels
            )

            selected_index = school_labels.index(
                selected_label
            )

            selected_school = schools[
                selected_index
            ]

            st.session_state[
                "selected_school"
            ] = selected_school

            st.info(
                f"선택한 학교: "
                f"**{selected_school.get('SCHUL_NM', '')}** "
                f"({selected_school.get('LCTN_SC_NM', '')})"
            )


# ==================================================
# 날짜별 급식 조회
# ==================================================
if "selected_school" in st.session_state:

    st.divider()

    st.subheader("📅 날짜별 급식 보기")

    selected_date = st.date_input(
        "날짜를 선택하세요",
        value=today,
        max_value=today
    )

    date_str = selected_date.strftime(
        "%Y%m%d"
    )

    school = st.session_state[
        "selected_school"
    ]

    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": school[
            "ATPT_OFCDC_SC_CODE"
        ],
        "SD_SCHUL_CODE": school[
            "SD_SCHUL_CODE"
        ],
        "MMEAL_SC_CODE": "2",
        "MLSV_FROM_YMD": date_str,
        "MLSV_TO_YMD": date_str
    }

    try:

        response = requests.get(
            MEAL_URL,
            params=params,
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        rows = []

        if "mealServiceDietInfo" in data:

            if len(data["mealServiceDietInfo"]) >= 2:

                rows = data[
                    "mealServiceDietInfo"
                ][1].get(
                    "row",
                    []
                )

        st.divider()

        st.subheader(
            f"🍚 {selected_date.strftime('%Y년 %m월 %d일')} 중식"
        )

        if not rows:

            st.info(
                "이날은 등록된 중식 급식 정보가 없어요."
            )

        else:

            meal = rows[0]

            menu = meal.get(
                "DDISH_NM",
                ""
            )

            calorie = meal.get(
                "CAL_INFO",
                ""
            )

            # <br/> → 줄바꿈
            menu = menu.replace(
                "<br/>",
                "\n"
            )

            st.markdown("### 🍽️ 메뉴")

            st.markdown(
                menu.replace(
                    "\n",
                    "  \n"
                )
            )

            if calorie:

                st.metric(
                    "🔥 칼로리",
                    calorie
                )

            st.caption(
                "※ 메뉴 뒤의 괄호 숫자는 "
                "알레르기 유발 식품 번호입니다."
            )

    except Exception:

        st.error(
            "급식 정보를 불러오는 중 문제가 발생했어요."
        )
