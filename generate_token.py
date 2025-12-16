import os
from dotenv import load_dotenv
from livekit import api  # from livekit-api package

load_dotenv()

LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
ROOM_NAME = "dental-room"
IDENTITY = "dental-agent"

token = api.AccessToken(
    api_key=LIVEKIT_API_KEY,
    api_secret=LIVEKIT_API_SECRET,
).with_identity(IDENTITY).with_grants(
    api.VideoGrants(
        room_join=True,
        room=ROOM_NAME,
    )
).to_jwt()

print("Join token:", token)