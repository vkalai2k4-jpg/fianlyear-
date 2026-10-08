# AI Marketing Content Generator & Optimizer

Final-year capstone project — a Flask web app that generates AI-powered marketing
content, checks sentiment, recommends the best variation, routes it through manager
approval, and auto-publishes via email.

## Setup

1. Install Python 3.10+ if you don't have it.

2. Open this folder in VS Code, open a terminal, and create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate      (Windows)
   source venv/bin/activate   (Mac/Linux)
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   python -m textblob.download_corpora
   ```

4. Copy `.env.example` to `.env` and fill in your values:
   - `ANTHROPIC_API_KEY` — optional. Without it, the app uses built-in fallback
     content templates so you can still demo it.
   - `SECRET_KEY` — any random string.
   - `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` — optional, needed only for the
     Auto-Publish email step to actually send. Without it, the app will mark
     the send as skipped but still move the campaign through the workflow.

5. Run the app:
   ```
   python app.py
   ```
   Open http://127.0.0.1:5000 in your browser.

## How to demo the full workflow

1. Register two accounts: one as **Business Owner**, one as **Manager**.
2. As Owner: go to Customers, add 1-2 test customer emails.
3. As Owner: create a new campaign, fill in product details, pick a tone.
4. The app generates 3 content variations, scores sentiment, and highlights the
   recommended one.
5. Select a variation, preview it as a mock email, submit for approval.
6. Log out, log in as Manager, review the campaign, and Approve it.
7. On approval, the system automatically tries to send the email to the
   customer list and marks the campaign as "Sent".
8. Both dashboards show campaign history and status.

## New features added

- **Email OTP verification** — both owners/managers (on register) and customers (on being added)
  must verify a 6-digit code sent to their email before they can log in / receive campaigns.
- **12 marketing types** (Festival offer, Product launch, Discount sale, etc.) — the dropdown on
  the New Campaign page is built automatically from `content_templates.py`.
- **AI mode vs Template mode** — generate content with Claude, or fall back to a free,
  no-API-key template for the same 12 marketing types.
- **Bilingual content** — English, Tamil, or Tanglish, for both AI-generated content and emails.
- **Banner Studio** — generates a banner headline + subtext with Claude, plus a free background
  image via Pollinations.ai (no API key needed).
- **Templates Gallery** — browse all 12 ready-made templates.
- **Showcase** — pulls real approved/sent campaigns from your own database to display as examples.

## Project structure

```
ai_marketing_generator/
├── app.py              # Main Flask app and all routes
├── models.py            # SQLAlchemy database models
├── ai_generator.py       # Claude API call + sentiment scoring + fallback templates
├── email_utils.py        # SMTP/Gmail sending logic
├── requirements.txt
├── .env.example
├── templates/            # All HTML pages (Bootstrap)
└── static/css/style.css
```
