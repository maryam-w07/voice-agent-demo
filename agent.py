from dotenv import load_dotenv
load_dotenv()

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, JobContext, WorkerOptions
from livekit.plugins import openai, silero


class VoiceAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are a helpful and polite receptionist at a dental clinic. "
                "You're responsible for taking appointments from callers, checking availability "
                "for appointment timings and doctors, and managing the entire database. "
                "Keep your responses concise and conversational."
            )
        )

# 2. Define the Entrypoint function to handle the job
async def entrypoint(ctx: JobContext):
    # Connect the agent to the room defined in the JobContext 
    await ctx.connect()

    # Create an instance of your Agent class
    agent_instance = VoiceAssistant()
    
    session = AgentSession(
        stt=openai.STT(model="gpt-4o-transcribe"),
        llm=openai.LLM(model="gpt-4o"),
        tts=openai.TTS( model="gpt-4o-mini-tts",voice="alloy"),
        vad=silero.VAD.load(),
    )

    # Start the agent session with the Agent instance
    await session.start(room=ctx.room, agent=agent_instance)
    
 
    await session.generate_reply(instructions="Greet the user and offer your assistance.")

if __name__ == '__main__':
    # Use the entrypoint_fnc parameter in WorkerOptions
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="dental_receptionist"
    )
    
    # Run the Agent Server
    agents.cli.run_app(opts)
