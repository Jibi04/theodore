import pyttsx3


engine = pyttsx3.init()

rate = engine.getProperty('rate')
engine.setProperty('rate', 145)

engine.setProperty('volume', 1.9)

voices = engine.getProperty('voices')
engine.setProperty('voice', voices[23].id)

engine.say(f"Theodore here. is this a better voice?")
# print(voices)

engine.runAndWait()

# import pyaudio

# p = pyaudio.PyAudio()
# info = p.get_default_input_device_info()
# print("--------- Theodore output checks -----------")
# print("Default Mic: ", info['name'])
# print("Sample rate: ", info['defaultSampleRate'], " Hz")
# p.terminate()


# from faster_whisper import WhisperModel

# model = WhisperModel("tiny", device="cpu", compute_type="int8")
# print("Theodore's Brain is Loaded say something.\n...")