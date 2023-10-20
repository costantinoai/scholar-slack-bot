#!/bin/bash

declare -a ids=(
    "U4i0WGsAAAAJ"
    "FS0s6WYAAAAJ"
    "Tv-zquoAAAAJ"
)

source /home/eik-tb/miniconda3/etc/profile.d/conda.sh  # Use the correct path to conda.sh
conda activate scrape
cd /home/eik-tb/OneDrive_andreaivan.costantino@kuleuven.be/GitHub/scholar-slack-bot/

for id in "${ids[@]}"
do
   python main.py --add_scholar_id $id
done

