"""Generate studio voiceover audio clips for Aiccountant007 video (N3 task).

Supports ElevenLabs API if ELEVENLABS_API_KEY is present,
with high-fidelity neural fallback (en-US-ChristopherNeural / professional auditor tone).
"""

import asyncio
import os
import subprocess
from pathlib import Path

VOICE_DIR = Path("docs/video/voice")
VOICE_DIR.mkdir(parents=True, exist_ok=True)

# Frames from docs/video/SCRIPT.md
SCRIPTS = [
    (
        "01_intro.mp3",
        5,
        "Welcome to Aiccountant007: autonomous agentic commerce with real cryptographic accountability.",
    ),
    (
        "02_problem.mp3",
        15,
        "In an agentic economy, hiring unknown AI agents is risky. Pay upfront, and you risk hallucinations or fraud. Put invoices in prompts, and prompt injections can drain your wallet.",
    ),
    (
        "03_hash_escrow.mp3",
        12,
        "Our client agent packages September invoices, binding their SHA-256 hash to a Cardano escrow contract. It discovers competing firms and hires CheapBooks for two ADA.",
    ),
    (
        "04_audit_dispute.mp3",
        13,
        "CheapBooks delivers, but our independent verifier catches invalid VAT rates. Payment is blocked, a refund is automatically requested and authorized, and the seller's reputation is slashed.",
    ),
    (
        "05_injection_defense.mp3",
        11,
        "Next, invoice number eight attempts a prompt injection, demanding ten times the price. Our deterministic wallet policy intercepts and blocks the attack.",
    ),
    (
        "06_honest_firm.mp3",
        12,
        "The agent switches to ProÚčetní. Work is verified against Czech accounting standards and ARES registries. Payment is released. An accidental duplicate batch is blocked instantly.",
    ),
    (
        "07_refund_settled.mp3",
        7,
        "With the refund settled, Batch 1 is assigned to ProÚčetní, who completes the extraction perfectly.",
    ),
    (
        "08_outro_matrix.mp3",
        15,
        "Real cryptographic binding, real accounting verification, and real wallet policies. Trade safely in the agentic economy with Aiccountant007.",
    ),
]


async def generate_clip(filename: str, max_sec: int, text: str) -> float:
    dest = VOICE_DIR / filename
    eleven_key = os.environ.get("ELEVENLABS_API_KEY")

    if eleven_key:
        print(f"Generating {filename} via ElevenLabs API...")
        # ElevenLabs generation logic if key provided
        import httpx
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Default Rachel or Adam
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        resp = httpx.post(  # noqa: ASYNC210
            url,
            headers={"xi-api-key": eleven_key, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {"stability": 0.65, "similarity_boost": 0.8},
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    else:
        import edge_tts
        # Professional auditor / documentary tone
        voice = "en-US-ChristopherNeural"
        communicate = edge_tts.Communicate(text, voice=voice, rate="+2%", pitch="-1Hz")
        await communicate.save(str(dest))

    # Inspect duration with ffprobe / ffmpeg
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(dest),
    ]
    dur_str = subprocess.check_output(cmd, text=True).strip()  # noqa: ASYNC221
    dur = float(dur_str)
    print(f"Generated {filename}: {dur:.2f}s (target budget: {max_sec}s)")
    return dur


def generate_readme(durations: list[tuple[str, int, float, str]], total_duration: float):
    readme_path = VOICE_DIR / "README.md"
    lines = [
        "# Video Voiceover Tracks (N3)",
        "",
        f"Total Voiceover Duration: **{total_duration:.2f} seconds** (fits within 90-second limit).",
        "",
        "## Voice Profile & Generation Settings",
        "- **Voice**: Studio Documentary / Professional Auditor (`en-US-ChristopherNeural` / ElevenLabs compatible)",
        "- **Pacing**: Neutral cadence, authoritative, 48 kHz high-fidelity MP3",
        "- **ElevenLabs Best Use Compatibility**: Ready for zero-config run or drop-in `ELEVENLABS_API_KEY`",
        "",
        "## Clip Breakdown",
        "| File | Target Budget | Actual Duration | Voiceover Text |",
        "|---|---|---|---|",
    ]
    for fn, budget, actual, txt in durations:
        lines.append(f"| `{fn}` | {budget}s | {actual:.2f}s | {txt} |")

    lines.append("")
    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {readme_path}")


async def main():
    durations = []
    total = 0.0
    for filename, budget, text in SCRIPTS:
        dur = await generate_clip(filename, budget, text)
        durations.append((filename, budget, dur, text))
        total += dur

    print("\n==========================================")
    print(f"Total narration duration: {total:.2f}s (Budget: 90s)")
    print("==========================================")
    assert total <= 90.0, f"Total duration {total} exceeds 90s!"

    generate_readme(durations, total)


if __name__ == "__main__":
    asyncio.run(main())
