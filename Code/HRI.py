#imports
from naoqi import ALProxy
import numpy as np
import pandas as pd
import requests
import os
from dotenv import load_dotenv

#define the openrouter.ai API key
load_dotenv()
api_key = os.getenv("API_KEY")

#create tts connection to robot
tts = ALProxy("ALTextToSpeech", "192.168.10.98", 9559)

#import required data
df_users = pd.read_csv("users.csv")
df_music = pd.read_csv("music.csv")
#df_dancemoves = pd.read_csv("dancemoves.csv")

#extract info on the current user --> we assume an instructor already tells the robot which student is next
user_name = "Alex Johnson"
try:
    user_row = df_users[df_users["name"] == user_name]
    user_gender = user_row["gender"].values[0]
    user_age = user_row["age"].values[0]
    user_fav_genre = user_row["favourite_dance_genre"].values[0]
    user_strengths = user_row["dance_strengths"].values[0]
    user_weaknesses = user_row["dance_weaknesses"].values[0]
    #tts.say(f"Hi {user_name}! Are you ready for todays dance lesson?")
except:
    pass
    #tts.say(f"I dont have any data on {user_name}. Do you want me to create a new profile for him?")
    #[TO-DO] Create logic for making new profile but i dont think we need that for the project

pass
