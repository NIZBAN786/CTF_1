import os
import re
import hmac
from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_qrcode import QRcode
from PIL import Image, ImageDraw, ImageFont
import piexif
from io import BytesIO
import base64
import qrcode


# =============================
# Configuration and constants
# =============================

# Flags (easy to change in one place)
FLAG_STAGE1 = "_0dayBrothers{m3tadata_never_lies}"
FLAG_STAGE2 = "_0dayBrothers{cipher_breaker}"
FLAG_STAGE3 = "_0dayBrothers{r3_path_unlocked}"

TELEGRAM_URL = "https://t.me/+RV0uY3zR_nNmNjU1"


def ensure_static_image_with_exif(static_dir: str) -> None:
    """Create `/static/ctf_stage1.jpg` with EXIF metadata containing FLAG_STAGE1 if it doesn't exist."""
    os.makedirs(static_dir, exist_ok=True)
    image_path = os.path.join(static_dir, "ctf_stage1.jpg")

    # Always (re)generate so the EXIF reflects current flags

    # Create a simple banner image
    width, height = 960, 540
    background_color = (15, 23, 42)  # slate-900-ish
    accent_color = (234, 88, 12)     # orange-600-ish
    text_color = (241, 245, 249)     # slate-100-ish

    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image)

    # Title
    title_text = "CTF Stage 1"
    subtitle_text = "Some secrets hide where pixels meet the truth."

    # Try to use a default font; Pillow will fall back if not found
    try:
        font_title = ImageFont.truetype("arial.ttf", 64)
        font_sub = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    # Draw a simple accent rectangle
    draw.rectangle([(0, height - 12), (width, height)], fill=accent_color)

    # Centered title
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    sub_bbox = draw.textbbox((0, 0), subtitle_text, font=font_sub)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_h = sub_bbox[3] - sub_bbox[1]
    draw.text(((width - title_w) / 2, (height - title_h) / 2 - 20), title_text, font=font_title, fill=text_color)
    draw.text(((width - sub_w) / 2, (height - sub_h) / 2 + 44), subtitle_text, font=font_sub, fill=(203, 213, 225))

    # Prepare EXIF data embedding only the flag (no hints)
    exif_dict = {
        "0th": {
            piexif.ImageIFD.ImageDescription: FLAG_STAGE1.encode("utf-8"),
            piexif.ImageIFD.Artist: b"",
        },
        "Exif": {
            piexif.ExifIFD.UserComment: b"",
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif_dict)

    image.save(image_path, format="JPEG", quality=92, exif=exif_bytes)


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

    # Initialize QR extension
    QRcode(app)

    # Ensure static assets exist
    ensure_static_image_with_exif(app.static_folder)

    # -----------------------------
    # Helpers
    # -----------------------------
    def is_logged_in() -> bool:
        return bool(session.get("auth"))

    def login_required():
        if not is_logged_in():
            return redirect(url_for("login"))
        return None

    # -----------------------------
    # Routes
    # -----------------------------
    @app.route("/")
    def index():
        if is_logged_in():
            return redirect(url_for("stage1"))
        return redirect(url_for("login"))

    @app.route("/gate", methods=["GET", "POST"]) 
    def login():
        error = None
        sqli_patterns = [
            re.compile(r"'\s*or\s*1\s*=\s*1", re.IGNORECASE),
            re.compile(r"'\s*or\s*'([^']+)'\s*=\s*'\\1'", re.IGNORECASE),
        ]

        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")

            # Intentionally insecure demonstration (do NOT do this in real apps)
            fake_sql = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}';"

            # Fake SQLi bypass check (generic tautology detection)
            if any(p.search(username) for p in sqli_patterns):
                session["auth"] = True
                session["user"] = "admin"
                return redirect(url_for("stage1"))

            # Optional mock credential (not necessary for the CTF path)
            if username == "player" and password == "ctf":
                session["auth"] = True
                session["user"] = "player"
                return redirect(url_for("stage1"))

            error = "Invalid credentials."

        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/gallery")
    def stage1():
        guard = login_required()
        if guard:
            return guard
        return render_template("stage1.html")

    @app.route("/codex", methods=["GET", "POST"])
    def stage2():
        guard = login_required()
        if guard:
            return guard
        # Ciphertext from a monoalphabetic substitution (Atbash on letters)
        cipher_text = "_0wzbYilgsvih{xrksvi_yivzpvi}"
        error = None
        if request.method == "POST":
            submitted = request.form.get("flag", "")
            # Basic hardening: limit size and use constant-time comparison
            if not isinstance(submitted, str) or len(submitted) > 100:
                error = "Invalid"
            elif hmac.compare_digest(submitted.strip(), FLAG_STAGE2):
                session["stage2_ok"] = True
                return redirect(url_for("stage3_code"))
            else:
                error = "Invalid"
        return render_template("stage2.html", cipher_text=cipher_text, error=error)

    @app.route("/node/seed")
    def stage3_code():
        guard = login_required()
        if guard:
            return guard
        return render_template("stage3.html", stage3_flag=FLAG_STAGE3)

    @app.route("/gate/open/<string:flag>")
    def stage3_flag_redirect(flag: str):
        guard = login_required()
        if guard:
            return guard
        if flag == FLAG_STAGE3:
            # Show the final reward page with a QR code pointing to Telegram
            return redirect(url_for("reward"))
        return render_template("404.html"), 404

    @app.route("/finale")
    def reward():
        # Final reward page: display QR code and link
        def generate_qr_data_uri(data: str) -> str:
            image = qrcode.make(data)
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            return f"data:image/png;base64,{encoded}"

        qr_data_uri = generate_qr_data_uri(TELEGRAM_URL)
        return render_template("reward.html", telegram_url=TELEGRAM_URL, qr_data_uri=qr_data_uri)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


