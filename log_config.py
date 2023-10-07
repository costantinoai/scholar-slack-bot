#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct  7 17:42:13 2023

@author: costantino_ai
"""

import logging

# Define custom logging levels
MIN = 35
STANDARD = 25

# Add custom logging levels
logging.addLevelName(MIN, "MIN")
logging.addLevelName(STANDARD, "STANDARD")