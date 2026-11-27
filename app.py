import streamlit as st
import os
import asyncio
import random
import urllib.parse
import io
import requests

# -------------------------------------------------------------
# ⚠️ Pillow 10+ 와 MoviePy 1.0.3 버전 충돌 완벽 방어 패치
# -------------------------------------------------------------
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips
)

st.set_page_config(page_title="AI 숏츠 메이커", page_icon="🎬", layout="centered")
OUTPUT_DIR = "shorts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------------------
# 세션 상태 관리 (모바일 친화적인 스텝형 UI)
# -------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = 1
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "final_video_path" not in st.session_state:
    st.session_state.final_video_path = None

# 상단 네비게이션 (뒤로 가기 / 처음으로)
col_nav1, col_nav2 = st.columns([1, 1])
with col_nav1:
    if st.session_state.step > 1:
        if st.button("👈 이전 단계로", use_container_width=True):
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
# 1. 안전한 무료 이미지 생성 함수
# -------------------------------------------------------------
def generate_safe_image(prompt: str, scene_idx: int) -> str:
    img_path = os.path.join(OUTPUT_DIR, f"scene_{scene_idx}.png")
    style_suffix = ", highly detailed 3D technical render, unreal engine 5, octane render, 8k resolution, cinematic studio lighting, vertical 9:16 wallpaper"
    full_prompt = prompt + style_suffix
    encoded_prompt = urllib.parse.quote(full_prompt)
    seed = random.randint(1, 999999)
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&model=flux&seed={seed}&nologo=true"

    success = False
    try:
        response = requests.get(image_url, timeout=30)
        if response.status_code == 200 and len(response.content) > 5000:
            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            img.save(img_path, "PNG")
            success = True
    except Exception:
        success = False

    if not success:
        fallback_img = Image.new("RGB", (1080, 1920), color=(15, 20, 35))
        draw = ImageDraw.Draw(fallback_img)
        for y in range(0, 1920, 80):
            draw.line([(0, y), (1080, y)], fill=(30, 40, 65), width=2)
        fallback_img.save(img_path, "PNG")

    return img_path

# -------------------------------------------------------------
# 2. 무료 TTS 음성 생성
# -------------------------------------------------------------
async def create_tts_async(text: str, voice: str, rate: str, output_path: str):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)

def generate_audio(text: str, voice: str, rate: str, scene_idx: int) -> str:
    audio_path = os.path.join(OUTPUT_DIR, f"audio_{scene_idx}.mp3")
    asyncio.run(create_tts_async(text, voice, rate, audio_path))
    return audio_path

# -------------------------------------------------------------
# 3. 이미지에 자막을 직접 얹는 안전 렌더링 (ImageMagick 오류 원천 차단)
# -------------------------------------------------------------
def add_subtitle_to_image(image_path: str, text: str) -> str:
    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # 기본 폰트 로드
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
    except Exception:
        font = ImageFont.load_default()

    # 하단 자막 배경 반투명 박스
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([(60, 1400), (1020, 1580)], fill=(0, 0, 0, 180))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # 텍스트 그리기
    draw.text((100, 1450), text, fill=(255, 230, 0, 255), font=font)

    out_path = image_path.replace(".png", "_sub.png")
    img.convert("RGB").save(out_path, "PNG")
    return out_path

# -------------------------------------------------------------
# 4. 무빙 비디오 합성
# -------------------------------------------------------------
def render_video_with_motion(scenes_data):
    clips = []
    for scene in scenes_data:
        audio = AudioFileClip(scene["audio_path"])
        duration = audio.duration

        # 자막이 입혀진 이미지 생성
        subbed_img_path = add_subtitle_to_image(scene["image_path"], scene["text"])

        img_clip = ImageClip(subbed_img_path).set_duration(duration)
        img_clip = img_clip.resize(height=1920).crop(x_center=img_clip.w/2, width=1080)

        # 안전한 줌인 모션
        img_clip = img_clip.resize(lambda t: 1.0 + (0.10 / duration) * t)
        img_clip = img_clip.set_audio(audio)
        clips.append(img_clip)

    final_video = concatenate_videoclips(clips, method="compose")
    output_mp4 = os.path.join(OUTPUT_DIR, "final_free_shorts.mp4")
    final_video.write_videofile(output_mp4, fps=30, codec="libx264", audio_codec="aac")
    return output_mp4

# 추천 프리셋
PRESETS = {
    "⚡ 전기차 1단 감속기의 비밀": [
        {"text": "전기차는 기어가 1단밖에 없는데 고속도로에서 어떻게 200km로 달릴까요?", "prompt": "Futuristic electric car motor and single speed gearbox, cutaway 3D diagram, blue glowing power lines"},
        {"text": "비결은 감속기입니다. 일반 엔진과 달리 전기 모터는 1분에 만 번 넘게 무섭게 회전합니다.", "prompt": "High speed spinning electric rotor coils, magnetic energy field, hyperrealistic engineering render"},
        {"text": "모터가 8바퀴 돌 때 바퀴를 딱 1바퀴로 감속시키면, 폭발적인 토크와 속도가 동시에 나옵니다.", "prompt": "Reduction gear system connecting to sports car wheel, precision polished steel gears in motion"},
        {"text": "복잡한 변속기 없이 톱니 한 쌍으로 끝내는 단순함, 이게 바로 전기차의 혁신입니다.", "prompt": "Cutaway chassis of electric vehicle with glowing battery pack and dual electric motors, studio dark background"}
    ]
}

# -------------------------------------------------------------
# 화면 1: 주제 선택
# -------------------------------------------------------------
if st.session_state.step == 1:
    st.header("1️⃣ 주제를 선택하세요")
    st.caption("원클릭 프리셋을 누르면 대본이 자동으로 채워집니다.")

    if st.button("⚡ 전기차 1단 감속기의 비밀 (원클릭 시작)", type="primary", use_container_width=True):
        st.session_state.scenes = PRESETS["⚡ 전기차 1단 감속기의 비밀"]
        st.session_state.step = 2
        st.rerun()

# -------------------------------------------------------------
# 화면 2: 대본 검토 및 제작 시작
# -------------------------------------------------------------
elif st.session_state.step == 2:
    st.header("2️⃣ 대본 및 장면 확인")
    st.caption("내용을 확인하고 아래 버튼을 누르면 영상이 제작됩니다.")

    for i, sc in enumerate(st.session_state.scenes):
        with st.expander(f"📍 장면 {i+1} 내용", expanded=False):
            st.write(f"**자막**: {sc['text']}")
            st.write(f"**그림 프롬프트**: {sc['prompt']}")

    st.markdown("---")
    if st.button("🚀 숏츠 영상 제작하기", type="primary", use_container_width=True):
        with st.status("🎬 숏츠 영상을 제작하고 있습니다...", expanded=True) as status:
            scenes_data = []
            for idx, item in enumerate(st.session_state.scenes):
                st.write(f"⏳ **장면 {idx+1}/{len(st.session_state.scenes)}** 에셋 준비 중...")
                audio_file = generate_audio(item["text"], "ko-KR-InJoonNeural", "+15%", idx+1)
                image_file = generate_safe_image(item["prompt"], idx+1)
                scenes_data.append({"text": item["text"], "audio_path": audio_file, "image_path": image_file})

            st.write("✂️ **다이내믹 줌인 모션 & 영상 합성 중...**")
            final_mp4 = render_video_with_motion(scenes_data)
            st.session_state.final_video_path = final_mp4
            status.update(label="🎉 숏츠 영상 완성!", state="complete", expanded=False)

        st.session_state.step = 3
        st.rerun()

# -------------------------------------------------------------
# 화면 3: 완성 및 대형 다운로드 화면
# -------------------------------------------------------------
elif st.session_state.step == 3:
    st.header("🎉 영상이 완성되었습니다!")
    st.video(st.session_state.final_video_path)

    with open(st.session_state.final_video_path, "rb") as f:
        st.download_button(
            label="📥 아이폰에 완성 영상 다운로드 (.mp4)",
            data=f,
            file_name="ai_shorts_video.mp4",
            mime="video/mp4",
            type="primary",
            use_container_width=True
        )
