# main.py
from audio_listener_whisper import AudioListenerWhisper
from video_player import VideoPlayer

if __name__ == "__main__":
    player = VideoPlayer()
    listener = AudioListenerWhisper(player, ventana_seg=2.5, solapamiento_seg=0.5)

    listener.iniciar()
    player.iniciar()