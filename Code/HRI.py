#imports
from naoqi import ALProxy
import numpy as np
import pandas as pd
import requests
import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

#define the openrouter.ai API key
load_dotenv()
api_key = os.getenv("API_KEY")

#create tts connection to robot
tts = ALProxy("ALTextToSpeech", "192.168.10.98", 9559)

#-------------------------------------------DATA MANAGMENT----------------------------------------

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

#[TO-DO] EXTRACT the song info

#Create a custom knowledge graph because its stupid that we can only run python2 and everything is outdated
class KnowledgeGraph(object):
    def __init__(self):
        self.triples = [] #save in simple list (scalability not an issue in test implementation)

    def add(self, subject, relationship, obj):
        """Add a triple to the graph"""
        self.triples.append((subject, relationship, obj))

    def query(self, subject=None, relationship=None, obj=None):
        """
        Query the graph using optional filters.
        Any of subject, relationship, or object can be None (wildcard).
        """
        results = []
        for s, r, o in self.triples:
            if ((subject is None or s == subject) and
                (relationship is None or r == relationship) and
                (obj is None or o == obj)):
                results.append((s, r, o))
        return results

    def __str__(self):
        return "\n".join(["{} --{}--> {}".format(s, r, o) for s, r, o in self.triples])
    
#create knowledge graph
kg = KnowledgeGraph()

#TRANFORM userdata
kg.add(user_name, "is_old", user_age)
kg.add(user_name, "has_gender", user_gender)
kg.add(user_name, "has_favourite_genre", user_fav_genre)
for weakness in user_weaknesses.split(", "):
    kg.add(user_name, "has_weakness", weakness)
for strength in user_strengths.split(", "):
    kg.add(user_name, "has_strength", strength)

#EXTRACT and TRANSORM song data that is needed to make a decision on what song to dance to today
for index, row in df_music.iterrows():
    kg.add(row["song_title"], "good_for_weakness", row["good_to_practice_skills"])
    kg.add(row["song_title"], "by", "artist")
    kg.add(row["song_title"], "has_genre", row["genre"])
    kg.add(row["song_title"], "bad_to_pracitce", row["bad_to_practice_skills"])

#-------------------------------------------/DATA MANAGMENT----------------------------------------

#Set up for LLM queries

#Create a class to query the LLM 
class LLMChatSession(object):
    def __init__(self):
        self.api_key = api_key
        self.model_name = "deepseek/deepseek-r1-0528-qwen3-8b:free"
        self.headers = {
            "Authorization": "Bearer {}".format(api_key),
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "HRI Project - Nao as Dance instructor",
        }
        self.messages = []  #full chat history, including system + user + assistant

    def start_session(self, system_content):
        #Reset chat with new system prompt
        self.messages = [{"role": "system", "content": system_content}]

    def send_message(self, user_content):
        #Append user message
        self.messages.append({"role": "user", "content": user_content})

        data_model = {
            "model": self.model_name,
            "messages": self.messages,
        }

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=self.headers,
            json=data_model
        )
        response_json = response.json()

        #Extract assistant reply
        assistant_message = response_json["choices"][0]["message"]["content"]

        #Append assistant reply to history
        self.messages.append({"role": "assistant", "content": assistant_message})

        return assistant_message

#Initialize sessions
user_chat = LLMChatSession() #primary chat with the user
query_chat = LLMChatSession() #chat to generate querys to feed into the llm, equivalent to LOAD stage of ETL
social_superviser_chat = LLMChatSession() #chat to check if any query or input to the LLM is harmfull
functional_supervicer_chat = LLMChatSession() #chat to explain why an action cannot be done if it is harmfull

#Generate the system prompts for each session
system_userchat_prompt = """You are Nao, an educational dance instructor for children. Right now you teach {}, a {} {}.
Their primary strengths are {} and their weaknesses are {}. You initially asked 
'Are you ready for today's lesson?'. You should finish your response with
the question whether they are ready to get started. If they want to work on something else
try to motivate them to focus on their weaknesses. If they are really insistent you
can give in after a while.""".format(user_name, user_age, user_gender, user_strengths, user_weaknesses)

system_querychat_prompt = """You are an module in a social robot that functions as a dance instructor for children. Your job 
inside the robot is to generate querys to get information from a custom knowledge graph. 
Only generate querys of the form kg.query(subject=<possible subject>, relationship=<possible realtionship>, object=<possible object>).
You dont have to include subject, realtionship and object in each query. All of these are optional for example i can query what Alex Johnsons
faviourite genre is with the query kg.query(subject="Alex Johnson, relationship="has_favourite_genre")
Dont output anything else. Sperate each query by a , 
An example output would be kg.query(realtionship="has_genre"), kg.query(object="Alex Johnson", subject="15")
You will get some information on your current task as input and you should output the querys.
The kg can onyl possibly include the following realtionships (object, realtionship, subject): 
(<user_name>, "is_old", <user_age>)
(<user_name>, "has_gender", <user_gender>)
(<user_name>, "has_favourite_genre", <user_fav_genre>)
(<user_name>, "has_weakness", <weakness>)
(<user_name>, "has_strength", <strength>)
(<song_title>, "good_for_weakness", <good_to_practice_skills>)
(<song_title>, "by", <artist>)
(<song_title>, "has_genre", <genre>)
(<song_title>, "bad_to_pracitce", <bad_to_practice_skills>)
Your current user_name is {}
""".format(user_name)

#start each session with the system prompt
user_chat.start_session(system_userchat_prompt)
query_chat.start_session(system_querychat_prompt)

#Get the song that we want to do today
querys = query_chat.send_message("Generate querys to find songs that are beneficial for the user to study")
relevant_info = 

# Now send messages in a loop or as needed, the model remembers context!
reply = user_chat.send_message("Of course I am ready!")
#tts.say(reply)
print(reply)

