import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import base64
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from utils.generator import generate_business_plan
from utils.pptx_generator import generate_pitch_deck_pptx
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')


def default_form_values():
    return {
        'company_name': '',
        'tagline': '',
        'problem': '',
        'solution': '',
        'target_market': '',
        'business_model': '',
        'go_to_market': '',
        'competition': '',
        'unfair_advantage': '',
        'team': '',
        'financials': '',
        'ask': ''
    }


@app.route('/', methods=['GET'])
def index():
    values = default_form_values()

    if request.args.get('demo') == '1':
        values = {
            'company_name': 'Acme AI',
            'tagline': 'AI co-pilot for small retail inventory',
            'problem': 'Small retailers lose sales and cash flow due to stockouts and overstocking. Manual inventory decisions are error-prone and time-consuming.',
            'solution': 'A plug-and-play AI inventory co-pilot that forecasts demand, auto-reorders from suppliers, and optimizes pricing with a simple dashboard.',
            'target_market': 'Independent SMB retailers in the US (boutiques, convenience stores, specialty shops), ~1.2M stores with $50B TAM for inventory tools.',
            'business_model': 'SaaS subscription: $79-$299/mo per location + 0.2% of managed purchases. Partnerships with POS providers.',
            'go_to_market': 'Integrations with Square/Shopify POS, channel partners, and local retail associations. Inside sales and self-serve onboarding.',
            'competition': 'Legacy ERP and spreadsheets; modern tools like Inventory Planner. We differentiate via true AI automation, speed to value, and pricing.',
            'unfair_advantage': 'Proprietary demand model trained on anonymized POS integrations and supplier lead times; onboarding in under 30 minutes.',
            'team': 'Founders: ex-Amazon supply chain PM, ex-OpenAI ML engineer, ex-Square BD lead. Advisors from retail tech.',
            'financials': 'Yr1: $300k ARR; Yr2: $1.8M ARR; Yr3: $6.5M ARR. 80% gross margin, CAC payback < 4 months.',
            'ask': 'Raising $1.5M seed to accelerate integrations, expand GTM, and achieve 1,000 locations. Use of funds: 50% eng, 30% GTM, 20% ops.'
        }

    return render_template('index.html', values=values)


@app.route('/generate', methods=['POST'])
def generate():
    form = {k: (request.form.get(k) or '').strip() for k in default_form_values().keys()}

    plan_text, slides = generate_business_plan(form)

    # Generate PPTX
    pptx_bytes = generate_pitch_deck_pptx(form, slides)
    b64_pptx = base64.b64encode(pptx_bytes.getvalue()).decode('utf-8')

    # Store in session for download
    session['pptx_b64'] = b64_pptx

    # Also store plan for text download
    session['plan_text'] = plan_text

    return render_template('result.html', plan_text=plan_text, values=form)


@app.route('/download/slides', methods=['GET'])
def download_slides():
    b64 = session.get('pptx_b64')
    if not b64:
        flash('Nothing to download. Please generate a deck first.')
        return redirect(url_for('index'))
    raw = base64.b64decode(b64)
    bio = BytesIO(raw)
    bio.seek(0)
    return send_file(
        bio,
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        as_attachment=True,
        download_name='pitch_deck.pptx'
    )


@app.route('/download/plan', methods=['GET'])
def download_plan():
    plan_text = session.get('plan_text', '')
    if not plan_text:
        flash('Nothing to download. Please generate a plan first.')
        return redirect(url_for('index'))
    bio = BytesIO(plan_text.encode('utf-8'))
    bio.seek(0)
    return send_file(
        bio,
        mimetype='text/plain; charset=utf-8',
        as_attachment=True,
        download_name='business_plan.txt'
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)



def create_app():
    return app


@app.route('/health', methods=['GET'])
def _auto_stub_health():
    return 'Auto-generated stub for /health', 200
