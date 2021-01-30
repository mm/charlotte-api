"""Contains methods for generating API keys and validating
whether an API key matches the hash stored on record for a user.
"""

from functools import wraps
from typing import NamedTuple
from secrets import token_hex, compare_digest
from hashlib import sha256
from flask import request, jsonify
from src.model import User

api_pair = NamedTuple('KeyDetails', [('api_key', str), ('hashed_key', str)])

class AuthError(Exception):
    """Exception raised when validating incoming JWTs or API
    keys.
    """
    def __init__(self, message, status_code=401):
        self.message = message
        self.status_code = status_code


def generate_api_key() -> api_pair:
    """Generates a random token to use as an API key.
    Returns a named tuple containing the key (`api_key`) and a hash
    value (`hashed_key`). The hashed version is what is saved
    to the database.
    """

    api_key = str(token_hex(32))  # 32 bytes of randomness
    hash_value = sha256(api_key.encode('utf-8')).hexdigest()
    return api_pair(api_key, hash_value)


def validate_api_key(user_id: int, api_key: str) -> bool:
    """Checks the hash of the API key submitted against
    that currently stored in the database. Returns True
    if the key is a match.

    Arguments:
    - user_id: An integer representing the user in the database
    - api_key: The key to check against
    """
    if (not user_id) or (not api_key):
        return False

    # Compute SHA-256 hash of API key to check:
    submitted_hash = sha256(api_key.encode('utf-8')).hexdigest()

    # Get hash for user ID in database:
    try:
        user = User.query.get(user_id)
        user_hash = user.api_key
    except Exception as e:
        print("User fetching failed.")
        return False
    
    return compare_digest(submitted_hash, user_hash)


def user_for_api_key(api_key: str) -> User:
    """Returns a User object for a specified API key,
    or None if no user exists with that key.
    """
    
    if api_key:
        # Compute SHA-256 hash of API key to query table for:
        key_hash = sha256(api_key.encode('utf-8')).hexdigest()

        # Check table for a User with that key:
        user = User.query.filter_by(api_key=key_hash).first()
        return user
    return None


def user_from_jwt(authorization_header):
    """Attempts to validate a JWT and retrieve the user from the JWT
    claims. Returns a User object if authentication was successful.
    """
    return None


def requires_auth(f):
    """Wraps a view function to ensure a valid JWT or
    API key has been provided in the request. 
    
    Will yield a 403 if unsuccessful, or return the view function 
    with the `current_user` variable populated as a User object otherwise.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = None
        if 'Authorization' in request.headers:
            # JWT may have been passed in, validate it:
            user = user_from_jwt(request.headers.get('Authorization'))
        if 'x-api-key' in request.headers:
            # User may have passed an API key:
            api_key = request.headers.get('x-api-key')
            user = user_for_api_key(api_key)
        if user is None:
            raise AuthError("Authorization is required to access this resource")
        return f(*args, **kwargs, current_user=user)
    return decorated_function
