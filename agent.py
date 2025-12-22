from dotenv import load_dotenv
load_dotenv()
import os
import datetime
from livekit import agents 
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, function_tool, RunContext ##RunContext used in the function signatures
from livekit.plugins import openai, silero
from calender_tools import check_doctor_availability, init_calendar, list_doctors_and_services, book_appointment, cancel_appointment, current_time_date,_parse_datetime


# Initialize calendar client
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
TOKEN_FILE = "token.json"


# Check if CALENDAR_ID is set
if CALENDAR_ID is None:
    raise ValueError("GOOGLE_CALENDAR_ID environment variable is not set. Please set it in your .env file.")
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
                "You are a polite and professional Eva dental clinic receptionist"
                "clinic hours are from 9 A.M to 7 P.M. Monday to Saturday. closed on sunday."
                "Help callers book and cancel appointments.Before you book an appointmnet, check for availability,call check_doctor_availability_tool .if their preffered time slot is available tell them its avail nd you will proceed with booking otherwise ask them for another slot or recommend an available slot .You will then convert this to YYYY-MM-DD format yourself when calling the booking tool. "
                "Always collect required details before booking and before u actually book the appointment event in calender, read the booking details to caller nd ask them to confirm it nd then proceed with actually creating the event in calender. "
                "Use available tools when needed. be aware of current date nd year(use current_time_date_tool for current date nd year), you can only book appointments for the running day or future dates, not the bygone time. "
                "Keep responses short and conversational."
                "if a caller asks for information on doctors and services, use the list_doctors_tool tool."
                "dont hallucinate- you have all the tools provided that u need for engaging with callers as a receptionist."
                "use the tools available. "
                "DO NOT say you can not verify a slot or there is an issue, when a caller asks you book an appointment in the afternoon, or late in the evening, you can call the check_doctor_availability tool for that specefic date nd if it doesnot overlap with the doctor mantioned u can give them a slot.Otherwise, dont say i cant check slots, recommend them a slot."
            ),
        )

    # Tools using RunContext
    #by defining these methods  directly within the Agent subclass,LiveKit automatically tells the LLM (GPT-4o) that these functions are available, along with their parameters.
    #the tools are defined within the VoiceAssistant class, and by doing so, the LiveKit framework automatically calls/registers them with the LLM.
    @function_tool
    async def list_doctors_tool(self, context: RunContext) -> str:
        
        return await list_doctors_and_services(context)
    
    
    @function_tool
    async def check_doctor_availability_tool(
        self,
        context: RunContext,
        doctor_name: str,
        start_time: str,
        end_time: str,
    ) -> bool:
        return await check_doctor_availability(
            context,
            doctor_name,
            start_time,
            end_time
            
        )
    

    @function_tool
    async def current_time_date_tool(self,context: RunContext) -> str:
        return await current_time_date(context)
        

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
