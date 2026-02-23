from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from app import cache
import os
import json
from datetime import datetime

main_bp = Blueprint(
    "main",
    __name__,
    template_folder="templates"
)

@main_bp.route("/")
@cache.cached(timeout=300)
def index():
    return render_template("main/index.html")

@main_bp.route("/about")
@cache.cached(timeout=300)
def about():
    return render_template("main/about.html")

@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get('name') or request.form.get('your-name')
        email = request.form.get('email') or request.form.get('your-email')
        subject = request.form.get('subject') or request.form.get('your-subject')
        message = request.form.get('message') or request.form.get('your-message')

        entry = {
            'name': name,
            'email': email,
            'subject': subject,
            'message': message,
            'received_at': datetime.utcnow().isoformat() + 'Z'
        }

        storage_dir = os.path.join(os.getcwd(), 'storage')
        os.makedirs(storage_dir, exist_ok=True)
        submissions_file = os.path.join(storage_dir, 'contact_submissions.jsonl')
        try:
            with open(submissions_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

        return render_template('main/contact.html', success=True)

    return render_template("main/contact.html")


@main_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    # Accept form-encoded or JSON body
    email = request.form.get('email') or (request.get_json(silent=True) or {}).get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Email required'}), 400

    storage_dir = os.path.join(os.getcwd(), 'storage')
    os.makedirs(storage_dir, exist_ok=True)
    subs_file = os.path.join(storage_dir, 'newsletter_subscribers.jsonl')
    entry = {'email': email, 'subscribed_at': datetime.utcnow().isoformat() + 'Z'}
    try:
        with open(subs_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        return jsonify({'success': False, 'message': 'Could not save subscription'}), 500

    return jsonify({'success': True, 'message': 'Subscribed successfully'})
