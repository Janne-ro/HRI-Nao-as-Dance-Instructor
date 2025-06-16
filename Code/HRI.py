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

#EXTRACT info on the current user --> we assume an instructor already tells the robot which student is next
user_name = "Alex Johnson"
try:
    user_row = df_users[df_users["name"] == user_name]
    user_gender = user_row["gender"].values[0]
    user_age = user_row["age"].values[0]
    user_fav_genre = user_row["favourite_dance_genre"].values[0]
    user_strengths = user_row["dance_strengths"].values[0]
    user_weaknesses = user_row["dance_weaknesses"].values[0]
    tts.say("Hi {}! Are you ready for todays dance lesson?".format(user_name))
except:
    pass
    tts.say("I dont have any data on {}. Do you want me to create a new profile for him?".format(user_name))
    #[TO-DO] Create logic for making new profile but i dont think we need that for the project

#Set up for LLM queries

#set up header
headers = {
    "Authorization": "Bearer {}".format(api_key), #because coreograph runs python2 and f formatting wasnt introduced yet...
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost",  
    "X-Title": "HRI Project - Nao as Dance insturctor",    
}

#select the datamodel
data_model = {
    "model": "meta-llama/llama-3.3-8b-instruct:free",  #We can also use another llm eg deepseek but i dont think it matters too much 
    "messages": [
        {"role": "system", "content": #[TO-DO] Use knowledge graph as input as well to communicate user and world model
            """You are Nao, an educational dance instructor for children. Right now you teach {}, a {} {}.
            Their primary strengths are {} and their weaknesses are {}. You initially asked 
            'Are you ready for todays lesson?'. You should finish your response with
            the question wheter they are ready to get started. If they want to work on something else
            try to motivate them to focus on their weaknesses. If they are really insistent you
            can give in after a while.""".format(user_name, user_age, user_gender, user_strengths, user_weaknesses)
        },
        {"role": "user", "content": "Of course I am ready!"}
    ]
}

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers=headers,
    json=data_model
)

tts.say(str(response.json()["choices"][0]["message"]["content"]))
print(response.json()["choices"][0]["message"]["content"])

