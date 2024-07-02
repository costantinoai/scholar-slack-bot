#!/bin/bash
source /home/eik-tb/miniconda3/etc/profile.d/conda.sh  # Use the correct path to conda.sh
conda activate scrape
cd /home/eik-tb/OneDrive_andreaivan.costantino@kuleuven.be/GitHub/scholar-slack-bot/
python main.py --verbose
