# -*- coding: utf-8 -*-
"""Configuración de pytest: hace importables los módulos de src/ (ADR-002)."""
import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
