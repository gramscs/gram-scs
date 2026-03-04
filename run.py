from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Use debug mode only in development
    debug = os.getenv('FLASK_ENV') == 'development'
    app.run(debug=debug)

