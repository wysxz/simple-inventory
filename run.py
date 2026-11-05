from project.app import app

if __name__ == '__main__':
    # Start app
    app.run(
        debug=app.config['DEBUG'],
        host=app.config.get("HOST", "127.0.0.1"),
        port=app.config.get("PORT", 8700),
        threaded=True
    )
