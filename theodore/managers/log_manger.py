from theodore.core.utils import send_message
from pathlib import Path
import concurrent.futures
import re, os

# --------------------------
# Pseudo-code
# --------------------------

class LogManager:

    def get_file_ranges(self, filepath, num_of_chunks):
        """
        Calculates safe start and end bytes file sizes

        Args:
            filepath: File to calculate safe chunk ranges
            num_of_chunks: no of chunks to divide file into

        returns: A list of tuples with start and end bytes
        """
        if not isinstance(filepath, Path):
            return []
        
        # Step 1. get file size in bytes
        filesize = Path(filepath).stat().st_size
        
        base_chunk_size = filesize // num_of_chunks

        current_start = 0
        chunk_ranges = []
        with open(filepath, 'rb') as f:
            for i in range(num_of_chunks):
                # Edge-case 1: return up-to file-end at the second to last chunk
                if i == num_of_chunks - 1:
                    chunk_ranges.append((current_start, filesize))
                    break
                
                # Step 2. get end of chunk size
                raw_end = current_start + base_chunk_size

                # Step 3. set position of pointer at raw_end
                f.seek(raw_end)

                # adjust pointer to a safe new line
                # Note: readline() reads until a newline '\n'
                tail_end = f.readline(1024 * 8) # read up to 8kb find the next line

                # Edge-case 2. EOF 
                # if raw_end is greater than or equal to the filesize
                if raw_end >= filesize:
                    chunk_ranges.append((current_start, filesize))
                    break

                # Edge-case 3. If no newline found even after 8kb read. We've reached EOF
                if not tail_end:
                    chunk_ranges.append((current_start, filesize))
                    break
                
                # get a safe-current position of pointer
                safe_end = f.tell()

                # append position to list
                chunk_ranges.append((current_start, safe_end))

                # update current start
                current_start = safe_end 
        return chunk_ranges

    def search_logs(self, start_byte, end_byte, pattern, filepath):
        """
        Calculates and reads log files in chunks and parses for matches with pattern

        Args:
            filepath: file to read
            start_byte: Where to start from
            end_byte: Where to end read
            pattern: Pattern to search

        Returns: A dictionary list of of line matches and timestamps
        """
        matches = []
        if not Path(filepath).exists():
            return []

        # Encode pattern for file search efficiency
        compiled_pattern = re.compile(pattern.encode('utf-8'))

        with open(filepath, 'rb') as f:
            # Set position at start byte-start
            f.seek(start_byte)

            # Amount of bytes to read
            bytes_to_read = end_byte - start_byte

            # Read file within range
            data_bytes = f.read(bytes_to_read)

            # Decode bytes to text mode
            data_text = data_bytes.decode(encoding='utf-8', errors='ignore')

            for line in data_text.splitlines():
                if re.search(compiled_pattern, line.encode('utf-8')):
                    timestamp = line[:]
                    matches.append({
                        "timestamp": timestamp,
                        "line": line.strip()
                    })

        return matches

    def parallel_file_search(self, pattern, filepath):
        num_threads = os.cpu_count() * 2

        chunk_args = self.get_file_ranges(filepath, num_threads)
        all_matches = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_chunks = [
                executor.submit(
                    self.search_logs, 
                    start, 
                    end, 
                    pattern, 
                    filepath
                ) 
                for start, end in chunk_args
            ]

            for future in concurrent.futures.as_completed(future_chunks):
                try:
                    match = future.result()
                    all_matches.extend(match)
                except Exception as e:
                    return send_message(False, message=f'Chunk processing generated an exception: {str(e)}')

        all_matches.sort(key=lambda x: x['timestamp'])
        return send_message(True, data=all_matches)