from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from app import cache
from app.models import db, Lead, NewsletterSubscriber
import os
import logging
import re
from datetime import datetime, UTC

# Configure logging
logger = logging.getLogger(__name__)


main_bp = Blueprint(
    "main",
    __name__,
    template_folder="templates"
)


# ----------------------------
# HOME
# ----------------------------
@main_bp.route("/")
@cache.cached(timeout=300)
def index():
    return render_template("main/index.html")


# ----------------------------
# ABOUT
# ----------------------------
@main_bp.route("/about")
@cache.cached(timeout=300)
def about():
    return render_template("main/about.html")


# ----------------------------
# CONTACT
# ----------------------------
@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        try:
            source = request.form.get('source', '').strip().lower()
            return_to_homepage = source == 'homepage'

            def _redirect_after_submit():
                if return_to_homepage:
                    return redirect(url_for("main.index") + "#contact")
                return redirect(url_for("main.contact"))

            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()
            
            # Validate inputs
            if not name or not email or not message:
                flash("Please fill in all required fields.", "error")
                if return_to_homepage:
                    return _redirect_after_submit()
                return render_template("main/contact.html")
            
            # Validate email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash("Please enter a valid email address.", "error")
                if return_to_homepage:
                    return _redirect_after_submit()
                return render_template("main/contact.html")
            
            try:
                lead = Lead(
                    name=name,
                    email=email,
                    phone=phone,
                    subject=subject,
                    message=message,
                )
                db.session.add(lead)
                db.session.commit()
                logger.info("Contact lead saved to database for %s", email)
            except Exception as e:
                db.session.rollback()
                logger.error(f"Failed to save contact lead: {e}")
                flash("There was an issue submitting your message. Please try again.", "error")
                if return_to_homepage:
                    return _redirect_after_submit()
                return render_template("main/contact.html")

            flash("Message sent successfully! We'll get back to you soon.", "success")
            return _redirect_after_submit()
            
        except Exception as e:
            logger.error(f"Unexpected error in contact form: {e}")
            flash("An unexpected error occurred. Please try again later.", "error")
            if request.form.get('source', '').strip().lower() == 'homepage':
                return redirect(url_for("main.index") + "#contact")
            return render_template("main/contact.html")

    return render_template("main/contact.html")


# ----------------------------
# NEWSLETTER
# ----------------------------
@main_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    try:
        email = request.form.get('email') or (request.get_json(silent=True) or {}).get('email')

        if not email or not email.strip():
            return jsonify({'success': False, 'message': 'Email address is required'}), 400

        email = email.strip().lower()

        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'}), 400

        existing = NewsletterSubscriber.query.filter_by(email=email).first()
        if existing:
            return jsonify({'success': True, 'message': 'You are already subscribed!'})

        subscriber = NewsletterSubscriber(email=email, subscribed_at=datetime.now(UTC))
        db.session.add(subscriber)
        db.session.commit()
        logger.info("Newsletter subscription saved for %s", email)
        return jsonify({'success': True, 'message': 'Successfully subscribed to newsletter'})

    except Exception as e:
        db.session.rollback()
        logger.error("Unexpected error in newsletter subscription: %s", e)
        return jsonify({'success': False, 'message': 'An unexpected error occurred'}), 500

