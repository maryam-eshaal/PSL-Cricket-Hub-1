"""
PSL Cricket Hub
===============
One file, three ways to use it:

  streamlit run app.py      -> the full web app (Streamlit + Pandas + Matplotlib + Pillow)
  python app.py             -> a small Gradio explorer (teams, players, seasons)
  python app.py --turtle    -> a Turtle drawing of the PSL trophy (needs a desktop window)

DATA NOTE
All cricket facts below were checked against public sources (Wikipedia season pages,
ESPNcricinfo, PCB / news reports, myKhel) in November 2026. Where a fact could not be
verified it is shown as "N/A" or "—" instead of being guessed.
Team logos and player photos are NOT official: logos are generated badges drawn with
Pillow, and photos are generated initials avatars (you can upload your own photo).
"""

import base64
import io
import json
import os
import subprocess
import sys
from datetime import date, datetime

import matplotlib

matplotlib.use("Agg")  # draw charts without needing a display window
import matplotlib.pyplot as plt
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont, ImageOps

VOTES_FILE = "votes.json"  # votes are saved here so they survive a restart

# =====================================================================
# 1. DATA  (edit this section to update the app)
# =====================================================================

# Colours are decorative theme colours, not official brand colours.
TEAMS = {
    "Hyderabad Kingsmen": {"code": "HK", "city": "Hyderabad, Sindh", "colors": ("#AD1457", "#F9A825"),
                           "captain": "Marnus Labuschagne", "joined": 2026},
    "Islamabad United": {"code": "IU", "city": "Islamabad", "colors": ("#C62828", "#FF8A65"),
                         "captain": "Shadab Khan", "joined": 2016},
    "Karachi Kings": {"code": "KK", "city": "Karachi, Sindh", "colors": ("#1565C0", "#4FC3F7"),
                      "captain": "David Warner", "joined": 2016},
    "Lahore Qalandars": {"code": "LQ", "city": "Lahore, Punjab", "colors": ("#2E7D32", "#C0CA33"),
                         "captain": "Shaheen Shah Afridi", "joined": 2016},
    "Multan Sultans": {"code": "MS", "city": "Multan, Punjab", "colors": ("#00796B", "#80CBC4"),
                       "captain": "Ashton Turner", "joined": 2018},
    "Peshawar Zalmi": {"code": "PZ", "city": "Peshawar, Khyber Pakhtunkhwa", "colors": ("#F9A825", "#212121"),
                       "captain": "Babar Azam", "joined": 2016},
    "Quetta Gladiators": {"code": "QG", "city": "Quetta, Balochistan", "colors": ("#6A1B9A", "#BA68C8"),
                          "captain": "Saud Shakeel", "joined": 2016},
    "Rawalpindiz": {"code": "RP", "city": "Rawalpindi, Punjab", "colors": ("#E65100", "#FFB74D"),
                    "captain": "Mohammad Rizwan", "joined": 2026},
}
CAPTAIN_NOTE = {
    "Multan Sultans": "Wikipedia lists Ashton Turner as 2026 captain; one pre-season preview named Shan Masood. "
                      "Please double-check before relying on it.",
}

# 2026 squads (Wikipedia, PSL 2026 page). "*" = overseas player, "(c)" = captain.
SQUADS = {
    "Hyderabad Kingsmen": ["Marnus Labuschagne (c)*", "Saim Ayub", "Hassan Khan", "Usman Khan (wk)", "Glenn Maxwell*",
                           "Akif Javed", "Maaz Sadaqat", "Mohammad Ali", "Kusal Perera*", "Irfan Khan Niazi",
                           "Shayan Jahangir", "Hammad Azam", "Asif Mehmood", "Hunain Shah", "Riley Meredith*",
                           "Sharjeel Khan", "Rizwan Mehmood", "Saad Ali", "Tayyab Arif", "Ahmed Hussain",
                           "Maheesh Theekshana*", "Saad Khan"],
    "Islamabad United": ["Shadab Khan (c)", "Andries Gous*", "Chris Green*", "Devon Conway*", "Faheem Ashraf",
                         "Mehran Mumtaz", "Mark Chapman*", "Imad Wasim", "Mir Hamza Sajjad", "Sameer Minhas",
                         "Sameen Gul", "Haider Ali", "Richard Gleeson*", "Mohammad Hasnain",
                         "Dipendra Singh Airee*", "Mohammad Faiq", "Salman Irshad", "Salman Mirza", "Nisar Ahmad",
                         "Mohsin Riaz", "Muhammad Jawadullah*", "Mubasir Khan"],
    "Karachi Kings": ["David Warner (c)*", "Hassan Ali", "Abbas Afridi", "Khushdil Shah", "Saad Baig", "Moeen Ali*",
                      "Azam Khan", "Salman Ali Agha", "Shahid Aziz", "Mir Hamza", "Adam Zampa*",
                      "Mohammad Hamza Sohail", "Aqib Ilyas*", "Khuzaima Tanveer", "Muhammad Waseem*", "Ihsanullah",
                      "Rizwan Ullah", "Reeza Hendricks*", "Haroon Arshad", "Faham-ul-Haq", "Omair Yousuf",
                      "Jason Roy*"],
    "Lahore Qalandars": ["Shaheen Shah Afridi (c)", "Abdullah Shafique", "Sikandar Raza*", "Muhammad Naeem",
                         "Mustafizur Rahman*", "Haris Rauf", "Usama Mir", "Fakhar Zaman", "Ubaid Shah",
                         "Haseebullah Khan", "Mohammad Farooq", "Parvez Hossain Emon*", "Asif Ali", "Tayyab Tahir",
                         "Rubin Hermann*", "Dunith Wellalage*", "Maaz Khan", "Shahab Khan", "Daniel Sams*",
                         "Ryan Burl*", "Hussain Talat", "Charith Asalanka*"],
    "Multan Sultans": ["Ashton Turner (c)*", "Shan Masood", "Steve Smith*", "Mohammad Nawaz", "Sahibzada Farhan",
                       "Mohammad Wasim Jr.", "Peter Siddle*", "Tabraiz Shamsi*", "Lachlan Shaw*", "Delano Potgieter*",
                       "Josh Philippe*", "Momin Qamar", "Mohammad Awais Zafar", "Mohammad Shehzad",
                       "Mohammad Ismail", "Arshad Iqbal", "Atizaz Habib Khan", "Faisal Akram", "Arafat Minhas",
                       "Mohammad Imran Randhawa", "Shehzad Gul", "Mohammad Huraira"],
    "Peshawar Zalmi": ["Babar Azam (c)", "Sufiyan Muqeem", "Abdul Samad", "Ali Raza", "Aaron Hardie*", "Aamir Jamal",
                       "Khurram Shahzad", "Mohammad Haris", "Khalid Usman", "Abdul Subhan", "James Vince*",
                       "Michael Bracewell*", "Kusal Mendis*", "Iftikhar Ahmed", "Nahid Rana*", "Mirza Tahir Baig",
                       "Kashif Ali", "Shahnawaz Dahani", "Farhan Yousaf", "Mohammad Basit", "Shoriful Islam*",
                       "Tanzid Hasan*", "Brian Bennett*", "Umar Akmal", "Mehran Mumtaz"],
    "Quetta Gladiators": ["Saud Shakeel (c)", "Abrar Ahmed", "Hassan Nawaz", "Usman Tariq", "Shamyl Hussain",
                          "Rilee Rossouw*", "Jahandad Khan", "Khawaja Nafay", "Wasim Akram Jr.", "Khan Zaib",
                          "Bismillah Khan", "Saqib Khan", "Brett Hampton*", "Sam Harper*", "Bevon Jacobs*",
                          "Ben McDermott*", "Tom Curran*", "Jahanzaib Sultan", "Ahmed Daniyal", "Alzarri Joseph*",
                          "Ahsan Ali", "Ali Khan*", "Abdul Bangalzai"],
    "Rawalpindiz": ["Mohammad Rizwan (c, wk)", "Sam Billings*", "Yasir Khan", "Naseem Shah", "Rishad Hossain*",
                    "Daryl Mitchell*", "Mohammad Amir", "Abdullah Fazal", "Amad Butt", "Dian Forrester*",
                    "Kamran Ghulam", "Fawad Ali", "Mohammad Amir Khan", "Asif Afridi", "Shahzaib Khan",
                    "Saad Masood", "Jalat Khan", "Cole McConchie*", "Usman Khawaja*", "Imam-ul-Haq", "Sajid Khan",
                    "Abdul Faseeh", "Ben Sears*"],
}

# Season history. runs/wkts = (player, team, number). "time" is only filled when a source gave it.
SEASONS = [
    {"year": 2016, "edition": 1, "teams": 5, "winner": "Islamabad United", "runner_up": "Quetta Gladiators",
     "date": "2016-02-23", "time": "21:00 PKT", "venue": "Dubai International Cricket Stadium, Dubai",
     "result": "Islamabad United won by 6 wickets", "pom": "Dwayne Smith",
     "pott": "Ravi Bopara (Karachi Kings)", "runs": ("Umar Akmal", "Lahore Qalandars", 335),
     "wkts": ("Andre Russell", "Islamabad United", 16)},
    {"year": 2017, "edition": 2, "teams": 5, "winner": "Peshawar Zalmi", "runner_up": "Quetta Gladiators",
     "date": "2017-03-05", "time": "—", "venue": "Gaddafi Stadium, Lahore",
     "result": "Peshawar Zalmi won by 58 runs", "pom": "—",
     "pott": "Kamran Akmal (Peshawar Zalmi)", "runs": ("Kamran Akmal", "Peshawar Zalmi", 353),
     "wkts": ("Sohail Khan", "Karachi Kings", 16)},
    {"year": 2018, "edition": 3, "teams": 6, "winner": "Islamabad United", "runner_up": "Peshawar Zalmi",
     "date": "2018-03-25", "time": "—", "venue": "National Stadium, Karachi",
     "result": "Islamabad United won by 3 wickets", "pom": "Luke Ronchi",
     "pott": "Luke Ronchi (Islamabad United)", "runs": ("Luke Ronchi", "Islamabad United", 435),
     "wkts": ("Faheem Ashraf (IU) & Wahab Riaz (PZ), tied", "Islamabad United", 18)},
    {"year": 2019, "edition": 4, "teams": 6, "winner": "Quetta Gladiators", "runner_up": "Peshawar Zalmi",
     "date": "2019-03-17", "time": "—", "venue": "National Stadium, Karachi",
     "result": "Quetta Gladiators won by 8 wickets", "pom": "Mohammad Hasnain",
     "pott": "Shane Watson (Quetta Gladiators)", "runs": ("Shane Watson", "Quetta Gladiators", 430),
     "wkts": ("Hasan Ali", "Peshawar Zalmi", 25)},
    {"year": 2020, "edition": 5, "teams": 6, "winner": "Karachi Kings", "runner_up": "Lahore Qalandars",
     "date": "2020-11-17", "time": "—", "venue": "National Stadium, Karachi",
     "result": "Karachi Kings won by 5 wickets", "pom": "Babar Azam",
     "pott": "Babar Azam (Karachi Kings)", "runs": ("Babar Azam", "Karachi Kings", 473),
     "wkts": ("Shaheen Shah Afridi", "Lahore Qalandars", 17)},
    {"year": 2021, "edition": 6, "teams": 6, "winner": "Multan Sultans", "runner_up": "Peshawar Zalmi",
     "date": "2021-06-24", "time": "—", "venue": "Sheikh Zayed Cricket Stadium, Abu Dhabi",
     "result": "Multan Sultans won by 47 runs", "pom": "Sohaib Maqsood",
     "pott": "Sohaib Maqsood (Multan Sultans)", "runs": ("Babar Azam", "Karachi Kings", 554),
     "wkts": ("Shahnawaz Dahani", "Multan Sultans", 20)},
    {"year": 2022, "edition": 7, "teams": 6, "winner": "Lahore Qalandars", "runner_up": "Multan Sultans",
     "date": "2022-02-27", "time": "—", "venue": "Gaddafi Stadium, Lahore",
     "result": "Lahore Qalandars won by 42 runs", "pom": "Mohammad Hafeez",
     "pott": "Mohammad Rizwan (Multan Sultans)", "runs": ("Fakhar Zaman", "Lahore Qalandars", 588),
     "wkts": ("Shaheen Shah Afridi", "Lahore Qalandars", 20)},
    {"year": 2023, "edition": 8, "teams": 6, "winner": "Lahore Qalandars", "runner_up": "Multan Sultans",
     "date": "2023-03-18", "time": "—", "venue": "Gaddafi Stadium, Lahore",
     "result": "Lahore Qalandars won by 1 run", "pom": "Shaheen Shah Afridi",
     "pott": "Ihsanullah (Multan Sultans)", "runs": ("Mohammad Rizwan", "Multan Sultans", 550),
     "wkts": ("Abbas Afridi", "Multan Sultans", 23)},
    {"year": 2024, "edition": 9, "teams": 6, "winner": "Islamabad United", "runner_up": "Multan Sultans",
     "date": "2024-03-18", "time": "—", "venue": "National Stadium, Karachi",
     "result": "Islamabad United won by 2 wickets", "pom": "Imad Wasim",
     "pott": "Shadab Khan (Islamabad United)", "runs": ("Babar Azam", "Peshawar Zalmi", 569),
     "wkts": ("Usama Mir", "Multan Sultans", 24)},
    {"year": 2025, "edition": 10, "teams": 6, "winner": "Lahore Qalandars", "runner_up": "Quetta Gladiators",
     "date": "2025-05-25", "time": "—", "venue": "Gaddafi Stadium, Lahore",
     "result": "Lahore Qalandars won by 6 wickets", "pom": "Kusal Perera",
     "pott": "Hasan Nawaz (Quetta Gladiators)", "runs": ("Sahibzada Farhan", "Islamabad United", 449),
     "wkts": ("Shaheen Shah Afridi", "Lahore Qalandars", 19)},
    {"year": 2026, "edition": 11, "teams": 8, "winner": "Peshawar Zalmi", "runner_up": "Hyderabad Kingsmen",
     "date": "2026-05-03", "time": "—", "venue": "Gaddafi Stadium, Lahore",
     "result": "Peshawar Zalmi won by 5 wickets", "pom": "Aaron Hardie",
     "pott": "Sufiyan Muqeem (Peshawar Zalmi)", "runs": ("Babar Azam", "Peshawar Zalmi", 588),
     "wkts": ("Sufiyan Muqeem", "Peshawar Zalmi", 22)},
]

# The next season (dates confirmed by the PCB on 8 Oct 2026; fixtures and venues not yet announced).
NEXT_SEASON = {"name": "PSL 12 (2027)", "dates": "18 March – 2 May 2027", "time": "TBA", "venue": "TBA",
               "status": "Dates confirmed – fixtures and venues to be announced"}

# Final-match scoreboards (first innings team, then chasing team). Only finals with a verified scorecard.
# Each side: (team, runs, wickets lost, overs)
FINAL_SCORES = [
    {"year": 2016, "first": ("Quetta Gladiators", 174, 7, "20"), "second": ("Islamabad United", 175, 4, "18.4")},
    {"year": 2018, "first": ("Peshawar Zalmi", 148, 9, "20"), "second": ("Islamabad United", 154, 7, "16.5")},
    {"year": 2019, "first": ("Peshawar Zalmi", 138, 8, "20"), "second": ("Quetta Gladiators", 139, 2, "17.5")},
    {"year": 2020, "first": ("Lahore Qalandars", 134, 7, "20"), "second": ("Karachi Kings", 135, 5, "18.4")},
    {"year": 2021, "first": ("Multan Sultans", 206, 4, "20"), "second": ("Peshawar Zalmi", 159, 9, "20")},
    {"year": 2022, "first": ("Lahore Qalandars", 180, 5, "20"), "second": ("Multan Sultans", 138, 10, "19.3")},
    {"year": 2024, "first": ("Multan Sultans", 159, 9, "20"), "second": ("Islamabad United", 163, 8, "20")},
    {"year": 2025, "first": ("Quetta Gladiators", 201, 9, "20"), "second": ("Lahore Qalandars", 204, 4, "19.5")},
]

# PSL 2026 league table (ESPNcricinfo via Wikipedia): team, played, won, lost, no result, points, NRR
POINTS_2026 = [
    ("Peshawar Zalmi", 10, 8, 1, 1, 17, 2.324),
    ("Islamabad United", 10, 6, 3, 1, 13, 1.667),
    ("Multan Sultans", 10, 6, 4, 0, 12, 0.326),
    ("Hyderabad Kingsmen", 10, 5, 5, 0, 10, -0.361),
    ("Lahore Qalandars", 10, 5, 5, 0, 10, -0.482),
    ("Karachi Kings", 10, 5, 5, 0, 10, -0.869),
    ("Quetta Gladiators", 10, 3, 7, 0, 6, -0.410),
    ("Rawalpindiz", 10, 1, 9, 0, 2, -1.760),
]

# Player profiles. dob is only filled when it is certain; the age is calculated from it.
# stats = PSL 2026 numbers (Wikipedia / ESPNcricinfo; strike rate & sixes from myKhel) unless stated in "note".
PLAYERS = [
    {"name": "Babar Azam", "team": "Peshawar Zalmi", "country": "Pakistan", "role": "Batter (captain)",
     "dob": "1994-10-15", "stats": {"Runs": 588, "High score": "103", "Average": 73.50, "Strike rate": 145.90, "Sixes": 15},
     "note": "Top run-scorer of PSL 2026 and reached 4,000 PSL runs that season."},
    {"name": "Kusal Mendis", "team": "Peshawar Zalmi", "country": "Sri Lanka", "role": "Wicket-keeper batter",
     "dob": "1995-02-02", "stats": {"Runs": 550, "High score": "109", "Average": 55.00, "Strike rate": 168.19, "Sixes": 23},
     "note": "First Sri Lankan to score a PSL century; wicket-keeper of the 2026 tournament."},
    {"name": "Sufiyan Muqeem", "team": "Peshawar Zalmi", "country": "Pakistan", "role": "Bowler (spinner)",
     "dob": None, "stats": {"Wickets": 22, "Best bowling": "4/32", "Average": 14.40},
     "note": "Player of the Tournament and most wickets in PSL 2026."},
    {"name": "Aaron Hardie", "team": "Peshawar Zalmi", "country": "Australia", "role": "All-rounder",
     "dob": None, "stats": {}, "note": "Player of the Match in the 2026 final."},
    {"name": "Mohammad Haris", "team": "Peshawar Zalmi", "country": "Pakistan", "role": "Batter",
     "dob": "2001-03-30", "stats": {}, "note": "Signed for PKR 2.20 crore for 2026."},
    {"name": "Shadab Khan", "team": "Islamabad United", "country": "Pakistan", "role": "All-rounder (captain)",
     "dob": "1998-10-04", "stats": {"Wickets": 17, "Best bowling": "3/13", "Average": 14.47},
     "note": "Player of the Tournament 2024; All-rounder of the tournament 2026."},
    {"name": "Imad Wasim", "team": "Islamabad United", "country": "Pakistan", "role": "All-rounder",
     "dob": "1988-12-18", "stats": {"Wickets": 12, "Best bowling": "3/21"},
     "note": "Player of the Match in the 2024 final."},
    {"name": "David Warner", "team": "Karachi Kings", "country": "Australia", "role": "Batter (captain)",
     "dob": "1986-10-27", "stats": {}, "note": "Named in the PSL 2025 team of the tournament."},
    {"name": "Hasan Ali", "team": "Karachi Kings", "country": "Pakistan", "role": "Bowler (fast)",
     "dob": "1994-02-07", "stats": {"Wickets": 15, "Best bowling": "4/27"},
     "note": "Holds the record for most wickets in one PSL season (25 in 2019)."},
    {"name": "Shaheen Shah Afridi", "team": "Lahore Qalandars", "country": "Pakistan", "role": "Bowler (fast, captain)",
     "dob": "2000-04-06", "stats": {"Wickets": 16, "Best bowling": "4/18", "Average": 18.18},
     "note": "Captained Lahore to the 2022, 2023 and 2025 titles; most wickets in 2020, 2022 and 2025."},
    {"name": "Fakhar Zaman", "team": "Lahore Qalandars", "country": "Pakistan", "role": "Batter",
     "dob": "1990-04-10", "stats": {"Runs": 401, "High score": "103", "Average": 57.28, "Strike rate": 151.89, "Sixes": 12},
     "note": "Most runs in 2022 (588); 439 runs in 2025."},
    {"name": "Shan Masood", "team": "Multan Sultans", "country": "Pakistan", "role": "Batter",
     "dob": "1989-10-14", "stats": {"Runs": 367, "High score": "69*", "Average": 45.87, "Strike rate": 158.18, "Sixes": 15},
     "note": "Named in the 2026 team of the tournament."},
    {"name": "Steve Smith", "team": "Multan Sultans", "country": "Australia", "role": "Batter",
     "dob": "1989-06-02", "stats": {"Runs": 380, "High score": "106", "Average": 34.54, "Strike rate": 161.70, "Sixes": 18},
     "note": "Scored his maiden PSL century in 2026."},
    {"name": "Sahibzada Farhan", "team": "Multan Sultans", "country": "Pakistan", "role": "Batter",
     "dob": None, "stats": {"Runs": 380, "High score": "106*", "Average": 42.22, "Strike rate": 166.66, "Sixes": 23},
     "note": "Top run-scorer of PSL 2025 (449 runs for Islamabad United)."},
    {"name": "Ashton Turner", "team": "Multan Sultans", "country": "Australia", "role": "Batter (captain)",
     "dob": "1993-01-25", "stats": {}, "note": "Listed as 2026 captain on Wikipedia."},
    {"name": "Saud Shakeel", "team": "Quetta Gladiators", "country": "Pakistan", "role": "Batter (captain)",
     "dob": "1995-09-05", "stats": {}, "note": "Captained Quetta in the 2025 final."},
    {"name": "Rilee Rossouw", "team": "Quetta Gladiators", "country": "South Africa", "role": "Batter",
     "dob": "1989-10-09", "stats": {"Runs": 317, "High score": "90", "Average": 39.62, "Strike rate": 142.79, "Sixes": 14},
     "note": "First overseas player to play 100 PSL matches."},
    {"name": "Abrar Ahmed", "team": "Quetta Gladiators", "country": "Pakistan", "role": "Bowler (spinner)",
     "dob": None, "stats": {}, "note": "Best Bowler of PSL 2025 (17 wickets)."},
    {"name": "Marnus Labuschagne", "team": "Hyderabad Kingsmen", "country": "Australia", "role": "Batter (captain)",
     "dob": "1994-06-22", "stats": {"Runs": 344, "High score": "61*", "Average": 28.66, "Strike rate": 130.30, "Sixes": 4},
     "note": "Captain of the debutants who reached the 2026 final."},
    {"name": "Usman Khan", "team": "Hyderabad Kingsmen", "country": "Pakistan", "role": "Wicket-keeper batter",
     "dob": None, "stats": {"Runs": 389, "High score": "101", "Average": 35.36, "Strike rate": 162.76, "Sixes": 22},
     "note": "Scored his fourth PSL century in 2026, the most by any batter."},
    {"name": "Glenn Maxwell", "team": "Hyderabad Kingsmen", "country": "Australia", "role": "All-rounder",
     "dob": "1988-10-14", "stats": {}, "note": "Took his 200th T20 wicket during PSL 2026."},
    {"name": "Mohammad Ali", "team": "Hyderabad Kingsmen", "country": "Pakistan", "role": "Bowler (fast)",
     "dob": None, "stats": {"Wickets": 20, "Best bowling": "3/21", "Average": 18.95},
     "note": "Second on the 2026 wicket-takers list."},
    {"name": "Hunain Shah", "team": "Hyderabad Kingsmen", "country": "Pakistan", "role": "Bowler (fast)",
     "dob": None, "stats": {"Wickets": 17, "Best bowling": "4/22", "Average": 18.41},
     "note": "Emerging Player of the 2026 tournament."},
    {"name": "Mohammad Rizwan", "team": "Rawalpindiz", "country": "Pakistan", "role": "Wicket-keeper batter (captain)",
     "dob": "1992-06-01", "stats": {}, "note": "Player of the Tournament 2022; most runs in 2023 (550)."},
    {"name": "Naseem Shah", "team": "Rawalpindiz", "country": "Pakistan", "role": "Bowler (fast)",
     "dob": "2003-02-15", "stats": {}, "note": "Most expensive player at the 2026 auction (Rs 8.65 crore)."},
    {"name": "Daryl Mitchell", "team": "Rawalpindiz", "country": "New Zealand", "role": "All-rounder",
     "dob": "1991-05-20", "stats": {}, "note": "Most expensive overseas signing at the 2026 auction (Rs 8 crore)."},
]

DATA_SOURCES = [
    ("Season pages (winners, finals, awards, 2026 squads and table)", "https://en.wikipedia.org/wiki/Pakistan_Super_League"),
    ("PSL 12 window announcement (PCB, 8 Oct 2026)", "https://tribune.com.pk/story/2633656/hbl-psl-12-to-return-with-eight-teams"),
    ("PSL 2026 stats", "https://www.mykhel.com/cricket/psl-2026-stats-top-run-scorers-top-wicket-takers-most-sixes-highest-scores-all-you-need-to-know-430157.html"),
    ("PSL 2025 awards", "https://tribune.com.pk/story/2547768/Top-performing-players-of-HBL-PSL-X-honoured"),
    ("ESPNcricinfo PSL records", "https://www.espncricinfo.com/records/tournament/batting-most-runs-career/pakistan-super-league-17816"),
]


# =====================================================================
# 2. HELPERS  (data, images, charts)
# =====================================================================

def team_record(team):
    """Return (list of title years, list of runner-up years) for a team."""
    titles = [s["year"] for s in SEASONS if s["winner"] == team]
    runners = [s["year"] for s in SEASONS if s["runner_up"] == team]
    return titles, runners


def team_color(team):
    return TEAMS[team]["colors"][0]


def age_from_dob(dob):
    """Calculate age today from an ISO date string; None if the date is not known."""
    if not dob:
        return None
    born = datetime.strptime(dob, "%Y-%m-%d").date()
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def fmt_date(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")


def seasons_df():
    rows = []
    for s in SEASONS:
        rows.append({
            "Year": s["year"], "Edition": "PSL %d" % s["edition"], "Teams": s["teams"],
            "Winner": s["winner"], "Runner-up": s["runner_up"],
            "Top run-scorer": "%s (%s) - %d" % (s["runs"][0], TEAMS[s["runs"][1]]["code"], s["runs"][2]),
            "Top wicket-taker": "%s - %d" % (s["wkts"][0], s["wkts"][2]),
            "Player of the Tournament": s["pott"],
        })
    return pd.DataFrame(rows).sort_values("Year", ascending=False)


def schedule_df():
    rows = [{"Date": NEXT_SEASON["dates"], "Time": NEXT_SEASON["time"], "Match": NEXT_SEASON["name"],
             "Venue": NEXT_SEASON["venue"], "Status": NEXT_SEASON["status"]}]
    for s in sorted(SEASONS, key=lambda x: x["year"], reverse=True):
        rows.append({"Date": fmt_date(s["date"]), "Time": s["time"],
                     "Match": "PSL %d final: %s vs %s" % (s["year"], s["winner"], s["runner_up"]),
                     "Venue": s["venue"], "Status": "Completed - " + s["result"]})
    return pd.DataFrame(rows)


def scores_df():
    rows = []
    for f in FINAL_SCORES:
        season = next(s for s in SEASONS if s["year"] == f["year"])
        for label, side in (("Batted first", f["first"]), ("Batted second", f["second"])):
            rows.append({"Season": f["year"], "Innings": label, "Team": side[0], "Runs": side[1],
                         "Wickets": side[2], "Overs": side[3], "Result": season["result"]})
    return pd.DataFrame(rows)


def points_df():
    df = pd.DataFrame(POINTS_2026, columns=["Team", "Played", "Won", "Lost", "No result", "Points", "NRR"])
    df.insert(0, "Pos", range(1, len(df) + 1))
    return df


# ---------- Pillow: logos, avatars, cards ----------

def hex_to_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def get_font(size):
    for name in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def vertical_gradient(w, h, c1, c2):
    top, bottom = hex_to_rgb(c1), hex_to_rgb(c2)
    img = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
        d.line([(0, y), (w, y)], fill=color)
    return img


def draw_centered(draw, text, font, center_x, center_y, fill="white"):
    box = draw.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.text((center_x - w / 2 - box[0], center_y - h / 2 - box[1]), text, font=font, fill=fill)


def make_logo(team, size=300):
    """A generated badge (NOT the official logo): gradient circle + team code + city."""
    info = TEAMS[team]
    c1, c2 = info["colors"]
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((4, 4, size - 4, size - 4), fill=255)
    badge.paste(vertical_gradient(size, size, c1, c2), (0, 0), mask)
    d = ImageDraw.Draw(badge)
    d.ellipse((4, 4, size - 4, size - 4), outline="white", width=max(4, size // 36))
    d.ellipse((size * 0.08, size * 0.08, size * 0.92, size * 0.92), outline=(255, 255, 255, 120), width=2)
    draw_centered(d, info["code"], get_font(int(size * 0.36)), size / 2, size * 0.44)
    draw_centered(d, info["city"].split(",")[0].upper(), get_font(int(size * 0.075)), size / 2, size * 0.74)
    return badge


def circle_crop(img, size):
    img = ImageOps.fit(img.convert("RGBA"), (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def make_avatar(name, team, size=220):
    """Generated initials avatar (placeholder for a real photo)."""
    c1, c2 = TEAMS[team]["colors"]
    base = vertical_gradient(size, size, c1, c2)
    d = ImageDraw.Draw(base)
    initials = "".join(part[0] for part in name.replace("(", " ").split()[:2]).upper()
    draw_centered(d, initials, get_font(int(size * 0.4)), size / 2, size / 2)
    return circle_crop(base, size)


def make_team_card(team):
    """A shareable PNG team card made with Pillow."""
    c1, c2 = TEAMS[team]["colors"]
    card = vertical_gradient(900, 420, c1, c2)
    card.paste(make_logo(team, 300), (50, 60), make_logo(team, 300))
    d = ImageDraw.Draw(card)
    titles, runners = team_record(team)
    d.text((390, 60), team, font=get_font(46), fill="white")
    lines = ["City: " + TEAMS[team]["city"],
             "2026 captain: " + TEAMS[team]["captain"],
             "PSL titles: %d %s" % (len(titles), titles if titles else ""),
             "Runner-up finishes: %d" % len(runners),
             "Joined PSL: %d" % TEAMS[team]["joined"]]
    y = 140
    for line in lines:
        d.text((390, y), line, font=get_font(28), fill="white")
        y += 52
    return card.convert("RGB")


def img_to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# ---------- Matplotlib charts ----------

def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def chart_titles():
    names = list(TEAMS)
    counts = [len(team_record(t)[0]) for t in names]
    runners = [len(team_record(t)[1]) for t in names]
    fig, ax = plt.subplots(figsize=(9, 4))
    x = range(len(names))
    ax.bar([i - 0.2 for i in x], counts, 0.4, color=[team_color(t) for t in names], label="Titles")
    ax.bar([i + 0.2 for i in x], runners, 0.4, color="#B0BEC5", label="Runner-up")
    ax.set_xticks(list(x))
    ax.set_xticklabels([TEAMS[t]["code"] for t in names])
    ax.set_ylabel("Count")
    ax.set_title("PSL titles and runner-up finishes (2016-2026)")
    ax.legend()
    style_axes(ax)
    return fig


def chart_top_runs():
    fig, ax = plt.subplots(figsize=(9, 4))
    years = [s["year"] for s in SEASONS]
    runs = [s["runs"][2] for s in SEASONS]
    ax.bar([str(y) for y in years], runs, color=[team_color(s["runs"][1]) for s in SEASONS])
    for i, s in enumerate(SEASONS):
        ax.text(i, runs[i] + 8, s["runs"][0].split()[-1], ha="center", fontsize=8, rotation=90)
    ax.set_ylim(0, max(runs) + 130)
    ax.set_ylabel("Runs")
    ax.set_title("Highest run-scorer each season")
    style_axes(ax)
    return fig


def chart_top_wickets():
    fig, ax = plt.subplots(figsize=(9, 4))
    years = [s["year"] for s in SEASONS]
    wkts = [s["wkts"][2] for s in SEASONS]
    ax.plot([str(y) for y in years], wkts, marker="o", color="#6A1B9A")
    for y, w in zip(years, wkts):
        ax.annotate(str(w), (str(y), w), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8)
    ax.set_ylabel("Wickets")
    ax.set_title("Most wickets in a season")
    style_axes(ax)
    return fig


def chart_points():
    df = points_df()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.barh(df["Team"][::-1], df["Points"][::-1], color=[team_color(t) for t in df["Team"][::-1]])
    for i, (pts, nrr) in enumerate(zip(df["Points"][::-1], df["NRR"][::-1])):
        ax.text(pts + 0.2, i, "%d pts (NRR %+.3f)" % (pts, nrr), va="center", fontsize=8)
    ax.set_xlim(0, df["Points"].max() + 6)
    ax.set_title("PSL 2026 league table")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig


def chart_final(year):
    f = next(x for x in FINAL_SCORES if x["year"] == year)
    sides = [f["first"], f["second"]]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    ax.bar([s[0] for s in sides], [s[1] for s in sides], color=[team_color(s[0]) for s in sides])
    for i, s in enumerate(sides):
        ax.text(i, s[1] + 3, "%d/%d (%s ov)" % (s[1], s[2], s[3]), ha="center", fontsize=9)
    ax.set_ylim(0, max(s[1] for s in sides) + 30)
    ax.set_ylabel("Runs")
    ax.set_title("PSL %d final" % year)
    style_axes(ax)
    return fig


def chart_votes(votes):
    names = list(votes)
    total = sum(votes.values())
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(names[::-1], [votes[n] for n in names[::-1]], color=[team_color(n) for n in names[::-1]])
    for i, n in enumerate(names[::-1]):
        pct = votes[n] / total * 100 if total else 0
        ax.text(votes[n] + 0.05, i, "%.1f%% (%d)" % (pct, votes[n]), va="center", fontsize=9)
    ax.set_xlim(0, max(max(votes.values()), 1) * 1.3)
    ax.set_xlabel("Votes")
    ax.set_title("Fan vote - favourite team")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig


def chart_player_stat(metric):
    people = [p for p in PLAYERS if metric in p["stats"]]
    people.sort(key=lambda p: p["stats"][metric], reverse=True)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar([p["name"].split()[-1] for p in people], [p["stats"][metric] for p in people],
           color=[team_color(p["team"]) for p in people])
    ax.set_ylabel(metric)
    ax.set_title("PSL 2026 - %s (players in this app)" % metric)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    style_axes(ax)
    fig.tight_layout()
    return fig


# ---------- Voting ----------

def load_votes():
    votes = {t: 0 for t in TEAMS}
    if os.path.exists(VOTES_FILE):
        try:
            with open(VOTES_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for t in votes:
                votes[t] = int(saved.get(t, 0))
        except (OSError, ValueError):
            pass
    return votes


def save_votes(votes):
    with open(VOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(votes, f)


# ---------- Live cricket API (optional) ----------

def fetch_live_matches(api_key):
    """Optional: CricAPI / cricketdata.org 'currentMatches' endpoint. Returns (rows, message)."""
    url = "https://api.cricapi.com/v1/currentMatches"
    try:
        resp = requests.get(url, params={"apikey": api_key, "offset": 0}, timeout=10)
        payload = resp.json()
    except (requests.RequestException, ValueError) as err:
        return [], "Could not reach the live API: %s" % err
    if payload.get("status") != "success":
        return [], "API replied: %s" % payload.get("reason", payload.get("status", "unknown error"))
    rows = []
    for m in payload.get("data", []):
        name = m.get("name", "")
        if "pakistan super league" in name.lower() or "psl" in name.lower():
            score = "; ".join("%s: %s/%s (%s ov)" % (s.get("inning", ""), s.get("r"), s.get("w"), s.get("o"))
                              for s in m.get("score", []))
            rows.append({"Match": name, "Date": m.get("date", ""), "Venue": m.get("venue", ""),
                         "Status": m.get("status", ""), "Score": score})
    if not rows:
        return [], "The API is working, but no PSL match is live or listed right now."
    return rows, "OK"


# ---------- Turtle drawing ----------

def turtle_trophy():
    """Draws a golden trophy with Turtle. Needs a desktop window (Windows/Mac/Linux desktop)."""
    import turtle

    screen = turtle.Screen()
    screen.title("PSL trophy - drawn with Turtle")
    screen.bgcolor("#10202e")
    t = turtle.Turtle()
    t.hideturtle()
    t.speed(0)

    def rect(x, y, w, h, color):
        t.penup(); t.goto(x, y); t.setheading(0); t.color(color); t.pendown(); t.begin_fill()
        for side in (w, h, w, h):
            t.forward(side); t.left(90)
        t.end_fill(); t.penup()

    rect(-90, -170, 180, 30, "#8d6e1f")   # base
    rect(-60, -140, 120, 20, "#b8912c")
    rect(-15, -120, 30, 90, "#d4af37")    # stem
    t.goto(0, -30); t.setheading(0); t.color("#f4cf47"); t.pendown(); t.begin_fill()
    t.circle(-90, 180)                    # cup bowl
    t.goto(0, -30)
    t.end_fill(); t.penup()
    rect(-90, -30, 180, 15, "#f4cf47")    # rim
    t.pensize(10); t.color("#d4af37")     # handles
    for sign in (-1, 1):
        t.goto(sign * 90, -35); t.setheading(90 if sign == 1 else 90); t.pendown()
        t.circle(-sign * 35, 180); t.penup()
    t.pensize(2)
    t.goto(0, 40); t.color("white"); t.setheading(0)   # star
    t.goto(-18, 20); t.pendown(); t.begin_fill()
    for _ in range(5):
        t.forward(36); t.right(144)
    t.end_fill(); t.penup()
    t.goto(0, -210); t.color("white")
    t.write("PSL  CHAMPIONS", align="center", font=("Arial", 18, "bold"))
    turtle.done()


# =====================================================================
# 3. STREAMLIT APP
# =====================================================================

CSS = """
<style>
.hero {background: linear-gradient(120deg,#0f2027,#2c5364 45%,#6a1b9a); color: white;
       padding: 28px 30px; border-radius: 20px; margin-bottom: 18px;}
.hero h1 {margin: 0; font-size: 2.1rem;}
.hero p {margin: 6px 0 0 0; opacity: .9;}
.card {border-radius: 16px; padding: 14px 16px; color: white; margin-bottom: 10px;
       box-shadow: 0 4px 14px rgba(0,0,0,.18);}
.pill {display:inline-block; padding: 2px 10px; border-radius: 999px; background: rgba(255,255,255,.22);
       font-size: .8rem; margin-right: 4px;}
@media (max-width: 640px) {.hero h1 {font-size: 1.5rem;} .hero {padding: 18px;}}
</style>
"""


def hero(title, subtitle):
    st.markdown('<div class="hero"><h1>%s</h1><p>%s</p></div>' % (title, subtitle), unsafe_allow_html=True)


def team_banner(team):
    c1, c2 = TEAMS[team]["colors"]
    titles, runners = team_record(team)
    st.markdown(
        '<div class="card" style="background:linear-gradient(120deg,%s,%s)"><b style="font-size:1.2rem">%s</b><br>'
        '<span class="pill">%s</span><span class="pill">%d title(s)</span><span class="pill">%d runner-up</span></div>'
        % (c1, c2, team, TEAMS[team]["city"], len(titles), len(runners)), unsafe_allow_html=True)


CELEBRATION_HTML = """
<div style="font-family:Arial,sans-serif;text-align:center;color:white;border-radius:18px;overflow:hidden;
            position:relative;height:400px;background:linear-gradient(135deg,__C1__,__C2__);">
  <canvas id="c" style="position:absolute;left:0;top:0;width:100%;height:100%"></canvas>
  <div style="position:relative;padding-top:14px">
    <div style="font-size:38px">&#127881;&#127942;&#127881;</div>
    <img src="__LOGO__" width="150" style="animation:hop 1s ease-in-out infinite;margin:6px 0">
    <h2 style="margin:4px 0;text-shadow:0 2px 6px rgba(0,0,0,.4)">__TEAM__</h2>
    <p style="margin:4px 24px;font-size:17px;text-shadow:0 2px 6px rgba(0,0,0,.4)">__MESSAGE__</p>
  </div>
  <style>@keyframes hop{0%,100%{transform:translateY(0)}50%{transform:translateY(-12px)}}</style>
  <script>
    const cv=document.getElementById('c'),ctx=cv.getContext('2d');
    cv.width=cv.clientWidth;cv.height=cv.clientHeight;
    const cols=['#ff595e','#ffca3a','#8ac926','#1982c4','#6a4c93','#ffffff'];
    const bits=[];
    for(let i=0;i<170;i++){bits.push({x:Math.random()*cv.width,y:Math.random()*-cv.height,
      r:4+Math.random()*6,s:1.5+Math.random()*3.5,d:Math.random()*6.28,c:cols[i%cols.length]});}
    function draw(){ctx.clearRect(0,0,cv.width,cv.height);
      bits.forEach(b=>{b.y+=b.s;b.x+=Math.sin(b.d+=0.05)*1.5;
        if(b.y>cv.height){b.y=-10;b.x=Math.random()*cv.width;}
        ctx.fillStyle=b.c;ctx.fillRect(b.x,b.y,b.r,b.r*1.6);});
      requestAnimationFrame(draw);}
    draw();
  </script>
</div>
"""


def celebration_html(team, message):
    c1, c2 = TEAMS[team]["colors"]
    html = CELEBRATION_HTML
    for key, value in (("__C1__", c1), ("__C2__", c2), ("__LOGO__", img_to_b64(make_logo(team, 220))),
                       ("__TEAM__", team), ("__MESSAGE__", message)):
        html = html.replace(key, value)
    return html


def open_celebration(team, message):
    """Show the cute winner popup (a dialog with confetti). Falls back to inline on old Streamlit."""
    if hasattr(st, "dialog"):
        @st.dialog("Congratulations!")
        def popup():
            components.html(celebration_html(team, message), height=420)
            st.button("Close")
        popup()
    else:
        st.success("Congratulations, %s!" % team)
        components.html(celebration_html(team, message), height=420)


# ---------- pages ----------

def page_home():
    hero("🏏 PSL Cricket Hub", "Teams, players, scoreboards, history and fan voting - all in one place.")
    latest = SEASONS[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Seasons played", len(SEASONS))
    c2.metric("Teams in 2026", len(TEAMS))
    c3.metric("Most titles", "3", "Islamabad United & Lahore Qalandars")
    c4.metric("2026 champions", latest["winner"])
    left, right = st.columns([1, 2])
    with left:
        st.image(make_logo(latest["winner"], 260), width=200)
        st.caption("Generated badge (not the official logo)")
    with right:
        st.subheader("PSL 2026 final")
        st.write("%s beat %s - %s. Played on %s at %s." %
                 (latest["winner"], latest["runner_up"], latest["result"].split("won by ")[1],
                  fmt_date(latest["date"]), latest["venue"]))
        st.write("Player of the Match: **%s**. Player of the Tournament: **%s**." % (latest["pom"], latest["pott"]))
        st.info("Next up: **%s** - %s. %s." % (NEXT_SEASON["name"], NEXT_SEASON["dates"], NEXT_SEASON["status"]))
    st.pyplot(chart_titles(), clear_figure=True)
    st.caption("Use the sidebar to explore teams, players, matches, history and the fan vote.")


def page_teams():
    hero("🛡️ Teams", "All eight franchises that played PSL 2026, with captains, squads and records.")
    names = list(TEAMS)
    cols = st.columns(4)
    for i, name in enumerate(names):
        with cols[i % 4]:
            st.image(make_logo(name, 200), width=120)
            st.caption(name)
    team = st.selectbox("Choose a team", names, index=names.index("Peshawar Zalmi"))
    team_banner(team)
    titles, runners = team_record(team)
    left, right = st.columns([1, 2])
    with left:
        st.image(make_logo(team, 300), width=220)
    with right:
        st.write("**Captain (2026):** %s" % TEAMS[team]["captain"])
        if team in CAPTAIN_NOTE:
            st.caption(CAPTAIN_NOTE[team])
        st.write("**Titles:** %s" % (", ".join(map(str, titles)) if titles else "None yet"))
        st.write("**Runner-up:** %s" % (", ".join(map(str, runners)) if runners else "None yet"))
        row = points_df()[points_df()["Team"] == team].iloc[0]
        st.write("**2026 league stage:** position %d, %d wins, %d losses, %d points (NRR %+.3f)" %
                 (row["Pos"], row["Won"], row["Lost"], row["Points"], row["NRR"]))
        st.caption("Franchise records are carried by team name; Rawalpindiz and Hyderabad Kingsmen debuted in 2026.")
    st.subheader("2026 squad")
    st.caption("* = overseas player, (c) = captain. Squads can change after publication - check official sources.")
    squad = pd.DataFrame({"Player": [p.replace("*", "") for p in SQUADS[team]],
                          "Overseas": ["Yes" if p.endswith("*") else "" for p in SQUADS[team]]})
    st.dataframe(squad, hide_index=True)
    card = make_team_card(team)
    buf = io.BytesIO()
    card.save(buf, format="PNG")
    st.image(card, caption="Team card made with Pillow")
    st.download_button("Download team card (PNG)", buf.getvalue(), file_name="%s_card.png" % TEAMS[team]["code"],
                       mime="image/png")


def page_players():
    hero("🧢 Players", "Profiles with country, role, age and PSL 2026 numbers. Unknown facts show as N/A.")
    team_filter = st.selectbox("Filter by team", ["All teams"] + list(TEAMS))
    pool = [p for p in PLAYERS if team_filter == "All teams" or p["team"] == team_filter]
    name = st.selectbox("Choose a player", [p["name"] for p in pool])
    p = next(x for x in PLAYERS if x["name"] == name)
    team_banner(p["team"])
    left, right = st.columns([1, 2])
    with left:
        upload = st.file_uploader("Add a photo (optional)", type=["png", "jpg", "jpeg"], key="photo_" + name)
        if upload is not None:
            st.image(circle_crop(Image.open(upload), 220), width=200)
        else:
            st.image(make_avatar(p["name"], p["team"]), width=200)
            st.caption("Generated avatar - official photos are not bundled.")
    with right:
        age = age_from_dob(p["dob"])
        st.write("**Country:** %s" % p["country"])
        st.write("**Role:** %s" % p["role"])
        st.write("**Age:** %s" % (str(age) + " years" if age is not None else "N/A"))
        st.write("**Team (2026):** %s" % p["team"])
        st.write("**Note:** %s" % p["note"])
        if p["stats"]:
            st.write("**PSL 2026 stats**")
            st.dataframe(pd.DataFrame([p["stats"]]), hide_index=True)
        else:
            st.write("**PSL 2026 stats:** N/A (not in the verified sources used here)")
    st.subheader("Stats explorer")
    metric = st.radio("Metric", ["Runs", "Wickets"], horizontal=True)
    st.pyplot(chart_player_stat(metric), clear_figure=True)


def page_matches():
    hero("📅 Matches & Scoreboards", "Schedule, final scorecards, the 2026 table and optional live data.")
    tab1, tab2, tab3, tab4 = st.tabs(["Schedule", "Final scoreboards", "2026 table", "Live (optional API)"])
    with tab1:
        st.dataframe(schedule_df(), hide_index=True)
        st.caption("Times are only shown when a source gave them. PSL 12 fixtures were not announced yet "
                   "(as of November 2026).")
    with tab2:
        years = [f["year"] for f in FINAL_SCORES]
        year = st.select_slider("Season", options=years, value=years[-1])
        f = next(x for x in FINAL_SCORES if x["year"] == year)
        c1, c2 = st.columns(2)
        for col, label, side in ((c1, "Batted first", f["first"]), (c2, "Batted second", f["second"])):
            col.metric("%s (%s)" % (side[0], label), "%d/%d" % (side[1], side[2]), "%s overs" % side[3],
                       delta_color="off")
        st.success(next(s for s in SEASONS if s["year"] == year)["result"])
        st.pyplot(chart_final(year), clear_figure=True)
        st.dataframe(scores_df(), hide_index=True)
        st.caption("Scorecards for the 2017, 2023 and 2026 finals were not verified, so they are left out.")
    with tab3:
        st.dataframe(points_df(), hide_index=True)
        st.pyplot(chart_points(), clear_figure=True)
    with tab4:
        st.write("Optional: paste a free API key from cricketdata.org (CricAPI) to look for live PSL matches. "
                 "You can also set the environment variable CRICAPI_KEY.")
        key = st.text_input("API key", value=os.environ.get("CRICAPI_KEY", ""), type="password")
        if st.button("Fetch live PSL matches"):
            if not key:
                st.warning("Please enter an API key first.")
            else:
                rows, message = fetch_live_matches(key)
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True)
                else:
                    st.info(message)


def page_history():
    hero("🏆 History & Records", "Every PSL season from 2016 to 2026.")
    st.dataframe(seasons_df(), hide_index=True)
    year = st.select_slider("Season details", options=[s["year"] for s in SEASONS], value=SEASONS[-1]["year"])
    s = next(x for x in SEASONS if x["year"] == year)
    team_banner(s["winner"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Winner", s["winner"])
    c2.metric("Runner-up", s["runner_up"])
    c3.metric("Teams", s["teams"])
    st.write("**Final:** %s on %s at %s. Player of the Match: %s." % (s["result"], fmt_date(s["date"]), s["venue"], s["pom"]))
    st.write("**Most runs:** %s (%s) - %d  |  **Most wickets:** %s - %d" %
             (s["runs"][0], TEAMS[s["runs"][1]]["code"], s["runs"][2], s["wkts"][0], s["wkts"][2]))
    st.write("**Player of the Tournament:** %s" % s["pott"])
    if st.button("🎉 Celebrate the %d champions" % year):
        open_celebration(s["winner"], "%s are the PSL %d champions - %s!" % (s["winner"], year, s["result"].lower()))
    st.pyplot(chart_top_runs(), clear_figure=True)
    st.pyplot(chart_top_wickets(), clear_figure=True)
    st.caption("2019: the Wikipedia infobox and table say 430 runs for Shane Watson; its text says 435. "
               "The table value (430, also on ESPNcricinfo) is used.")


def page_vote():
    hero("🗳️ Fan Vote", "Pick your favourite PSL team and watch the percentages move.")
    votes = load_votes()
    cols = st.columns(4)
    for i, name in enumerate(TEAMS):
        with cols[i % 4]:
            st.image(make_logo(name, 160), width=90)
    team = st.selectbox("Your favourite team", list(TEAMS))
    if st.button("Cast my vote"):
        if st.session_state.get("voted"):
            st.warning("You already voted in this browser session. Thank you!")
        else:
            votes[team] += 1
            save_votes(votes)
            st.session_state["voted"] = True
            st.toast("Vote counted for %s!" % team)
    total = sum(votes.values())
    st.metric("Total votes", total)
    table = pd.DataFrame({"Team": list(votes), "Votes": list(votes.values()),
                          "Percent": ["%.1f%%" % (v / total * 100 if total else 0) for v in votes.values()]})
    st.dataframe(table.sort_values("Votes", ascending=False), hide_index=True)
    st.pyplot(chart_votes(votes), clear_figure=True)
    if st.button("👑 Crown the fan favourite"):
        if total == 0:
            st.warning("No votes yet - be the first to vote!")
        else:
            top = max(votes.values())
            leaders = [t for t, v in votes.items() if v == top]
            pct = top / total * 100
            tie = " (tied with %s)" % ", ".join(leaders[1:]) if len(leaders) > 1 else ""
            open_celebration(leaders[0], "Fans' favourite with %.1f%% of the votes%s. Congratulations!" % (pct, tie))
    with st.expander("Admin: reset votes"):
        if st.button("Reset all votes to zero"):
            save_votes({t: 0 for t in TEAMS})
            st.session_state["voted"] = False
            st.rerun()
    st.caption("Votes are stored in votes.json next to app.py. One vote per browser session (simple check, "
               "not secure against cheating).")


def page_fun():
    hero("🎨 Fun corner", "Draw the trophy with Turtle and learn where the data comes from.")
    st.write("The Turtle drawing opens in its own desktop window, so it works on Windows/Mac/Linux desktops "
             "but not on Google Colab or other servers.")
    if st.button("Draw the PSL trophy with Turtle"):
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            st.warning("No display found (this is normal on Google Colab). Run the app on your own computer to use Turtle.")
        else:
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "--turtle"])
            st.success("A Turtle window should appear. It may open behind this browser window.")
    st.subheader("Data sources")
    for label, url in DATA_SOURCES:
        st.markdown("- [%s](%s)" % (label, url))
    st.caption("Data checked in November 2026. Logos and photos are generated placeholders, not official artwork.")


def run_streamlit():
    st.set_page_config(page_title="PSL Cricket Hub", page_icon="🏏", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    pages = {"🏠 Home": page_home, "🛡️ Teams": page_teams, "🧢 Players": page_players,
             "📅 Matches & Scoreboards": page_matches, "🏆 History & Records": page_history,
             "🗳️ Fan Vote": page_vote, "🎨 Fun corner": page_fun}
    st.sidebar.title("🏏 PSL Cricket Hub")
    choice = st.sidebar.radio("Navigate", list(pages))
    st.sidebar.caption("PSL 11 (2026) champions: Peshawar Zalmi")
    pages[choice]()


# =====================================================================
# 4. GRADIO EXPLORER  (python app.py)
# =====================================================================

def run_gradio():
    try:
        import gradio as gr
    except ImportError:
        print("Gradio is not installed. Run: pip install -r requirements.txt")
        return

    def team_view(name):
        titles, runners = team_record(name)
        squad = ", ".join(SQUADS[name])
        text = ("### %s\n**City:** %s  \n**2026 captain:** %s  \n**Titles:** %s  \n**Runner-up:** %s  \n\n"
                "**2026 squad:** %s\n\n_* = overseas player_" %
                (name, TEAMS[name]["city"], TEAMS[name]["captain"],
                 ", ".join(map(str, titles)) or "None yet", ", ".join(map(str, runners)) or "None yet", squad))
        return make_logo(name, 300), text

    def player_view(name):
        p = next(x for x in PLAYERS if x["name"] == name)
        age = age_from_dob(p["dob"])
        stats = ", ".join("%s: %s" % (k, v) for k, v in p["stats"].items()) or "N/A"
        text = ("### %s\n**Team:** %s  \n**Country:** %s  \n**Role:** %s  \n**Age:** %s  \n"
                "**PSL 2026 stats:** %s  \n**Note:** %s" %
                (p["name"], p["team"], p["country"], p["role"], age if age is not None else "N/A", stats, p["note"]))
        return make_avatar(p["name"], p["team"]), text

    def season_view(year):
        s = next(x for x in SEASONS if x["year"] == int(year))
        return ("### PSL %d (edition %d)\n**Winner:** %s  \n**Runner-up:** %s  \n**Final:** %s, %s, %s  \n"
                "**Most runs:** %s - %d  \n**Most wickets:** %s - %d  \n**Player of the Tournament:** %s" %
                (s["year"], s["edition"], s["winner"], s["runner_up"], s["result"], fmt_date(s["date"]), s["venue"],
                 s["runs"][0], s["runs"][2], s["wkts"][0], s["wkts"][2], s["pott"]))

    team_names = list(TEAMS)
    player_names = [p["name"] for p in PLAYERS]
    years = [str(s["year"]) for s in SEASONS]
    with gr.Blocks(title="PSL Cricket Hub (Gradio)") as demo:
        gr.Markdown("# 🏏 PSL Cricket Hub - quick explorer\nFor the full app run `streamlit run app.py`.")
        with gr.Tab("Teams"):
            team_dd = gr.Dropdown(team_names, value=team_names[0], label="Team")
            team_img = gr.Image(type="pil", label="Generated badge (not official)")
            team_md = gr.Markdown()
            team_dd.change(team_view, team_dd, [team_img, team_md])
            demo.load(team_view, team_dd, [team_img, team_md])
        with gr.Tab("Players"):
            player_dd = gr.Dropdown(player_names, value=player_names[0], label="Player")
            player_img = gr.Image(type="pil", label="Generated avatar")
            player_md = gr.Markdown()
            player_dd.change(player_view, player_dd, [player_img, player_md])
            demo.load(player_view, player_dd, [player_img, player_md])
        with gr.Tab("Seasons"):
            gr.Dataframe(value=seasons_df(), label="All seasons")
            year_dd = gr.Dropdown(years, value=years[-1], label="Season")
            year_md = gr.Markdown()
            year_dd.change(season_view, year_dd, year_md)
            demo.load(season_view, year_dd, year_md)
    demo.launch(share="google.colab" in sys.modules)


# =====================================================================
# 5. ENTRY POINT
# =====================================================================

def running_in_streamlit():
    try:
        import streamlit.runtime as runtime
        return runtime.exists()
    except Exception:
        return False


def main():
    if "--turtle" in sys.argv:
        turtle_trophy()
    elif running_in_streamlit():
        run_streamlit()
    else:
        run_gradio()


if __name__ == "__main__":
    main()
