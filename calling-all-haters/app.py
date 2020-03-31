import asyncio
import copy
import functools
import hashlib
import hmac
import json
import logging
import os
import random
import sqlite3
import socket
import time
import traceback
import uuid
from datetime import datetime
from enum import Enum

from quart import (Quart, abort, copy_current_websocket_context, jsonify,
                   make_response, redirect, render_template, request, session,
                   websocket)

import utils
from compress import Compress


async def validate_token(token):
    valid, token_user_id, _session_hmac = utils.parse_token(token)
    logging.debug(f"Validating token. valid: {valid}, user id: {token_user_id}, hmac: {_session_hmac}")
    if not valid:
        return False, utils.InvalidToken(f'Invalid format')

    cur = db.cursor()
    cur.execute('SELECT * FROM USERS WHERE id = ?', (token_user_id,))
    res = utils.sanitize_sqlite(cur, cur.fetchone(), isone=True)
    user = User(res, False)
    if not res:
        logging.debug(f"Failed to validate token due to invalid id. Received {token_user_id}")
        return False, utils.InvalidToken(f'Could not find user with id "{user.id}" or retrieve their hmac value')

    _id_bytes = user.id.to_bytes((user.id.bit_length() + 8) // 8, 'big', signed=True)
    _uuid1_bytes = bytes.fromhex(res['hmac'])
    _hmac = hmac.new(_id_bytes, _uuid1_bytes, 'md5').digest()

    logging.debug(f"{_hmac} == {_session_hmac}")
    if not hmac.compare_digest(_hmac, _session_hmac):
        logging.debug("Failed to validate hmac digests")
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
        logging.debug(f"Fetched user with object {res}")
        return User(res, False)
    else:
        logging.debug(f"Failed to retrieve user. id: {id}, fetch_from_name: {fetch_from_name}")
        return None


async def validate_password(user, passhash):
    if type(user) == int:
        user = await get_user(user)
        if not user:
            logging.debug(f"Failed to retrieve user. user: {user}")
            return None, utils.AuthorizationException('Invalid user')
    digest = hashlib.sha256(passhash.encode("utf8")).hexdigest()
    logging.debug(f"{digest} == {user.hash}")
    return digest == user.hash


async def can_authenticate(allow_guests=True):
    token = request.headers.get("authorization", request.cookies.get("token", session.get("token")))
    logging.debug(f"Received token '{token}'")
    if not token:
        logging.debug("Failing due to no token")
        return False, "You do not have a token. Login as a guest or user to receive one."
    if token == "guest" and not allow_guests:
        logging.debug("Endpoint expected guests however user had a guest token")
        return False, "Guests are not allowed to use this. Login as a user to use this."
    valid_token, resp = await validate_token(token)
    logging.debug(f"Finished validation. valid: {valid_token}")
    return valid_token, resp


async def fetch_custom_deck(id):
    return False, None


def require_token_api(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        valid_token, resp = await can_authenticate()
        if valid_token:
            return await func(*args, **kwargs)
        else:
            return jsonify({"success": False, "error": "Unauthorized"})


def require_token_endpoint(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        valid_token, resp = await can_authenticate()
        if valid_token:
            return await func(*args, **kwargs)
        else:
            return abort(401)


class Round:
    __slots__ = ['number', 'black_card', 'czar', 'played', 'winning', 'winning_card', 'active', 'game']

    def __init__(self, data, game):
        self.number = data.get("number")
        self.black_card = Card(data.get("black_card", ""), CardType.black_card)
        self.czar = data.get("czar")
        self.played = {}
        self.winning = None
        self.winning_card = None
        self.active = []
        self.game = game

    def to_data(self, reveal_played=False, return_scores=True):
        data = {
            "number": self.number,
            "black_card": self.black_card.to_data(True),
            "czar": self.czar.to_data(),
            "active": len(self.active) - 1
        }
        if return_scores:
            data['scores'] = dict([(p.id, p.points) for p in self.game.players])
        if reveal_played:
            data["played"] = list([player.id, [c.to_data() for c in card]] for player, card in self.played.values())
        else:
            data["played"] = list([player_id, None] for player_id in self.played.keys())

        if self.winning:
            data["winning"] = self.winning.to_data()
            data["winning_card"] = [c.to_data() for c in self.winning_card]
        return data


class Game:
    __slots__ = ['id', 'encoded_id', 'settings', 'started_at', 'is_live', 'game_duration', 'players', 'decks', 'started', 'current_black_card', 'czar_index', 'state', 'timeout', 'host', 'game_task_holder', 'rounds']

    def __init__(self, data, host):
        self.id = data.get("id", 0)
        self.encoded_id = data.get("encoded_id")
        self.settings = data.get("settings", game_defaults)
        self.started_at = utils.timestamp()
        self.is_live = data.get("is_live", False)
        self.game_duration = data.get("game_duration", 0)

        self.rounds = []
        self.players = []
        self.decks = [default_packs[_id] for _id in self.settings['game_packs']]
        self.started = False
        self.current_black_card = None
        self.czar_index = random.randint(0, 10)
        self.state = 0
        self.game_task_holder = None
        self.timeout = 0

        _host = Player(self, host, None, {"is_host": True})
        self.host = _host

    def to_data(self, safe=True, discovery=False):
        data = {
            "decks": [deck.to_data() for deck in self.decks],
            "players": [player.to_data() for player in self.players],
            "host": self.host.to_data(),
            "id": self.id,
            "encoded_id": self.encoded_id,
            "is_live": self.is_live,
            "state": self.state
        }
        data['settings'] = copy.deepcopy(self.settings)
        if safe:
            data['settings']['password'] = bool(data['settings']['password'])
        if discovery:
            data['decks'] = [deck['name'] for deck in data['decks']]
        return data

    def to_db(self):
        data = self.to_data(True, True)
        data['rounds'] = [r.to_data(reveal_played=True) for r in self.rounds]
        data['duration'] = self.game_duration
        return data

    # States:
    # 0: Lobby room
    # 1: Round start
    # 2: Players card picking
    # 3: Czar picking card
    # 4: Going to next round

    def round_to_data(self, show_played=False):
        data = {
            "round": len(self.rounds) + 1,
            "black_card": self.current_black_card,
            "timeout": self.timeout,
            "state": self.state
        }
        if show_played:
            data['show_played'] = [[c.text for c in p.played_card] for p in self.players if p.played_card]
        return data

    async def destroy(self, message="This game has ended"):
        await self.broadcast({
            "o": 3,
            "m": message
        })
        del games[self.encoded_id]
        if self.game_task_holder is not None:
            self.game_task_holder.cancel()

    async def game_task(self):
        await self.broadcast({
            "o": 0,
            "e": "GAME_START",
        })
        try:
            while True:
                game_round = Round({
                    "number": len(self.rounds) + 1
                }, self)

                self.rounds.append(game_round)
                self.czar_index += 1

                seconds_wait = int(self.settings['timer_limit'] * 60)
                game_round.active = [player for player in self.players if player.active]

                if len(game_round.active) < 2:
                    await self.destroy("Not enough players to continue",)
                    return

                game_round.czar = game_round.active[self.czar_index % len(game_round.active)]
                game_round.czar.is_czar = True

                self.state = 1
                await self.broadcast({
                    "o": 0,
                    "e": "ROUND_UPDATE",
                    "d": game_round.to_data(),
                    "s": self.state
                })

                for player in self.players:
                    player.played_card = None
                    player.fill_deck(10, list(set([a for b in [[c.text for c in p.deck] for p in self.players] for a in b])))
                    try:
                        await player.websocket.send(json.dumps({
                            "o": 0,
                            "e": "PLAYER_UPDATE",
                            "d": player.to_data(False)
                        }))
                    except BaseException:
                        traceback.print_exc()

                for deck in utils.shuffle([deck for deck in self.decks if len(deck.black) > 0]):
                    game_round.black_card = deck.retrieve_black_card()
                    break

                self.state = 2
                self.timeout = utils.timestamp() + seconds_wait
                await self.broadcast({
                    "o": 0,
                    "e": "ROUND_UPDATE",
                    "d": game_round.to_data(),
                    "s": self.state,
                    "t": self.timeout * 1000
                })

                # Waiting for players to select cards
                # game_round.active.remove(game_round.czar)
                active_ids = [p.id for p in game_round.active]
                while utils.timestamp() < self.timeout:
                    await asyncio.sleep(1)
                    # if len(game_round.played) >= len(game_round.active) - 1:
                    if len([p for p, c in game_round.played.values() if p.id in active_ids]) >= len(game_round.active) - 1:
                        break

                # Purge inactive users
                submitted = [player for player, cards in game_round.played.values()]
                not_submitted = [player for player in game_round.active if player not in submitted and not player.is_czar]
                for player in not_submitted:
                    player.active = False
                    try:
                        await player.websocket.send(json.dumps({
                            "o": 3,
                            "m": "You were kicked for being inactive",
                            "t": 3
                        }))
                    except BaseException:
                        traceback.print_exc()

                if len(game_round.played) > 0:
                    # Prepare czar selection
                    self.state = 3
                    self.timeout = utils.timestamp() + 60
                    await self.broadcast({
                        "o": 0,
                        "e": "ROUND_UPDATE",
                        "d": game_round.to_data(reveal_played=True),
                        "s": self.state,
                        "t": self.timeout * 1000
                    })

                    if len(game_round.played) == 1:
                        game_round.winning_card = list(game_round.played.values())[0][1]
                        game_round.winning = list(game_round.played.values())[0][0]

                    # Waiting fo czar to select cards
                    while utils.timestamp() < self.timeout:
                        await asyncio.sleep(1)
                        if game_round.winning_card:
                            break

                    if not game_round.winning_card:
                        game_round.czar.active = False
                        try:
                            await game_round.czar.websocket.send(json.dumps({
                                "o": 3,
                                "m": "You were kicked for being inactive",
                                "t": 3
                            }))
                        except BaseException:
                            traceback.print_exc()

                    if game_round.winning:
                        game_round.winning.points += 1

                self.state = 4
                await self.broadcast({
                    "o": 0,
                    "e": "ROUND_END",
                    "d": game_round.to_data(reveal_played=True),
                    "s": self.state,
                    "t": -1
                })

                for player in self.players:
                    player.is_czar = False

                await asyncio.sleep(5)
                player_won = [p for p in self.players if p.points >= self.settings['score_limit']]
                if player_won:
                    player_won = player_won[0]
                    break

            await self.broadcast({
                "o": 0,
                "e": "GAME_END",
                "d": player_won.to_data()
            })

            self.game_duration = utils.timestamp() - self.started_at
            db_entry = self.to_db()

            f = open("game_"+str(self.id)+".json", "w")
            json.dump(db_entry, f)
            f.close()

            db.execute(
                "INSERT INTO GAMES (id, rounds, started_at, game_duration, players) VALUES(?, ?, ?, ?, ?)",
                (self.id, json.dumps(db_entry['rounds']), self.started_at, self.game_duration, json.dumps(db_entry['players']))
            )
            for player in self.players:
                if not player.is_guest:
                    if player_won.id == player.user.id:
                        player.user.total_wins += 1
                    player.user.total_points += player.points
                    _games = player.user.games
                    if type(_games) != list:
                        _games = [_games]
                    _games.append(self.id)
                    dumped_games = json.dumps(_games)
                    db.execute(
                        "UPDATE USERS SET games = ?, total_wins = ?, total_points = ? WHERE id = ?",
                        (dumped_games, player.user.total_wins, player.user.total_points, player.user.id)
                    )
            db.commit()

            del games[self.encoded_id]
            # EXPORT GAME
        except BaseException:
            traceback.print_exc()

        pass

    async def broadcast(self, data):
        if not isinstance(data, str):
            data = json.dumps(data)
        for player in [p for p in self.players if p.active]:
            try:
                await player.websocket.send(data)
            except BaseException:
                traceback.print_exc()

    async def player_join(self, player):
        # Send player information and change conflicting names
        player.active = True
        for _player in self.players:
            if _player.id == player.id:
                _player.active = True
            else:
                if _player.display_name == player.display_name:
                    names = [p.display_name for p in self.players]
                    if player.is_guest:
                        i = 0
                        while True:
                            i += 1
                            if f"{player.name}({i})" not in names:
                                break
                        player.display_name = f"{player.name}({i})"
                        await self.broadcast({
                            "o": 0,
                            "e": "PLAYER_UPDATE",
                            "d": player.to_data()
                        })
                    else:
                        i = 0
                        while True:
                            i += 1
                            if f"{_player.name}({i})" not in names:
                                break
                        _player.display_name = f"{_player.name}({i})"
                        await self.broadcast({
                            "o": 0,
                            "e": "PLAYER_UPDATE",
                            "d": _player.to_data()
                        })

        # Send Game Information
        await player.websocket.send(json.dumps({
            "o": 0,
            "e": "GAME_INIT",
            "d": player.game.to_data(False, True)
        }))

        # Send Player Information
        await player.websocket.send(json.dumps({
            "o": 0,
            "e": "PLAYER_UPDATE",
            "d": player.to_data(False)
        }))

        # Send Round Information
        if len(player.game.rounds) > 0:
            await player.websocket.send(json.dumps({
                "o": 0,
                "e": "ROUND_UPDATE",
                "d": player.game.rounds[-1].to_data(reveal_played=player.game.state == 3),
                "s": player.game.state,
                "t": player.game.timeout * 1000
            }))

    async def player_leave(self, player):
        player.active = False
        for _player in self.players:
            if _player.id == player.id:
                _player.active = False


class Player:
    __slots__ = ['deck', 'display_name', 'id', 'is_czar', 'is_guest', 'is_host', 'is_spectator', 'name', 'points', 'user', 'websocket', 'active', 'game', 'played_card']

    def __init__(self, game, user, _websocket, data={}):
        self.user = user
        self.is_czar = False
        self.is_host = data.get("is_host", False)
        self.is_guest = data.get("is_guest", getattr(user, "is_guest", False))
        self.is_spectator = data.get("is_spectator", False)
        self.name = self.user.name
        self.display_name = data.get("display", self.name)
        self.id = user.id
        self.active = False
        self.points = 0
        self.deck = []
        self.websocket = _websocket
        self.game = game
        self.played_card = None

    def to_data(self, safe=True):
        # Exports data to how data is sent to users
        # If safe, it means its data thats expectedto go to anyone
        # this means that safe=False sends whats in the users deck
        # (intended for that player only)
        data = {
            "is_czar": self.is_czar,
            "is_host": self.is_host,
            "is_guest": self.is_guest,
            "is_spectator": self.is_spectator,
            "name": self.name,
            "display_name": self.display_name,
            "id": self.id,
            "points": self.points,
        }
        if not safe:
            data['deck'] = [card.to_data() for card in self.deck]
        return data

    def fill_deck(self, count, _filter=[]):
        # Fills players deck with the specific number of white cards
        self.deck = self.deck[:count]
        while len(self.deck) < count:
            card = None
            while not card:
                for deck in utils.shuffle([deck for deck in self.game.decks if len(deck.white) > 0]):
                    card = copy.copy(deck.retrieve_white_card(self.deck))
                    if card is not None and card not in _filter:
                        card.identifier = utils.generateHex(16)
                        self.deck.append(card)
                        break
        pass


class User:
    __slots__ = ['games', 'id', 'is_guest', 'name', 'total_points', 'total_wins', '_games', 'hmac', 'hash', 'created_at']

    def __init__(self, data, is_guest):
        self.name = data.get("name")
        self.id = data.get("id")
        self.games = data.get("games", "[]")
        self.games = json.loads(self.games) if isinstance(self.games, str) else self.games
        self._games = {}
        self.total_points = data.get("total_points", 0)
        self.total_wins = data.get("total_wins", 0)
        self.is_guest = is_guest
        self.hmac = data.get("hmac")
        self.hash = data.get("hash")
        self.created_at = data.get("created_at")

    async def fetch_games(self):
        # Converts games in game list to their game objects.
        for game in self.games:
            if game not in self._games:
                with db.cursor() as cur:
                    cur.execute(
                        f'SELECT * FROM GAMES WHERE id = ?',
                        (id,)
                    )
                    res = utils.sanitize_sqlite(cur, cur.fetchone(), isone=True)
                    if res:
                        self._games[game] = Game(res, False)
        return self._games

    def from_data(self, data):
        # Exports from how data is stored
        self.name = data.get("name")
        self.id = data.get("id")
        self.games = json.loads(data.get("games", "[]"))
        self.total_points = data.get("total_points", 0)
        self.total_wins = data.get("total_wins", 0)
        self.hmac = data.get("hmac")
        self.hash = data.get("hash")
        self.created_at = data.get("created_at")
        return self

    def to_data(self):
        # Exports data to how data is stored
        return {
            "name": self.name,
            "id": self.id,
            "total_points": self.total_points,
            "total_wins": self.total_wins,
            "created_at": self.created_at,
            "is_guest": self.is_guest,
            "games": self.games
        }


class Deck:
    __slots__ = ['name', 'id', 'white', 'black', 'empty', 'short']

    def __init__(self, data):
        self.name = data.get("name")
        self.short = data.get("short", self.name[:2])
        self.id = data.get("id")
        self.white = [Card(card, CardType.white_card, deck=self.id, is_blank=False) for card in data.get("white", [])]
        self.black = [Card(card, CardType.black_card, deck=self.id, is_blank=False) for card in data.get("black", [])]
        self.empty = data.get("empty", 0)

    def from_data(self, data):
        # Exports from how data is stored
        self.name = data.get("name")
        self.short = data.get("short", self.name[:2])
        self.id = data.get("id")
        self.white = [Card(card, CardType.white_card, deck=self.id, is_blank=False) for card in data.get("white", [])]
        self.black = [Card(card, CardType.black_card, deck=self.id, is_blank=False) for card in data.get("black", [])]
        self.empty = data.get("empty", 0)

    def to_data(self):
        # Exports data to how data is stored
        return {
            "name": self.name,
            "id": self.id,
            "white": [card.text for card in self.white],
            "black": [card.text for card in self.black],
            "empty": self.empty,
            "short": self.short,
        }

    def retrieve_black_card(self, filter=[]):
        # Returns a random black card.
        # If a filter is specified, it will ignore cards with that name
        for card in utils.shuffle(self.black):
            if card not in filter:
                return card
        else:
            # If we cant find one at random might aswell give up and return one
            return card

    def retrieve_white_card(self, filter=[], blank_cards=True):
        # Returns a random white card.
        # If a filter is specified, it will ignore cards with that name
        # If blank cards is true, it will have a possibilty of returning a blank card
        if blank_cards:
            if random.randint(-self.empty, len(self.white)) < 0:
                return Card("", CardType.blank_card, is_blank=True)
        for card in utils.shuffle(self.white):
            if card.text not in [c.text for c in filter]:
                return card
        else:
            # If we cant find one at random might aswell give up and return one
            return None


class CardType(Enum):
    white_card = 0
    black_card = 1
    blank_card = 2


class Card:
    __slots__ = ['text', 'type', 'is_blank', 'deck', 'identifier']

    def __init__(self, text, _type, deck=None, is_blank=False):
        self.text = text
        self.type = _type
        self.is_blank = is_blank or self.type.value == 2
        self.deck = deck
        self.identifier = 0
        if self.type == CardType.black_card and "_" not in self.text:
            self.text = self.text.rstrip() + " _"

    def to_data(self, return_deck=False):
        data = {
            "text": self.text,
            "type": self.type.value,
            "identifier": self.identifier
        }
        if return_deck:
            data["deck"] = self.deck
        return data


class Heartbeat:
    __slots__ = ['time', 'count', 'interval', 'delta', 'is_closed']

    def __init__(self, interval, delta=None):
        self.time = utils.timestamp()
        self.count = 0
        self.interval = interval
        self.delta = delta or int(self.interval / 2) - 0.1
        self.is_closed = False


logging.getLogger().setLevel(logging.DEBUG)
app = Quart(__name__)
app.secret_key = "wglfULERHGGFBUPY"
def gettime():
    return int(utils.timestamp())
app.jinja_env.globals['time'] = gettime
Compress(app)


logging.info("Connecting to database")
db = sqlite3.connect("database.db")
db.execute("CREATE TABLE IF NOT EXISTS USERS (id integer primary key, name text, created_at date, games text, total_points integer, total_wins integer, hmac text, hash text)")
db.execute("CREATE TABLE IF NOT EXISTS GAMES (id integer primary key, rounds text, started_at date, game_duration integer, players text)")
db.execute("CREATE TABLE IF NOT EXISTS DECKS (id integer primary key, name text, white text, black text, blank integer)")
db.commit()
logging.info("Created and commited any nonexistant databases")


games = {}
default_packs = {}
default_card_pack_location = "defaultpacks"
game_defaults = {
    "score_limit": 8,
    "timer_limit": 1,
    "player_limit": None,
    "game_packs": ["base_game_1.0", "base_game_1.3", "base_game_1.5", "base_game_1.6", "first_expansion", "second_expansion", "third_expansion", "forth_expansion", "fifth_expansion", "sixth_expansion"],
    "custom_packs": [],
    "password": None,
    "show_password": False,
    "allow_guests": True,
}

if os.path.isdir(default_card_pack_location):
    logging.info(f"Found default card pack location")
    for _file in os.listdir(default_card_pack_location):
        _file = os.path.join(default_card_pack_location, _file)
        logging.info(f"Found file '{_file}'")
        try:
            with open(_file, "r") as f:
                data = json.load(f)
                deck = Deck(data)
                default_packs[deck.id] = deck
                logging.info(f"Successfuly loaded deck with name: {deck.name}")
        except BaseException:
            traceback.print_exc()
else:
    logging.warning(f"Could not locate default card pack location.")


@app.route("/")
async def _index():
    return await render_template("index.html", session=session)


@app.route("/game")
@app.route("/game/<gameid>")
async def _game(gameid=None):
    return await render_template("game.html", session=session)


async def _game_websocket_heartbeat(heartbeat):
    while not heartbeat.is_closed:
        await asyncio.sleep((heartbeat.interval + heartbeat.delta) - (utils.timestamp() - heartbeat.time) + 0.5)
        if (utils.timestamp() - heartbeat.time) > (heartbeat.interval + heartbeat.delta):
            heartbeat.is_closed = True
            await websocket.send(json.dumps({
                "o": 3,
                "m": "Failed heartbeat"
            }))
            return


async def _game_websocket_receive(heartbeat, game):
    try:
        authenticated = False
        player = None
        while not heartbeat.is_closed:
            response = await websocket.receive()
            try:
                response = json.loads(response)
            except BaseException:
                traceback.print_exc()

            logging.debug(response)
            opcode = response.get("o")
            if opcode is None:
                continue

    #   "d": {
    #     "score_limit": $("#settings-score-limit").val(),
    #     "timer_limit": $("#settings-timer-limit").val(),
    #     "player_limit": [$("#settings-player-limit-enabled")[0].checked, $("#settings-player-limit").val()],
    #     "password": [$("#settings-password-enabled")[0].checked, $("#settings-password").val(), $("#settings-password-show")[0].checked],
    #     "gamepacks": $("#settings-game-packs").val(),
    #     "custompacks": $("#settings-custom-game-packs").val()
    #   }

            if opcode == 0:
                # DISPATCH
                event = response.get("e")
                if event is None:
                    continue
                if event == "GAME_START" and not game.started:
                    if authenticated and player.is_host:
                        if len(game.decks) < 1:
                            await player.websocket.send(json.dumps({
                                "o": 3,
                                "t": 2,
                                "m": "No decks have been selected"
                            }))
                            continue
                        whites = 0
                        blacks = 0
                        for deck in game.decks:
                            whites += len(deck.white)
                            blacks += len(deck.black)
                        if blacks < 50:
                            await player.websocket.send(json.dumps({
                                "o": 3,
                                "t": 2,
                                "m": f"Not enough black cards. You must have atleast 50, you currently have {blacks}"
                            }))
                            continue
                        if whites < 50:
                            await player.websocket.send(json.dumps({
                                "o": 3,
                                "t": 2,
                                "m": f"Not enough white cards. You must have atleast 200, you currently have {whites}"
                            }))
                            continue
                        if len(game.players) < 2:
                            await player.websocket.send(json.dumps({
                                "o": 3,
                                "t": 2,
                                "m": f"Not enough players. You need atleast 2 players to start the game"
                            }))
                            continue
                        game.started = True
                        loop = asyncio.get_event_loop()
                        game.game_task_holder = loop.create_task(game.game_task())
                    else:
                        await player.websocket.send(json.dumps({
                            "o": 3,
                            "t": 2,
                            "m": "You do not have permission to do this"
                        }))
                if event == "UPDATE_SETTINGS":
                    if authenticated and player.is_host:
                        data = response.get("d")
                        if data is None:
                            continue

                        _custompacks = []
                        gamepacks = []

                        if data.get("score_limit") is not None:
                            try:
                                score_limit = int(data.get("score_limit"))
                            except BaseException:
                                pass
                            else:
                                if score_limit >= 1:
                                    game.settings['score_limit'] = score_limit
                        if data.get("timer_limit") is not None:
                            try:
                                timer_limit = float(data.get("timer_limit"))
                            except BaseException:
                                pass
                            else:
                                if timer_limit >= 0.25:
                                    game.settings['timer_limit'] = timer_limit
                        if data.get("player_limit") is not None:
                            try:
                                player_limit_enabled, player_limit = data.get("player_limit")
                                player_limit = int(player_limit)
                            except BaseException:
                                pass
                            else:
                                game.settings['player_limit'] = player_limit if player_limit_enabled and player_limit >= 1 else None
                        if data.get("password") is not None:
                            password_enabled, password, show_password = data.get("password")
                            game.settings['password'] = password if password_enabled and len(password) > 0 else None
                            game.settings['show_password'] = show_password
                        if data.get("gamepacks") is not None:
                            gamepacks = [_id for _id in data.get("gamepacks") if _id in default_packs]
                            game.settings['game_packs'] = gamepacks
                        if data.get("custompacks") is not None:
                            custompacks = [p.strip() for p in data.get("custompacks").split(",")]
                            for _id in custompacks:
                                found, pack = await fetch_custom_deck(_id)
                                if found:
                                    _custompacks.append(pack)
                            game.settings['custom_packs'] = [p.id for p in _custompacks]
                        if data.get("allow_guests") is not None:
                            game.settings['allow_guests'] = data.get("allow_guests")

                        game.decks = [default_packs[_id] for _id in game.settings['game_packs']] + [await fetch_custom_deck(_id)[1] for _id in game.settings['custom_packs']]
                        await game.broadcast({
                            "o": 0,
                            "e": "GAME_UPDATE",
                            "d": game.settings
                        })
                    else:
                        await player.websocket.send(json.dumps({
                            "o": 3,
                            "t": 2,
                            "m": "You do not have permission to do this"
                        }))
                if event == "PLAYER_SELECT" and game.started and game.state == 2 and not player.is_czar:
                    data = response.get("d")
                    if data is None or type(data) != list:
                        continue

                    game_round = player.game.rounds[-1]
                    player.active = True
                    if player.id not in [p.id for p in game_round.active]:
                        continue

                    max_cards = game_round.black_card.text.count("_")
                    cards = data[:max_cards]
                    deck_cards = dict((c.identifier, c) for c in player.deck)
                    deck_ids = deck_cards.keys()

                    for card in cards:
                        if card not in deck_ids:
                            break
                    else:
                        game_round.played[player.id] = [player, [deck_cards[card] for card in cards]]
                        player.played_card = [c for c in player.deck if c.identifier in cards]
                        player.deck = [c for c in player.deck if c.identifier not in cards]

                        await player.game.broadcast({
                            "o": 0,
                            "e": "ROUND_UPDATE",
                            "d": game_round.to_data(),
                            "s": player.game.state,
                            "t": player.game.timeout * 1000
                        })
                if event == "CZAR_SELECT" and game.started and game.state == 3 and player.is_czar:
                    data = response.get("d")
                    if data is None:
                        continue

                    game_round = player.game.rounds[-1]
                    for _player in game_round.active:
                        if _player.id == data:
                            game_round.winning = _player
                            game_round.winning_card = _player.played_card
                            break

            if opcode == 2:
                # IDENTIFY
                data = response.get("d")
                if data is None:
                    continue
                token = data.get("t")
                if token is None:
                    continue
                if (game.settings.get('player_limit', 0) or 0) > 0 and len(game.players) >= (game.settings.get('player_limit', 0) or 0):
                    return await websocket.send(json.dumps({
                        "o": 3,
                        "m": "Game full",
                    }))
                if game.settings['password'] and not session.get("data", {}).get("id", 0) in [p.id for p in game.players + [game.host]]:
                    password = data.get("p")
                    if password != game.settings['password']:
                        return await websocket.send(json.dumps({
                            "o": 3,
                            "m": "Invalid password",
                            "t": 1
                        }))
                authorized, user = await validate_token(token)
                if authorized is False:
                    user = User(session.get('data', {'name': 'Guest ' + utils.generateHex()}), True)
                if user.is_guest and not game.settings['allow_guests']:
                    return await websocket.send(json.dumps({
                        "o": 3,
                        "m": "This group is for logged in users only"
                    }))
                authenticated = True
                for _player in game.players:
                    if _player.id == user.id:
                        player = _player
                        break
                else:
                    player = Player(game, user, copy.copy(websocket), {"is_host": user.id == game.host.id})
                    game.players.append(player)
                    await game.broadcast({
                        "o": 0,
                        "e": "PLAYER_ADDITION",
                        "d": player.to_data(True)
                    })
                player.active = True
                player.websocket = copy.copy(websocket)
                await game.player_join(player)
            if opcode == 3:
                # HEARTBEAT
                heartbeat.count = response.get("d", heartbeat.count + 1)
                heartbeat.time = utils.timestamp()
                await websocket.send(json.dumps({
                    "o": 4,
                    "d": heartbeat.count
                }))
    except Exception:
        traceback.print_exc()


@app.websocket("/game/<gameid>")
async def _game_websocket(gameid=None):
    if gameid is None:
        return await websocket.send(json.dumps({
            "o": 3,
            "m": "Missing gameid"
        }))
    if gameid not in games:
        return await websocket.send(json.dumps({
            "o": 3,
            "m": "This game does not exist or is not live"
        }))

    heartbeat = Heartbeat(15)
    game = games[gameid]

    await websocket.accept()
    await websocket.send(json.dumps({
        "o": 1,
        "d": heartbeat.interval
    }))

    fut = [
        asyncio.ensure_future(copy_current_websocket_context(_game_websocket_receive)(heartbeat, game)),
        asyncio.ensure_future(copy_current_websocket_context(_game_websocket_heartbeat)(heartbeat))
    ]
    await asyncio.wait(fut, return_when=asyncio.FIRST_COMPLETED)
    logging.debug("Cleaning futures")
    for future in fut:
        future.cancel()


@app.route("/leaderboards")
async def _leaderboards():
    return await render_template("leaderboards.html", session=session)


@app.route("/games")
async def _games():
    resp, user = await can_authenticate(allow_guests=True)
    print(resp, user)
    return jsonify(user.to_data())


@app.route("/games/<id>")
async def _games_view(id):
    id = utils.decodeid(id)
    cur = db.cursor()
    cur.execute('SELECT * FROM GAMES WHERE id = ?', (id,))
    fetches = cur.fetchall()
    if len(fetches) > 0:
        round_data = utils.sanitize_sqlite(cur, fetches[0], isone=True)
        round_data['players'] = json.loads(round_data['players'])
        round_data['rounds'] = json.loads(round_data['rounds'])
        return jsonify({"success": True, "results": round_data})
    else:
        return jsonify({"success": False, "results": None})

@app.route("/logout")
async def _logout():
    session.clear()
    resp = await make_response(redirect("/"))
    resp.delete_cookie("data")
    resp.delete_cookie("token")
    resp.delete_cookie("session")
    return resp


@app.route("/api/ntp")
async def _api_ntp():
    return jsonify(int(datetime.utcnow().timestamp() * 1000))


@app.route("/api/discovery")
async def _api_discovery():
    return jsonify([game.to_data(discovery=True) for game in games.values()])


@app.route("/api/leaderboards")
async def _api_leaderboards():
    cur = db.cursor()

    cur.execute('SELECT name,total_wins,id FROM USERS ORDER BY total_wins DESC')
    total_wins = utils.sanitize_sqlite(cur, cur.fetchall())
    cur.execute('SELECT name,total_points,id FROM USERS ORDER BY total_points DESC')
    total_points = utils.sanitize_sqlite(cur, cur.fetchall())

    data = {"wins": total_wins[:10], "points": total_points[:10]}
    _id = session.get("data", {}).get("id", None)
    if _id:
        wpos = [n for n, v in enumerate(total_wins) if v['id'] == _id]
        ppos = [n for n, v in enumerate(total_points) if v['id'] == _id]
        if wpos and ppos:
            data['positions'] = {
                "wins": wpos[0],
                "points": ppos[0]
            }

    return jsonify(data)


@app.route("/api/login", methods=['POST'])
async def _api_login():
    form = await request.form
    username = form.get("username")
    password = form.get("password")
    guest_login = form.get("guest", "false").lower() == "true"

    if guest_login:
        if username.strip() == "":
            return jsonify({"success": False, "error": "Invalid username"})
        if " " in username:
            return jsonify({"success": False, "error": "Usernames cannot have spaces"})

        token = "guest"
        session['token'] = token
        user = User({"name": username, 'id': str(uuid.uuid4())}, True)
        session['data'] = user.to_data()
        logging.info(f"Authenticated guest {user.name} with token {token}")
        resp = await make_response(jsonify({"success": True, "token": token, "data": user.to_data()}))
        resp.set_cookie("token", token)
        resp.set_cookie("data", json.dumps(user.to_data()))
        return resp
    else:
        if not (username and password):
            return jsonify({"success": False, "error": "Missing username or password in form"})
        user = await get_user(username, fetch_from_name=True)

        if user is None:
            return jsonify({"success": False, "error": "Invalid username or password"})
        if not await validate_password(user, password):
            return jsonify({"success": False, "error": "Invalid username or password"})

        token, _hmac = utils.create_token(user)
        db.execute(
            "UPDATE USERS SET hmac = ? WHERE id = ?",
            (_hmac, user.id,)
        )
        db.commit()

        session['token'] = token
        session['data'] = user.to_data()
        logging.info(f"Authenticated user {user.name} ({user.id}) with token {token}")
        resp = await make_response(jsonify({"success": True, "token": token, "data": user.to_data()}))
        resp.set_cookie("token", token)
        resp.set_cookie("data", json.dumps(user.to_data()))
        return resp


@app.route("/api/register", methods=['POST'])
async def _api_register():
    form = await request.form
    username = form.get("username")
    password = form.get("password")

    if not (username and password):
        return jsonify({"success": False, "error": "Missing username or password"})

    if username.strip() == "":
        return jsonify({"success": False, "error": "Invalid username"})
    if password.strip() == "":
        return jsonify({"success": False, "error": "Invalid password"})
    if " " in username:
        return jsonify({"success": False, "error": "Usernames cannot have spaces"})
    if " " in password:
        return jsonify({"success": False, "error": "Passwords cannot have spaces"})

    user = await get_user(username, fetch_from_name=True)
    if user:
        return jsonify({"success": False, "error": "A user already has this name"})

    password_hash = hashlib.sha256(password.encode("utf8")).hexdigest()

    _id = uuid.uuid1().int >> 94
    _now = datetime.utcnow()

    token, _hmac = utils.create_token(User({"id": _id}, False))

    db.execute(
        "INSERT INTO USERS (id, name, created_at, games, total_points, total_wins, hmac, hash) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        (_id, username, _now, "[]", 0, 0, _hmac, password_hash)
    )
    db.commit()

    user = await get_user(_id)
    session['token'] = token
    session['data'] = user.to_data()
    logging.info(f"Registered and authenticated user {user.name} ({user.id}) with token {token}")
    resp = await make_response(jsonify({"success": True, "token": token, "data": user.to_data()}))
    resp.set_cookie("token", token)
    resp.set_cookie("data", json.dumps(user.to_data()))
    return resp


@app.route("/api/game/<id>")
async def _api_game_id(id):
    _id = utils.decodeid(id)
    cur = db.cursor()
    cur.execute('SELECT * FROM USERS WHERE id = ?', (_id,))
    res = utils.sanitize_sqlite(cur, cur.fetchone(), isone=True)
    return jsonify(res)



@app.route("/api/creategame")
async def _api_creategame():
    valid_token, user = await can_authenticate(allow_guests=False)
    if valid_token:
        for game in games.values():
            if (game.host.id == user.id) and game.is_live and not game.started:
                break
        else:
            _base, _id = utils.encodeid()
            custom_settings = {}
            settings = copy.copy(game_defaults)
            settings.update(custom_settings)
            game = Game({"id": _id, "encoded_id": _base, "is_live": True, "settings": settings}, user)
            logging.info(f"Created new game with id {_id} ({_base})")
            games[game.encoded_id] = game
        return jsonify({"success": True, "data": game.to_data(False)})
    else:
        return jsonify({"success": False, "error": "Guests cannot make games. Please login"})


@app.route("/api/packs/default")
async def _api_packs_default():
    return jsonify([deck.to_data() for deck in default_packs.values()])


# / - Index page
# /game/<gameid> - Page when in a game
# /games/<gameid> - View game history
# /profile - View account profile
# /ws - Connect to game backend

# /api/creategame
# /api/profile - Returns profile information
# /api/game/<> - Returns previous/current game information
# /api/packs/default - Returns default packs
# /api/packs/search - Searches custom packs
# /api/packs/custom/<> - Returns pack information for a custom pack


host_name = socket.gethostname()
print(f"Host IP: {socket.gethostbyname(host_name)}")
app.run(host=utils.HOST, port=utils.PORT, debug=utils.DEBUG)
