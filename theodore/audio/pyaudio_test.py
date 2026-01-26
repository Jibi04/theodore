import pyaudio
import numpy as np
import traceback
import wave

from typing import List, Any
from faster_whisper import WhisperModel
from collections import deque


AUDIO_PATH = "/home/jibi/scripts/theodore/theodore/audio/wave_write.wav"

def write_audio(path, audio, sr=16000):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())
    return path

    

class Buffer:
    def __init__(self, chunk: int = 1024, sample_rate: int = 16000, seconds: int = 4, dtype = np.int16):
        self.chunk = chunk
        self.sample_rate = sample_rate
        self.buffer_size = int(sample_rate/chunk) * seconds
        self._buffer = deque(maxlen=self.buffer_size)

        # sound card to ram transport size
        self._dtype = dtype

    def get_rms(self, data: np.ndarray) -> np.ndarray:
        audio_data = data.astype(np.float64)
        return np.sqrt(np.mean(audio_data**2))
    
    def get_clip(self) -> List[np.ndarray]:
        return list(self._buffer)
    
    def clear_buffer(self) -> None:
        return self._buffer.clear()
    
    def add_chunk(self, data) -> np.ndarray:
        audio_data = self.process_chunk(data)
        self._buffer.append(audio_data)
        return audio_data
    
    def process_chunk(self, frame: bytes) -> np.ndarray:
        return np.frombuffer(buffer=frame, dtype=self._dtype)

class Consumer:
    def __init__(self, model_size: str ="tiny", compute_type: str ="int8"):
        self.compute_type = compute_type
        self.model_size = model_size
        self.model = WhisperModel(self.model_size, device="cpu", compute_type=self.compute_type)

    def process_clip(self, clip: np.ndarray):
        print("Processing clip with Faster whisper...")
        clip = write_audio(audio=clip, path=AUDIO_PATH)
        segments, info = self.model.transcribe(audio=clip, language="en", beam_size=1)
        for segment in segments:
            print(f"Start: {segment.start: .2f}\nStop: {segment.end: .2f}\nText: {segment.text}\nProbability: {segment.avg_logprob: .2f}")




class Producer:
    def __init__(self, buffer: Buffer, consumer: Consumer, channels = 1, format=pyaudio.paInt16):
        self.pa = pyaudio.PyAudio()
        self.format = format
        self._channels = channels
        self.consumer = consumer
        self._buffer_instance = buffer
        self._stream = self.open_mic()
        self.thresh = self.calibrate()
        print(f"Using Device: {self.pa.get_default_input_device_info()['name']}")
        print("this is thresh: ", self.thresh)
    
    def open_mic(self):
        stream = self.pa.open(
                rate=self._buffer_instance.sample_rate,
                channels=self._channels,
                format= self.format,
                frames_per_buffer=self._buffer_instance.chunk,
                input=True
            )
        
        return stream
    
    def close_mic(self) -> None:
        print("Closing mic...")
        return self._stream.close()
    
    def terminate_audio(self) -> None:
        print("Terminating Audio instance...")
        return self.pa.terminate()
    
    def shutdown(self) -> None:
        print("Shutting Down...")
        self.close_mic()
        self.terminate_audio()
        print("Theodore ears Shutdown!")
        return

    
    def is_listening(self) -> bool:
        return self._stream.is_active()
    
    def calibrate(self) -> float:
        chunks = []
        for _ in range(25):
            chunk = self._stream.read(exception_on_overflow=False, num_frames=self._buffer_instance.chunk)
            data = np.frombuffer(chunk, dtype=self._buffer_instance._dtype)
            chunks.append(self._buffer_instance.get_rms(data))
        
        # 28000 seems to be the sweetspot Aparrently
        return min(np.mean(chunks) * 1.35, 5000.0)
        
    
    def listen(self):
        is_talking = False
        silence_count = 0
        captured_frames = []
        pre_roll_snapshot = []

        while True:
            chunk = self._stream.read(num_frames=self._buffer_instance.chunk, exception_on_overflow=False)
            processed_chunk = self._buffer_instance.add_chunk(chunk)
            vol = self._buffer_instance.get_rms(processed_chunk)

            if vol > self.thresh:
                print("\rSound detected reading...")
                if not is_talking:
                    # snapshot of initial chunk
                    pre_roll_snapshot = self._buffer_instance.get_clip()
                    print("initial chunk snapped!")

                # start listening
                captured_frames.append(processed_chunk)
                is_talking = True
                silence_count = 0

            if is_talking:
                # is talking signal is set, but silence detected wait for silence-count
                if vol < self.thresh: silence_count += 1

                if silence_count > 30:
                    print(f"\rsilence count reached {silence_count} initiating processing.")
                    raw_clip : np.ndarray = np.concatenate(pre_roll_snapshot + captured_frames)
                    
                    # convert to 32 bit and normalize for whisper (-1,1)
                    normalized = raw_clip.astype(np.float32) / 32768.0

                    # process the clip
                    print("\rsending clip for processing...")
                    self.consumer.process_clip(normalized)

                    # cleanup
                    silence_count = 0
                    is_talking = False
                    captured_frames = []
                    pre_roll_snapshot = []
                    self._buffer_instance.clear_buffer()
                


if __name__ == "__main__":
    buffer = Buffer()
    translator = Consumer(model_size="base.en")
    listener = Producer(buffer=buffer, consumer=translator)
    try:
        print("Theodore Listening...")
        listener.listen()
    except IOError:
        print("An error occurred during read")
        print(traceback.format_exc())
    except KeyboardInterrupt:
        print("Shutdown Initiated!")
    except Exception:
        print("An uncaught exception Occured.")
        print(traceback.format_exc())
    finally:
        listener.shutdown()


