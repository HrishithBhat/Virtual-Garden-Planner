import os
from backend.app import create_app, init_database

if __name__ == '__main__':
    # Initialize database
    init_database()

    # Create and run app
    app = create_app()
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', '0') in ('1','true','True')
    app.run(debug=debug, host=host, port=port)
