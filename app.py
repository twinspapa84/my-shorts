import streamlit as st
import os
import asyncio
import random
import urllib.parse
import io
import requests
from PIL import Image, ImageDraw
import edge_tts
from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    TextClip,
    concatenate_videoclips
)

st.set_page_config(page_title="AI 숏츠 메이커", page_icon="🎬", layout="centered")
OUTPUT_DIR = "shorts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------------------
# 안전한 무료 이미지 생성 함수 (오류 시 자동 방어)
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
            # 정상적인 이미지인지 PIL로 검증
            img = Image.open(io.BytesIO(response.content))
            img = img.convert("RGB")
            img.save(img_path, "PNG")
            success = True
    except Exception:
        success = False

    # 서버 다운 등으로 실패했을 때 앱이 멈추지 않도록 비상용 고화질 배경 자동 생성
    if not success:
        fallback_img = Image.new("RGB", (1080, 1920), color=(15, 20, 35))
        draw = ImageDraw.Draw(fallback_img)
        # 은은한 격자 무늬 배경
        for y in range(0, 1920, 80):
            draw.line([(0, y), (1080, y)], fill=(30, 40, 65), width=2)
        for x in range(0, 1080, 80):
            draw.line([(x, 0), (x, 1920)], fill=(30, 40, 65), width=2)
        fallback_img.save(img_path, "PNG")

    return img_path

# -------------------------------------------------------------
# 무료 TTS 생성 함수
# -------------------------------------------------------------
async def create_tts_async(text: str, voice: str, rate: str, output_path: str):
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)

def generate_audio(text: str, voice: str, rate: str, scene_idx: int) -> str:
    audio_path = os.path.join(OUTPUT_DIR, f"audio_{scene_idx}.mp3")
    asyncio.run(create_tts_async(text, voice, rate, audio_path))
    return audio_path

# -------------------------------------------------------------
# 영상 합성 함수
# -------------------------------------------------------------
def render_video_with_motion(scenes_data):
    clips = []
    font_path = "C:/Windows/Fonts/malgunbd.ttf" if os.name == 'nt' else "/System/Library/Fonts/Supplemental/AppleGothic.ttf"
    if not os.path.exists(font_path):
        font_path = "NanumGothicBold"

    for scene in scenes_data:
        audio = AudioFileClip(scene["audio_path"])
        duration = audio.duration

        # 줌인 모션 적용
        img_clip = ImageClip(scene["image_path"]).set_duration(duration)
        img_clip = img_clip.resize(height=1920).crop(x_center=img_clip.w/2, width=1080)
        img_clip = img_clip.resize(lambda t: 1.0 + (0.12 / duration) * t)

        # 볼드 자막
        txt_clip = TextClip(
            scene["text"],
            fontsize=50,
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

# -------------------------------------------------------------
# UI 화면
# -------------------------------------------------------------
st.title("🎬 100% 무료 AI 숏츠 제작 스튜디오")

default_scenes = [
    {
        "text": "전기차는 기어가 1단밖에 없는데, 어떻게 고속도로에서 200km로 달릴까요?",
        "prompt": "Futuristic electric car motor and single speed gearbox, cutaway 3D diagram, blue glowing power lines"
    },
    {
        "text": "비결은 감속기입니다. 일반 엔진과 달리 전기 모터는 1분에 만 번 넘게 무섭게 회전합니다.",
        "prompt": "High speed spinning electric rotor coils, magnetic energy field, hyperrealistic engineering render"
    },
    {
        "text": "모터가 8바퀴 돌 때 바퀴를 딱 1바퀴로 감속시키면, 폭발적인 힘과 최고 속도가 동시에 나옵니다.",
        "prompt": "Reduction gear system connecting to sports car wheel, precision polished steel gears in motion"
    },
    {
        "text": "변속기 없이 톱니 한 쌍으로 끝내는 단순함, 이게 바로 전기차가 빠른 진짜 이유입니다.",
        "prompt": "Cutaway chassis of electric vehicle with glowing battery pack and dual electric motors, studio dark background"
    }
]

scene_inputs = []
for i, sc in enumerate(default_scenes):
    with st.expander(f"📍 장면 {i+1} 설정", expanded=(i==0)):
        col1, col2 = st.columns([1, 1])
        with col1:
            t = st.text_area(f"자막 {i+1}", value=sc["text"], key=f"t_{i}", height=80)
        with col2:
            p = st.text_area(f"그림 프롬프트 {i+1}", value=sc["prompt"], key=f"p_{i}", height=80)
        scene_inputs.append({"text": t, "prompt": p})

st.markdown("---")
if st.button("🚀 숏츠 영상 제작하기", use_container_width=True, type="primary"):
    with st.status("🎬 숏츠 영상을 제작하고 있습니다...", expanded=True) as status:
        scenes_data = []
        for idx, item in enumerate(scene_inputs):
            st.write(f"⏳ **장면 {idx+1}/{len(scene_inputs)}** 음성 & 이미지 준비 중...")
            audio_file = generate_audio(item["text"], "ko-KR-InJoonNeural", "+15%", idx+1)
            image_file = generate_safe_image(item["prompt"], idx+1)
            scenes_data.append({
                "text": item["text"],
                "audio_path": audio_file,
                "image_path": image_file
            })

        st.write("✂️ **다이내믹 줌인 모션 & 노란색 볼드 자막 합성 중...**")
        final_video_path = render_video_with_motion(scenes_data)
        status.update(label="🎉 숏츠 영상 완성!", state="complete", expanded=False)

    st.subheader("📺 완성된 숏츠 영상 미리보기")
    st.video(final_video_path)
    with open(final_video_path, "rb") as f:
        st.download_button(
            label="📥 완성 영상 다운로드 (.mp4)",
            data=f,
            file_name="ai_shorts_video.mp4",
            mime="video/mp4",
            use_container_width=True
        )
