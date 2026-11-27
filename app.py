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

st.set_page_config(page_title="100% 무료 AI 숏츠 스튜디오", page_icon="🎬", layout="wide")
OUTPUT_DIR = "shorts_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

st.title("🎬 100% 무료 AI 숏츠 제작 스튜디오")
st.caption("유료 결제 없이! 무료 고화질 Flux 이미지 + 마이크로소프트 TTS + 줌인 무빙 자막으로 완성도 높은 숏츠를 만듭니다.")

with st.sidebar:
    st.header("⚙️ 연출 설정")
    voice_choice = st.selectbox(
        "🎙️ 내레이션 목소리",
        ["ko-KR-InJoonNeural (남성 / 차분하고 신뢰감)", "ko-KR-SunHiNeural (여성 / 밝고 선명함)"]
    )
    voice_code = voice_choice.split()[0]
    speed_choice = st.slider("⚡ 내레이션 속도", min_value=1.0, max_value=1.3, value=1.15, step=0.05)
    speed_rate = f"+{int((speed_choice - 1.0) * 100)}%"
    subtitle_color = st.color_picker("🎨 자막 강조 색상", "#FFE500")

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

def render_video_with_motion(scenes_data, text_color):
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
            color=text_color,
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

st.subheader("📝 숏츠 대본 및 장면 구성")
default_scenes = [
    {
        "text": "전기차는 기어가 1단밖에 없는데, 어떻게 고속도로에서 200km로 달릴까요?",
        "prompt": "Cinematic close-up of futuristic electric vehicle gearbox and motor gears, metallic mechanism, glowing blue electrical circuits"
    },
    {
        "text": "비결은 바로 '감속기'입니다. 일반 엔진과 달리 전기 모터는 1분에 만 번 이상 엄청난 속도로 회전합니다.",
        "prompt": "High-speed spinning copper motor rotor, magnetic coils, glowing energy lines, technical engineering cross-section"
    },
    {
        "text": "모터가 8바퀴 돌 때 바퀴를 딱 1바퀴만 돌려주면, 엄청난 토크와 폭발적인 속도가 동시에 만들어집니다.",
        "prompt": "Reduction gear system connecting electric motor to car wheel, 3D mechanical schematic diagram, precision steel gears"
    },
    {
        "text": "복잡한 변속기 없이 톱니 한 쌍으로 끝내는 것, 이게 바로 전기차의 가장 무서운 혁신입니다.",
        "prompt": "Complete cutaway 3D view of an electric supercar chassis, glowing battery pack, dual motors, dark sleek showroom lighting"
    }
]

scene_inputs = []
for i, sc in enumerate(default_scenes):
    with st.expander(f"📍 장면 {i+1} 설정", expanded=(i==0)):
        col_text, col_prompt = st.columns([1, 1])
        with col_text:
            text_val = st.text_area(f"내레이션 (자막)", value=sc["text"], key=f"text_{i}", height=100)
        with col_prompt:
            prompt_val = st.text_area(f"3D 비주얼 프롬프트 (영문)", value=sc["prompt"], key=f"prompt_{i}", height=100)
        scene_inputs.append({"text": text_val, "prompt": prompt_val})

st.markdown("---")
if st.button("🚀 100% 무료 숏츠 영상 제작하기", use_container_width=True, type="primary"):
    with st.status("🎬 숏츠 영상을 제작하고 있습니다...", expanded=True) as status:
        scenes_data = []
        for idx, item in enumerate(scene_inputs):
            st.write(f"⏳ **장면 {idx+1}/{len(scene_inputs)}** 생성 중...")
            audio_file = generate_audio(item["text"], voice_code, speed_rate, idx+1)
            image_file = generate_free_flux_image(item["prompt"], idx+1)
            scenes_data.append({
                "text": item["text"],
                "audio_path": audio_file,
                "image_path": image_file
            })

        st.write("✂️ **다이내믹 줌인 모션 & 노란색 볼드 자막 합성 중...**")
        final_video_path = render_video_with_motion(scenes_data, subtitle_color)
        status.update(label="🎉 숏츠 영상 완성!", state="complete", expanded=False)

    st.subheader("📺 완성된 숏츠 영상 미리보기")
    st.video(final_video_path)
    with open(final_video_path, "rb") as f:
        st.download_button(
            label="📥 완성 영상 다운로드 (.mp4)",
            data=f,
            file_name="free_ai_shorts.mp4",
            mime="video/mp4"
        )
