import random
import string

from compress import compress_response
from quart import Quart, jsonify, render_template, request, session, websocket


def generateHex(length=8):
    return "".join(random.choices(list(string.hexdigits), k=8))


class Game:
    __slots__ = ['players', 'settings', 'decks']

    def __init__(self, data, host):
        self.settings = data
        self.players = []
        self.decks = []

class Player:
    __slots__ = ['name', 'display_name', 'id', 'points', 'deck', 'is_czar', 'is_host', 'is_guest', 'user']

    def __init__(self, data):
        self.user = data.get("user")
        self.is_czar = False
        self.is_host = data.get("host")
        self.is_guest = bool(self.user)
        self.name = data.get("name")
        self.display_name = data.get("display", self.name)
        self.id = data.get("id")
        self.points = 0
        self.deck = []


class User:
    __slots__ = ['name', 'id', 'games', 'total_points', 'total_wins']

    def __init__(self, data):
        self.name = data.get("name")
        self.id = data.get("id")
        self.games = []
        self.total_points = data.get("total_points", 0)
        self.total_wins = data.get("total_wins", 0)


class Deck:
    __slots__ = ['name', 'id', 'white', 'black', 'empty']

    def __init__(self, data):
        self.name = data.get("name")
        self.id = data.get("id")
        self.white = data.get("white", [])
        self.black = data.get("black", [])
        self.empty = data.get("empty", 0)


app = Quart(__name__)


@app.route("/")
@compress_response()
async def _index():
    return await render_template("index.html")

@app.route("/game")
@compress_response()
async def _game():
    return await render_template("game.html")


# / - Index page
# /game - Page when in a game
# /games/<> - View game history
# /profile - View account profile
# /leaderboards - View leaderboards
# /ws - Connect to game backend

# /api/profile - Returns profile information
# /api/game/<> - Returns previous game information
# /api/leaderboards - Returns leaderboard information
# /api/discovery - Lists active games
# /api/login - Endpoint for logging in
# /api/register - Endpoint for registering

app.run(host="0.0.0.0", port=80, debug=True)
