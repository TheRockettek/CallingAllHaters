from enum import Enum
import hmac
import sqlite3

from datetime import datetime
from quart import Quart, jsonify, render_template, request, session, websocket

import utils
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
        return User(res)
    else:
        return None


class Game:
    __slots__ = ['czar_index', 'decks', 'game_duration', 'players', 'settings', 'started_at']

    def __init__(self, data, host):
        self.settings = data
        self.players = []
        self.decks = []
        self.czar_index = -1
        self.started_at = datetime.utcnow()
        self.game_duration = 0

    def to_data(self):
        pass


class Player:
    __slots__ = ['deck', 'display_name', 'id', 'is_czar', 'is_guest', 'is_host', 'is_spectator', 'name', 'points', 'user']

    def __init__(self, user, data):
        self.user = user
        self.is_czar = False
        self.is_host = data.get("is_host", False)
        self.is_guest = data.get("is_guest", False)
        self.is_spectator = data.get("is_spectator", False)
        self.name = self.user.name
        self.display_name = data.get("display", self.name)
        self.id = data.get("id")
        self.points = 0
        self.deck = []

    def to_data(self, safe=True):
        # Exports data to how data is sent to users
        # If safe, it means its data thats expectedto go to anyone
        # this means that safe=False sends whats in the users deck
        # (intended for that player only)
        pass

    def fill_deck(self, count):
        # Fills players deck with the specific number of white cards
        pass


class User:
    __slots__ = ['games', 'id', 'is_guest', 'name', 'total_points', 'total_wins']

    def __init__(self, data, is_guest):
        self.name = data.get("name")
        self.id = data.get("id")
        self.games = data.get("games", [])
        self._games = []
        self.total_points = data.get("total_points", 0)
        self.total_wins = data.get("total_wins", 0)
        self.is_guest = is_guest

    async def fetch_games():
        # Converts games in game list to their game objects.
        pass

    def from_data(self, data):
        # Exports from how data is stored
        pass

    def to_data(self):
        # Exports data to how data is stored
        pass


class Deck:
    __slots__ = ['name', 'id', 'white', 'black', 'empty']

    def __init__(self, data):
        self.name = data.get("name")
        self.id = data.get("id")
        self.white = data.get("white", [])
        self.black = data.get("black", [])
        self.empty = data.get("empty", 0)

    def from_data(self, data):
        # Exports from how data is stored
        pass

    def to_data(self):
        # Exports data to how data is stored
        pass

    def retrieve_black_card(self, filter=[]):
        # Returns a random black card.
        # If a filter is specified, it will ignore cards with that name
        pass

    def retrieve_white_card(self, filter=[], blank_cards=True):
        # Returns a random white card.
        # If a filter is specified, it will ignore cards with that name
        # If blank cards is true, it will have a possibilty of returning a blank card
        pass


class CardType(Enum):
    white_card = 0
    black_card = 1
    blank_card = 2


class Card:
    __slots__ = ['text', 'type', 'is_blank']

    def __init__(self, text, _type, is_blank=False):
        self.text = text
        self.type = _type
        self.is_blank = is_blank or self.type.value == 2


app = Quart(__name__)
db = sqlite3.connect("database.db")
games = []


@app.route("/")
@compress_response()
async def _index():
    return await render_template("index.html")


@app.route("/game")
@compress_response()
async def _game():
    return await render_template("game.html")


@app.route("/api/discovery")
@compress_response()
async def _api_discovery():
    return jsonify([game.to_data() for game in games])

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
