import webrtcvad
import wave
from pydub import AudioSegment


def has_speech(audio_path):
    vad = webrtcvad.Vad(2)  # Aggressiveness from 0 to 3
    with wave.open(audio_path, 'rb') as wf:
        print(wf.getparams())
        frames = wf.readframes(wf.getnframes())
        print(f"Reading {len(frames)} frames from {audio_path}")
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



if __name__ == "__main__":
    filename = f"generated_audio/request-448293150008803338.wav"
    # filename = f"generated_audio/output.mp3"

    with open(filename, "rb") as f:
        sound = AudioSegment.from_file(f)
        sound.export("output.wav", format="wav")

    if has_speech("output.wav"):
        print(f"Speech detected in audio from user")
    else:
        print(f"No speech detected in audio from user")
