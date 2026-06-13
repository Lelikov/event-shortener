class NotFoundError(Exception):
    """Requested short URL does not exist (or was deleted)."""


class IdentGenerationError(Exception):
    """Could not allocate a unique ident after the bounded retry budget."""
