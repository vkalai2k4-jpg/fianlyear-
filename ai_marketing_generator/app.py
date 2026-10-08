import os
import json
from datetime import datetime
from urllib.parse import quote
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from PIL import Image

from models import db, User, Campaign, ContentVariation, Approval, Customer
from llm_client import call_llm, LLMError, is_configured as llm_configured
from ai_generator import (
    generate_content_variations, score_sentiment, pick_best_variation, generate_banner_text,
    compose_banner_image, generate_campaign_ideas
)
from email_utils import send_campaign_email, send_otp_email
from auth_utils import generate_otp, get_otp_expiry, is_otp_valid
from content_templates import get_marketing_type_choices, fill_template

# Load .env from the project folder (works no matter which folder you run from)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///marketing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

GENERATED_DIR = os.path.join(app.root_path, 'static', 'generated')
os.makedirs(GENERATED_DIR, exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------

@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'manager':
            return redirect(url_for('manager_dashboard'))
        return redirect(url_for('owner_dashboard'))
    return render_template('landing.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        email = request.form['email']
        phone_number = request.form.get('phone_number', '')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))

        otp = generate_otp()
        user = User(
            username=username,
            password=generate_password_hash(password),
            role=role,
            email=email,
            phone_number=phone_number,
            is_verified=False,
            otp_code=otp,
            otp_expiry=get_otp_expiry()
        )
        db.session.add(user)
        db.session.commit()

        success, message = send_otp_email(email, otp, purpose="account verification")
        if success:
            flash('Account created. Enter the OTP sent to your email to verify.', 'success')
        else:
            flash(f'Account created, but OTP email could not be sent ({message}). Use the code shown below in demo mode: {otp}', 'warning')

        return redirect(url_for('verify_user_otp', user_id=user.id))

    return render_template('register.html')


@app.route('/verify-otp/user/<int:user_id>', methods=['GET', 'POST'])
def verify_user_otp(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        entered = request.form['otp']
        valid, error = is_otp_valid(user.otp_code, user.otp_expiry, entered)

        if valid:
            user.is_verified = True
            user.otp_code = None
            user.otp_expiry = None
            db.session.commit()
            flash('Email verified. You can now log in.', 'success')
            return redirect(url_for('login'))

        flash(error, 'danger')

    return render_template('verify_otp.html', target='user', target_id=user.id, contact=user.email)


@app.route('/resend-otp/user/<int:user_id>')
def resend_user_otp(user_id):
    user = User.query.get_or_404(user_id)
    otp = generate_otp()
    user.otp_code = otp
    user.otp_expiry = get_otp_expiry()
    db.session.commit()

    success, message = send_otp_email(user.email, otp, purpose="account verification")
    flash('A new OTP has been sent.' if success else f'Could not send OTP: {message} (demo code: {otp})', 'success' if success else 'warning')
    return redirect(url_for('verify_user_otp', user_id=user.id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if not user.is_verified:
                flash('Please verify your email before logging in.', 'warning')
                return redirect(url_for('verify_user_otp', user_id=user.id))
            login_user(user)
            if user.role == 'manager':
                return redirect(url_for('manager_dashboard'))
            return redirect(url_for('owner_dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------------------------------------------------------
# OWNER ROUTES
# ---------------------------------------------------------

@app.route('/owner/dashboard')
@login_required
def owner_dashboard():
    if current_user.role != 'owner':
        return redirect(url_for('manager_dashboard'))

    campaigns = Campaign.query.filter_by(owner_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    stats = {
        'total': len(campaigns),
        'pending': sum(1 for c in campaigns if c.status == 'Pending'),
        'approved': sum(1 for c in campaigns if c.status in ('Approved', 'Sent')),
        'sent': sum(1 for c in campaigns if c.status == 'Sent'),
        'customers': Customer.query.filter_by(is_verified=True).count(),
    }
    return render_template('owner_dashboard.html', campaigns=campaigns, stats=stats)


@app.route('/campaign-ideas', methods=['GET', 'POST'])
@login_required
def campaign_ideas():
    ideas = None
    business_type = ''
    if request.method == 'POST':
        business_type = request.form.get('business_type', '').strip()
        ideas = generate_campaign_ideas(business_type)
    return render_template('campaign_ideas.html', ideas=ideas, business_type=business_type)


@app.route('/campaign/new', methods=['GET', 'POST'])
@login_required
def campaign_input():
    if request.method == 'POST':
        campaign = Campaign(
            owner_id=current_user.id,
            product_name=request.form['product_name'],
            description=request.form['description'],
            target_audience=request.form['target_audience'],
            platform=request.form['platform'],
            goal=request.form['goal'],
            tone=request.form['tone'],
            marketing_type=request.form.get('marketing_type'),
            language=request.form.get('language', 'English'),
            content_mode=request.form.get('content_mode', 'AI'),
            status='Draft'
        )
        db.session.add(campaign)
        db.session.commit()
        return redirect(url_for('generate_content', campaign_id=campaign.id))

    marketing_types = get_marketing_type_choices()
    selected_type = request.args.get('marketing_type')
    idea_title = request.args.get('idea_title', '')
    idea_description = request.args.get('idea_description', '')
    use_template = bool(selected_type) and not idea_title
    return render_template(
        'campaign_input.html',
        marketing_types=marketing_types,
        selected_type=selected_type,
        use_template=use_template,
        idea_title=idea_title,
        idea_description=idea_description
    )


@app.route('/campaign/<int:campaign_id>/generate')
@login_required
def generate_content(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)

    # Clear old variations if regenerating
    ContentVariation.query.filter_by(campaign_id=campaign.id).delete()

    if campaign.content_mode == 'Template':
        raw_variations = [fill_template(
            campaign.marketing_type, campaign.product_name,
            campaign.description, campaign.target_audience
        )]
    else:
        raw_variations = generate_content_variations(
            campaign.product_name, campaign.description, campaign.target_audience,
            campaign.platform, campaign.goal, campaign.tone,
            marketing_type=campaign.marketing_type, language=campaign.language
        )

    scored = []
    for v in raw_variations:
        text_for_sentiment = f"{v.get('headline', '')} {v.get('caption', '')}"
        score = score_sentiment(text_for_sentiment)
        scored.append({**v, 'sentiment_score': score})

    best_index = pick_best_variation(scored)

    for i, v in enumerate(scored):
        cv = ContentVariation(
            campaign_id=campaign.id,
            headline=v.get('headline', ''),
            caption=v.get('caption', ''),
            cta=v.get('cta', ''),
            sentiment_score=v['sentiment_score'],
            is_recommended=(i == best_index)
        )
        db.session.add(cv)

    db.session.commit()
    return redirect(url_for('content_results', campaign_id=campaign.id))


@app.route('/campaign/<int:campaign_id>/results')
@login_required
def content_results(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    variations = ContentVariation.query.filter_by(campaign_id=campaign.id).all()
    return render_template('content_results.html', campaign=campaign, variations=variations)


@app.route('/campaign/<int:campaign_id>/select/<int:variation_id>')
@login_required
def select_variation(campaign_id, variation_id):
    variations = ContentVariation.query.filter_by(campaign_id=campaign_id).all()
    for v in variations:
        v.is_recommended = (v.id == variation_id)
    db.session.commit()
    return redirect(url_for('email_preview', campaign_id=campaign_id))


def _send_campaign_now(campaign, selected):
    """Shared send logic used by both the direct-send path and manager publish."""
    customers = Customer.query.filter_by(is_verified=True).all()
    recipient_list = [c.email for c in customers]

    subject = selected.headline if selected else campaign.product_name
    body_html = f"<h2>{selected.headline}</h2><p>{selected.caption}</p><p><b>{selected.cta}</b></p>" if selected else ""

    success, message = send_campaign_email(subject, body_html, recipient_list)
    if success:
        campaign.status = 'Sent'
        db.session.commit()
    return success, message


@app.route('/campaign/<int:campaign_id>/preview', methods=['GET', 'POST'])
@login_required
def email_preview(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    selected = ContentVariation.query.filter_by(campaign_id=campaign.id, is_recommended=True).first()

    if request.method == 'POST':
        success, message = _send_campaign_now(campaign, selected)
        flash(message, 'success' if success else 'warning')
        return redirect(url_for('owner_dashboard'))

    return render_template('email_preview.html', campaign=campaign, selected=selected)


@app.route('/campaign/<int:campaign_id>/download')
@login_required
def download_content(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    selected = ContentVariation.query.filter_by(campaign_id=campaign.id, is_recommended=True).first()

    if not selected:
        flash('No content selected yet for this campaign.', 'warning')
        return redirect(url_for('content_results', campaign_id=campaign.id))

    text = (
        f"{campaign.product_name}\n"
        f"{'=' * len(campaign.product_name)}\n\n"
        f"Headline: {selected.headline}\n\n"
        f"Caption:\n{selected.caption}\n\n"
        f"Call to action: {selected.cta}\n\n"
        f"Platform: {campaign.platform} | Tone: {campaign.tone} | Marketing type: {campaign.marketing_type}\n"
    )

    filename = f"content_{campaign.id}.txt"
    file_path = os.path.join(GENERATED_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)


# ---------------------------------------------------------
# MANAGER ROUTES
# ---------------------------------------------------------

@app.route('/manager/dashboard')
@login_required
def manager_dashboard():
    if current_user.role != 'manager':
        return redirect(url_for('owner_dashboard'))

    pending = Campaign.query.filter_by(status='Pending').order_by(Campaign.created_at.desc()).all()
    reviewed = Campaign.query.filter(Campaign.status.in_(['Approved', 'Rejected', 'Sent'])).order_by(Campaign.created_at.desc()).all()
    return render_template('manager_dashboard.html', pending=pending, reviewed=reviewed)


@app.route('/manager/review/<int:campaign_id>')
@login_required
def review_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    selected = ContentVariation.query.filter_by(campaign_id=campaign.id, is_recommended=True).first()
    return render_template('review_campaign.html', campaign=campaign, selected=selected)


@app.route('/manager/decide/<int:campaign_id>', methods=['POST'])
@login_required
def decide_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    decision = request.form['decision']  # 'Approved' or 'Rejected'
    comment = request.form.get('comment', '')

    approval = Approval(
        campaign_id=campaign.id,
        manager_id=current_user.id,
        comment=comment,
        decision=decision
    )
    db.session.add(approval)
    campaign.status = decision
    db.session.commit()

    if decision == 'Approved':
        return redirect(url_for('publish_campaign', campaign_id=campaign.id))

    flash('Campaign rejected.', 'warning')
    return redirect(url_for('manager_dashboard'))


@app.route('/manager/publish/<int:campaign_id>')
@login_required
def publish_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    selected = ContentVariation.query.filter_by(campaign_id=campaign.id, is_recommended=True).first()

    success, message = _send_campaign_now(campaign, selected)
    flash(message, 'success' if success else 'warning')

    return redirect(url_for('manager_dashboard'))


# ---------------------------------------------------------
# CUSTOMER LIST (simple management so Auto-Publish has recipients)
# ---------------------------------------------------------

@app.route('/customers', methods=['GET', 'POST'])
@login_required
def manage_customers():
    if request.method == 'POST':
        otp = generate_otp()
        customer = Customer(
            name=request.form['name'],
            email=request.form['email'],
            preferred_language=request.form.get('preferred_language', 'English'),
            is_verified=False,
            otp_code=otp,
            otp_expiry=get_otp_expiry()
        )
        db.session.add(customer)
        db.session.commit()

        success, message = send_otp_email(customer.email, otp, purpose="customer verification")
        if success:
            flash('Customer added. Verification code sent - ask them to verify to receive campaigns.', 'success')
        else:
            flash(f'Customer added, but OTP email could not be sent ({message}). Demo code: {otp}', 'warning')

        return redirect(url_for('manage_customers'))

    customers = Customer.query.all()
    return render_template('customers.html', customers=customers)


@app.route('/customers/verify/<int:customer_id>', methods=['GET', 'POST'])
@login_required
def verify_customer_otp(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        entered = request.form['otp']
        valid, error = is_otp_valid(customer.otp_code, customer.otp_expiry, entered)

        if valid:
            customer.is_verified = True
            customer.otp_code = None
            customer.otp_expiry = None
            db.session.commit()
            flash(f'{customer.name} is now verified.', 'success')
            return redirect(url_for('manage_customers'))

        flash(error, 'danger')

    return render_template('verify_otp.html', target='customer', target_id=customer.id, contact=customer.email)


@app.route('/customers/resend-otp/<int:customer_id>')
@login_required
def resend_customer_otp(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    otp = generate_otp()
    customer.otp_code = otp
    customer.otp_expiry = get_otp_expiry()
    db.session.commit()

    success, message = send_otp_email(customer.email, otp, purpose="customer verification")
    flash('A new OTP has been sent.' if success else f'Could not send OTP: {message} (demo code: {otp})', 'success' if success else 'warning')
    return redirect(url_for('verify_customer_otp', customer_id=customer.id))


# ---------------------------------------------------------
# BANNER STUDIO (free image generation via Pollinations.ai - no API key needed)
# ---------------------------------------------------------

@app.route('/banner-studio', methods=['GET', 'POST'])
@login_required
def banner_studio():
    result = None
    image_url = None
    banner_file = None

    if request.method == 'POST':
        product_name = request.form['product_name']
        description = request.form['description']
        style = request.form.get('style', 'Festive')
        language = request.form.get('language', 'English')
        shop_name = request.form.get('shop_name', '').strip()
        shop_address = request.form.get('shop_address', '').strip()
        shop_phone = request.form.get('shop_phone', '').strip()
        offer_text = request.form.get('offer_text', '').strip()

        result = generate_banner_text(product_name, description, style=style, language=language)

        uploaded_file = request.files.get('shop_photo')
        is_uploaded = False

        if uploaded_file and uploaded_file.filename:
            background_source = Image.open(uploaded_file.stream).convert("RGB")
            is_uploaded = True
        else:
            prompt = quote(f"{result['image_prompt']}, {style.lower()} style, banner, no text")
            image_url = f"https://image.pollinations.ai/prompt/{prompt}?width=800&height=400&nologo=true"
            background_source = image_url

        final_banner = compose_banner_image(
            background_source,
            headline=result['headline'],
            subtext=result['subtext'],
            shop_name=shop_name,
            shop_address=shop_address,
            shop_phone=shop_phone,
            offer_text=offer_text,
            is_uploaded_photo=is_uploaded
        )

        if final_banner:
            banner_file = f"banner_{current_user.id}_{int(datetime.utcnow().timestamp())}.png"
            final_banner.save(os.path.join(GENERATED_DIR, banner_file))
        else:
            flash('Could not compose the final banner image (check internet connection / Pillow install). Showing the plain background instead.', 'warning')

    return render_template('banner_studio.html', result=result, image_url=image_url, banner_file=banner_file)


@app.route('/banner-studio/download/<filename>')
@login_required
def banner_download(filename):
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)


# ---------------------------------------------------------
# TEMPLATES GALLERY
# ---------------------------------------------------------

@app.route('/templates-gallery')
@login_required
def templates_gallery():
    marketing_types = get_marketing_type_choices()
    previews = [
        {
            'type': mt,
            'preview': fill_template(mt, '[Your Product]', '[Your product description goes here]', '[your customers]')
        }
        for mt in marketing_types
    ]
    return render_template('templates_gallery.html', previews=previews)


# ---------------------------------------------------------
# SHOWCASE (real approved/sent campaigns from this app's own data)
# ---------------------------------------------------------

@app.route('/showcase')
@login_required
def showcase():
    campaigns = Campaign.query.filter(Campaign.status.in_(['Approved', 'Sent'])) \
        .order_by(Campaign.created_at.desc()).limit(12).all()

    items = []
    for c in campaigns:
        selected = ContentVariation.query.filter_by(campaign_id=c.id, is_recommended=True).first()
        if selected:
            items.append({'campaign': c, 'content': selected})

    return render_template('showcase.html', items=items)



# ---------------------------------------------------------
# ASK AI (marketing helper widget, for the logged-in owner/manager only -
# general marketing advice, not shop-specific facts like timings/delivery)
# ---------------------------------------------------------

@app.route('/ask-ai/query', methods=['POST'])
@login_required
def ask_ai_query():
    question = (request.get_json(silent=True) or {}).get('question', '').strip()
    if not question:
        return jsonify({'error': 'Please type a question.'}), 400

    if not llm_configured():
        return jsonify({'error': 'AI is not configured yet. Set OPENROUTER_API_KEY in .env and restart the app.'}), 400

    prompt = f"""You are a marketing assistant helping a small business owner who uses this app.
Answer ONLY general marketing questions (content ideas, tone, platform choice, offer wording, timing strategy, etc).
If asked about facts you cannot know (their specific stock, exact shop hours, real sales numbers), say you don't have that data and suggest where in the app to find or enter it.
Keep answers short - 2 to 4 sentences, practical, friendly.

Question: {question}"""

    try:
        answer = call_llm(prompt, max_tokens=300)
    except LLMError as e:
        return jsonify({'error': str(e)}), 502

    return jsonify({'answer': answer.strip()})


# ---------------------------------------------------------
# DB INIT
# ---------------------------------------------------------

@app.cli.command('init-db')
def init_db():
    db.create_all()
    print('Database tables created.')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
