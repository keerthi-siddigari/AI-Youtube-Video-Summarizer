from flask import Flask, request, jsonify, render_template
import yt_dlp
import os
import re
from groq import Groq
from dotenv import load_dotenv
from deepgram import DeepgramClient
import asyncio

load_dotenv()
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

# v6 way to initialize Deepgram
dg_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
app = Flask(__name__)

# ----------------- Groq Setup -----------------
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ----------------- Helper Functions -----------------

def download_subtitles(video_url):
    ydl_opts = {
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "skip_download": True,
        "outtmpl": "subtitle_%(id)s.%(ext)s",
        "quiet": True,
        "socket_timeout": 10
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    for file in os.listdir():
        if file.endswith(".vtt"):
            return file
    return None


def clean_vtt(file_path):
    lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "-->" in line or line.isdigit() or line == "WEBVTT" or line == "":
                continue
            lines.append(line)
    return " ".join(lines)


def get_video_info(video_url):
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    return {
        "title": info.get("title", "No Title"),
        "thumbnail": info.get("thumbnail", "")
    }


# Audio extraction
def download_audio(video_url):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "audio_%(id)s.%(ext)s",
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    for file in os.listdir():
        if file.endswith(".mp3"):
            return file

    return None  


async def transcribe_with_deepgram(audio_file):
    with open(audio_file, "rb") as f:
        response = await dg_client.listen.prerecorded.v("1").transcribe_file(
            {"buffer": f},
            {"punctuate": True}
        )

    return response["results"]["channels"][0]["alternatives"][0]["transcript"]

def audio_to_text(audio_file):
    return asyncio.run(transcribe_with_deepgram(audio_file))


def chunk_text(text, max_chunk_size=2000):
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) < max_chunk_size:
            current += sentence + " "
        else:
            chunks.append(current.strip())
            current = sentence + " "

    if current:
        chunks.append(current.strip())

    return chunks


def limit_lines(text, max_lines):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines[:max_lines])


# ----------------- GROQ SUMMARIZER -----------------
def groq_summarize(text, length_type="medium", bullet_mode=False):

    if length_type == "short":
        instruction = """
        Summarize the text in 3-4 lines.

        Focus only on the most important ideas and insights.
        Avoid storytelling details or specific minor events.

        STRICT RULES:
        - No introductions or headings
        - No filler or generic phrases
        - No unnecessary or low-value details
        - Do NOT add assumptions beyond the text
        - Write naturally and directly
        - Keep each sentence meaningful
        """

    elif length_type == "medium":
        instruction = """
        Summarize the text in 6-8 lines.

        Focus on key ideas and useful insights.
        Prioritize concepts over step-by-step events.

        STRICT RULES:
        - Do NOT include any introductory phrases
        - Do NOT say "Here is a summary" or similar
        - Do NOT mention line counts
        - Avoid long paragraphs
        - Avoid minor descriptive details
        - Do NOT add assumptions beyond the text

        STYLE:
        - 1 idea per line
        - Keep sentences short, clear, and natural
        - Make it easy to scan and understand
        """

    elif length_type == "detailed":
        instruction = """
        Summarize the text in 10-14 lines.

        Structure the output exactly as:

        Main Ideas
        • ...

        Key Insights
        • ...

        Focus on:
        - important concepts
        - meaningful insights
        - useful takeaways

        STRICT RULES:
        - No introductions or explanations
        - No numbering (use bullet points only)
        - Avoid repetition of similar ideas
        - Avoid minor or trivial details
        - Focus on concepts, not specific incidents
        - Keep it clean, concise, and well-structured
        """

    if bullet_mode:
        instruction += "\nUse bullet points wherever possible for clarity."

    prompt = f"""
    You are generating a clean, structured, and user-friendly summary.

    Follow all rules strictly. Do not break formatting instructions.
    Prioritize key concepts and insights over storytelling.

    {instruction}

    Text:
    {text}
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a precise and structured summarization assistant."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()


def preprocess_text(text):
    text = re.sub(r'\s+', ' ', text)

    fillers = [" uh ", " um ", " yk "]
    for word in fillers:
        text = text.replace(word, " ")

    return text.strip()


def smart_trim(text, max_chars=6000):
    if len(text) <= max_chars:
        return text

    half = max_chars // 2
    return text[:half] + " " + text[-half:]


# ----------------- ROUTES -----------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/summarize", methods=["POST"])
def summarize():
    data = request.json
    url = data.get("url")
    length_type = data.get("length", "medium")
    bullet_mode = data.get("bullet", False)

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        # Catch unavailable videos
        try:
            video_info = get_video_info(url)
        except Exception:
            return jsonify({"error": "Video not available or cannot be accessed."}), 400

        # Try subtitles first
        subtitle_file = download_subtitles(url)
        if subtitle_file:
            full_text = clean_vtt(subtitle_file)
            os.remove(subtitle_file)
        else:
            # If no subtitles, fallback to audio
            audio_file = None
            try:
                audio_file = download_audio(url)

                if not os.path.exists(audio_file):
                    return jsonify({"error": "Audio processing failed"}), 500

                full_text = audio_to_text(audio_file)

            finally:
                if audio_file and os.path.exists(audio_file):
                    os.remove(audio_file)

        if not full_text.strip():
            return jsonify({"error": "No text extracted from video"}), 400

        full_text = preprocess_text(full_text)
        full_text = smart_trim(full_text, max_chars=6000)

        chunks = chunk_text(full_text)

        summaries = []
        for chunk in chunks:
            out = groq_summarize(chunk, length_type, bullet_mode)
            summaries.append(out)

        combined = " ".join(summaries)

        final_summary = groq_summarize(combined, length_type, bullet_mode)

        if length_type == "short":
            final_summary = limit_lines(final_summary, 4)
        elif length_type == "medium":
            final_summary = limit_lines(final_summary, 8)
        elif length_type == "detailed":
            final_summary = limit_lines(final_summary, 14)

        return jsonify({
            "title": video_info["title"],
            "thumbnail": video_info["thumbnail"],
            "summary": final_summary
        })

    except Exception as e:
        return jsonify({"error": f"Something went wrong: {str(e)}"}), 500


# ----------------- RUN -----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)