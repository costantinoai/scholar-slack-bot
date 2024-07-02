#!/bin/bash
source /home/costantino_ai/miniconda3/etc/profile.d/conda.sh  # Use the correct path to conda.sh
conda activate scrape
cd /home/eik-tb/costantino_ai/GitHub/scholar-slack-bot/
python main.py --verbose
