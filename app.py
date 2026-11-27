import streamlit as st
import os
import asyncio
import random
import urllib.parse
import requests
import edge_tts
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    TextClip,
    concatenate_videoclips
)

# -------------------------------------------------------------
# 0. 앱 기본 설정
# -------------------------------------------------------------
st.set_page_config(page_title="AI 숏츠 메이커", page_icon="🎬", layout="centered")
OUTPUT_DIR = "shorts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 세션 상태 초기화 (단계별 화면 이동)
if "step" not in st.session_state:
    st.session_state.step = 1  # 1: 주제선택, 2: 씬편집, 3: 완성화면
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "final_video_path" not in st.session_state:
    st.session_state.final_video_path = None

# -------------------------------------------------------------
# 상단 네비게이션 헤더 (뒤로가기 / 처음으로)
# -------------------------------------------------------------
col_nav1, col_nav2 = st.columns([1, 1])
with col_nav1:
    if st.session_state.step > 1:
        if st.button("👈 뒤로 가기", use_container_width=True):
            st.session_state.step -= 1
            st.rerun()
with col_nav2:
    if st.session_state.step > 1:
        if st.button("🔄 처음으로 (새로 만들기)", use_container_width=True):
            st.session_state.step = 1
            st.session_state.final_video_path = None
            st.rerun()

st.markdown("---")

# -------------------------------------------------------------
# 핵심 로직 함수들 (무료 이미지, 무료 TTS, 비디오 렌더링)
# -------------------------------------------------------------
def generate_free_flux_image(prompt: str, scene_idx: int) -> str:
    style_suffix = ", highly detailed 3D technical render, unreal engine 5, octane render, 8k resolution, cinematic studio lighting, photorealistic mechanism, vertical 9:16 wallpaper"
    full_prompt = prompt + style_suffix
    encoded_prompt = urllib.parse.quote(full_prompt)
    seed = random.randint(1, 999999)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={seed}&nologo=true"
    response = requests.get(image_url, timeout=40)
    img_path = os.path.join(OUTPUT_DIR, f"flux_scene_{scene_idx}.png")
    with open(img_path, "wb") as f:
        f.write(response.content)
    return img_path

async def create_tts_async(text: str, voice: str, rate: str, output_path: str):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)

def generate_audio(text: str, voice: str, rate: str, scene_idx: int) -> str:
    audio_path = os.path.join(OUTPUT_DIR, f"audio_scene_{scene_idx}.mp3")
    asyncio.run(create_tts_async(text, voice, rate, audio_path))
    return audio_path

def render_video_with_motion(scenes_data):
    clips = []
    font_path = "C:/Windows/Fonts/malgunbd.ttf" if os.name == 'nt' else "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    if not os.path.exists(font_path):
        font_path = "NanumGothicBold"

    for scene in scenes_data:
        audio = AudioFileClip(scene["audio_path"])
        duration = audio.duration
        img_clip = ImageClip(scene["image_path"]).set_duration(duration)
        img_clip = img_clip.resize(height=1920).crop(x_center=img_clip.w/2, width=1080)
        img_clip = img_clip.resize(lambda t: 1.0 + (0.15 / duration) * t)

        txt_clip = TextClip(
            scene["text"],
            fontsize=52,
            font=font_path,
            color="#FFE500",
            stroke_color='black',
            stroke_width=4,
            method='caption',
            size=(960, None)
        ).set_duration(duration).set_position(('center', 1450))

        scene_clip = CompositeVideoClip([img_clip, txt_clip], size=(1080, 1920))
        scene_clip = scene_clip.set_audio(audio)
        clips.append(scene_clip)

    final_video = concatenate_videoclips(clips, method="compose")
    output_mp4 = os.path.join(OUTPUT_DIR, "final_free_shorts.mp4")
    final_video.write_videofile(output_mp4, fps=30, codec="libx264", audio_codec="aac")
    return output_mp4

# 프리셋 데이터
PRESETS = {
    "⚡ 전기차 1단 기어의 비밀": [
        {"text": "전기차는 기어가 1단밖에 없는데, 어떻게 고속도로에서 200km로 달릴까요?", "prompt": "Futuristic electric car motor and single speed gearbox, cutaway 3D diagram, blue glowing power lines"},
        {"text": "비결은 감속기입니다. 일반 엔진과 달리 전기 모터는 1분에 만 번 넘게 무섭게 회전합니다.", "prompt": "High speed spinning electric rotor coils, magnetic energy field, hyperrealistic engineering render"},
        {"text": "모터가 8바퀴 돌 때 바퀴를 딱 1바퀴로 감속시키면, 폭발적인 힘과 최고 속도가 동시에 나옵니다.", "prompt": "Reduction gear system connecting to sports car wheel, precision polished steel gears in motion"},
        {"text": "변속기 없이 톱니 한 쌍으로 끝내는 단순함, 이게 바로 전기차가 빠른 진짜 이유입니다.", "prompt": "Cutaway chassis of electric vehicle with glowing battery pack and dual electric motors, studio dark background"}
    ],
    "🏙️ 100년 뒤 서울의 지하철": [
        {"text": "2126년, 100년 뒤 서울 지하철 2호선은 과연 어떤 모습일까요?", "prompt": "Futuristic flying subway capsule train hovering through Seoul city sky, cyberpunk neon signs, 2126 year"},
        {"text": "하늘을 나는 자기부상 캡슐 열차로 바뀌어 강남에서 홍대까지 단 3분 만에 주파합니다.", "prompt": "Interior of ultra modern high tech futuristic train with holographic maps, glass windows overlooking Han River"},
        {"text": "하지만 출퇴근 시간 지옥철의 혼잡함은 100년이 지나도 여전히 똑같습니다.", "prompt": "Crowded futuristic Gangnam station platform with androids and cybernetically enhanced citizens"}
    ]
}

# -------------------------------------------------------------
# STEP 1: 주제 및 프리셋 선택
# -------------------------------------------------------------
if st.session_state.step == 1:
    st.header("1️⃣ 어떤 주제로 만들까요?")
    st.caption("아래 추천 주제 버튼을 누르거나 직접 대본을 작성해 보세요.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚡ 전기차의 비밀 (원클릭)", use_container_width=True):
            st.session_state.scenes = PRESETS["⚡ 전기차 1단 기어의 비밀"]
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("🏙️ 100년 뒤 서울 (원클릭)", use_container_width=True):
            st.session_state.scenes = PRESETS["🏙️ 100년 뒤 서울의 지하철"]
            st.session_state.step = 2
            st.rerun()

# -------------------------------------------------------------
# STEP 2: 대본 및 씬 확인 / 수정
# -------------------------------------------------------------
elif st.session_state.step == 2:
    st.header("2️⃣ 대본과 장면을 확인하세요")
    st.caption("내용을 직접 고치실 수 있습니다. 마음에 들면 아래 제작 버튼을 눌러주세요.")

    updated_scenes = []
    for i, sc in enumerate(st.session_state.scenes):
        with st.expander(f"📍 장면 {i+1} 내용", expanded=True):
            t = st.text_area("자막 (내레이션)", value=sc["text"], key=f"t_{i}", height=80)
            p = st.text_area("그림 설명 (영문 프롬프트)", value=sc["prompt"], key=f"p_{i}", height=80)
            updated_scenes.append({"text": t, "prompt": p})

    st.session_state.scenes = updated_scenes

    if st.button("🚀 숏츠 영상 제작 시작하기!", type="primary", use_container_width=True):
        with st.status("🎬 숏츠 영상을 제작하고 있습니다...", expanded=True) as status:
            scenes_data = []
            for idx, item in enumerate(st.session_state.scenes):
                st.write(f"⏳ **장면 {idx+1}/{len(st.session_state.scenes)}** 음성 & 3D 렌더링 중...")
                audio_file = generate_audio(item["text"], "ko-KR-InJoonNeural", "+15%", idx+1)
                image_file = generate_free_flux_image(item["prompt"], idx+1)
                scenes_data.append({"text": item["text"], "audio_path": audio_file, "image_path": image_file})

            st.write("✂️ **다이내믹 줌인 모션 & 노란색 볼드 자막 합성 중...**")
            final_mp4 = render_video_with_motion(scenes_data)
            st.session_state.final_video_path = final_mp4
            status.update(label="🎉 숏츠 영상 완성!", state="complete", expanded=False)

        st.session_state.step = 3
        st.rerun()

# -------------------------------------------------------------
# STEP 3: 완성 화면 & 대형 다운로드
# -------------------------------------------------------------
elif st.session_state.step == 3:
    st.header("🎉 영상이 완성되었습니다!")
    st.video(st.session_state.final_video_path)

    with open(st.session_state.final_video_path, "rb") as f:
        st.download_button(
            label="📥 아이폰에 영상 다운로드 (.mp4)",
            data=f,
            file_name="ai_shorts_video.mp4",
            mime="video/mp4",
            type="primary",
            use_container_width=True
        )
