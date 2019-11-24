from quart import Quart, jsonify, render_template, request, session, websocket

import objects
from compress import compress_response

app = Quart(__name__)


@app.route("/")
@compress_response()
async def _index():
    return await render_template("index.html")

@app.route("/game")
@compress_response()
async def _game():
    return await render_template("game.html")


app.run(host="0.0.0.0", port=80, debug=True)
