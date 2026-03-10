import streamlit as st
import os
import re
import tempfile
import random
from itertools import groupby
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import moviepy.editor as mpy

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(page_title="자동 영상 제작", page_icon="🎬", layout="wide")


# ─── SRT Parser ─────────────────────────────────────────────────────────────
def parse_srt(content: str) -> list:
    subtitles = []
    blocks = re.split(r"\n\s*\n", content.strip())

    def ts_to_sec(ts: str) -> float:
        h, m, s_ms = ts.split(":")
        s, ms = s_ms.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    for block in blocks:
        lines = [l.strip() for l in block.strip().split("\n") if l.strip()]
        if len(lines) < 3:
            continue
        for j, line in enumerate(lines):
            m = re.match(
                r"(\d{2}:\d{2}:\d{2},\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2},\d{3})", line
            )
            if m:
                text = " ".join(lines[j + 1 :])
                subtitles.append(
                    {
                        "index": int(lines[0]) if lines[0].isdigit() else len(subtitles) + 1,
                        "start": ts_to_sec(m.group(1)),
                        "end": ts_to_sec(m.group(2)),
                        "text": text,
                    }
                )
                break
    return subtitles


# ─── Font ────────────────────────────────────────────────────────────────────
_font_cache: dict = {}


def get_font(size: int) -> ImageFont.FreeTypeFont:
    if size in _font_cache:
        return _font_cache[size]
    candidates = [
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font = None
    for p in candidates:
        try:
            font = ImageFont.truetype(p, size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()
    _font_cache[size] = font
    return font


# ─── Image helpers ───────────────────────────────────────────────────────────
def resize_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Scale + center-crop to exactly w×h."""
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return img.crop((x, y, x + w, y + h))


def draw_subtitle(img: Image.Image, text: str, font_size: int = 38) -> Image.Image:
    """Render Korean subtitle with semi-transparent background."""
    if not text.strip():
        return img
    img = img.copy().convert("RGBA")
    w, h = img.size
    draw = ImageDraw.Draw(img)
    font = get_font(font_size)

    # Character-level wrap (works for Korean + mixed text)
    max_line_w = w - 80
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_line_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    if not lines:
        return img.convert("RGB")

    line_h = font_size + 8
    pad = 12
    margin_bottom = 40
    box_y1 = h - line_h * len(lines) - pad * 2 - margin_bottom
    box_y2 = h - margin_bottom

    # Semi-transparent background
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    try:
        od.rounded_rectangle([(20, box_y1), (w - 20, box_y2)], radius=8, fill=(0, 0, 0, 160))
    except AttributeError:
        od.rectangle([(20, box_y1), (w - 20, box_y2)], fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tx = (w - (bbox[2] - bbox[0])) // 2
        ty = box_y1 + pad + i * line_h
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            draw.text((tx + dx, ty + dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((tx, ty), line, font=font, fill=(255, 255, 255, 255))

    return img.convert("RGB")


# ─── Animation helper ────────────────────────────────────────────────────────
# 각 애니메이션: (이름, x_start, x_end, y_start, y_end, z_start, z_end)
# x/y 는 big_img 내 crop 시작점 비율 (0=왼쪽/위, 1=오른쪽/아래)
# z 는 zoom 배율 (1.0=full, 1.25=125% zoom-in)
_ANIM_PRESETS = [
    ("줌인",          0.5, 0.5, 0.5, 0.5, 1.00, 1.25),
    ("줌아웃",        0.5, 0.5, 0.5, 0.5, 1.25, 1.00),
    ("왼→오른",       0.0, 1.0, 0.5, 0.5, 1.15, 1.15),
    ("오른→왼",       1.0, 0.0, 0.5, 0.5, 1.15, 1.15),
    ("위→아래",       0.5, 0.5, 0.0, 1.0, 1.15, 1.15),
    ("아래→위",       0.5, 0.5, 1.0, 0.0, 1.15, 1.15),
    ("좌상→우하",     0.0, 1.0, 0.0, 1.0, 1.15, 1.15),
    ("우하→좌상",     1.0, 0.0, 1.0, 0.0, 1.15, 1.15),
    ("좌하→우상",     0.0, 1.0, 1.0, 0.0, 1.15, 1.15),
    ("우상→좌하",     1.0, 0.0, 0.0, 1.0, 1.15, 1.15),
]


def _lerp(a, b, p):
    return a + (b - a) * p


def make_anim_clip(img_path: str, duration: float, vw: int, vh: int,
                   fps: int, preset: tuple) -> "mpy.VideoClip":
    """preset = (name, xs, xe, ys, ye, zs, ze)"""
    _, xs, xe, ys, ye, zs, ze = preset
    sf = max(zs, ze)                         # 필요한 최대 배율만큼 이미지 확대
    sf = max(sf, 1.01)
    big = resize_cover(
        Image.open(img_path).convert("RGB"),
        int(vw * sf), int(vh * sf),
    )
    arr = np.array(big)
    ih_a, iw_a = arr.shape[:2]

    def make_frame(t, _arr=arr, _dur=duration,
                   _xs=xs, _xe=xe, _ys=ys, _ye=ye,
                   _zs=zs, _ze=ze, _sf=sf, w=vw, h=vh):
        p = min(t / _dur, 1.0) if _dur > 0 else 0
        z = _lerp(_zs, _ze, p)
        cw, ch = max(1, int(w / z * _sf)), max(1, int(h / z * _sf))
        cw, ch = min(cw, iw_a), min(ch, ih_a)

        max_ox = iw_a - cw
        max_oy = ih_a - ch
        ox = int(_lerp(_xs, _xe, p) * max_ox)
        oy = int(_lerp(_ys, _ye, p) * max_oy)
        ox = max(0, min(ox, max_ox))
        oy = max(0, min(oy, max_oy))

        frame = Image.fromarray(_arr[oy:oy + ch, ox:ox + cw]).resize((w, h), Image.LANCZOS)
        return np.array(frame)

    return mpy.VideoClip(make_frame, duration=duration).set_fps(fps)


# ─── Video creation ──────────────────────────────────────────────────────────
def create_video(
    image_paths: list,
    subtitles: list,
    audio_path: str,
    output_path: str,
    video_size: tuple = (1280, 720),
    premium: bool = False,
    font_size: int = 38,
    fps: int = 24,
    anim_mode: str = "random",   # "random" | preset 이름
    progress_cb=None,
):
    vw, vh = video_size
    clips = []
    n = len(subtitles)
    n_imgs = len(image_paths)

    # 각 자막에 이미지 인덱스 할당
    tagged = [(min(i * n_imgs // n, n_imgs - 1), sub) for i, sub in enumerate(subtitles)]

    # 같은 이미지 인덱스가 연속되는 구간끼리 묶기
    groups = []
    for img_idx, group_iter in groupby(tagged, key=lambda x: x[0]):
        group_subs = [s for _, s in group_iter]
        total_dur = sum(max(s["end"] - s["start"], 0.1) for s in group_subs)
        groups.append((img_idx, total_dur))

    n_groups = len(groups)
    for gi, (img_idx, duration) in enumerate(groups):
        if progress_cb:
            progress_cb(gi / n_groups * 0.80, f"클립 {gi + 1}/{n_groups} 생성 중...")

        img_path = image_paths[img_idx]

        if premium:
            # ── 애니메이션: 전체 구간 동안 천천히 움직임 ──────────────────
            if anim_mode == "random":
                preset = random.choice(_ANIM_PRESETS)
            else:
                preset = next((p for p in _ANIM_PRESETS if p[0] == anim_mode),
                              random.choice(_ANIM_PRESETS))
            clip = make_anim_clip(img_path, duration, vw, vh, fps, preset)
        else:
            # ── Static image ───────────────────────────────────────────────
            base = resize_cover(Image.open(img_path).convert("RGB"), vw, vh)
            clip = mpy.ImageClip(np.array(base)).set_duration(duration)

        clips.append(clip)

    if progress_cb:
        progress_cb(0.82, "클립 합치는 중...")

    final = mpy.concatenate_videoclips(clips, method="compose")

    if audio_path and os.path.exists(audio_path):
        if progress_cb:
            progress_cb(0.86, "오디오 합치는 중...")
        audio = mpy.AudioFileClip(audio_path)
        audio_dur = audio.duration
        vid_dur = final.duration

        if audio_dur > vid_dur:
            # 오디오가 더 길면 마지막 이미지를 늘려서 오디오 길이에 맞춤
            last_clip = clips[-1]
            extra = audio_dur - vid_dur
            extended = last_clip.set_duration(last_clip.duration + extra)
            final = mpy.concatenate_videoclips(clips[:-1] + [extended], method="compose")
        elif audio_dur < vid_dur:
            final = final.subclip(0, audio_dur)

        final = final.set_audio(audio)

    if progress_cb:
        progress_cb(0.90, "MP4 인코딩 중... (잠시 기다려 주세요)")

    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast" if not premium else "fast",
        threads=4,
        logger=None,
    )

    # 파일 핸들 해제 (Windows PermissionError 방지)
    final.close()
    for c in clips:
        c.close()

    if progress_cb:
        progress_cb(1.0, "완료!")


# ─── UI ──────────────────────────────────────────────────────────────────────
st.title("🎬 자동 영상 변환")
st.markdown("이미지 + SRT 자막 + 오디오(WAV/MP3) → MP4 영상")

# ── 렌더링 모드 ──────────────────────────────────────────────────────────────
st.subheader("🖥️ 렌더링 모드 선택")
st.markdown("원하시는 작업 방식을 선택해 주세요:")

mode_label = st.radio(
    "mode",
    [
        "⚡ 초고속 모드 (정지 화면) : 1~2분 내외로 빠르게 렌더링 완성",
        "🎬 프리미엄 모드 (줌인/줌아웃) : 사진이 미세하게 움직이는 고퀄리티 모션 적용 "
        "(기본 20~30분 이상 소요. 이미지 수에 따라 시간이 더 걸릴 수 있으니, "
        "렌더링을 켜두시고 커피 한잔 드시거나 다른 업무를 편하게 보고 오세요!)",
    ],
    index=1,
    label_visibility="collapsed",
)
mode = "fast" if "초고속" in mode_label else "premium"

st.divider()

# ── 파일 업로드 ──────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🎵 1. 음성 (.wav / .mp3)")
    audio_file = st.file_uploader(
        "음성 파일", type=["wav", "mp3"], key="audio", label_visibility="collapsed"
    )
    if audio_file:
        st.audio(audio_file)

    st.markdown("#### 📝 3. 대본 (.txt) — 선택사항")
    script_file = st.file_uploader(
        "대본 파일", type=["txt"], key="script", label_visibility="collapsed"
    )

with col2:
    st.markdown("#### 💬 2. 자막 (.srt)")
    srt_file = st.file_uploader(
        "SRT 파일", type=["srt"], key="srt", label_visibility="collapsed"
    )

    st.markdown("#### 🖼️ 4. 이미지 (여러 장 가능)")
    image_files = st.file_uploader(
        "이미지 파일 (PNG, JPG, JPEG, JFIF)",
        type=["png", "jpg", "jpeg", "jfif"],
        accept_multiple_files=True,
        key="images",
        label_visibility="collapsed",
    )
    if image_files:
        st.caption(f"✅ {len(image_files)}장 업로드됨")

# ── 이미지에서 해상도 자동 감지 ──────────────────────────────────────────────
def detect_video_size(uploaded_images, quality_label: str) -> tuple:
    """첫 번째 이미지의 비율을 감지해 적절한 해상도를 반환."""
    if not uploaded_images:
        return (1280, 720)

    img = Image.open(uploaded_images[0])
    iw, ih = img.size
    ratio = iw / ih  # 1.0 보다 크면 가로, 작으면 세로

    long_edge_map = {"FHD": 1920, "HD": 1280, "SD": 854}
    long = long_edge_map.get(quality_label, 1280)

    if ratio >= 1.0:          # 가로형 (16:9 등)
        h = round(long / ratio / 2) * 2
        return (long, h)
    else:                     # 세로형 (9:16 등)
        w = round(long * ratio / 2) * 2
        return (w, long)


# ── 상세 설정 ────────────────────────────────────────────────────────────────
with st.expander("⚙️ 영상 상세 설정"):
    c1, c2, c3 = st.columns(3)
    with c1:
        quality_label = st.selectbox("화질 (긴 변 기준)", ["FHD", "HD", "SD"], index=1)
    with c2:
        font_size = st.slider("자막 폰트 크기", 20, 72, 38, step=2)
    with c3:
        fps = st.selectbox("FPS", [24, 30, 60], index=1)

    anim_options = ["랜덤 (클립마다 다름)"] + [p[0] for p in _ANIM_PRESETS]
    anim_label = st.selectbox(
        "🎞️ 프리미엄 모드 애니메이션",
        anim_options,
        index=0,
        help="프리미엄 모드에서만 적용됩니다.",
    )
    anim_mode = "random" if anim_label == "랜덤 (클립마다 다름)" else anim_label

video_size = detect_video_size(image_files, quality_label)
if image_files:
    st.caption(f"📐 감지된 영상 해상도: **{video_size[0]}×{video_size[1]}**")

# ── 미리보기 ─────────────────────────────────────────────────────────────────
if srt_file and image_files:
    raw = srt_file.read()
    srt_file.seek(0)
    try:
        srt_content = raw.decode("utf-8")
    except UnicodeDecodeError:
        srt_content = raw.decode("cp949", errors="replace")

    subtitles_preview = parse_srt(srt_content)

    def natural_key_preview(f):
        nums = re.findall(r"\d+", f.name)
        return [int(n) for n in nums] if nums else [0]

    sorted_preview = sorted(image_files, key=natural_key_preview)

    st.subheader(f"미리보기 — 이미지 {len(image_files)}장 / 자막 {len(subtitles_preview)}개")
    if len(image_files) < len(subtitles_preview):
        st.info(
            f"이미지가 {len(image_files)}장으로 자막({len(subtitles_preview)}개)보다 적습니다. "
            "이미지를 순환하여 사용합니다."
        )

    per_page = 5
    max_show = min(len(subtitles_preview), 20)
    for row_start in range(0, max_show, per_page):
        row_end = min(row_start + per_page, max_show)
        cols = st.columns(row_end - row_start)
        for j, idx in enumerate(range(row_start, row_end)):
            sub = subtitles_preview[idx]
            n_prev = len(subtitles_preview)
            n_prev_imgs = len(sorted_preview)
            img_idx = min(idx * n_prev_imgs // n_prev, n_prev_imgs - 1)
            img_f = sorted_preview[img_idx]
            with cols[j]:
                st.image(img_f, width=200)
                dur = sub["end"] - sub["start"]
                st.caption(
                    f"**#{sub['index']}** 이미지{img_idx + 1} ({dur:.1f}s)"
                )

st.divider()

# ── 생성 버튼 ────────────────────────────────────────────────────────────────
if st.button("🚀 자동 영상 변환 시작", type="primary", use_container_width=True):  # noqa: buttons don't support width= yet
    errors = []
    if not audio_file:
        errors.append("음성(WAV/MP3) 파일을 업로드해 주세요.")
    if not srt_file:
        errors.append("자막(SRT) 파일을 업로드해 주세요.")
    if not image_files:
        errors.append("이미지를 1장 이상 업로드해 주세요.")
    for e in errors:
        st.error(e)

    if not errors:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            # Save audio
            audio_ext = audio_file.name.rsplit(".", 1)[-1].lower()
            audio_path = os.path.join(tmpdir, f"audio.{audio_ext}")
            audio_file.seek(0)
            with open(audio_path, "wb") as f:
                f.write(audio_file.read())

            # Parse SRT
            srt_file.seek(0)
            raw = srt_file.read()
            try:
                srt_content = raw.decode("utf-8")
            except UnicodeDecodeError:
                srt_content = raw.decode("cp949", errors="replace")
            subtitles = parse_srt(srt_content)

            if not subtitles:
                st.error("자막 파일을 파싱할 수 없습니다. SRT 형식을 확인해 주세요.")
                st.stop()

            # Save images — 파일명 내 숫자 기준으로 정렬 (자연 정렬)
            def natural_key(f):
                nums = re.findall(r"\d+", f.name)
                return [int(n) for n in nums] if nums else [0]

            sorted_files = sorted(image_files, key=natural_key)

            img_paths = []
            for idx, img_f in enumerate(sorted_files):
                ext = img_f.name.rsplit(".", 1)[-1].lower()
                if ext == "jfif":
                    ext = "jpg"
                p = os.path.join(tmpdir, f"img_{idx:04d}.{ext}")
                img_f.seek(0)  # 미리보기에서 읽힌 포인터 초기화
                with open(p, "wb") as f:
                    f.write(img_f.read())
                img_paths.append(p)

            output_path = os.path.join(tmpdir, "output.mp4")

            prog_bar = st.progress(0.0)
            status = st.empty()

            def update_prog(pct, msg):
                prog_bar.progress(float(min(pct, 1.0)))
                status.text(f"⏳ {msg}")

            try:
                create_video(
                    image_paths=img_paths,
                    subtitles=subtitles,
                    audio_path=audio_path,
                    output_path=output_path,
                    video_size=video_size,
                    premium=(mode == "premium"),
                    font_size=font_size,
                    fps=fps,
                    anim_mode=anim_mode,
                    progress_cb=update_prog,
                )

                prog_bar.progress(1.0)
                status.text("✅ 영상 생성 완료!")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

                size_mb = len(video_bytes) / 1024 / 1024
                st.success(f"🎉 영상이 성공적으로 생성되었습니다! ({size_mb:.1f} MB)")
                vid_col, _ = st.columns([1, 3])
                with vid_col:
                    st.video(video_bytes)
                st.download_button(
                    label="📥 MP4 영상 다운로드",
                    data=video_bytes,
                    file_name="output_video.mp4",
                    mime="video/mp4",
                    use_container_width=True,  # noqa: download_button doesn't support width= yet
                )

            except Exception as exc:
                st.error(f"오류가 발생했습니다: {exc}")
                with st.expander("오류 상세 정보"):
                    st.exception(exc)
