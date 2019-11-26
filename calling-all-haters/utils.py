import random
import string
import datetime
import uuid
import base64
import hmac


class NameAlreadyExists(Exception):
    pass


class InvalidToken(Exception):
    pass


class AuthorizationException(Exception):
    pass


class WebsocketException(Exception):
    pass


def generateHex(length=8):
    return "".join(random.choices(list(string.hexdigits), k=8))


def sanitize_sqlite(cursor, results, isone=False):
    _keys = [d[0] for d in cursor.description]
    if not results:
        return results
    if isone:
        sanitized = dict(zip(_keys, results))
        return sanitized
    else:
        sanitized = []
        for v in results:
            sanitized.append(dict(zip(_keys, v)))
        return sanitized


def create_token(user):
    _time = int(datetime.now().timestamp())
    _uuid1 = uuid.uuid1()

    _uuid1_bytes = _uuid1.int.to_bytes((_uuid1.int.bit_length() + 8) // 8, 'big', signed=True)
    _id_bytes = user.id.to_bytes((user.id.bit_length() + 8) // 8, 'big', signed=True)
    _hmac = hmac.new(_id_bytes, _uuid1_bytes).digest()

    _id_b64 = base64.b64encode(user.id.to_bytes((user.id.bit_length() + 8) // 8, 'big', signed=True)).decode()
    _time_b64 = base64.b64encode(_time.to_bytes((_time.bit_length() + 8) // 8, 'big', signed=True)).decode()
    _hmac_b64 = base64.b64encode(_hmac).decode()

    return f'{_id_b64}.{_time_b64}.{_hmac_b64}'.replace("=", "_"), _uuid1_bytes.hex()


def parse_token(token):
    user_id, timestamp, _hmac = token.replace("_", "=").split(".")
    if len(token.split(".")) != 3:
        return False, None, None
    try:
        token_user_id = int.from_bytes(base64.b64decode(user_id), 'big', signed=True)
        _session_hmac = base64.b64decode(_hmac)
    except Exception:
        return False, None, None
    return True, token_user_id, _session_hmac
