"""Generate 1920x1080 title cards for Aiccountant007 video (N4 task)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path("docs/video")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_BOLD = "/usr/share/fonts/truetype/lato/Lato-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/lato/Lato-Regular.ttf"
FONT_SEMI = "/usr/share/fonts/truetype/lato/Lato-Semibold.ttf"
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

BG_DARK = (15, 23, 42)          # Deep slate #0f172a
CARD_BG = (30, 41, 59)          # Slate #1e293b
CARD_BORDER = (51, 65, 85)      # Slate border #334155
CYAN = (56, 189, 248)           # Sky cyan #38bdf8
CARDANO_BLUE = (0, 140, 255)    # Cardano blue
EMERALD = (52, 211, 153)        # Emerald green #34d399
AMBER = (251, 191, 36)          # Amber #fbbf24
ROSE = (244, 63, 94)            # Rose red #f43f5e
TEXT_WHITE = (248, 250, 252)    # Pure white #f8fafc
TEXT_MUTED = (148, 163, 184)    # Slate muted #94a3b8


def draw_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill=CARD_BG, outline=CARD_BORDER, radius=16):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def generate_title_start():
    img = Image.new("RGB", (1920, 1080), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Decorative header glow accent line
    draw.rectangle([(0, 0), (1920, 8)], fill=CYAN)

    font_badge = ImageFont.truetype(FONT_SEMI, 24)
    font_title = ImageFont.truetype(FONT_BOLD, 76)
    font_sub = ImageFont.truetype(FONT_SEMI, 34)
    font_card_title = ImageFont.truetype(FONT_BOLD, 26)
    font_card_desc = ImageFont.truetype(FONT_REGULAR, 20)
    font_footer = ImageFont.truetype(FONT_REGULAR, 24)
    font_footer_bold = ImageFont.truetype(FONT_BOLD, 24)

    # Top Tag / Badges
    draw_card(draw, (120, 60, 480, 110), fill=(24, 34, 53), outline=CYAN, radius=24)
    draw.text((150, 72), "HACKATHON: FROM DUSK TILL DAWN #01", fill=CYAN, font=font_badge)

    draw_card(draw, (500, 60, 820, 110), fill=(24, 34, 53), outline=AMBER, radius=24)
    draw.text((530, 72), "TRACK: AGENTIC ECONOMY", fill=AMBER, font=font_badge)

    draw_card(draw, (840, 60, 1150, 110), fill=(24, 34, 53), outline=EMERALD, radius=24)
    draw.text((870, 72), "PARTNER: MASUMI NETWORK", fill=EMERALD, font=font_badge)

    # Main Project Title
    draw.text((120, 150), "Aiccountant007", fill=TEXT_WHITE, font=font_title)
    
    # Accent color in subtitle
    draw.text((120, 245), "Autonomous B2B Accounting, Independent Auditing & Smart Escrow on Cardano", fill=CYAN, font=font_sub)

    # 4 Architecture Pillars
    cards = [
        (
            "1. MIP-004 Cryptographic Binding",
            "Buyer hashes document packages (SHA-256)\nand locks escrow on Cardano Preprod\nbound to immutable inputHash.",
            CYAN,
        ),
        (
            "2. Independent Verifier",
            "Audits math lines, Czech VAT (21%/12%/0%),\nISDOC 6.0 XML standards, and live\nARES national company registry.",
            EMERALD,
        ),
        (
            "3. Autonomous Escrow & Disputes",
            "Sloppy sellers are challenged deterministically.\nRefunds auto-authorized via POST /dispute,\nslashing Bayesian reputation.",
            AMBER,
        ),
        (
            "4. Deterministic Wallet Policy",
            "Protects purchasing wallet against prompt\ninjections (10x price), budget overruns,\nand duplicate invoice submissions.",
            ROSE,
        ),
    ]

    card_w = 400
    card_h = 360
    start_x = 120
    gap = 26
    start_y = 350

    for i, (title, desc, accent) in enumerate(cards):
        x = start_x + i * (card_w + gap)
        y = start_y
        draw_card(draw, (x, y, x + card_w, y + card_h), radius=16)
        # Accent top bar in card
        draw.rounded_rectangle([(x, y), (x + card_w, y + 8)], radius=4, fill=accent)
        # Card title
        draw.text((x + 28, y + 36), title, fill=TEXT_WHITE, font=font_card_title)
        # Card desc
        draw.multiline_text((x + 28, y + 105), desc, fill=TEXT_MUTED, font=font_card_desc, spacing=10)

    # Bottom team and metadata card
    draw_card(draw, (120, 800, 1800, 980), fill=(24, 34, 53), outline=CARD_BORDER, radius=20)
    
    draw.text((160, 835), "Team ELEPASH:", fill=TEXT_WHITE, font=font_footer_bold)
    draw.text((360, 835), "Eduard (@ChotaMode)  ·  Pavlo (@vhodny)  ·  Alex (@uvalenu)", fill=CYAN, font=font_footer)

    draw.text((160, 900), "Repository:", fill=TEXT_WHITE, font=font_footer_bold)
    draw.text((360, 900), "https://github.com/chotamode/Aiccountant007  ·  Python 3.12 · 88 Tests Passing", fill=EMERALD, font=font_footer)

    out_file = OUTPUT_DIR / "title_start.png"
    img.save(out_file, "PNG")
    print(f"Saved {out_file} (1920x1080)")


def generate_title_end():
    img = Image.new("RGB", (1920, 1080), BG_DARK)
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (1920, 8)], fill=EMERALD)

    font_title = ImageFont.truetype(FONT_BOLD, 64)
    font_sub = ImageFont.truetype(FONT_SEMI, 28)
    font_table_hdr = ImageFont.truetype(FONT_BOLD, 22)
    font_table_body = ImageFont.truetype(FONT_SEMI, 20)
    font_table_desc = ImageFont.truetype(FONT_REGULAR, 18)
    font_badge = ImageFont.truetype(FONT_BOLD, 18)
    font_footer = ImageFont.truetype(FONT_REGULAR, 22)

    # Title & Subtitle
    draw.text((120, 50), "Architectural Truth Matrix", fill=TEXT_WHITE, font=font_title)
    draw.text((120, 130), "Honest Engineering: What is Real, What is Simulated, and What is External", fill=EMERALD, font=font_sub)

    # Table dimensions
    table_top = 190
    table_left = 120
    table_w = 1680
    row_h = 92
    col_feature_w = 460
    col_status_w = 260

    # Header Row
    draw_card(draw, (table_left, table_top, table_left + table_w, table_top + 50), fill=(24, 34, 53), outline=CARD_BORDER, radius=10)
    draw.text((table_left + 24, table_top + 14), "SUBSYSTEM / FEATURE", fill=TEXT_MUTED, font=font_table_hdr)
    draw.text((table_left + col_feature_w + 24, table_top + 14), "PRODUCTION STATUS", fill=TEXT_MUTED, font=font_table_hdr)
    draw.text((table_left + col_feature_w + col_status_w + 24, table_top + 14), "IMPLEMENTATION & DEMO BEHAVIOR", fill=TEXT_MUTED, font=font_table_hdr)

    rows = [
        (
            "Cryptographic Input Hashing",
            ("REAL", EMERALD),
            "MIP-004 inputHash computed from document contents & purchaser ID; bound to escrow contract.",
        ),
        (
            "Independent Accounting Verifier",
            ("REAL", EMERALD),
            "Audits math lines, Czech VAT (21%/12%/0%), ISDOC 6.0 XML, and Czech ARES company registry.",
        ),
        (
            "Wallet Policy & Security Guard",
            ("REAL", EMERALD),
            "ACID SQLite idempotency; strictly blocks prompt injections, duplicate invoices & budget overruns.",
        ),
        (
            "Bayesian Reputation Engine",
            ("REAL", EMERALD),
            "Beta-binomial scoring (paid + 1)/(total + 2); slashes sloppy sellers from future procurement.",
        ),
        (
            "SLA Dispute & Self-Refund",
            ("REAL", EMERALD),
            "Deterministic re-validation of seller errors in POST /dispute; triggers on-chain refund authorization.",
        ),
        (
            "Masumi Escrow Smart Contract",
            ("REAL / READY", CYAN),
            "Cardano Preprod integration via Masumi Payment Service node (with [SIMULATED] demo fallback).",
        ),
        (
            "Masumi Admin Dispute Resolution",
            ("NOT AUTOMATED", AMBER),
            "Unresolved seller disputes escalate to external Masumi multi-sig admin escrow mediation.",
        ),
    ]

    curr_y = table_top + 60
    for i, (feature, (status, color), detail) in enumerate(rows):
        bg = CARD_BG if i % 2 == 0 else (24, 34, 53)
        draw_card(draw, (table_left, curr_y, table_left + table_w, curr_y + row_h), fill=bg, outline=CARD_BORDER, radius=8)

        # Feature
        draw.text((table_left + 24, curr_y + 26), feature, fill=TEXT_WHITE, font=font_table_body)

        # Badge for status
        badge_w = 190
        badge_h = 40
        badge_x = table_left + col_feature_w + 20
        badge_y = curr_y + 20
        draw.rounded_rectangle([(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)], radius=8, fill=(15, 23, 42), outline=color, width=2)
        draw.text((badge_x + 18, badge_y + 9), status, fill=color, font=font_badge)

        # Detail
        draw.text((table_left + col_feature_w + col_status_w + 24, curr_y + 28), detail, fill=TEXT_MUTED, font=font_table_desc)

        curr_y += row_h + 10

    # Outro footer
    draw_card(draw, (table_left, 970, table_left + table_w, 1045), fill=(24, 34, 53), outline=CARD_BORDER, radius=12)
    draw.text((table_left + 30, 995), "Aiccountant007  ·  Agentic Economy on Cardano  ·  https://github.com/chotamode/Aiccountant007", fill=CYAN, font=font_footer)
    draw.text((table_left + 1250, 995), "From Dusk Till Dawn Hackathon #01", fill=TEXT_MUTED, font=font_footer)

    out_file = OUTPUT_DIR / "title_end.png"
    img.save(out_file, "PNG")
    print(f"Saved {out_file} (1920x1080)")


if __name__ == "__main__":
    generate_title_start()
    generate_title_end()
