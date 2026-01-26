import time
import queue
import threading
import traceback
import numpy as np
import sounddevice as sd

from scipy.signal import resample
from collections import deque
from faster_whisper import WhisperModel


# num_frames = 512 samples
# blocksize != buffersize
# blocksize == 1 chunk = sample * frame
# buffersize == num of chunks  = (sample_freq/blocksize) chunks per_second * total seconds


SAMPLE_RATE = 44100
WHISPER_SAMPLE_RATE = 16000 # READ 16000 freq amplitudes per sec
BLOCKSIZE = 512 # return 16000 freq amplitudes in chunks of 512 samples
DURATION = 4 # READ 16K samples per second for 4 seconds = 16000 * 4
DTYPE = np.int16
INPUT_DEVICE = 10
QUEUE = queue.Queue()
CHANNELS = 2
BUFFER_SIZE = int((SAMPLE_RATE * DURATION)/BLOCKSIZE )

def rms(chunk: np.ndarray) -> np.float64:
    return np.sqrt(np.mean(chunk.astype(np.float64)**2))

def normalize_audio(audio_data: np.ndarray):
    return audio_data.astype(np.float32)/32768.0

class Buffer:
    def __init__(self):
        self._buffer = deque(maxlen=BUFFER_SIZE)
    
    def tail(self, N: int) -> list[np.ndarray]:
        return list(self._buffer)[N:]
    
    def add(self, chunk: np.ndarray):
        return self._buffer.append(chunk)
    
    def clear(self):
        return self._buffer.clear()

class Consumer:
    def __init__(self, model_size: str, device_index:int = 0):
        self.model = WhisperModel(model_size, device="cpu", device_index=device_index, compute_type="int8")

    def transcribe(self, clip: np.ndarray):
        print("Processing Audio...")
        segments, _ = self.model.transcribe(audio=clip[::3], language="en", log_prob_threshold=-1.2)
        for segment in segments:
            if not segment:
                print("Unable To transcribe..")
                return
            print("Text: ", segment.text, "\nLog Prob: ", segment.avg_logprob)

class Producer:
    def __init__(self,  buffer: Buffer, consumer: Consumer):
        self.buffer = buffer
        self.consumer = consumer
        self.thresh = 800
        self.shutdown = False
        print(f"Thresh is {self.thresh: .3f}")

    def start_audio_handler(self):
        talking = False
        silence_count = 0
        stream_buffer = []

        while not self.shutdown:
            audio = QUEUE.get()
            vol = rms(audio)
            self.buffer.add(audio)

            if vol > self.thresh:
                print("Reading...")
                if not talking:
                    stream_buffer.extend(self.buffer.tail(-8))
                    talking = True
                    self.buffer.clear()
                    continue
                silence_count = 0
                stream_buffer.append(audio)
            elif vol <= self.thresh:
                if not talking:
                    continue
                silence_count += 1

            if silence_count > 35:
                print(f"Silence count reached {silence_count}.\nStarting  Audio Procesing...")
                # Time to process and transcribe audio
                self.processor(stream_buffer)

                # reset parameters for another read
                silence_count = 0
                talking = False
                stream_buffer = []

                # persistence buffer clearing
                self.buffer.clear()

    def processor(self, audio: list[np.ndarray]):
        # 1. Flatten the stereo/multi-chunk data
        cpt_arr = np.concatenate(audio)
        old_sample_1dim = np.mean(cpt_arr, axis=1)

        new_sample_count = int((len(old_sample_1dim)*WHISPER_SAMPLE_RATE)/SAMPLE_RATE)
        new_sample_1dim = resample(old_sample_1dim, new_sample_count)

        float32 = normalize_audio(new_sample_1dim)

        # Trigger transcription
        threading.Thread(target=self.consumer.transcribe, args=(float32,)).start()
    
    def shutdown_handler(self):
        self.shutdown = True
                
class Listener:
    def __init__(self):
        self.stream = self.open_mic()
        self.stop = False

    def open_mic(self):
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCKSIZE,
            dtype=DTYPE,
            channels=CHANNELS,
            device=INPUT_DEVICE
        )

        stream.start()
        return stream
    
    def _calibrate(self):
        audio = self.stream.read(
            frames=int(SAMPLE_RATE*0.5),
        )
        sd.wait()
        vol = rms(audio[0])
        return max(vol * 1.5, 1000)
    
    def listen(self):
        print("Listening...")
        while not self.stop:
            audio_data, overflow = self.stream.read(frames=BLOCKSIZE)
            QUEUE.put(audio_data)
    
    def shutdown_listener(self):
        self.stream.stop()
        self.stop = True


if __name__ == "__main__":
    consumer = Consumer(model_size="base.en")
    buffer = Buffer()
    producer = Producer(buffer=buffer, consumer=consumer)
    sr = Listener()
    try:
        t1 = threading.Thread(target=sr.listen, daemon=True)

        t1.start()
        producer.start_audio_handler()
        t1.join(2.0)
    except IOError:
        print(traceback.format_exc())
    except KeyboardInterrupt:
        print("shutdown Initiated.")
    finally:
        sr.shutdown_listener()
        producer.shutdown_handler()
        print("Audio Shutdown.")




