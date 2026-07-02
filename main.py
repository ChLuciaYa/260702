import streamlit as st
import random

st.set_page_config(page_title="MBTI 포켓몬 진로 추천 ✨", page_icon="⚡", layout="centered")

# ------------------ 스타일 ------------------
st.markdown("""
<style>
@keyframes floaty {
    0% { transform: translateY(0px); }
    50% { transform: translateY(-12px); }
    100% { transform: translateY(0px); }
}
@keyframes gradientBG {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes popIn {
    0% { transform: scale(0.7); opacity: 0; }
    70% { transform: scale(1.05); opacity: 1; }
    100% { transform: scale(1); }
}
.stApp {
    background: linear-gradient(-45deg, #ffecd2, #fcb69f, #a1c4fd, #c2e9fb);
    background-size: 400% 400%;
    animation: gradientBG 15s ease infinite;
}
.poke-img {
    animation: floaty 3s ease-in-out infinite;
}
.title-box {
    text-align: center;
    padding: 18px;
    border-radius: 20px;
    background: rgba(255,255,255,0.55);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    margin-bottom: 20px;
    animation: popIn 0.6s ease;
}
.result-card {
    background: rgba(255,255,255,0.75);
    border-radius: 24px;
    padding: 24px;
    text-align: center;
    box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    animation: popIn 0.5s ease;
    border: 3px solid rgba(255,255,255,0.8);
}
.job-pill {
    display: inline-block;
    background: linear-gradient(90deg, #ff9a9e, #fad0c4);
    color: #333;
    padding: 10px 18px;
    border-radius: 999px;
    margin: 6px;
    font-weight: 700;
    font-size: 16px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    animation: popIn 0.7s ease;
}
</style>
""", unsafe_allow_html=True)

# ------------------ 데이터 ------------------
MBTI_DATA = {
    "INTJ": {"emoji": "🧠", "name": "전략가형 천재", "pid": 65, "poke": "forura(알라카잠)",
             "jobs": ["🧩 데이터 사이언티스트", "♟️ 경영 전략 컨설턴트", "🔬 연구 개발(R&D) 엔지니어"]},
    "INTP": {"emoji": "🔍", "name": "논리적 분석가", "pid": 137, "poke": "폴리곤",
             "jobs": ["💻 소프트웨어 아키텍트", "📐 수학·이론 연구자", "🤖 AI 알고리즘 개발자"]},
    "ENTJ": {"emoji": "🔥", "name": "타고난 리더", "pid": 6, "poke": "리자몽",
             "jobs": ["🏢 스타트업 CEO", "📊 프로젝트 총괄 매니저", "⚖️ 정책 기획가"]},
    "ENTP": {"emoji": "💡", "name": "재기발랄한 발명가", "pid": 571, "poke": "조로아크",
             "jobs": ["🚀 창업가", "🎤 크리에이티브 디렉터", "🗣️ 협상 전문가"]},
    "INFJ": {"emoji": "🌙", "name": "신비로운 통찰가", "pid": 282, "poke": "가디안",
             "jobs": ["🖋️ 작가", "🧑‍⚕️ 상담심리사", "🎨 예술 치료사"]},
    "INFP": {"emoji": "🌈", "name": "무한한 상상의 몽상가", "pid": 133, "poke": "이브이",
             "jobs": ["🎬 시나리오 작가", "🎨 일러스트레이터", "🌱 사회적 기업가"]},
    "ENFJ": {"emoji": "🌟", "name": "카리스마 멘토", "pid": 448, "poke": "루카리오",
             "jobs": ["🧑‍🏫 교육자", "🗣️ 인재 코치", "📣 홍보·PR 전문가"]},
    "ENFP": {"emoji": "🎉", "name": "에너지 넘치는 활동가", "pid": 25, "poke": "피카츄",
             "jobs": ["🎤 방송인·MC", "📸 콘텐츠 크리에이터", "🎪 이벤트 기획자"]},
    "ISTJ": {"emoji": "🛡️", "name": "철벽 원칙주의자", "pid": 306, "poke": "boss마이트(보스로라)",
             "jobs": ["📋 회계사", "⚙️ 품질관리 엔지니어", "🏛️ 공무원"]},
    "ISFJ": {"emoji": "🤗", "name": "다정한 수호자", "pid": 113, "poke": "럭키",
             "jobs": ["🏥 간호사", "🧑‍🍼 보육 전문가", "📚 사서"]},
    "ESTJ": {"emoji": "💪", "name": "강력한 관리자", "pid": 68, "poke": "괴력몬",
             "jobs": ["🏭 운영 총괄 매니저", "👮 군·경찰 간부", "📈 영업 팀장"]},
    "ESFJ": {"emoji": "🎀", "name": "사교적인 조력자", "pid": 242, "poke": "해피너스",
             "jobs": ["🎊 웨딩·행사 플래너", "🧑‍⚕️ 병원 코디네이터", "🛎️ 호텔리어"]},
    "ISTP": {"emoji": "🔧", "name": "냉철한 장인", "pid": 123, "poke": "스라크",
             "jobs": ["🛠️ 정비 엔지니어", "🚁 파일럿", "🎮 게임 개발자"]},
    "ISFP": {"emoji": "🎨", "name": "감성적인 예술가", "pid": 134, "poke": "샤미드",
             "jobs": ["🖌️ 화가·디자이너", "📷 사진작가", "🎵 음악가"]},
    "ESTP": {"emoji": "⚡", "name": "행동파 모험가", "pid": 257, "poke": "번치코",
             "jobs": ["🏄 프로 스포츠 선수", "💼 세일즈 디렉터", "🚒 응급구조사"]},
    "ESFP": {"emoji": "🎤", "name": "무대의 주인공", "pid": 39, "poke": "푸린",
             "jobs": ["🎭 배우·연예인", "💃 댄서", "📺 인플루언서"]},
}

# ------------------ 헤더 ------------------
st.markdown("""
<div class="title-box">
<h1>⚡✨ MBTI 포켓몬 진로 추천기 ✨⚡</h1>
<p>당신의 MBTI를 고르면, 꼭 닮은 포켓몬과 찰떡궁합 직업 3가지를 알려드려요! 🎯🐾</p>
</div>
""", unsafe_allow_html=True)

mbti_list = list(MBTI_DATA.keys())
selected = st.selectbox("🔮 당신의 MBTI를 선택하세요", mbti_list, index=None, placeholder="MBTI 선택하기...")

if selected:
    data = MBTI_DATA[selected]
    img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{data['pid']}.png"

    st.markdown('<div class="result-card">', unsafe_allow_html=True)
    st.markdown(f"### {data['emoji']} {selected} — {data['name']}")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="poke-img">', unsafe_allow_html=True)
        st.image(img_url, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("#### 🌟 찰떡궁합 추천 직업 🌟")
    pills_html = "".join(f'<span class="job-pill">{job}</span>' for job in data["jobs"])
    st.markdown(f'<div style="text-align:center;">{pills_html}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    effect = random.choice(["balloons", "snow"])
    if effect == "balloons":
        st.balloons()
    else:
        st.snow()
else:
    st.info("👆 위에서 MBTI를 선택하면 결과가 짠! 하고 나타나요 🎁")
