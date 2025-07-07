import asyncio
import json
import logging
import os
import uuid
import fractions
import subprocess
import threading
import time
import traceback
from typing import Dict, Set, Optional, Tuple, TYPE_CHECKING, List, Union

import av
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack
from av.frame import Frame
from av.audio.frame import AudioFrame
from av.audio.resampler import AudioResampler
from av.video.frame import VideoFrame
from av.packet import Packet

if TYPE_CHECKING:
    from asyncio.subprocess import Process

# --- Configuration ---
ROOT = os.path.dirname(__file__)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
RTMP_URL = os.getenv("RTMP_URL", "rtmp://localhost:1935/live/stream")
USE_HARDWARE_ACCELERATION = os.getenv("USE_HARDWARE_ACCELERATION", "false").lower() == "true"

# FFmpeg command
# Bu komut RTMP akışını H.264 video ve PCM ses formatına dönüştürür,
# ardından Matroska konteynerına koyarak stdout'a yönlendirir.
def get_ffmpeg_command():
    base_command = [
        "ffmpeg",
        "-listen", "1",  # RTMP sunucusu olarak davran
        "-re",  # Girdiyi doğal frame hızında oku
    ]
    
    # Donanım hızlandırma etkinse ekle
    if USE_HARDWARE_ACCELERATION:
        base_command.extend([
            "-hwaccel", "auto",  # Mevcut donanım hızlandırmayı kullan
        ])
    
    base_command.extend([
        "-i", RTMP_URL,
        # Video ayarları
        "-vcodec", "libx264" if not USE_HARDWARE_ACCELERATION else "h264_vaapi",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-b:v", "2500k",  # Video bit hızı
        "-maxrate", "3000k",
        "-bufsize", "6000k",  # maxrate'in iki katı - bit hızı dalgalanmalarını yönetme
        "-g", "60",  # GOP (keyframe aralığı) - akıcılık için artırıldı
        # Ses ayarları – aiortc'nin Opus kodlaması yapabilmesi için ham PCM s16 çıktısı
        "-acodec", "pcm_s16le",
        "-ac", "2",  # Stereo ses
        "-ar", "48000",  # Örnekleme hızı (aiortc 48 kHz bekler)
        # Çıktı ayarları
        "-f", "matroska",  # Çıktı formatı
        "-loglevel", "warning",  # FFmpeg log seviyesini azalt
        "pipe:1",  # stdout'a çıktı
    ])
    
    return base_command

FFMPEG_COMMAND = get_ffmpeg_command()

# --- Globals ---
pcs: Set[RTCPeerConnection] = set()
relay = None
web_app = web.Application()

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc_server")


# --- Media Relay ---

class VideoRelayTrack(VideoStreamTrack):
    """
    Kuyruktan video frame'leri çeken bir video track.
    """
    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[Optional[Frame]] = asyncio.Queue(maxsize=180)  # ~3 sn @ 60 fps
        self._last_warning_ts: float = 0.0

    async def recv(self) -> Frame:
        frame = await self._queue.get()
        if frame is None:
            raise asyncio.CancelledError
        return frame

    def push(self, frame: Frame):
        """
        Decode edilmiş video frame'ini WebRTC pipeline'ına gönder.
        """
        global pcs
        if len(pcs) == 0:
            return  # İzleyen yoksa sessizce düşür

        if self._queue.full():
            # Kuyruk doluysa, sadece en eski frame'i at
            try:
                self._queue.get_nowait()
                now = time.time()
                if now - self._last_warning_ts > 5:
                    logger.warning("Video track kuyruğu dolu, eski bir frame düşürüldü.")
                    self._last_warning_ts = now
            except asyncio.QueueEmpty:
                pass

        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            pass

    def stop(self):
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass


class AudioRelayTrack(AudioStreamTrack):
    """
    Kuyruktan ses frame'leri çeken bir ses track.
    FFmpeg'den gelen ham PCM verisini WebRTC için yeniden örnekler.
    """
    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[Optional[Frame]] = asyncio.Queue(maxsize=250)
        self._last_warning_ts: float = 0.0
        
        # aiortc'nin beklediği formata dönüştürmek için bir resampler.
        # Bu, her zaman doğru formatta ve layout'ta frame'ler üretmemizi sağlar.
        self._resampler = AudioResampler(
            format="s16",    # Hedef format
            layout="stereo", # Hedef layout
            rate=48000,      # Hedef örnekleme hızı
        )

    async def recv(self) -> AudioFrame:
        # recv() metodu artık AudioFrame döndüreceğini belirtiyor.
        frame = await self._queue.get()
        if frame is None:
            raise asyncio.CancelledError
        return frame

    def push(self, frame: AudioFrame):
        """
        Gelen ses frame'ini yeniden örnekler ve kuyruğa ekler.
        """
        global pcs
        if len(pcs) == 0:
            return

        try:
            # Gelen frame'i resampler ile işle. Bu, birden fazla frame döndürebilir.
            resampled_frames = self._resampler.resample(frame)
            for resampled_frame in resampled_frames:
                self._add_frame_to_queue(resampled_frame)
        except Exception as e:
            # EOF hatalarını ve benzer yaygın hataları daha sessiz handle et
            error_msg = str(e)
            if "End of file" in error_msg or "541478725" in error_msg:
                # EOF hatalarını log spam'ini önlemek için daha az sıklıkta logla
                now = time.time()
                if now - self._last_warning_ts > 10:  # 10 saniyede bir
                    logger.info("Ses stream'i sona erdi veya kesinti oluştu (EOF hatası)")
                    self._last_warning_ts = now
            else:
                logger.warning(f"Ses frame'ini yeniden örneklerken hata oluştu: {e}")
            return
            
    def _add_frame_to_queue(self, frame: AudioFrame):
        """
        Bir audio frame'i kuyruğa ekler, gerekirse frame'leri düşürür.
        """
        if self._queue.full():
            # Kuyruk doluysa, en eski frame'i at.
            # Bu, yarısını atmaktan daha yumuşak bir geçiş sağlar.
            try:
                self._queue.get_nowait()
                now = time.time()
                if now - self._last_warning_ts > 5:
                    logger.warning("Ses track kuyruğu dolu, eski bir frame düşürüldü.")
                    self._last_warning_ts = now
            except asyncio.QueueEmpty:
                pass
        
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            # Bu durumun yaşanmaması gerekir ama yine de bir koruma.
            pass

    def stop(self):
        try:
            # Resampler'ı temizle, kalan frame'leri al
            final_frames = self._resampler.resample(None)
            for frame in final_frames:
                self._add_frame_to_queue(frame)
        except Exception:
            pass # Kapanışta hata olabilir, önemli değil.

        # Resampler'ı yeniden oluştur (temizlik için)
        try:
            self._resampler = AudioResampler(
                format="s16",
                layout="stereo",
                rate=48000,
            )
        except Exception:
            pass

        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass


class MediaRelay:
    """
    FFmpeg sürecini yönetir ve çıktısını tüm bağlı WebRTC eşlerine iletir.
    Ana asyncio event loop'unu bloke etmemek için FFmpeg süreci ve demuxing'i
    ayrı bir thread'de çalıştırır.
    """
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._process: Optional[subprocess.Popen] = None
        self._video_track: Optional[VideoRelayTrack] = None
        self._audio_track: Optional[AudioRelayTrack] = None
        self._tracks: List[Union[VideoRelayTrack, AudioRelayTrack]] = []
        self._should_run = True
        self._restart_count = 0
        self._max_restarts = 10

    @property
    def video_track(self) -> Optional[VideoRelayTrack]:
        return self._video_track
    
    @property
    def audio_track(self) -> Optional[AudioRelayTrack]:
        return self._audio_track

    def start(self, loop: asyncio.AbstractEventLoop):
        """
        Relay'in ana döngüsünü yeni bir thread'de başlatır.
        """
        self._should_run = True
        self._thread = threading.Thread(target=self._run_loop, args=(loop,), name="MediaRelayLoop")
        self._thread.start()
        logger.info("MediaRelay thread başlatıldı.")

    def stop(self):
        """
        Relay'i durdurur ve thread'in sonlanmasını bekler.
        """
        self._should_run = False
        if self._process:
            logger.info("FFmpeg süreci sonlandırılıyor...")
            self._process.terminate()
            
            # Düzgün kapanmayı bekle
            try:
                self._process.wait(timeout=3.0)
                logger.info("FFmpeg süreci düzgün şekilde sonlandırıldı.")
            except subprocess.TimeoutExpired:
                logger.warning("FFmpeg süreci düzgün kapanmadı, zorla sonlandırılıyor...")
                self._process.kill()
                try:
                    self._process.wait(timeout=2.0)
                    logger.info("FFmpeg süreci başarıyla sonlandırıldı.")
                except subprocess.TimeoutExpired:
                    logger.error("FFmpeg süreci sonlandırılamadı!")
                    
        if self._thread:
            logger.info("MediaRelay thread'inin bitmesi bekleniyor...")
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("MediaRelay thread zamanında bitmedi.")
        logger.info("MediaRelay durduruldu.")

    def _run_loop(self, loop: asyncio.AbstractEventLoop):
        """
        Relay thread'inin ana döngüsü. Sürekli olarak FFmpeg'i çalıştırmayı dener.
        """
        while self._should_run:
            if self._restart_count >= self._max_restarts:
                logger.error(f"Maksimum yeniden başlatma sayısına ({self._max_restarts}) ulaşıldı. MediaRelay durduruluyor.")
                self._should_run = False
                break
                
            logger.info("FFmpeg süreci relay thread'inde başlatılıyor...")
            self._start_and_demux(loop)
            
            if self._should_run:
                self._restart_count += 1
                wait_time = min(5 * self._restart_count, 30)  # Artan bekleme süresi, max 30 saniye
                logger.warning(f"FFmpeg süreci sona erdi. {wait_time} saniye içinde yeniden başlatılacak... (Deneme {self._restart_count}/{self._max_restarts})")
                for i in range(wait_time):
                    if not self._should_run: 
                        break
                    time.sleep(1)

    def _start_and_demux(self, loop: asyncio.AbstractEventLoop):
        """
        FFmpeg'i başlatır ve çıktısını demux eder. Bu senkron, bloke eden bir metoddur.
        """
        try:
            self._process = subprocess.Popen(
                FFMPEG_COMMAND,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Tamponlamayı devre dışı bırak
            )
            threading.Thread(target=self._log_stderr, name="FFmpegStderr").start()
            logger.info("FFmpeg süreci başarıyla başlatıldı.")

            # Track'leri oluştur ve mevcut eşlere bildir
            self._create_tracks(loop)

            # Demux ve relay
            self._demux(loop)
            
            # Başarılı çalışma sonrası restart sayacını sıfırla
            if self._process.returncode == 0:
                self._restart_count = 0

        except FileNotFoundError:
            logger.error("ffmpeg komutu bulunamadı. Relay devre dışı bırakılıyor.")
            self._should_run = False
        except Exception as e:
            logger.error(f"FFmpeg süreci veya demuxing'de hata: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            if self._process and self._process.stdout:
                self._process.stdout.close()
            if self._process and self._process.stderr:
                self._process.stderr.close()
            if self._process:
                self._process.wait()
            self._process = None
            self._destroy_tracks(loop)
            logger.info("FFmpeg süreci ve track'ler temizlendi.")
    
    def _create_tracks(self, loop: asyncio.AbstractEventLoop):
        """
        Video ve ses track'lerini oluşturur.
        """
        self._video_track = VideoRelayTrack()
        self._audio_track = AudioRelayTrack()
        self._tracks = [self._video_track, self._audio_track]

        def add_tracks_to_peers():
            for pc in pcs:
                # Video track'i ekle
                if self._video_track and not any(s.track and s.track.kind == "video" for s in pc.getSenders()):
                    pc.addTrack(self._video_track)
                    logger.info(f"Video track eklendi: {pc}")
                # Ses track'i ekle
                if self._audio_track and not any(s.track and s.track.kind == "audio" for s in pc.getSenders()):
                    pc.addTrack(self._audio_track)
                    logger.info(f"Ses track eklendi: {pc}")
        
        loop.call_soon_threadsafe(add_tracks_to_peers)

    def _destroy_tracks(self, loop: asyncio.AbstractEventLoop):
        """
        Tüm track'leri durdurur ve temizler.
        """
        def stop_all_tracks():
            for track in self._tracks:
                track.stop()
        
        if self._tracks:
            loop.call_soon_threadsafe(stop_all_tracks)
        
        self._tracks = []
        self._video_track = None
        self._audio_track = None

    def _demux(self, loop: asyncio.AbstractEventLoop):
        """
        PyAV kullanarak FFmpeg'den gelen Matroska akışını demux eder.
        """
        if self._process is None or self._process.stdout is None:
            logger.error("Demux yapılamıyor, FFmpeg süreci çalışmıyor veya stdout yok.")
            return

        container = None
        try:
            # PyAV container'ı aç
            container = av.open(self._process.stdout, mode='r', options={'probesize': '32', 'analyzeduration': '0'})
            
            # Stream bilgilerini logla
            for stream in container.streams:
                if stream.type == 'video':
                    logger.info(f"Video stream bulundu: {stream.codec_context.width}x{stream.codec_context.height} @ {stream.average_rate} fps")
                elif stream.type == 'audio':
                    logger.info(f"Ses stream bulundu: {stream.codec_context.sample_rate} Hz, {stream.codec_context.channels} kanal")
            
        except Exception as e:
            logger.error(f"FFmpeg stdout PyAV ile açılamadı: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return
        
        logger.info("Demux ve relay başlatılıyor.")
        frame_count = 0
        audio_frame_count = 0
        
        try:
            for packet in container.demux():
                if not self._should_run:
                    break
                    
                if packet.dts is None:
                    continue
                
                # Paket decode et
                try:
                    frames = packet.decode()
                    for frame in frames:
                        if frame is None or frame.is_corrupt:
                            logger.warning("Bozuk frame algılandı, atlanıyor.")
                            continue

                        if isinstance(frame, VideoFrame) and self._video_track:
                            frame_count += 1
                            loop.call_soon_threadsafe(self._video_track.push, frame)
                            
                        elif isinstance(frame, AudioFrame) and self._audio_track:
                            audio_frame_count += 1
                            # Ses frame'ini düzeltilmiş push metoduna gönder
                            loop.call_soon_threadsafe(self._audio_track.push, frame)
                            
                            # İlk birkaç ses frame'inin bilgilerini logla (debug için)
                            if audio_frame_count <= 5:
                                channels = "N/A"
                                if hasattr(frame.layout, 'channels'):
                                    channels = frame.layout.channels
                                elif hasattr(frame, 'channels'):
                                    channels = frame.channels
                                    
                                logger.info(f"Ses frame #{audio_frame_count}: "
                                          f"channels={channels}, "
                                          f"samples={frame.samples}, "
                                          f"sample_rate={frame.sample_rate}, "
                                          f"format={getattr(frame.format, 'name', 'N/A')}, "
                                          f"layout={getattr(frame.layout, 'name', 'N/A')}")
                                
                except av.error.EOFError:
                    logger.info("Paket decode sırasında EOF.")
                    break
                except Exception as e:
                    logger.warning(f"Paket decode hatası: {e}")
                    continue

        except av.error.EOFError:
            logger.info("FFmpeg akışı sona erdi (EOF).")
        except Exception as e:
            # Kasıtlı olarak durduruyorsak hataları loglama
            if self._should_run:
                logger.error(f"Demuxing sırasında hata: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            logger.info(f"Demuxing tamamlandı. İşlenen frame'ler: Video={frame_count}, Ses={audio_frame_count}")
            if container:
                container.close()

    def _log_stderr(self):
        """
        FFmpeg stderr çıktısını loglar.
        """
        if not self._process or not self._process.stderr:
            return
            
        critical_errors = ['error', 'connection timeout', 'broken pipe', 
                          'no such file', 'permission denied', 'connection refused']
        
        # Bu hataları normal olarak kabul et ve log spam'ini önle
        expected_errors = ['end of file', 'eof', 'broken pipe', 'connection reset']
        
        for line in iter(self._process.stderr.readline, b''):
            try:
                line_str = line.decode('utf-8', errors='replace').strip()
                
                # Kritik hataları kontrol et
                if any(err in line_str.lower() for err in critical_errors):
                    logger.error(f"[ffmpeg/stderr] KRİTİK: {line_str}")
                    if 'connection' in line_str.lower():
                        logger.error("FFmpeg bağlantı hatası algılandı - akış kaynağı mevcut olmayabilir")
                elif any(err in line_str.lower() for err in expected_errors):
                    # Beklenen hataları daha sessiz logla
                    logger.debug(f"[ffmpeg/stderr] Beklenen hata: {line_str}")
                else:
                    # Normal FFmpeg mesajlarını daha az ayrıntılı logla
                    if 'frame=' not in line_str:  # Frame ilerleme mesajlarını atla
                        logger.info(f"[ffmpeg/stderr] {line_str}")
            except Exception as e:
                logger.error(f"FFmpeg stderr okuma hatası: {e}")
                
        logger.info("FFmpeg stderr izleme tamamlandı.")


# --- Static Files Directory ---
STATIC_DIR = os.path.join(ROOT, '.')

# --- aiohttp Routes ---
async def index(request):
    """Ana sayfa - static HTML dosyasını serve et"""
    try:
        with open(os.path.join(STATIC_DIR, 'index.html'), 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(content_type="text/html", text=content)
    except FileNotFoundError:
        return web.Response(status=404, text="index.html not found")

async def offer(request):
    """WebRTC offer'ını işle ve answer döndür"""
    params = await request.json()
    offer_sdp = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = f"PeerConnection({uuid.uuid4()})"
    pcs.add(pc)

    def log_info(msg, *args):
        logger.info(f"{pc_id} {msg}", *args)

    log_info("Oluşturuldu: %s", request.remote)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        log_info("ICE bağlantı durumu: %s", pc.iceConnectionState)
        if pc.iceConnectionState in ("failed", "closed", "disconnected"):
            log_info("Peer connection kapatılıyor.")
            if pc in pcs:
                pcs.discard(pc)
            await pc.close()

    # Relay'den track'leri ekle
    tracks_added = []
    if relay and relay.video_track:
        pc.addTrack(relay.video_track)
        tracks_added.append("video")
        log_info("Video track eklendi")
        
    if relay and relay.audio_track:
        pc.addTrack(relay.audio_track)
        tracks_added.append("audio")
        log_info("Ses track eklendi")
    
    if not tracks_added:
        logger.warning(f"{pc_id} Hiçbir track eklenmedi - relay henüz hazır olmayabilir")

    # SDP müzakeresi
    await pc.setRemoteDescription(offer_sdp)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )

async def health(request):
    """
    Sistem durumunu döndüren sağlık kontrolü endpoint'i.
    """
    ffmpeg_running = relay and relay._process and relay._process.poll() is None
    active_peers = len(pcs)
    relay_thread_alive = relay and relay._thread and relay._thread.is_alive()
    
    health_data = {
        "status": "healthy" if ffmpeg_running and relay_thread_alive else "unhealthy",
        "ffmpeg_running": ffmpeg_running,
        "active_peers": active_peers,
        "relay_thread_alive": relay_thread_alive,
        "video_track_available": relay and relay.video_track is not None,
        "audio_track_available": relay and relay.audio_track is not None,
        "restart_count": relay._restart_count if relay else 0,
    }
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    
    return web.Response(
        content_type="application/json",
        text=json.dumps(health_data),
        status=status_code
    )


async def on_shutdown(app):
    """
    aiohttp uygulaması kapanırken kaynakları temizle.
    """
    # Tüm aktif peer connection'ları kapat
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    
    # Media relay'i ve FFmpeg sürecini durdur
    if relay:
        relay.stop()

# --- Web App Setup ---
async def on_startup(app):
    """
    aiohttp uygulaması başlarken kaynakları başlat.
    """
    global relay
    relay = MediaRelay()
    loop = asyncio.get_running_loop()
    relay.start(loop)

# Static dosyalar için handler
async def static_file(request):
    """Static dosyaları serve et"""
    filename = request.match_info['filename']
    
    # Güvenlik kontrolü - sadece belirli dosyalara izin ver
    allowed_files = {
        'styles.css': 'text/css',
        'app.js': 'application/javascript',
        'index.html': 'text/html'
    }
    
    if filename not in allowed_files:
        return web.Response(status=404, text="File not found")
    
    file_path = os.path.join(STATIC_DIR, filename)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(
            content_type=allowed_files[filename],
            text=content
        )
    except FileNotFoundError:
        return web.Response(status=404, text=f"{filename} not found")

# Route'ları ekle
web_app.router.add_get("/", index)
web_app.router.add_post("/offer", offer)
web_app.router.add_get("/health", health)
web_app.router.add_get("/{filename}", static_file)

# Startup ve shutdown handler'ları ekle
web_app.on_startup.append(on_startup)
web_app.on_shutdown.append(on_shutdown)


if __name__ == "__main__":
    logger.info(f"Sunucu başlatılıyor: http://{HOST}:{PORT}")
    web.run_app(
        web_app,
        host=HOST,
        port=PORT,
    )