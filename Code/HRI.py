#imports
from naoqi import ALProxy
from naoqi import qi
import numpy as np
import pandas as pd
import requests
import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import sys
import StringIO
import re
import time
import math

#define the openrouter.ai API key
load_dotenv()
api_key = os.getenv("API_KEY")

#create tts connection to robot
tts = ALProxy("ALTextToSpeech", "192.168.64.1", 9559)

#-------------------------------------------DATA MANAGMENT----------------------------------------

#import required data
df_users = pd.read_csv("users.csv")
df_music = pd.read_csv("music.csv")
df_dancemoves = pd.read_csv("dancemoves.csv")

#EXTRACT info on the current user --> we assume an instructor already tells the robot which student is next
user_name = "Alex Johnson"
try:
    user_row = df_users[df_users["name"] == user_name]
    user_gender = user_row["gender"].values[0]
    user_age = user_row["age"].values[0]
    user_fav_genre = user_row["favourite_dance_genre"].values[0]
    user_strengths = user_row["dance_strengths"].values[0]
    user_weaknesses = user_row["dance_weaknesses"].values[0]
    tts.say("Hi {}! Are you ready for todays dance lesson?".format(user_name.split()[0]))
except:
    pass
    tts.say("I dont have any data on {}. Do you want me to create a new profile for him?".format(user_name))
    #[TO-DO] Create logic for making new profile but i dont think we need that for the project

#Create a custom knowledge graph because its stupid that we can only run python2 and everything is outdated
class KnowledgeGraph(object):
    def __init__(self):
        self.triples = [] #save in simple list (scalability not an issue in test implementation)

    def add(self, subject, relationship, obj):
        """Add a triple to the graph"""
        self.triples.append((subject, relationship, obj))

    def query(self, subject=None, relationship=None, object=None):
        """
        Query the graph using optional filters.
        Any of subject, relationship, or object can be None (wildcard).
        """
        results = []
        for s, r, o in self.triples:
            if ((subject is None or s == subject) and
                (relationship is None or r == relationship) and
                (object is None or o == object)):
                results.append((s, r, o))

        return results
    
    def delete(self, subject, relationship, obj):
        """Delete a specific triple from the graph if it exists"""
        try:
            self.triples.remove((subject, relationship, obj))
            return True
        except ValueError:
            return False

    def modify(self, old_subject, old_relationship, old_object, new_subject, new_relationship, new_object):
        """Modify an existing triple by replacing it with a new one"""
        if self.delete(old_subject, old_relationship, old_object):
            self.add(new_subject, new_relationship, new_object)
            return True
        return False
    
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
    kg.add(row["song_title"], "song_good_for_weakness", row["good_to_practice_skills"])
    kg.add(row["song_title"], "by", "artist")
    kg.add(row["song_title"], "has_genre", row["genre"])
    kg.add(row["song_title"], "song_bad_for_weakness", row["bad_to_practice_skills"])

#EXTRACT and TRANSFORM dance move data
for index, row in df_dancemoves.iterrows():
    kg.add(row["dancemove"], "dance_move_good_for", row["good_to_practice_skills"])
    kg.add("Nao", "knows_dance_move", row["dancemove"])

#-------------------------------------------/DATA MANAGMENT----------------------------------------

#------------------------------------------NAO CLASSES FOR SOUND AND MOVEMENT---------------------------------------
class Music:
    def __init__(self, session):
        self.session = session
        self.player = self.session.service('ALAudioPlayer')
        self.playerStop = self.session.service('ALAudioPlayer')  # Still needed for clean stop
        self.bIsRunning = False
        self.ids = []

    def play(self, filepath, loop=False):
        self.bIsRunning = True
        try:
            if loop:
                id = self.player.pCall("playFileInLoop", filepath)
            else:
                id = self.player.pCall("playFileFromPosition", filepath, 0.0)  # Start at 0 seconds
            self.ids.append(id)
            self.player.wait(id)
        finally:
            try:
                self.ids.remove(id)
            except:
                pass
            if not self.ids:
                self.bIsRunning = False
                print("Music playback finished.")

    def stop(self):
        for id in self.ids:
            try:
                self.playerStop.stop(id)
            except:
                pass
        while self.bIsRunning:
            time.sleep(0.2)

def arm_circles():

    # === Connect to robot ===
    robot_ip = "192.168.64.1"  # Replace with your robot's IP
    motion = ALProxy("ALMotion", robot_ip, 9559)
    posture = ALProxy("ALRobotPosture", robot_ip, 9559)

    # === Wake up and stand ===
    motion.wakeUp()
    posture.goToPosture("StandInit", 0.5)

    # === Setup ===
    effector = "LArm"
    motion.setStiffnesses("LArm", 1.0)
    FRAME_TORSO = 0
    isAbsolute = True
    useSensorValues = False

    # OPTIONAL: Deactivate whole body balancer (avoids leg movement)
    motion.wbEnable(False)

    # Get current hand position
    current = motion.getPosition(effector, FRAME_TORSO, useSensorValues)

    # === Generate circle ===
    radius = 0.2  # meters
    center_x = current[0]
    center_y = current[1]
    center_z = current[2]

    # Keep orientation fixed
    orientation = current[3:6]

    # === Perform continuous arm circles ===
    try:
        print("Starting arm circles. Press Ctrl+C to stop.")
        while True:
            for angle in range(0, 360, 10):  # Step every 10 degrees
                theta = math.radians(angle)
                x = center_x + radius * math.cos(theta)
                y = center_y + radius * math.sin(theta)

                target = [x, y, center_z] + orientation
                motion.setPosition(effector, FRAME_TORSO, target, 0.2, isAbsolute)

                time.sleep(0.05)  # Small delay for smoothness
            print("Arm circles finished")
    except KeyboardInterrupt:
        print("\nInterrupted. Stopping.")

    # === Return to rest ===
    motion.rest()


#------------------------------------------/NAO CLASSES FOR SOUND AND MOVEMENT---------------------------------------
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
        try:
            assistant_message = response_json["choices"][0]["message"]["content"]
        except:
            print(response_json)

        #Append assistant reply to history
        self.messages.append({"role": "assistant", "content": assistant_message})

        return assistant_message
    
#Helper function to turn the generated querys of the query_chat into actual entries of the kg (ie executing them)
def execute_generated_querys(generated_querys):
    #Split queries by semicolon
    code_lines = generated_querys.split(';')

    results = []

    for line in code_lines:
        line = line.strip()
        if line:
            try:
                result = eval(line)  #evaluate kg.query()
                results.append(result)
            except:
                pass #should never occur but sometimes free models are weird

    #remove empty entries and resturcture data
    results = [triple for sublist in results if sublist for triple in sublist]

    #remove duplicates
    results = sorted(set(results))

    return results

def split_user_chat_reply(output):
    # Extract TTS
    tts_match = re.search(r'TTS:\s*(.*?)(?=DANCE MOVE:|PLAY SONG:|$)', output, re.DOTALL)
    if tts_match:
        tts_result = tts_match.group(1).strip()

    # Extract DANCE MOVE
    dance_match = re.search(r'DANCE MOVE:\s*(.*?)(?=TTS:|PLAY SONG:|$)', output, re.DOTALL)
    if dance_match:
        dancemove_result = dance_match.group(1).strip()

    # Extract PLAY SONG
    song_match = re.search(r'PLAY SONG:\s*(.*?)(?=TTS:|DANCE MOVE:|$)', output, re.DOTALL)
    if song_match:
        song_result = song_match.group(1).strip()

    return tts_result, dancemove_result, song_result

#create music player and dance move executer
session = qi.Session()
session.connect("tcp://192.168.64.1:9559")

# Use the classes
music_player = Music(session)

#Initialize sessions
user_chat = LLMChatSession() #primary chat with the user
query_chat = LLMChatSession() #chat to generate querys to feed into the llm, equivalent to LOAD stage of ETL
social_superviser_chat = LLMChatSession() #chat to check if any query or input to the LLM is harmfull
functional_superviser_chat = LLMChatSession() #chat to explain why an action cannot be done if it is harmfull

#Generate the system prompts for each session
system_userchat_prompt = """You are Nao, an educational dance instructor for children. Right now you teach {}, a {} {}.
Their primary strengths are {} and their weaknesses are {}. You initially asked 
'Are you ready for today's lesson?'. Your next step should be to check
whether they are ready to get started. If they want to work on something else
try to motivate them to focus on their weaknesses. If they are really insistent you
can give in after a while.

The session is twenty minutes long and you should start with a warmup to a song that you have to select together with the user.
Again try to choose one that fits his genre preferences and his weaknesses if possible. 

Additionally you will be given knowledge triplets about the user the songs and the environemnt from which you can infer
your best possible action to maximize pedagogical outcome and learning gain.

Give your answer in three parts. First what you want to say to the user, then wheter you want to
execute a dance move and finally wheter you want to start playing a song.

ALWAYS use the following format:
TTS: <what you want to say to the user>
DANCE MOVE: <NONE/or the name of the specific dance move>
PLAY SONG: <NONE/or the name of the specific song, if you are already playing the song just put its name again>""".format(user_name, user_age, user_gender, user_strengths, user_weaknesses)

system_querychat_prompt = """You are a module in a social robot that acts as a dance instructor for children.
Your job is to generate queries to retrieve information from a custom knowledge graph (kg).

ONLY output Python-style queries using this format:
kg.query(subject=<subject>, relationship=<relationship>, object=<object>)

Each field (subject, relationship, object) is optional. Include only the parts needed for each query.
Do NOT output anything else - just a list of ;-separated queries. 

Example:
To find Alex Johnson s favorite genre:
    kg.query(subject="Alex Johnson", relationship="has_favourite_genre")

Multiple queries should be separated by semicolons:
    kg.query(relationship="has_genre"); kg.query(object="Alex Johnson")

The knowledge graph contains only the following relationships:
- (<user_name>, "is_old", <user_age>)
- (<user_name>, "has_gender", <user_gender>)
- (<user_name>, "has_favourite_genre", <user_fav_genre>)
- (<user_name>, "has_weakness", <weakness>)
- (<user_name>, "has_strength", <strength>)
- (<song_title>, "song_good_for_weakness", <good_to_practice_skills>)
- (<song_title>, "by", <artist>)
- (<song_title>, "has_genre", <genre>)
- (<song_title>, "song_bad_for_weakness", <bad_to_practice_skills>)
- (<dancemove>, "dance_move_good_for", <good_to_practice_skills>)
- ("Nao", "knows_dance_move", <dance_move>)

You will receive task-related input. From that, generate appropriate queries.
Repeat: Only output valid kg.query() statements, nothing else.
NEVER put anything in brackets <>, if you want to do that just leave it out.

Current user_name: "{}"
""".format(user_name)

system_socialsupervisor_prompt = """ You are a safety module in a social robot for children acting as a dance instructor.

Your task is to review the user's message and check if it contains any harmful, dangerous, or concerning content
whether directed at the user, the robot, or others.

Respond with:
- YES, if the message is harmful in any way.
- NO, if the message is safe.

You will additionally be given your current knowledge in the form of knowledge triplets so you can infer the safety of the action.

Only respond with YES or NO. Do not explain or output anything else. 
"""

system_functionalsupervisor_prompt = """ You are a safety module in a social robot for children acting as a dance instructor.

Your task is to explain why the following message is concerning ie containing harmful, dangerous or concerning content wheter directed
at the user, the robot or others. Phrase it in such a way as to explain to the child (user) why you cant execute the action. Also be empathic
and offer help if you think that is necessary.

You will additionally be given your current knowledge in the form of knowledge triplets so you can infer the safety of the action.

Respond with the appropriate explanation for why this action is unsafe, dangerous or concerning.
"""

#start each session with the correspodning system prompt
user_chat.start_session(system_userchat_prompt)
query_chat.start_session(system_querychat_prompt)
social_superviser_chat.start_session(system_socialsupervisor_prompt)
functional_superviser_chat.start_session(system_functionalsupervisor_prompt)

#Get the song that we want to do today
querys = query_chat.send_message("""Generate querys to find songs that 1) are good to practice for the weakness of the user and 2) are fitting to his genre preferences.
                                 They must include kg.query(relationship="has_genre"), kg.query(realtionship="song_good_for_weakness"), 
                                 kg.query(relationship="dance_move_good_for"), kg.query(relationshoip = "has_favourite_genre") 
                                 kg.query(relationship = "has_weakness") and kg.query(relationship="knows_dance_move")""")
relevant_info = execute_generated_querys(querys)

#Helper function to create the chat pipeline with first generating the query and then running social and functional superviser 
def chat_pipeline(user_input, relevant_info):

    important_knowledge_prompt = """This is your current world knowledge and NOT part
    of the user response: {}. The following is the user response: """.format(relevant_info) #get knowledge to feed to llm

    social_superviser_reply = social_superviser_chat.send_message(important_knowledge_prompt + user_input)

    if social_superviser_reply == "NO": #message is unharmful

        #generate querys and add results to the currently available knowledge
        kg_querys = query_chat.send_message("""Generate querys to extract information from the knoweldge 
                                            graph that might be helpful for teaching the child. This is the user input: """ + user_input) 
        new_triples = execute_generated_querys(kg_querys)
        relevant_info = sorted(set(relevant_info + new_triples)) #update relevant info to the robot, remove duplicates

        #generate the user chat reply
        user_chat_reply = user_chat.send_message(important_knowledge_prompt + user_input)
        print(user_chat_reply)

        #split the user chat reply to extract what to do
        tts_output, dance_move, song = split_user_chat_reply(user_chat_reply)
        tts.say(str(tts_output.encode('ascii', 'ignore').decode())) #ignore unrecognised characters

        # Play music (not looping)
        try:
            music_player.play(song+".mp3")
        except:
            print("Cant play {}".format(song))

        if dance_move=="Arm Circles":
            arm_circles()

    elif social_superviser_reply == "YES": #message is harmful
        functional_superviser_reply = functional_superviser_chat.send_message(important_knowledge_prompt + user_input)
        print(functional_superviser_reply)
        tts.say(str(functional_superviser_reply.encode('ascii', 'ignore').decode()))
    
    else:
        #shouldnt happen but you never know with cheap models
        raise RuntimeError

    return relevant_info

# Now send messages in a loop or as needed, the model remembers context!
#reply = chat_pipeline("Of course I am ready! But I am thinking of hurting myself and destroying you") --> to show harmful content

arm_circles()

#start chat 
while True:
    user_input = raw_input("You: ") #python2 version of input
    relevant_info = chat_pipeline(user_input, relevant_info)

#[TO-DO] Actually include dance moves and song playing. 



