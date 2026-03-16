"""sigmark -- GPG signing for static site markdown content."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sigmark")
except PackageNotFoundError:
    __version__ = "0.1.0"  # fallback for development

__author__ = "Alex Towell"
__email__ = "lex@metafunctor.com"
