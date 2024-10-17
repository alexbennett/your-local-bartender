import numpy as np
import subprocess
import logging
import webrtcvad
import wave
import time

from ylb import config
from ylb import utils
from ylb.utils import TextColor
from ylb import openai_client as client


def has_speech(audio_path):
    vad = webrtcvad.Vad(3)  # Aggressiveness from 0 to 3
    with wave.open(audio_path, 'rb') as wf:
        frames = wf.readframes(wf.getnframes())
        sample_rate = wf.getframerate()
        frame_duration = 30  # in ms
        frame_size = int(sample_rate * frame_duration / 1000) * wf.getsampwidth()
        for i in range(0, len(frames), frame_size):
            frame = frames[i:i+frame_size]
            if len(frame) < frame_size:
                continue
            if vad.is_speech(frame, sample_rate):
                return True
    return False