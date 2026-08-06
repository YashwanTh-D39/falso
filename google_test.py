from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

client = genai.Client(api_key=os.getenv("AQ.Ab8RN6L48WaUJundfuV5guIxNntyA0QuHMCxDeesjIU2qKaALg"))

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Say hello in one sentence."
)

print(response.text)