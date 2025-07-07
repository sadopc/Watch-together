# 🎬 Birlikte Dizi İzleme Sunucusu

# 🎬 Watch-Together Streaming Server

---

## ✨ Özellikler / ✨ Features

### TR

**🖥️ Sunucu Özellikleri:**
* **Düşük Gecikme**: WebRTC teknolojisi sayesinde minimal gecikme
* **Tarayıcı Uyumluluğu**: Herhangi bir eklenti gerektirmeden modern tarayıcılarda çalışır
* **Otomatik Yeniden Başlatma**: RTMP akışı kesildiğinde otomatik olarak yeniden başlatır
* **Donanım Hızlandırma**: Opsiyonel GPU hızlandırma desteği
* **Çoklu İzleyici**: Birden fazla kişi aynı anda izleyebilir

**🎨 Web Arayüzü Özellikleri:**
* **Modern Tasarım**: Profesyonel karanlık tema ve Inter fontu
* **Responsive Design**: Mobil ve masaüstü uyumlu responsive tasarım
* **Gerçek Zamanlı İstatistikler**: FPS, bitrate, çözünürlük ve gecikme bilgileri
* **Gelişmiş Kontroller**: Oynatma, ses, tam ekran ve kalite kontrolleri
* **Toast Bildirimler**: Kullanıcı dostu bildirim sistemi
* **Otomatik Kalite**: Akıllı kalite ayarlama sistemi
* **Klavye Kısayolları**: Spacebar (oynat/durdur), M (sessiz), F (tam ekran)
* **Görsel Geri Bildirim**: Bağlantı durumu ve server health kontrolü

### EN

**🖥️ Server Features:**
* **Low Latency**: Minimal delay thanks to WebRTC
* **Browser Compatibility**: Works in modern browsers with no plugins
* **Auto-Restart**: Automatically restarts when the RTMP stream drops
* **Hardware Acceleration**: Optional GPU acceleration support
* **Multi-Viewer**: Multiple people can watch simultaneously

**🎨 Web Interface Features:**
* **Modern Design**: Professional dark theme with Inter font
* **Responsive Design**: Mobile and desktop friendly responsive layout
* **Real-time Statistics**: FPS, bitrate, resolution and latency monitoring
* **Advanced Controls**: Play, audio, fullscreen and quality controls
* **Toast Notifications**: User-friendly notification system
* **Auto Quality**: Smart quality adjustment system
* **Keyboard Shortcuts**: Spacebar (play/pause), M (mute), F (fullscreen)
* **Visual Feedback**: Connection status and server health monitoring

---

## 🛠️ Gereksinimler / 🛠️ Requirements

### TR

#### Sistem Gereksinimleri

* Python 3.12+
* FFmpeg (sistem üzerinde kurulu olmalı)
* OBS Studio (RTMP stream göndermek için)
* Modern tarayıcı (Chrome 80+, Firefox 75+, Safari 14+, Edge 80+)

#### Python Bağımlılıkları

* `requirements.txt` dosyasında listelenen paketler

#### Frontend Teknolojileri

* **HTML5**: Semantic markup ve modern video API'ları
* **CSS3**: Modern styling, CSS Grid, Flexbox ve CSS Custom Properties
* **JavaScript ES6+**: WebRTC API, Modern DOM manipülasyonu
* **Font Awesome**: İkonlar için
* **Google Fonts**: Inter font ailesi

### EN

#### System Requirements

* Python 3.12+
* FFmpeg (installed on the system)
* OBS Studio (for sending RTMP stream)
* Modern browser (Chrome 80+, Firefox 75+, Safari 14+, Edge 80+)

#### Python Dependencies

* All packages listed in `requirements.txt`

#### Frontend Technologies

* **HTML5**: Semantic markup and modern video APIs
* **CSS3**: Modern styling, CSS Grid, Flexbox and CSS Custom Properties
* **JavaScript ES6+**: WebRTC API, Modern DOM manipulation
* **Font Awesome**: For icons
* **Google Fonts**: Inter font family

---

## 📥 Kurulum / 📥 Installation

### TR

1. Projeyi klonlayın ve dizine girin:

   ```bash
   git clone <repository-url>
   cd yayin
   ```
2. Sanal ortam oluşturun (önerilen):

   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # veya
   venv\Scripts\activate     # Windows
   ```
3. Bağımlılıkları kurun:

   ```bash
   pip install -r requirements.txt
   ```
4. FFmpeg kurulumunu yapın:

   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg

   # macOS (Homebrew)
   brew install ffmpeg

   # Windows
   # FFmpeg'i resmi sitesinden indirip PATH'e ekleyin
   ```

### EN

1. Clone and enter the project directory:

   ```bash
   git clone <repository-url>
   cd yayin
   ```
2. (Recommended) Create a virtual environment:

   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate     # Windows
   ```
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Install FFmpeg:

   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install ffmpeg

   # macOS (Homebrew)
   brew install ffmpeg

   # Windows
   # Download FFmpeg from official site and add to PATH
   ```

---

## 🚀 Kullanım / 🚀 Usage

### TR

1. **Sunucuyu başlatın:**

   ```bash
   python stream_server.py
   ```

   Sunucu varsayılan olarak `http://localhost:8080` adresinde çalışır.

2. **OBS ayarları:**

   * Ayarlar → Yayın
   * Servis: Custom
   * Sunucu: `rtmp://localhost:1935/live`
   * Yayın Anahtarı: `stream`

3. **Yayını başlatın:**

   * OBS'de **Yayını Başlat**
   * Tarayıcıda `http://localhost:8080` adresini açın

4. **Web Arayüzü Kullanımı:**

   * **Otomatik Oynatma**: Video yayın başladığında otomatik olarak oynatılır
   * **Kontroller**: Alt taraftaki kontrol çubuğunu kullanarak oynatma/durdurma, ses ve tam ekran
   * **İstatistikler**: Sağ taraftaki panelde gerçek zamanlı yayın bilgilerini görüntüleyin
   * **Kalite Ayarları**: Otomatik kalite veya manuel kalite seçimi
   * **Klavye Kısayolları**: 
     - `Spacebar`: Oynat/Durdur
     - `M`: Sessiz/Sesli
     - `F`: Tam ekran
     - `Esc`: Tam ekrandan çık

5. **Tailscale ile paylaşım:**

   * `tailscale ip` komutuyla IP'nizi alın
   * Kız arkadaşınızla `http://[tailscale-ip]:8080` paylaşın

### EN

1. **Start the server:**

   ```bash
   python stream_server.py
   ```

   By default it listens on `http://localhost:8080`.

2. **OBS settings:**

   * Settings → Stream
   * Service: Custom
   * Server: `rtmp://localhost:1935/live`
   * Stream Key: `stream`

3. **Go Live:**

   * Click **Start Streaming** in OBS
   * Open `http://localhost:8080` in your browser

4. **Web Interface Usage:**

   * **Auto-play**: Video automatically starts when stream begins
   * **Controls**: Use bottom control bar for play/pause, audio and fullscreen
   * **Statistics**: View real-time stream information in the right panel
   * **Quality Settings**: Auto quality or manual quality selection
   * **Keyboard Shortcuts**:
     - `Spacebar`: Play/Pause
     - `M`: Mute/Unmute
     - `F`: Fullscreen
     - `Esc`: Exit fullscreen

5. **Share via Tailscale:**

   * Run `tailscale ip` to get your IP
   * Send `http://[tailscale-ip]:8080` to your partner

---

## ⚙️ Konfigürasyon / ⚙️ Configuration

### TR

```bash
export HOST="0.0.0.0"
export PORT="8080"
export RTMP_URL="rtmp://localhost:1935/live/stream"
export USE_HARDWARE_ACCELERATION="true"
```

### EN

```bash
export HOST="0.0.0.0"
export PORT="8080"
export RTMP_URL="rtmp://localhost:1935/live/stream"
export USE_HARDWARE_ACCELERATION="true"
```

---

## 🔧 Sorun Giderme / 🔧 Troubleshooting

### TR

**1. “FFmpeg bulunamadı”**

```bash
ffmpeg -version
which ffmpeg
```

**2. RTMP bağlantı problemi**

* OBS’de URL’yi kontrol edin
* Güvenlik duvarı/port 1935
  **3. Ses sorunu**
* OBS ses seviyeleri
* Tarayıcı izinleri
  **4. Yüksek CPU**
* GPU hızlandırma
* Çözünürlüğü düşürün
* Bitrate optimizasyonu

### EN

**1. “FFmpeg not found”**

```bash
ffmpeg -version
which ffmpeg
```

**2. RTMP Connection Issues**

* Verify URL in OBS
* Firewall / port 1935
  **3. Audio Issues**
* Check OBS audio levels
* Browser permissions
  **4. High CPU Usage**
* Enable GPU accel
* Lower resolution
* Optimize bitrate

---

## 💡 İpuçları / 💡 Tips

### TR

* OBS’de “Tune” → “zerolatency”
* İnternet hızınıza göre bitrate ayarlayın
* Mobilde düşük çözünürlük
* Harici erişimi kapatın

### EN

* In OBS set “Tune” to “zerolatency”
* Adjust bitrate to your internet speed
* Use low resolution on mobile
* Disable external access except Tailscale

---

## 📱 Tarayıcı Uyumluluğu / 📱 Browser Support

### TR

* Chrome/Chromium 80+
* Firefox 75+
* Safari 14+
* Edge 80+
* Mobil tarayıcılar

### EN

* Chrome/Chromium 80+
* Firefox 75+
* Safari 14+
* Edge 80+
* Mobile browsers

---

## 🤝 Katkıda Bulunma / 🤝 Contributing

### TR

Öneri ve iyileştirmelere açığız!

### EN

Contributions and suggestions are welcome!

---

## 📄 Lisans / 📄 License

### TR

MIT Lisansı altında.

### EN

Licensed under MIT.

---

**Not / Note**: Bu proje, sevgili kız arkadaşımla birlikte dizi izlemek için geliştirildi. Umarım sizin de güzel anılar yaratır! 💕
**Note**: Built to watch shows together with my beloved. Hope it creates great memories for you, too! 💕
# Watch-together
