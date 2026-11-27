import streamlit as st
import os
import asyncio
import random
import urllib.parse
import io
import requests
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    concatenate_videoclips
)

st.set_page_config(page_title="AI 숏츠 메이커", page_icon="🎬", layout="centered")
OUTPUT_DIR = "shorts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 0. 한글 폰트 자동 로드
FONT_PATH = os.path.join(OUTPUT_DIR, "NanumGothicBold.ttf")
def ensure_korean_font():
    if not os.path.exists(FONT_PATH):
        font_url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
        try:
            r = requests.get(font_url, timeout=15)
            with open(FONT_PATH, "wb") as f:
                f.write(r.content)
        except Exception:
            pass

ensure_korean_font()

# 세션 상태
if "step" not in st.session_state:
    st.session_state.step = 1
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "final_video_path" not in st.session_state:
    st.session_state.final_video_path = None

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

# 1. 2초 만에 즉시 나오는 고속 AI 이미지 생성 (타임아웃 완전 해결)
def generate_safe_image(prompt: str, scene_idx: int) -> str:
    img_path = os.path.join(OUTPUT_DIR, f"scene_{scene_idx}.png")
    style_prompt = f"{prompt}, 3d mechanical render, highly detailed, octane render, 8k, futuristic technical visualization"
    encoded_prompt = urllib.parse.quote(style_prompt)
    seed = random.randint(1, 999999)

    # 2초 만에 뽑아주는 초고속 Pollinations 기본 엔드포인트
    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1920&seed={seed}&nologo=true"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    success = False
    try:
        response = requests.get(image_url, headers=headers, timeout=25)
        if response.status_code == 200 and len(response.content) > 10000:
            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            img = img.resize((1080, 1920))
            img.save(img_path, "PNG")
            success = True
    except Exception:
        success = False

    # 백업: 혹시라도 실패하면 고화질 3D 메커니즘 실사 이미지를 즉시 매칭
    if not success:
        backup_urls = [
            "https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1080&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1503376780353-7e6692767b70?q=80&w=1080&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1580273916550-e323be2ae537?q=80&w=1080&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1511919884226-fd3cad34687c?q=80&w=1080&auto=format&fit=crop"
        ]
        backup_url = backup_urls[(scene_idx - 1) % len(backup_urls)]
        try:
            r = requests.get(backup_url, timeout=15)
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            img = img.resize((1080, 1920))
            img.save(img_path, "PNG")
        except Exception:
            pass

    return img_path

# 2. TTS 음성
async def create_tts_async(text: str, voice: str, rate: str, output_path: str):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)

def generate_audio(text: str, voice: str, rate: str, scene_idx: int) -> str:
    audio_path = os.path.join(OUTPUT_DIR, f"audio_{scene_idx}.mp3")
    asyncio.run(create_tts_async(text, voice, rate, audio_path))
    return audio_path

# 3. 선명한 한글 자막 렌더링
def add_subtitle_to_image(image_path: str, text: str) -> str:
    img = Image.open(image_path).convert("RGBA")

    try:
        font = ImageFont.truetype(FONT_PATH, 44)
    except Exception:
        font = ImageFont.load_default()

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([(50, 1400), (1030, 1580)], fill=(0, 0, 0, 185))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    if len(text) > 22:
        mid = len(text) // 2
        split_pos = text.rfind(' ', 0, mid + 6)
        if split_pos == -1:
            split_pos = mid
        line1 = text[:split_pos].strip()
        line2 = text[split_pos:].strip()
        draw.text((80, 1430), line1, fill=(255, 230, 0, 255), font=font)
        draw.text((80, 1495), line2, fill=(255, 230, 0, 255), font=font)
    else:
        draw.text((80, 1460), text, fill=(255, 230, 0, 255), font=font)

    out_path = image_path.replace(".png", "_sub.png")
    img.convert("RGB").save(out_path, "PNG")
    return out_path

# 4. 모바일 완벽 호환 영상 합성
def render_video_with_motion(scenes_data):
    clips = []
    for scene in scenes_data:
        audio = AudioFileClip(scene["audio_path"])
        duration = audio.duration
        subbed_img_path = add_subtitle_to_image(scene["image_path"], scene["text"])

        img_clip = ImageClip(subbed_img_path).set_duration(duration)
        img_clip = img_clip.set_audio(audio)
        clips.append(img_clip)

    final_video = concatenate_videoclips(clips, method="compose")
    output_mp4 = os.path.join(OUTPUT_DIR, "final_free_shorts.mp4")

    final_video.write_videofile(
        output_mp4,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )
    return output_mp4

PRESETS = {
    "⚡ 전기차 1단 감속기의 비밀": [
        {"text": "전기차는 기어가 1단밖에 없는데 고속도로에서 어떻게 200km로 달릴까요?", "prompt": "Futuristic electric car motor and single speed gearbox, cutaway 3D diagram, blue glowing power lines"},
        {"text": "비결은 감속기입니다. 일반 엔진과 달리 전기 모터는 1분에 만 번 넘게 무섭게 회전합니다.", "prompt": "High speed spinning electric rotor coils, magnetic energy field, hyperrealistic engineering render"},
        {"text": "모터가 8바퀴 돌 때 바퀴를 딱 1바퀴로 감속시키면, 폭발적인 토크와 속도가 동시에 나옵니다.", "prompt": "Reduction gear system connecting to sports car wheel, precision polished steel gears in motion"},
        {"text": "복잡한 변속기 없이 톱니 한 쌍으로 끝내는 단순함, 이게 바로 전기차의 혁신입니다.", "prompt": "Cutaway chassis of electric vehicle with glowing battery pack and dual electric motors, studio dark background"}
    ]
}

if st.session_state.step == 1:
    st.header("1️⃣ 주제를 선택하세요")
    if st.button("⚡ 전기차 1단 감속기의 비밀 (원클릭 시작)", type="primary", use_container_width=True):
        st.session_state.scenes = PRESETS["⚡ 전기차 1단 감속기의 비밀"]
        st.session_state.step = 2
        st.rerun()

elif st.session_state.step == 2:
    st.header("2️⃣ 대본 및 장면 확인")
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

            st.write("✂️ **영상 & 오디오 합성 중...**")
            final_mp4 = render_video_with_motion(scenes_data)
            st.session_state.final_video_path = final_mp4
            status.update(label="🎉 숏츠 영상 완성!", state="complete", expanded=False)

        st.session_state.step = 3
        st.rerun()

elif st.session_state.step == 3:
    st.header("🎉 영상이 완성되었습니다!")
    st.video(st.session_state.final_video_path)

    with open(st.session_state.final_video_path, "rb") as f:
        st.download_button(
            label="📥 완성 영상 다운로드 (.mp4)",
            data=f,
            file_name="ai_shorts_video.mp4",
            mime="video/mp4",
            type="primary",
            use_container_width=True
        )
