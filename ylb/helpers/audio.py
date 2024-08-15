import scipy.io.wavfile as wavfile
import sounddevice as sd
import numpy as np
import subprocess
import logging

from ylb import config
from ylb import utils
from ylb.utils import TextColor
from ylb import openai_client as client
from typing import Optional


@utils.function_info
def listen(duration: Optional[int] = config.AUDIO_DEFAULT_DURATION) -> str:
    """
    Record microphone audio for the specified duration and return the transcribed text.

    :param duration: The duration of the audio recording in seconds. Default is 5 seconds.
    :type duration: integer
    :return: The transcribed text from the recorded audio.
    :rtype: string
    """
    if duration is None:
        duration = config.AUDIO_DEFAULT_DURATION
    logging.warning(
        f"{TextColor.FAIL}{TextColor.BOLD}🔴 Recording audio for {duration} seconds...{TextColor.ENDC}"
    )
    audio = sd.rec(
        int(config.AUDIO_DEFAULT_SAMPLE_RATE * duration),
        samplerate=config.AUDIO_DEFAULT_SAMPLE_RATE,
        channels=1,
    )
    sd.wait()
    audio = np.squeeze(audio)
    audio = (audio * 32767).astype(np.int16)
    filename = ".memory/request.wav"
    wavfile.write(filename, config.AUDIO_DEFAULT_SAMPLE_RATE, audio)

    with open(filename, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model=config.OPENAI_VOICE_MODEL,
            file=audio_file,
            response_format="text",
        )

    print(
        f"\n{TextColor.BOLD}{TextColor.WARNING}[👂] {transcript.strip()}{TextColor.ENDC}\n"
    )

    return transcript


@utils.function_info
def speak(text: str) -> None:
    """
    Generate text-to-speech audio and play it. Used to communcicate with the end user. Typically, `listen()` would be subsequently called to capture the user's response.

    :param text: The text to be converted into speech.
    :type text: string
    :return: The text that was spoken.
    :rtype: string

    :Example:
    >>> speak('This is some text to speak!')
    'Text spoken successfully'
    """
    try:
        if type(text) != str:
            raise TypeError("Text must be a string")

        # Use OpenAI's Python library to generate speech from text
        response = client.audio.speech.create(
            model=config.OPENAI_TTS_MODEL,
            voice=config.OPENAI_TTS_VOICE,
            input=text,
        )
        response.stream_to_file(".memory/response.wav")

        # Play the audio file using FFmpeg's ffplay
        print(
            f"\n{TextColor.OKGREEN}{TextColor.BOLD}[🗣️]{text.strip()}{TextColor.ENDC}\n"
        )
        subprocess.run(
            [
                "ffplay",
                "-loglevel",
                "quiet",
                "-nodisp",
                "-autoexit",
                ".memory/response.wav",
            ],
            check=True,
        )
        return f"Text spoken successfully"
    except Exception as e:
        logging.error(f"Failed to speak text: {e}")
        return f"Failed to speak text: {e}"
