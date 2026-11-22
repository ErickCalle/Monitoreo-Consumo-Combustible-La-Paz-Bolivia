"""Parche de compatibilidad: manim-slides 5.7.0 todavia usa un par de
claves de configuracion de Manim que la version instalada (0.22.1) ya
elimino o endurecio. Se importa (solo por su efecto secundario) ANTES
de `from manim_slides import Slide` en cualquier escena.
"""

from manim._config.utils import ManimConfig

if not hasattr(ManimConfig, "write_to_movie"):
    ManimConfig.write_to_movie = property(lambda self: True, lambda self, v: None)

_orig_max_files_cached = ManimConfig.max_files_cached


def _max_files_cached_set(self, val):
    if val == float("inf"):
        val = -1
    _orig_max_files_cached.fset(self, val)


ManimConfig.max_files_cached = property(_orig_max_files_cached.fget, _max_files_cached_set)

if not hasattr(ManimConfig, "flush_cache"):
    def _flush_cache_get(self):
        return self.__dict__.get("_ms_compat_flush_cache", False)

    def _flush_cache_set(self, val):
        self.__dict__["_ms_compat_flush_cache"] = val

    ManimConfig.flush_cache = property(_flush_cache_get, _flush_cache_set)
