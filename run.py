"""
FraudGuard AI - Development Server Entrypoint
"""

import os
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    is_prod = os.environ.get('FLASK_ENV') == 'production'
    print(f"\n* Starting FraudGuard AI on http://127.0.0.1:{port}")
    print("* Educational Fraud Detection Prototype (Model Estimates, Not Certified Banking Guarantees)")
    app.run(host='127.0.0.1', port=port, debug=(not is_prod))
