from backend.app import create_app, init_database

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Create and run app
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)