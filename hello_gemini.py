from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()
response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents="In one sentence, what is a 10-K filing?",
)
print(response.text)