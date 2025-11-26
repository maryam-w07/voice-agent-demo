import speech_recognition as sr
from openai import OpenAI
from pydub import AudioSegment
from pydub.playback import play
from dotenv import load_dotenv
import os


load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")


client = OpenAI(api_key=API_KEY)  
print(sr.Microphone.list_microphone_names())


def stt():
    r = sr.Recognizer() #recognizer obj
    with sr.Microphone() as source: #opens microphone
        print("Speak...")
        audio = r.listen(source) #records nd saves the recorded audio as an AudioData obj
    wav_data = audio.get_wav_data() #raw to byte wav,in-format for openai

    resp = client.audio.transcriptions.create(
        model="whisper-1",
        file=("speech.wav", wav_data)
    )
    return resp.text


def ask_gpt(text):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": text}]
    )
    return resp.choices[0].message.content


def tts_and_play(text):
    audio = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text
    ) #audio is not a file yet,it’s the TTS response object.
    global tts_time
    tts_time=time.time() #storing current time stamp,this marks the moment after the model finished generating audio.
    audio_path = "reply.mp3"
    audio.stream_to_file(audio_path) #Streams it directly into an MP3 file on disk
    sound = AudioSegment.from_file(audio_path) #audiosegment to load the mp3 file into memory
    play(sound)


import time
def main_loop():
    print("🤖 OpenAI Voice Agent (Whisper STT → GPT → OpenAI TTS). Say 'stop' or 'exit' to quit.")

    while True:
        loop_start = time.time()  # START measuring latency 

        user_text = stt()
        if not user_text:
            print("⚠️ No speech detected — try again.")
            continue

        print("🗣️ You said:", user_text)
        if any(tok in user_text.lower() for tok in ["stop", "exit", "quit"]):
            tts_and_play("Stopping now. Goodbye!")
            break

    
        reply = ask_gpt(user_text)
        print("🤖 Agent:", reply)

        loop_end = time.time()  
        tts_and_play(reply)
        processing_time = tts_time - loop_start
        print(f"⏱️ Processing time: {processing_time:.2f}s")

        

if __name__ == "__main__":
    main_loop()




