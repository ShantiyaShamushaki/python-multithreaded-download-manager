# Multi-threaded Download Manager (Python)

**Overview**
This project is a multi-threaded file download manager implemented in Python. It is built with a clean, modular architecture to ensure performance, scalability, and maintainability. The system divides a file into multiple byte ranges (chunks) and downloads them concurrently using independent threads. Once all threads complete, the file segments are merged into a single output file.

The design is inspired by download managers such as *IDM*, focusing on thread synchronization, safe pause/resume mechanisms, and network resilience.

---

## Key Features
- Multi-Threaded Core: Parallel file downloading through independent threads (using Python’s threading module).
- HTTP Range Requests: Supports Range headers for partial file retrieval (HTTP 206).
- Pause / Resume / Stop: Fully controllable download flow using threading.Event.
- Real-Time Progress Updates: Through callback functions for CLI or GUI visualization.
- Error Handling: Manages SSL, timeout, and DNS issues with retry-safe design.
- Chunk Combining: After download completion, chunks are automatically merged into a single file.
- GUI Integration: A PyQt6 interface allows real-time visualization, including per-thread progress bars and configurable thread count.

---

## Architecture
1. Core (core.py)
The core of the system is encapsulated in the DownloadManager class.

Responsibilities

- Initialize download parameters (url, filename, num_threads, chunk_size).
- Fetch file info via a HEAD request (get_file_info()).
- Split total size into byte ranges using split_ranges().
- Spawn worker threads, each executing _download_chunk().
- Merge .partN files in _combine_chunks().
- Each thread reads a specific byte range defined by the HTTP Range header:

```
Range: bytes=start-end
```

Threads report intermediate progress through progress_callback and can be individually paused/resumed using event flags.

2. Thread Synchronization
threading.Event is used for thread coordination:

- pause_event: Pauses all threads by blocking their read loops.
- stop_event: Terminates all threads gracefully without corrupting partial data.
Thread safety is preserved using threading.Lock when updating shared attributes (e.g., self.downloaded).

3. GUI Layer (PyQt6)
The GUI layer (gui_pyqt6.py) provides an interactive interface:

- Set file URL and thread count manually.
- Start, pause, resume, and stop downloads.
- Display global progress and individual per-thread progress bars, similar to IDM.
- Uses QThread and pyqtSignal for async communication between the core and the UI without freezing.
The GUI and core communicate via:


```python

signal_progress.emit(percent, downloaded_mb, speed_mb_s)
signal_thread_progress.emit(thread_id, percent)
```

Run GUI Version

```bash
python main.py
```
## Future Improvements
- Add persistent resume between sessions using metadata storage (JSON/SQLite).
- Integrate bandwidth throttling control per thread.
- Implement retry cycle for failed threads.
- Extend GUI with multiple download queue management.


## Screen Shot
![screen shot](.assets/screenshot.png)

© 2025 Shantiya — Advanced Python Download Manager with Multi-Threaded Architecture and PyQt6 Visualization.


