from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/process_coordinates")
def process_coordinates():
    lat = request.args.get("lat")
    lng = request.args.get("lng")

    if lat is None or lng is None:
        return jsonify({"error": "Missing coordinates"}), 400

    try:
        lat = float(lat)
        lng = float(lng)
    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400

    # Print received coordinates
    print(f"Received coordinates: Lat={lat}, Lng={lng}")

    return jsonify({"message": "Coordinates received!"})


if __name__ == "__main__":
    app.run(debug=True)
