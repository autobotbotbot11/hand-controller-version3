"""UI package.

Keep this package-level import surface intentionally lightweight.
Do not import PyQt-heavy modules here, because some Windows environments
need MediaPipe to initialize before any Qt-related imports happen.
"""

__all__: list[str] = []
