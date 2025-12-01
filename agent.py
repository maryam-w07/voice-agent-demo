from dotenv import load_dotenv
load_dotenv()

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, JobContext, WorkerOptions
from livekit.plugins import openai, silero

# 1. Define the Agent's behavior (Instructions and optional tools)
class VoiceAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful and polite voice AI assistant. Keep your responses concise and conversational.")

# 2. Define the Entrypoint function to handle the job
async def entrypoint(ctx: JobContext):
    # Connect the agent to the room defined in the JobContext
    await ctx.connect()

    # Create an instance of your Agent class
    agent_instance = VoiceAssistant()
    
    
    session = AgentSession(
        stt=openai.STT(),
        llm=openai.LLM(),
        tts=openai.TTS(voice="alloy"),
        vad=silero.VAD.load(),
    )

    # Start the agent session with the Agent instance
    await session.start(room=ctx.room, agent=agent_instance)
    
 
    await session.generate_reply(instructions="Greet the user and offer your assistance.")

if __name__ == '__main__':
    # Use the entrypoint_fnc parameter in WorkerOptions
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint
    )
    
    # Run the Agent Server
    agents.cli.run_app(opts)
