"""Ensure the QtMultimedia backend is loadable during UI tests (Windows Store Python
restricts the DLL search path; this mirrors what app bootstrap does at runtime)."""

from cravingcrave.app import _ensure_media_backend

_ensure_media_backend()
