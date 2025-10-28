
import os, base64
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_API_MODEL", "gpt-4o-mini")

SYS = ("You are a senior frontend engineer. Convert a webpage screenshot + HTML into "
       "React 18 + Tailwind components. Split into multiple files. "
       "Output as plain text using blocks like: [FILE: src/components/Name.jsx] then code. "
       "No markdown fences.")

def build_messages(html: str, image_b64: str):
    return [
        {"role":"system","content":SYS},
        {"role":"user","content":[
            {"type":"input_image","image_data":image_b64},
            {"type":"text","text": "Create semantic components (Header, Nav, Card, Footer). Use Tailwind classes. "
                                   "Each component begins with [FILE: ...].

HTML:
" + html[:100000]}
        ]}
    ]

def gpt_generate(html: str, image_b64: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=build_messages(html, image_b64),
        temperature=0.1,
        max_tokens=6000,
    )
    return resp.choices[0].message.content or ""
