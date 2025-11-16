import threading
import requests
import os
import time

class DownloadManager:
    def __init__(self, url: str, output_path: str, num_threads: int = 4, chunk_size: int = 8192):
        # --- Input parameters ---
        self.url = url.strip()                          
        self.output_path = output_path                  
        self.num_threads = max(1, int(num_threads))     
        self.chunk_size = max(1024, int(chunk_size))    

        # --- File / server info ---
        self.total_size = 0                            
        self.accept_ranges = False                     
        self.file_name = url.split("/")[-1]     

        # --- Thread management ---
        self.threads = []                              
        self.thread_status = {}                        

        # --- Control events (thread-safe flags) ---
        self.stop_event = threading.Event()            
        self.pause_event = threading.Event()           

        # --- Download statistics ---
        self.downloaded_total = 0                      
        self.percent_complete = 0.0                    
        self.current_speed = 0.0                        

        # --- Optional callback handlers ---
        self.progress_callback = None                   
        self.status_callback = None                     

        # --- Execution flags ---
        self.is_running = False                     
        self.is_finished = False                        

        # --- Reserved attributes for future extensions ---
        self.metadata = {}                              
        self.temp_path = None                
        
    def get_file_info(self) -> dict:

        try:
            # --- Attempt to retrieve headers only ---
            response = requests.head(self.url, allow_redirects=True, timeout=15)

            # --- Fallback: Some servers return incomplete headers for HEAD ---
            if not response.ok or "Content-Length" not in response.headers:
                response = requests.get(self.url, stream=True, timeout=15)
                response.raise_for_status()

            # --- Extract key metadata ---
            total_size_str = response.headers.get("Content-Length")
            if total_size_str is None:
                raise Exception(f"Server did not provide Content-Length for URL: {self.url}")

            total_size = int(total_size_str)
            accept_ranges = response.headers.get("Accept-Ranges", "").lower() == "bytes"

            # --- Store metadata internally ---
            self.total_size = total_size
            self.accept_ranges = accept_ranges

            # --- Return summary dictionary ---
            return {
                "url": self.url,
                "total_size": total_size,
                "accept_ranges": accept_ranges,
                "status_code": response.status_code
            }

        except Exception as e:
            raise Exception(f"Failed to fetch file metadata: {e}")        
       
    def split_ranges(self) -> list:
        if not self.accept_ranges or self.num_threads == 1:
            # Server doesn't support Range requests or single-thread mode
            return [(0, self.total_size - 1)]

        ranges = []
        chunk_size = self.total_size // self.num_threads  # approximate division

        for i in range(self.num_threads):
            start = i * chunk_size
            # last part must include all remaining bytes to avoid truncation
            end = (start + chunk_size - 1) if i < self.num_threads - 1 else self.total_size - 1
            ranges.append((start, end))

        return ranges 
          
    def _download_chunk(self, thread_index: int, start: int, end: int, progress_callback=None) -> None:
        headers = {"Range": f"bytes={start}-{end}"}
        chunk_filename = f"{self.file_name}.part{thread_index}"

        try:
            with requests.get(self.url, headers=headers, stream=True, timeout=20) as response:
                # 206 expected for partial content
                if response.status_code not in (200, 206):
                    raise Exception(f"Unexpected status code {response.status_code} for thread {thread_index}")

                with open(chunk_filename, "wb") as f:
                    for block in response.iter_content(chunk_size=self.chunk_size):

                        # --- Stop Event ---
                        if self.stop_event.is_set():
                            return

                        # --- Pause Event ---
                        while self.pause_event.is_set():
                            self.pause_event.wait(0.1)

                        # --- Write Data Chunk ---
                        if block:
                            f.write(block)
                            self.downloaded_total += len(block)

                            # --- Update Progress (safely bounded 0–100) ---
                            if self.total_size > 0 and progress_callback:
                                percent = min((self.downloaded_total / self.total_size) * 100.0, 100.0)
                                progress_callback(percent)

        except Exception as e:
            self.thread_status[thread_index] = False
            raise Exception(f"Thread {thread_index} failed: {e}")

        # Thread finished successfully
        self.thread_status[thread_index] = True
    
    def _combine_chunks(self):
        try:
            with open(self.file_name, "wb") as final_file:
                for i in range(self.num_threads):
                    part_file = f"{self.file_name}.part{i}"
                    with open(part_file, "rb") as pf:
                        while True:
                            data = pf.read(self.chunk_size)
                            if not data:
                                break
                            final_file.write(data)
                    os.remove(part_file)
            if self.status_callback:
                self.status_callback("completed")
            else:
                print(f"[+] File merge completed successfully → {self.file_name}")
        except Exception as e:
            if self.status_callback:
                self.status_callback("error", str(e))
            else:
                print(f"[!] Error combining chunks: {e}")
            raise
    
    def start(self) -> None:
        print(self.file_name)
        if not self.file_name or not isinstance(self.file_name, str):
            raise ValueError(f"Output filename invalid: {self.file_name}")
        # --- Step 1: Prepare environment ---
        try:
            self.stop_event.clear()
            self.pause_event.clear()
            self.downloaded_total = 0
            self.thread_status = [False] * self.num_threads

            # Inform GUI/CLI that download is starting
            if self.status_callback:
                self.status_callback("starting")

            # Get file info from server (size, range)
            self.get_file_info()

            if not self.accept_ranges:
                raise Exception("Server does not support Range requests.")

            # --- Step 2: Split file into ranges ---
            ranges = self.split_ranges()

            # --- Step 3: Create and start worker threads ---
            threads = []
            for i, (start, end) in enumerate(ranges):
                t = threading.Thread(target=self._download_chunk, args=(i, start, end))
                t.daemon = True
                threads.append(t)
                t.start()

            if self.status_callback:
                self.status_callback("downloading")

            # --- Step 4: Monitor threads & handle pause/stop ---
            while any(t.is_alive() for t in threads):
                if self.stop_event.is_set():
                    # Stop trigger → terminate all threads
                    for t in threads:
                        if t.is_alive():
                            t.join(timeout=0.2)
                    if self.status_callback:
                        self.status_callback("stopped")
                    return

                if self.pause_event.is_set():
                    if self.status_callback:
                        self.status_callback("paused")
                    # Wait until resumed
                    while self.pause_event.is_set() and not self.stop_event.is_set():
                        time.sleep(0.3)
                    if self.status_callback:
                        self.status_callback("resumed")

                # Periodic progress callback
                if self.progress_callback and self.total_size > 0:
                    percent = min(100.0, (self.downloaded_total / self.total_size) * 100)
                    self.progress_callback(round(percent, 2))

                time.sleep(0.2)

            # --- Step 5: Join all threads to ensure completion ---
            for t in threads:
                t.join()

            # Check that all threads completed successfully
            if not all(self.thread_status):
                raise Exception("One or more threads failed to download properly.")

            # --- Step 6: Combine chunks into final file ---
            self._combine_chunks()

            if self.status_callback:
                self.status_callback("completed")
            else:
                print(f"[+] Download completed successfully: {self.filename}")

        except Exception as e:
            # --- Global exception handling ---
            if self.status_callback:
                self.status_callback("error", str(e))
            else:
                print(f"[!] Download error: {e}")
            raise
    
    
    
