#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 17:42:13 2023

@author: costantino_ai
"""

import logging

# Map custom names to standard levels for backward compatibility
MIN = logging.INFO
STANDARD = logging.DEBUG


def configure_logging(verbose: bool = False) -> None:
    """Configure root logger with standard format."""
    level = STANDARD if verbose else MIN
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

