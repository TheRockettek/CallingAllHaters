import hmac
import sqlite3

from quart import Quart, jsonify, render_template, request, session, websocket

import utils
import objects
from compress import compress_response


async def validate_token(token, user=None):
    valid, token_user_id, _session_hmac = utils.parse_token(token)
    if not valid:
        return False, utils.InvalidToken(f'Invalid format')

    cur = db.cursor()
    cur.execute('SELECT hmac FROM USERS WHERE id = ?', (token_user_id,))
    res = utils.sanitize_sqlite(cur, cur.fetchone(), isone=True)
    if not res:
        return False, utils.InvalidToken(f'Could not find user with id "{user.id}" or retrieve their hmac value')

    _id_bytes = user.id.to_bytes((user.id.bit_length() + 8) // 8, 'big', signed=True)
    _uuid1_bytes = bytes.fromhex(res['hmac'])
    _hmac = hmac.new(_id_bytes, _uuid1_bytes).digest()

    if not hmac.compare_digest(_hmac, _session_hmac):
        return False, utils.InvalidToken(f'Initial digest "{_hmac}" did not match session digest "{_session_hmac}"')

    return True, user


async def get_user(id, fetch_from_name=False):
    cur = db.cursor()
    if fetch_from_name:
        cur.execute(
            f'SELECT * FROM USERS WHERE name = ?',
            (id,)
        )
    else:
        cur.execute(
            f'SELECT * FROM USERS WHERE id = ?',
            (id,)
        )
    res = utils.sanitize_sqlite(cur, cur.fetchone(), isone=True)
    if res:
        return objects.User(res)
    else:
        return None


class Game:
    __slots__ = ['players', 'settings', 'decks', 'db']

    def __init__(self, data, host):
        self.settings = data
        self.players = []
        self.decks = []


class Player:
    __slots__ = ['name', 'display_name', 'id', 'points', 'deck', 'is_czar', 'is_host', 'is_guest', 'user', 'db']

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
    __slots__ = ['name', 'id', 'games', 'total_points', 'total_wins', 'db']

    def __init__(self, data):
        self.name = data.get("name")
        self.id = data.get("id")
        self.games = []
        self.total_points = data.get("total_points", 0)
        self.total_wins = data.get("total_wins", 0)


class Deck:
    __slots__ = ['name', 'id', 'white', 'black', 'empty', 'db']

    def __init__(self, data):
        self.name = data.get("name")
        self.id = data.get("id")
        self.white = data.get("white", [])
        self.black = data.get("black", [])
        self.empty = data.get("empty", 0)


app = Quart(__name__)
db = sqlite3.connect("database.db")


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
