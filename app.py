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

# 한글 폰트 준비
FONT_PATH = os.path.join(OUTPUT_DIR, "NanumGothicBold.ttf")
if not os.path.exists(FONT_PATH):
    try:
        r = requests.get("https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf", timeout=15)
        with open(FONT_PATH, "wb") as f:
            f.write(r.content)
    except Exception:
        pass

# 상태 관리
if "step" not in st.session_state:
    st.session_state.step = 1
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "final_video_path" not in st.session_state:
    st.session_state.final_video_path = None

# 상단 네비게이션
col1, col2 = st.columns(2)
with col1:
    if st.session_state.step > 1 and st.button("👈 이전 단계로", use_container_width=True):
        st.session_state.step -= 1
        st.rerun()
with col2:
    if st.session_state.step > 1 and st.button("🔄 처음으로", use_container_width=True):
        st.session_state.step = 1
        st.session_state.final_video_path = None
        st.rerun()

st.markdown("---")

# 이미지 생성 (타임아웃 방지 및 안전 규격)
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

    # 백업 이미지
    backups = [
        "https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1080&auto=format&fit=crop",
        "https://images.unsplash.com/photo-1503376780353-7e6692767b70?q=80&w=1080&auto=format&fit=crop",
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

# 음성 생성
async def create_tts(text: str, path: str):
    await edge_tts.Communicate(text, "ko-KR-InJoonNeural", rate="+15%").save(path)

def generate_audio(text: str, idx: int) -> str:
    path = os.path.join(OUTPUT_DIR, f"audio_{idx}.mp3")
    asyncio.run(create_tts(text, path))
    return path

# 자막 합성
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

# 영상 렌더링
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

# 추천 프리셋
PRESETS = {
    "⚡ 전기차 감속기 원리": [
        {"text": "전기차는 기어가 1단인데 어떻게 200km까지 달릴까요?", "prompt": "Futuristic electric car motor and single speed gearbox, cutaway 3D diagram"},
        {"text": "비결은 1분에 만 번 넘게 회전하는 모터와 감속기입니다.", "prompt": "High speed spinning electric rotor coils, magnetic energy field, hyperrealistic"},
        {"text": "모터 회전을 감속시켜 강력한 토크와 속도를 만들어냅니다.", "prompt": "Reduction gear system connecting to sports car wheel, precision steel gears"}
    ],
    "🏙️ 100년 뒤 서울의 모습": [
        {"text": "100년 뒤 서울의 한강과 남산타워는 과연 어떤 모습일까요?", "prompt": "Futuristic Seoul city 2126 year, Namsan tower with holographic rings, flying cars over Han river"},
        {"text": "하늘을 나는 자기부상 열차가 빌딩 숲 사이를 가로지릅니다.", "prompt": "Flying high speed maglev capsule train between mega skyscraper buildings in futuristic Seoul"},
        {"text": "하지만 출퇴근 시간의 북적거림은 100년이 지나도 여전합니다.", "prompt": "Crowded futuristic Seoul street market at night with neon signs, cyberpunk traditional fusion"}
    ]
}

# 1단계: 주제 선택 및 새 주제 설정
if st.session_state.step == 1:
    st.header("1️⃣ 주제를 선택하거나 직접 입력하세요")

    st.subheader("✏️ 새 주제 직접 입력하기")
    new_topic = st.text_input("원하는 영상 주제를 적어주세요", placeholder="예: 인류가 사라진 뒤 100년 후 지구")
    if st.button("이 주제로 만들기 시작", type="primary", use_container_width=True):
        topic_title = new_topic.strip() if new_topic.strip() else "새로운 주제"
        st.session_state.scenes = [
            {"text": f"{topic_title}에 대한 첫 번째 핵심 이야기입니다.", "prompt": f"Cinematic 3D render of {topic_title}, opening scene, vertical 9:16"},
            {"text": "이 현상이 일어나는 구체적인 이유와 과정입니다.", "prompt": f"Detailed technological visual of {topic_title}, futuristic 8k"},
            {"text": "결국 이것이 우리에게 주는 놀라운 결론입니다.", "prompt": f"Dramatic conclusion cinematic wide shot of {topic_title}"}
        ]
        st.session_state.step = 2
        st.rerun()

    st.write("---")
    st.subheader("💡 추천 인기 주제 (원클릭)")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("⚡ 전기차 감속기 원리", use_container_width=True):
            st.session_state.scenes = PRESETS["⚡ 전기차 감속기 원리"]
            st.session_state.step = 2
            st.rerun()
    with col_b:
        if st.button("🏙️ 100년 뒤 서울의 모습", use_container_width=True):
            st.session_state.scenes = PRESETS["🏙️ 100년 뒤 서울의 모습"]
            st.session_state.step = 2
            st.rerun()

# 2단계: 대본 검토 및 제작
elif st.session_state.step == 2:
    st.header("2️⃣ 대본 및 장면 확인")
    updated = []
    for i, sc in enumerate(st.session_state.scenes):
        with st.expander(f"📍 장면 {i+1}", expanded=True):
            t = st.text_area(f"자막 {i+1}", value=sc["text"], key=f"t_{i}", height=70)
            p = st.text_area(f"그림 프롬프트 {i+1}", value=sc["prompt"], key=f"p_{i}", height=70)
            updated.append({"text": t, "prompt": p})
    st.session_state.scenes = updated

    if st.button("🚀 숏츠 영상 제작하기", type="primary", use_container_width=True):
        with st.status("🎬 숏츠 영상 제작 중...", expanded=True) as status:
            data = []
            for idx, item in enumerate(st.session_state.scenes):
                st.write(f"⏳ 장면 {idx+1}/{len(st.session_state.scenes)} 생성 중...")
                a_p = generate_audio(item["text"], idx+1)
                i_p = generate_safe_image(item["prompt"], idx+1)
                data.append({"text": item["text"], "audio_path": a_p, "image_path": i_p})
            st.write("✂️ 영상 합성 중...")
            st.session_state.final_video_path = render_video(data)
            status.update(label="🎉 숏츠 영상 완성!", state="complete", expanded=False)
        st.session_state.step = 3
        st.rerun()

# 3단계: 완성 화면 및 다운로드
elif st.session_state.step == 3:
    st.header("🎉 영상이 완성되었습니다!")
    st.video(st.session_state.final_video_path)
    with open(st.session_state.final_video_path, "rb") as f:
        st.download_button("📥 아이폰에 영상 다운로드 (.mp4)", data=f, file_name="ai_shorts.mp4", mime="video/mp4", type="primary", use_container_width=True)
