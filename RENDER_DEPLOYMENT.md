# Deploying to Render

This guide explains how to deploy the Gram SCS Flask application to Render.com.

## Prerequisites

1. **GitHub Account** - with your fork of the repository
2. **Render Account** - sign up at [render.com](https://render.com)
3. **Email Configuration** (optional) - for contact form functionality

## Step-by-Step Deployment

### 1. Connect Your GitHub Repository to Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New"** and select **"Web Service"**
3. Choose **"Deploy an existing repository"**
4. Search for `gram-scs-it-dept` (your fork)
5. Select it and click **"Connect"**

### 2. Configure the Web Service

**Basic Settings:**
- **Name**: `gram-scs` (or any name you prefer)
- **Environment**: `Python 3`
- **Region**: Select closest to your users (e.g., Oregon, Frankfurt)
- **Plan**: Free tier available, upgrade as needed
- **Branch**: `main`

**Build Settings:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn --workers 3 --threads 2 --worker-class gthread --bind 0.0.0.0:10000 run:app`

Render will auto-detect these from `render.yaml` if present.

### 3. Set Environment Variables

In the Render dashboard, go to **Environment** and add:

```
FLASK_ENV=production
SECRET_KEY=<generate-a-random-secret-key>
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=<your-gmail@gmail.com>
MAIL_PASSWORD=<app-password-from-gmail>
CONTACT_EMAIL_RECIPIENT=<email-to-receive-forms>
```

**Generating a SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Gmail Configuration (if using contact form):**
1. Enable 2-Factor Authentication on your Gmail account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Generate an app password for Gmail
4. Use this password in `MAIL_PASSWORD`, NOT your actual Gmail password

### 4. Database Persistence (Important!)

**Warning**: SQLite on Render's free tier will be reset on each deployment. For free tier:

**Option A (Recommended for free tier):**
- Use PostgreSQL database (Render offers 90-day free tier)
- Update database connection string

**Option B (For testing/demo):**
- Keep current SQLite setup
- Accept that data resets on deployment
- Use `seed_data.py` to repopulate

### 5. Deploy

1. Click **"Create Web Service"**
2. Render will start building and deploying
3. Wait for **"Your service is live"** message
4. Your app will be available at `https://<service-name>.onrender.com`

## Post-Deployment Steps

### 1. Verify Deployment

```bash
# Check if app is running
curl https://<service-name>.onrender.com/

# Test track endpoint
curl -X POST https://<service-name>.onrender.com/track \
  -d "consignment_number=DEMO001"

# Test admin panel (secret route)
curl https://<service-name>.onrender.com/xk7m2p
```

### 2. Seed Initial Data

After deployment, you can seed data using the admin panel at `/xk7m2p`:
1. Visit `https://<service-name>.onrender.com/xk7m2p`
2. Add consignment entries manually

Or run locally and push to database:
```bash
python seed_data.py
```

### 3. Monitor Logs

In Render dashboard:
1. Go to your Web Service
2. Click **"Logs"** tab
3. View deployment and application logs
4. Check for any errors

### 4. Set Up Auto-Deploys

Render automatically redeploys on `git push` to `main` branch. This is already enabled.

To disable:
1. Go to **Settings** → **Auto-Deploy**
2. Toggle off if needed

## Troubleshooting

### **Port Issues**
- Render uses port 10000 by default
- Gunicorn command already configured in `Procfile` and `render.yaml`
- Do NOT expose port in Flask code

### **Static Files Not Loading**

Render should serve static files automatically. If issues:

```bash
# In Render dockerfile (if creating custom)
RUN python manage.py collectstatic --noinput
```

For Flask apps, static files work normally if using `url_for('static', ...)`.

### **Database Not Persisting**

This is expected on Render's free tier with SQLite. Options:

1. **Use PostgreSQL** (recommended):
   ```
   # In Render dashboard, create PostgreSQL database
   # Copy DATABASE_URL from credentials
   # Add to environment variables
   ```

2. **Switch to PostgreSQL in code**:
   ```python
   import os
   
   DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
   app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
   ```

3. **Accept SQLite reset** - reseed data on each restart

### **Email Not Sending**

1. Check MAIL_* environment variables are set correctly
2. Verify app password (not Gmail password) is used
3. Check logs for SMTP errors
4. May need to allow "Less secure apps" (depends on Gmail settings)

### **Admin Panel Not Working**

1. Ensure you're accessing `/xk7m2p` (secret route)
2. Database must be reachable
3. Check error logs in Render dashboard

### **High Memory Usage**

If app crashes due to memory:
1. Reduce number of workers in start command
2. Upgrade to paid plan
3. Optimize database queries

## Scaling Recommendations

### For Production Use:

1. **Upgrade Database**:
   - Switch from SQLite to PostgreSQL
   - Render offers managed PostgreSQL

2. **Add More Workers**:
   ```bash
   gunicorn --workers 4 --threads 2 ...
   ```

3. **Use Paid Plan**:
   - Free tier restarts after inactivity
   - Paid plans have better uptime
   - Better for production applications

4. **Enable Caching**:
   - Current implementation uses file-based cache
   - Consider Redis for production

5. **Set Up Backups**:
   - Automated database backups
   - Use Render's PostgreSQL backup feature
   - Or implement external backup service

## Useful Commands

### Redeploy Latest Code

```bash
git push origin main  # Triggers auto-deploy
```

### View Logs

In Render dashboard → Logs tab

### Manually Trigger Deploy

Render dashboard → Deployments → "Deploy latest"

### Check Service Status

```bash
# From Render dashboard
# Or use curl to check health
curl https://<service-name>.onrender.com/track
```

## File Structure for Deployment

```
gram-scs-it-dept/
├── Procfile                    # Deployment configuration
├── render.yaml                 # Render-specific config
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
├── run.py                       # Application entry point
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── services/
│   ├── main/
│   ├── pages/
│   └── templates/
└── static/                      # CSS, JS, images
```

## Environment Variables Reference

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_ENV` | Environment mode | `production` |
| `SECRET_KEY` | Flask secret key | Random hex string |
| `MAIL_SERVER` | SMTP server | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USE_TLS` | Use TLS | `true` |
| `MAIL_USERNAME` | Email address | `app@gmail.com` |
| `MAIL_PASSWORD` | App password | Generated from Gmail |
| `CONTACT_EMAIL_RECIPIENT` | Recipient email | `admin@example.com` |
| `DATABASE_URL` | Database connection | PostgreSQL conn string |
| `LOG_LEVEL` | Logging level | `INFO`, `DEBUG`, `ERROR` |

## Support & Documentation

- **Render Docs**: https://render.com/docs
- **Flask Docs**: https://flask.palletsprojects.com/
- **Gunicorn Docs**: https://gunicorn.org/
- **GitHub**: Your repository

## Next Steps

After deployment:
1. Test all features (track, contact, admin panel)
2. Monitor logs for errors
3. Set up email forwarding if needed
4. Configure custom domain (optional)
5. Set up monitoring/alerts (optional)

---

**Note**: For production deployments, always:
- Use strong SECRET_KEY
- Enable HTTPS (Render does this automatically)
- Use PostgreSQL instead of SQLite
- Set up regular backups
- Monitor application logs
