import secrets


_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
IDENT_LENGTH = 7


def generate_ident() -> str:
    """Return a random 7-char base62 ident (~62^7 ≈ 3.5e12 keyspace).

    Uniqueness is enforced by the DB; the controller regenerates on a unique
    violation, so this only needs to be uniformly random, not collision-proof.
    """
    return "".join(secrets.choice(_ALPHABET) for _ in range(IDENT_LENGTH))
