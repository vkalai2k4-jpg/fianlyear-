import os
import json
import re
from textblob import TextBlob

from llm_client import call_llm, LLMError, is_configured as llm_configured

try:
    import requests
    from PIL import Image, ImageDraw, ImageFont
    from io import BytesIO
    IMAGE_COMPOSER_AVAILABLE = True
except ImportError:
    IMAGE_COMPOSER_AVAILABLE = False


def _fallback_variations(product_name, description, audience, platform, goal, tone):
    """Used when no API key is set, or the API call fails - keeps the app demoable."""
    templates = [
        {
            "headline": f"Introducing {product_name} — Made for {audience or 'You'}",
            "caption": f"Discover {product_name}. {description[:100]} Perfect for {audience or 'everyone'} on {platform or 'your favorite platform'}.",
            "cta": "Shop Now"
        },
        {
            "headline": f"{product_name}: The {tone or 'Smart'} Choice",
            "caption": f"Looking for something better? {product_name} delivers exactly what {audience or 'you'} need. {description[:80]}",
            "cta": "Learn More"
        },
        {
            "headline": f"Don't Miss Out on {product_name}!",
            "caption": f"{description[:100]} Join thousands who trust {product_name} today.",
            "cta": "Get Started"
        },
    ]
    return templates


def generate_content_variations(product_name, description, audience, platform, goal, tone,
                                 marketing_type=None, language="English"):
    """
    Calls Claude API to generate 3 marketing content variations.
    Falls back to templates if no API key / call fails.
    Returns a list of dicts: [{headline, caption, cta}, ...]
    """
    if not llm_configured():
        return _fallback_variations(product_name, description, audience, platform, goal, tone)

    try:
        language_line = (
            "Write the content in Tamil (Tamil script)." if language == "Tamil"
            else "Write the content in Tanglish (Tamil words in English script, natural code-switching)." if language == "Tanglish"
            else "Write the content in English."
        )
        type_line = f"Marketing type: {marketing_type}" if marketing_type else ""

        prompt = f"""You are a marketing copywriter. Generate exactly 3 different marketing content variations
for the following campaign. Respond ONLY with valid JSON, no preamble, no markdown fences.

Product Name: {product_name}
Description: {description}
Target Audience: {audience}
Platform: {platform}
Campaign Goal: {goal}
Tone: {tone}
{type_line}
{language_line}

Return JSON in this exact format:
{{
  "variations": [
    {{"headline": "...", "caption": "...", "cta": "..."}},
    {{"headline": "...", "caption": "...", "cta": "..."}},
    {{"headline": "...", "caption": "...", "cta": "..."}}
  ]
}}
"""

        text = call_llm(prompt, max_tokens=1000)
        text = re.sub(r"```json|```", "", text).strip()
        data = json.loads(text)
        variations = data.get("variations", [])

        if not variations:
            raise ValueError("Empty variations from API")

        return variations

    except (LLMError, Exception) as e:
        print(f"[AI Generation] Falling back to templates due to: {e}")
        return _fallback_variations(product_name, description, audience, platform, goal, tone)


def _fallback_banner(product_name, description):
    return {
        "headline": product_name,
        "subtext": (description[:60] + "...") if len(description) > 60 else description,
        "image_prompt": f"clean product banner, {product_name}, festive colors, marketing poster style",
    }


def generate_banner_text(product_name, description, style="Festive", language="English"):
    """
    Asks Claude for a short banner headline + subtext + an image prompt
    (used with the free Pollinations.ai image API in the Banner Studio page).
    Falls back to simple text if no API key / call fails.
    Returns a dict: {headline, subtext, image_prompt}
    """
    if not llm_configured():
        return _fallback_banner(product_name, description)

    try:
        language_line = (
            "Write the headline and subtext in Tamil." if language == "Tamil"
            else "Write the headline and subtext in Tanglish." if language == "Tanglish"
            else "Write the headline and subtext in English."
        )

        prompt = f"""Create a short marketing banner for this product. Respond ONLY with valid JSON, no preamble, no markdown fences.

Product Name: {product_name}
Description: {description}
Banner style: {style}
{language_line}

Return JSON in this exact format:
{{
  "headline": "a punchy 4-6 word headline",
  "subtext": "a short 6-10 word supporting line",
  "image_prompt": "a short English description of a background image for this banner, for an AI image generator"
}}
"""

        text = call_llm(prompt, max_tokens=300)
        text = re.sub(r"```json|```", "", text).strip()
        data = json.loads(text)

        if not data.get("headline"):
            raise ValueError("Empty banner data from API")

        return data

    except (LLMError, Exception) as e:
        print(f"[Banner Generation] Falling back to simple text due to: {e}")
        return _fallback_banner(product_name, description)


def score_sentiment(text):
    """Returns a polarity score from -1 (negative) to 1 (positive) using TextBlob."""
    return round(TextBlob(text).sentiment.polarity, 3)


def pick_best_variation(variations_with_scores):
    """
    variations_with_scores: list of dicts with a 'sentiment_score' key.
    Returns the index of the best (highest positive sentiment) variation.
    """
    best_index = 0
    best_score = float("-inf")
    for i, v in enumerate(variations_with_scores):
        if v["sentiment_score"] > best_score:
            best_score = v["sentiment_score"]
            best_index = i
    return best_index


def _load_font(size):
    """Tries a few common font paths (Windows/Linux/Mac) so headline text
    renders at a real size; falls back to PIL's tiny default font if none exist."""
    candidates = [
        "arial.ttf",
        "Arial.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def enhance_shop_photo(image):
    """
    Applies an auto-enhancement pipeline to a customer-uploaded shop photo
    before it becomes the banner background: auto-contrast (histogram
    stretching), sharpening, and a mild color/brightness boost.
    """
    from PIL import ImageOps, ImageEnhance
    img = ImageOps.autocontrast(image, cutoff=1)
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = ImageEnhance.Brightness(img).enhance(1.05)
    return img


def _prepare_background(background_source):
    """background_source is either an image URL (str) or an already-open PIL Image."""
    if isinstance(background_source, Image.Image):
        return background_source
    try:
        resp = requests.get(background_source, timeout=20)
        return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


def compose_banner_image(background_source, headline, subtext, shop_name, shop_address="",
                          shop_phone="", offer_text="", is_uploaded_photo=False):
    """
    Builds the final banner: either from an AI-generated background URL, or
    from a customer-uploaded shop photo (auto-enhanced first). Overlays the
    shop's actual details as clearly readable text using a dark translucent
    strip for contrast. Returns a PIL Image, or None if unavailable.
    """
    if not IMAGE_COMPOSER_AVAILABLE:
        return None

    bg = _prepare_background(background_source)
    if bg is None:
        return None

    if is_uploaded_photo:
        bg = enhance_shop_photo(bg)

    bg = bg.resize((800, 400))
    draw = ImageDraw.Draw(bg, "RGBA")

    # Dark translucent strip at the bottom so text stays legible over any background
    strip_height = 170
    draw.rectangle(
        [(0, 400 - strip_height), (800, 400)],
        fill=(0, 0, 0, 160)
    )

    font_headline = _load_font(34)
    font_shop = _load_font(24)
    font_sub = _load_font(18)
    font_contact = _load_font(16)

    y = 400 - strip_height + 12
    draw.text((20, y), headline, font=font_headline, fill="white")
    y += 42

    if shop_name:
        draw.text((20, y), shop_name, font=font_shop, fill="#FFD54F")
        y += 30

    if subtext:
        draw.text((20, y), subtext, font=font_sub, fill="white")
        y += 26

    contact_line = " | ".join(part for part in [shop_address, shop_phone] if part)
    if contact_line:
        draw.text((20, y), contact_line, font=font_contact, fill="#E0E0E0")
        y += 22

    if offer_text:
        draw.text((20, y), offer_text, font=font_contact, fill="#4CAF50")

    return bg


def _fallback_campaign_ideas(business_type):
    bt = business_type or "your business"
    return [
        {"title": f"Festive Offer Blast for {bt}", "description": f"Run a limited-time festive discount campaign for {bt} to drive quick sales.", "marketing_type": "Festival Offer", "platform": "WhatsApp"},
        {"title": f"New Customer Welcome Series for {bt}", "description": f"A friendly welcome message series introducing {bt} to first-time customers.", "marketing_type": "Welcome Message", "platform": "Email"},
        {"title": f"Behind the Scenes at {bt}", "description": f"Share the story and people behind {bt} to build trust and brand awareness.", "marketing_type": "Brand Story", "platform": "Instagram"},
        {"title": f"Customer Testimonial Spotlight - {bt}", "description": f"Highlight a happy customer's experience with {bt} to build social proof.", "marketing_type": "Testimonial", "platform": "Facebook"},
        {"title": f"Flash Sale Countdown for {bt}", "description": f"Create urgency with a 24-hour flash sale announcement for {bt}.", "marketing_type": "Flash Sale", "platform": "WhatsApp"},
    ]


def generate_campaign_ideas(business_type):
    """Returns a short list of ready-to-use campaign idea concepts for the
    given business type. Falls back to a generic curated set if no API key."""
    if not llm_configured():
        return _fallback_campaign_ideas(business_type)

    try:
        prompt = f"""Suggest 5 ready-to-use marketing campaign ideas for this business type: {business_type or 'a small local business'}.

Respond ONLY with a valid JSON array, no preamble, no markdown fences.
Each item: {{"title": "short catchy idea name", "description": "1-2 sentence explanation", "marketing_type": "one of: Festival Offer, Welcome Message, Brand Story, Testimonial, Flash Sale, Product Launch, Referral Program", "platform": "one of: Email, Instagram, WhatsApp, Facebook"}}"""

        raw = call_llm(prompt, max_tokens=700)
        raw = re.sub(r"```json|```", "", raw).strip()
        return json.loads(raw)
    except (LLMError, Exception) as e:
        print(f"[Campaign Ideas] Falling back due to: {e}")
        return _fallback_campaign_ideas(business_type)
