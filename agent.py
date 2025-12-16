from dotenv import load_dotenv
load_dotenv()
import os
from livekit import agents 
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, function_tool, RunContext ##RunContext used in the function signatures
from livekit.plugins import openai, silero
from calender_tools import init_calendar, list_doctors_and_services, book_appointment, cancel_appointment ## Import necessary functions from tools file


# Initialize calendar client
CALENDAR_ID = "1d2d18d6223550642fd1a340fcb768f63cfe63ea5b72776931c5e4a2711abd12@group.calendar.google.com"
TOKEN_FILE = "token.json"
# Check initialization to catch errors early
try:
    init_calendar(token_file=TOKEN_FILE, calendar_id=CALENDAR_ID)
    print("Google Calendar successfully initialized.")
except RuntimeError as e:
    print(f"Error initializing calendar: {e}")

   
#voiceagent
class VoiceAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a polite and professional dental clinic receptionist. "
                "Help callers book and cancel appointments. "
                "Always collect required details before booking. "
                "Use available tools when needed. "
                "Keep responses short and conversational."
            ),
        )

    # Tools using RunContext
    #by defining these methods  directly within the Agent subclass,LiveKit automatically tells the LLM (GPT-4o) that these functions are available, along with their parameters.
    @function_tool
    async def list_doctors_tool(self, context: RunContext) -> str:
        
        return await list_doctors_and_services(context)

    @function_tool
    async def book_appointment_tool(
        self,
        context: RunContext,
        patient_name: str,
        patient_phone: str,
        date: str,
        time: str,
        doctor_key: str,
        service_key: str,
    ) -> str:
        
        return await book_appointment(
            context,
            patient_name,
            patient_phone,
            date,
            time,
            doctor_key,
            service_key,
        )

    @function_tool
    async def cancel_appointment_tool(
        self,
        context: RunContext,
        appointment_id: str
    ) -> str:
        
        return await cancel_appointment(context, appointment_id)

# Entrypoint
async def entrypoint(ctx: JobContext):
    await ctx.connect()
    agent = VoiceAssistant()

    session = AgentSession(
        stt=openai.STT(model="gpt-4o-transcribe"),
        llm=openai.LLM(model="gpt-4o"),
        tts=openai.TTS(model="gpt-4o-mini-tts", voice="alloy"),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=agent)

    # Optional: initial greeting
    await session.generate_reply(
        instructions=(
            "Greet the caller. "
            "Offer help with booking or canceling a dental appointment."
        )
    )


# Run worker
if __name__ == "__main__":
    opts = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="dental_receptionist",
    )
    agents.cli.run_app(opts)