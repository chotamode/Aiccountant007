"""Assemble the complete 90s hackathon video using ffmpeg, title slides, and voice tracks."""

import subprocess
from pathlib import Path

VIDEO_DIR = Path("docs/video")
VOICE_DIR = Path("docs/video/voice")
SLIDES_DIR = Path("docs/presentation/slides")

SEGMENTS = [
    ("title_start.png", "01_intro.mp3"),
    ("slide_02.png", "02_problem.mp3"),
    ("slide_04.png", "03_hash_escrow.mp3"),
    ("slide_06.png", "04_audit_dispute.mp3"),
    ("slide_05.png", "05_injection_defense.mp3"),
    ("slide_07.png", "06_honest_firm.mp3"),
    ("slide_08.png", "07_refund_settled.mp3"),
    ("title_end.png", "08_outro_matrix.mp3"),
]


def resolve_image(name: str) -> Path:
    if (VIDEO_DIR / name).exists():
        return VIDEO_DIR / name
    if (SLIDES_DIR / name).exists():
        return SLIDES_DIR / name
    raise FileNotFoundError(name)


def main():
    tmp_parts = []
    print("Building video segments with ffmpeg...")

    for i, (img_name, audio_name) in enumerate(SEGMENTS):
        img_path = resolve_image(img_name)
        audio_path = VOICE_DIR / audio_name
        part_out = VIDEO_DIR / f"part_{i:02d}.mp4"

        # Get audio duration
        dur_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        dur = float(subprocess.check_output(dur_cmd, text=True).strip())
        print(f"Segment {i+1}: {img_name} + {audio_name} ({dur:.2f}s)")

        # Create video segment
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_path),
            "-i", str(audio_path),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            "-t", str(dur),
            str(part_out),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tmp_parts.append(part_out)

    # Concat all segments
    concat_txt = VIDEO_DIR / "concat_list.txt"
    concat_txt.write_text("\n".join(f"file '{p.name}'" for p in tmp_parts), encoding="utf-8")

    final_video = VIDEO_DIR / "Aiccountant007_Demo_90s.mp4"
    print(f"Concatenating all segments into {final_video}...")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(final_video),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Clean up part files
    concat_txt.unlink(missing_ok=True)
    for p in tmp_parts:
        p.unlink(missing_ok=True)

    # Inspect final video duration
    dur_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(final_video),
    ]
    total_dur = float(subprocess.check_output(dur_cmd, text=True).strip())
    print(f"Successfully generated {final_video}!")
    print(f"Final video duration: {total_dur:.2f} seconds (Budget: <= 90.0s)")
    assert total_dur <= 90.0, f"Duration {total_dur} exceeds 90s!"


if __name__ == "__main__":
    main()
