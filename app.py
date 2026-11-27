import streamlit as st
import os
import asyncio
import random
import urllib.parse
import io
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

st.set_page_config(page_title="AI 숏츠 메이커", page_icon="🎬", layout="centered")
OUTPUT_DIR = "shorts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 0. 한글 폰트 준비
FONT_PATH = os.path.join(OUTPUT_DIR, "NanumGothicBold.ttf")
if not os.path.exists(FONT_PATH):
    try:
        r = requests.get("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", timeout=15)
        with open(FONT_PATH, "wb") as f:
            f.write(r.content)
    except Exception:
        pass

# 세션 상태 관리
if "step" not in st.session_state:
    st.session_state.step = 1
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "final_video_path" not in st.session_state:
    st.session_state.final_video_path = None

# 상단 네비게이션
col_nav1, col_nav2 = st.columns(2)
with col_nav1:
    if st.session_state.step > 1 and st.button("👈 이전 단계로", use_container_width=True):
        st.session_state.step -= 1
        st.rerun()
with col_nav2:
    if st.session_state.step > 1 and st.button("🔄 처음으로 (새로 만들기)", use_container_width=True):
        st.session_state.step = 1
        st.session_state.final_video_path = None
        st.rerun()

st.markdown("---")

# 1. 고속 이미지 생성 (타임아웃 방지 & 2중 백업)
def generate_safe_image(prompt: str, idx: int) -> str:
    path = os.path.join(OUTPUT_DIR, f"scene_{idx}.png")
    style_p = f"{prompt}, 3d mechanical render, highly detailed, octane render, 8k, vertical 9:16"
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(style_p)}?width=1080&height=1920&seed={random.randint(1,999999)}&nologo=true"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=25)
        if res.status_code == 200 and len(res.content) > 10000:
            img = Image.open(io.BytesIO(res.content)).convert("RGB").resize((1080, 1920))
            img.save(path, "PNG")
            return path
    except Exception:
        pass

    backups = [
        "https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1080&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1503376780353-7e6692767b70?q=80&w=1080&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1580273916550-e323be2ae537?q=80&w=1080&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?q=80&w=1080&auto=format&fit=crop"
    ]
    b_url = backups[(idx - 1) % len(backups)]
    try:
        r = requests.get(b_url, timeout=15)
        img = Image.open(io.BytesIO(r.content)).convert("RGB").resize((1080, 1920))
        img.save(path, "PNG")
    except Exception:
        pass
    return path

# 2. TTS 음성 생성
async def create_tts(text: str, path: str):
    communicate = edge_tts.Communicate(text, "ko-KR-InJoonNeural", rate="+15%")
    await communicate.save(path)

def generate_audio(text: str, idx: int) -> str:
    path = os.path.join(OUTPUT_DIR, f"audio_{idx}.mp3")
    asyncio.run(create_tts(text, path))
    return path

# 3. 선명한 한글 자막 렌더링
def add_subtitles(img_path: str, text: str) -> str:
    img = Image.open(img_path).convert("RGBA")
    try:
        font = ImageFont.truetype(FONT_PATH, 44)
    except Exception:
        font = ImageFont.load_default()
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([(50, 1400), (1030, 1580)], fill=(0, 0, 0, 185))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)
    if len(text) > 22:
        mid = len(text) // 2
        sp = text.rfind(' ', 0, mid + 6)
        sp = mid if sp == -1 else sp
        draw.text((80, 1430), text[:sp].strip(), fill=(255, 230, 0), font=font)
        draw.text((80, 1495), text[sp:].strip(), fill=(255, 230, 0), font=font)
    else:
        draw.text((80, 1460), text, fill=(255, 230, 0), font=font)
    out_p = img_path.replace(".png", "_sub.png")
    img.convert("RGB").save(out_p, "PNG")
    return out_p

# 4. 모바일 호환 영상 합성
def render_video(scenes_data) -> str:
    clips = []
    for sc in scenes_data:
        audio = AudioFileClip(sc["audio_path"])
        img_p = add_subtitles(sc["image_path"], sc["text"])
        clip = ImageClip(img_p).set_duration(audio.duration).set_audio(audio)
        clips.append(clip)
    final_v = concatenate_videoclips(clips, method="compose")
    out_mp4 = os.path.join(OUTPUT_DIR, "final_shorts.mp4")
    final_v.write_videofile(out_mp4, fps=30, codec="libx264", audio_codec="aac", ffmpeg_params=["-pix_fmt", "yuv420p"])
    return out_mp4

# 완성형 프리셋 (100년 뒤 서울 4장면 탑재)
PRESETS = {
    "🏙️ 100년 뒤 서울의 진짜 모습": [
        {
            "text": "2126년, 100년 뒤 서울은 과연 어떤 모습으로 변해있을까요?",
            "prompt": "Futuristic Seoul 2126, cinematic aerial view of Han River with glowing holographic bridges, Namsan Seoul Tower wrapped in floating energy rings, flying autonomous sky vehicles, neon cyberpunk night atmosphere, 8k resolution, octane render, photorealistic"
        },
        {
            "text": "하늘을 나는 캡슐 열차가 도입됐지만, 출퇴근 시간 2호선 지옥철은 100년이 지나도 똑같습니다.",
            "prompt": "Futuristic Seoul subway Gangnam station platform, ultra modern transparent maglev capsule train arriving, crowded with futuristic citizens and cybernetic androids, holographic Korean destination signs '강남역 2호선', cinematic lighting, hyper-realistic"
        },
        {
            "text": "한강 위로 솟아오른 200층 높이 아파트 창밖으로는, 수천 대의 택배 드론이 밤낮없이 날아다닙니다.",
            "prompt": "Inside a luxury high-tech futuristic Seoul apartment living room looking out massive glass window, stunning night view of vertical mega-city, thousands of glowing delivery drones flying in lanes over Han river, hyper-detailed, 8k"
        },
        {
            "text": "모든 것이 첨단 기술로 바뀌어도, 가장 한국적인 고궁만큼은 서울의 중심을 굳건히 지키고 있습니다.",
            "prompt": "Gwanghwamun gate and Gyeongbokgung palace preserved in the center of futuristic Seoul, surrounded by gigantic glass skyscrapers with subtle Korean traditional rooflines, neon holographic Korean calligraphy in night sky, breathtaking majestic cinematic shot, unreal engine 5 render"
        }
    ],
    "⚡ 전기차 1단 감속기 원리": [
        {"text": "전기차는 기어가 1단밖에 없는데 고속도로에서 어떻게 200km로 달릴까요?", "prompt": "Futuristic electric car motor and single speed gearbox, cutaway 3D diagram"},
        {"text": "비결은 1분에 만 번 넘게 회전하는 모터와 감속기입니다.", "prompt": "High speed spinning electric rotor coils, magnetic energy field, hyperrealistic"},
        {"text": "모터 회전을 감속시켜 강력한 토크와 속도를 만들어냅니다.", "prompt": "Reduction gear system connecting to sports car wheel, precision steel gears"}
    ]
}

# -------------------------------------------------------------
# 1단계: 주제 선택
# -------------------------------------------------------------
if st.session_state.step == 1:
    st.header("1️⃣ 주제를 선택하세요")

    st.subheader("🔥 추천 완성형 숏츠 (원클릭)")
    if st.button("🏙️ 100년 뒤 서울의 진짜 모습 (4개 장면 완성본)", type="primary", use_container_width=True):
        st.session_state.scenes = PRESETS["🏙️ 100년 뒤 서울의 진짜 모습"]
        st.session_state.step = 2
        st.rerun()

    if st.button("⚡ 전기차 감속기 원리", use_container_width=True):
        st.session_state.scenes = PRESETS["⚡ 전기차 1단 감속기 원리"]
        st.session_state.step = 2
        st.rerun()

    st.write("---")
    st.subheader("✏️ 새 주제 직접 입력하기")
    new_topic = st.text_input("원하는 영상 주제를 적어주세요", placeholder="예: 인류 멸망 후 동물들의 세상")
    if st.button("이 주제로 빈 대본 만들기", use_container_width=True):
        topic_title = new_topic.strip() if new_topic.strip() else "새 주제"
        st.session_state.scenes = [
            {"text": f"{topic_title}의 첫 번째 장면입니다.", "prompt": f"Cinematic 3D render of {topic_title}, opening scene"},
            {"text": f"{topic_title}의 두 번째 장면입니다.", "prompt": f"Detailed technological visual of {topic_title}"},
            {"text": f"{topic_title}의 세 번째 장면입니다.", "prompt": f"Dramatic visual of {topic_title}"},
            {"text": f"{topic_title}의 마지막 결론 장면입니다.", "prompt": f"Epic cinematic conclusion of {topic_title}"}
        ]
        st.session_state.step = 2
        st.rerun()

# -------------------------------------------------------------
# 2단계: 대본 검토 및 장면 추가/삭제
# -------------------------------------------------------------
elif st.session_state.step == 2:
    st.header("2️⃣ 대본 및 장면 편집")
    st.caption("각 장면의 자막과 프롬프트를 확인하고, 아래 버튼으로 장면을 늘리거나 줄일 수 있습니다.")

    updated = []
    for i, sc in enumerate(st.session_state.scenes):
        with st.expander(f"📍 장면 {i+1} 편집", expanded=True):
            t = st.text_area(f"자막 {i+1}", value=sc["text"], key=f"t_{i}", height=70)
            p = st.text_area(f"그림 프롬프트 {i+1}", value=sc["prompt"], key=f"p_{i}", height=70)
            updated.append({"text": t, "prompt": p})
    st.session_state.scenes = updated

    # 장면 추가 / 삭제 조작 버튼
    col_add, col_del = st.columns(2)
    with col_add:
        if st.button("➕ 장면 추가하기", use_container_width=True):
            st.session_state.scenes.append({
                "text": "새로 추가된 장면의 자막입니다.",
                "prompt": "Cinematic visual, highly detailed, 8k"
            })
            st.rerun()
    with col_del:
        if len(st.session_state.scenes) > 1 and st.button("🗑️ 마지막 장면 삭제", use_container_width=True):
            st.session_state.scenes.pop()
            st.rerun()

    st.markdown("---")
    if st.button("🚀 이 대본으로 숏츠 영상 제작하기", type="primary", use_container_width=True):
        with st.status("🎬 숏츠 영상을 제작하고 있습니다...", expanded=True) as status:
            data = []
            for idx, item in enumerate(st.session_state.scenes):
                st.write(f"⏳ **장면 {idx+1}/{len(st.session_state.scenes)}** 에셋 생성 중...")
                a_p = generate_audio(item["text"], idx+1)
                i_p = generate_safe_image(item["prompt"], idx+1)
                data.append({"text": item["text"], "audio_path": a_p, "image_path": i_p})
            st.write("✂️ 영상 & 오디오 합성 중...")
            st.session_state.final_video_path = render_video(data)
            status.update(label="🎉 숏츠 영상 완성!", state="complete", expanded=False)
        st.session_state.step = 3
        st.rerun()

# -------------------------------------------------------------
# 3단계: 완성 화면 및 다운로드
# -------------------------------------------------------------
elif st.session_state.step == 3:
    st.header("🎉 영상이 완성되었습니다!")
    st.video(st.session_state.final_video_path)
    with open(st.session_state.final_video_path, "rb") as f:
        st.download_button("📥 아이폰에 영상 다운로드 (.mp4)", data=f, file_name="ai_shorts.mp4", mime="video/mp4", type="primary", use_container_width=True)
