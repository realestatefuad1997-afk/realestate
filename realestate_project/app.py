from app import create_app

app = create_app()

if __name__ == "__main__":
    # DEBUG=True للبيئة التطويرية
    app.run(host="127.0.0.1", port=5000, debug=True)
