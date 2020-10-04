def detect_flask():
    try:
        import flask

        print("Flask found at", flask.__file__)
    except:
        print("No flask found")
