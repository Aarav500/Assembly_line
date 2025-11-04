from app import create_app


def main():
    app = create_app(testing=False)
    app.run(host="127.0.0.1", port=5001, debug=False)


if __name__ == "__main__":
    main()

