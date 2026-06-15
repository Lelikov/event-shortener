import secrets


_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
_GROUP_LENGTH = 3
_GROUP_COUNT = 3


def generate_ident() -> str:
    """Return a Google-Meet-style ident: three groups of three lowercase letters joined by '-'.

    Example: 'qmk-rba-htz', keyspace 26^9 ≈ 5.4e12.

    Uniqueness is enforced by the DB; the controller regenerates on a unique
    violation, so this only needs to be uniformly random, not collision-proof.
    """
    groups = (
        "".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LENGTH)) for _ in range(_GROUP_COUNT)
    )
    return "-".join(groups)
