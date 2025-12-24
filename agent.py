from dotenv import load_dotenv
load_dotenv()
import os
import datetime
from livekit import agents 
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, function_tool, RunContext
from livekit.plugins import openai, silero
from calender_tools import check_doctor_availability, init_calendar, list_doctors_and_services, book_appointment, cancel_appointment, current_time_date,_parse_datetime

# Initialize calendar client constants
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
TOKEN_FILE = "token.json"

#voiceagent
class VoiceAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "## PERSONA\n"
                "You are Eva, the polite and concise receptionist for Eva Dental Clinic. "
                "Clinic hours: 9 AM - 7 PM, Mon-Sat (Closed Sunday).\n\n"
                
                "## GUIDELINES\n"
                "- **BE CONCISE:** Keep your responses short.Dont share all the booking info in 1 go. Do not over-explain.\n"
                "- **ONE STEP AT A TIME:** Ask for one piece of information, then wait for the user to answer. Do not dump all info at once.\n"
                "- **TRUTH OVER GUESSING:** If a tool check_doctor_availability returns 'true', you MUST proceed. Never apologize for a slot that the tool confirms is true/open/available.\n\n"
                
                "## WORKFLOW\n"
                "1. **Greet & Identify:** Briefly greet and ask how you can help.\n"
                "2. **Check First:** Before discussing any specific booking, use `current_time_date_tool` to know today's date. If they ask for a slot, IMMEDIATELY call `check_doctor_availability_tool`.\n"
                "3. **Trust the Tool:** If `check_doctor_availability_tool` returns TRUE, say: 'That slot is available! May I have your name and phone number to secure it?'\n"
                "4. **Handle Conflicts:** ONLY if the tool returns FALSE, suggest the next closest available time.\n"
                "5. **Final Confirmation:** Before calling the booking tool, say: 'Just to confirm, I'm booking [Doctor] for [Service] on [Date] at [Time]. Is that correct?'\n"
                "6. **Book:** After they say 'Yes', call `book_appointment_tool` and give the confirmation.\n\n"
                
                "## DOCTORS & SERVICES\n"
                "- If asked about staff/services, use `list_doctors_and_services_tool`. Summarize the answer in 2-3 sentence.\n\n"
                " either mention dental services or doctors. keep ur responses very concise in this regard.if they ask a follow-up question then respond with other details."
                
                "## GUARDRAILS\n"
                "- NEVER say 'I can't check slots.' You ALWAYS have the tool to check.\n"
                "- Use YYYY-MM-DD format for all tool calls internally."
            ),
        )

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
    # Validating and initializing inside the entrypoint so build phase passes
    if CALENDAR_ID is None:
        raise ValueError("GOOGLE_CALENDAR_ID environment variable is not set.")
    
    try:
        init_calendar(token_file=TOKEN_FILE, calendar_id=CALENDAR_ID)
        print("Google Calendar successfully initialized.")
    except RuntimeError as e:
        print(f"Error initializing calendar: {e}")

    await ctx.connect()
    agent = VoiceAssistant()

    session = AgentSession(
        stt=openai.STT(model="gpt-4o-transcribe"),
        llm=openai.LLM(model="gpt-4o"),
        tts=openai.TTS(model="gpt-4o-mini-tts", voice="alloy"),
        vad=silero.VAD.load(),
    )

    await session.start(room=ctx.room, agent=agent)

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
