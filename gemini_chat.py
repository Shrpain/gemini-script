#!/usr/bin/env python3
import os
import sys
import json
import requests
import re
import datetime
import time
import urllib.parse  # Thêm thư viện urllib.parse để mã hóa text trong URL
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("Thư viện gTTS chưa được cài đặt. Cài đặt bằng lệnh: pip install gtts")

def extract_api_key(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            # Look for API key pattern in the file
            match = re.search(r'API:([\w-]+)', content)
            if match:
                return match.group(1)
            else:
                print("API key không tìm thấy trong tệp cấu hình.")
                sys.exit(1)
    except FileNotFoundError:
        print(f"Lỗi: Tệp cấu hình {file_path} không tìm thấy.")
        sys.exit(1)

def clean_response(response_text):
    if not response_text:
        return ""
        
    # Lưu văn bản gốc trước khi làm sạch để kiểm tra
    original_length = len(response_text.strip())
    
    # Remove asterisks
    cleaned_text = response_text.replace('*', '')
    
    # Remove time codes like (7:30-8:00)
    cleaned_text = re.sub(r'\(\d+:\d+-\d+:\d+\)', '', cleaned_text)
    
    # Remove timestamp patterns like 7:30, 12:45, etc.
    cleaned_text = re.sub(r'\b\d+:\d+\b', '', cleaned_text)
    
    # Remove square brackets and their contents that aren't part of [title]/[tiêu đề] and [content]/[nội dung]
    # Careful not to remove the actual tags we need
    cleaned_text = re.sub(r'\[(?!(title|tiêu đề|content|nội dung))[^\]]*\]', '', cleaned_text)
    
    # Remove parentheses and their contents
    cleaned_text = re.sub(r'\(.*?\)', '', cleaned_text)
    
    # Clear extra whitespace
    cleaned_text = re.sub(r' +', ' ', cleaned_text)
    cleaned_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_text)
    
    # Remove introductory phrases like "Tuyệt vời! Đây là kịch bản..."
    cleaned_text = re.sub(r'^(Tuyệt vời|Chắc chắn|Dưới đây|Đây là kịch bản|Đây là nội dung|Dưới đây là kịch bản)[^[]*', '', cleaned_text)
    
    # Remove any references or annotations
    cleaned_text = re.sub(r'\bRef\.?:?\s.*?$', '', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'\bNotes?:?\s.*?$', '', cleaned_text, flags=re.MULTILINE)
    cleaned_text = re.sub(r'\bSources?:?\s.*?$', '', cleaned_text, flags=re.MULTILINE)
    
    # Filter out any instructions or annotations that start with special characters
    cleaned_text = re.sub(r'^[-*_>]+.*$', '', cleaned_text, flags=re.MULTILINE)
    
    # Kết quả cuối cùng
    cleaned_text = cleaned_text.strip()
    cleaned_length = len(cleaned_text)
    
    # Kiểm tra nếu làm sạch đã loại bỏ quá nhiều nội dung
    if cleaned_length < original_length * 0.1 and original_length > 100:
        print(f"Cảnh báo: Làm sạch đã loại bỏ quá nhiều nội dung (từ {original_length} xuống {cleaned_length} ký tự)")
        # Trả về văn bản gốc nếu làm sạch đã xóa quá nhiều
        if cleaned_length < 50 and original_length > 100:
            print("Sử dụng văn bản gốc thay thế vì văn bản sau khi làm sạch quá ngắn")
            return response_text.strip()
    
    return cleaned_text

def save_responses(original_response, cleaned_response, topic, save_timestamp=False):
    """Save both original and cleaned responses to a file"""
    # Create responses directory if it doesn't exist
    if not os.path.exists('responses'):
        os.makedirs('responses')
    
    # Use a fixed filename for the most recent chat 
    base_filename = "gemini_latest_response"
    
    if save_timestamp:
        # Add timestamp to filename to avoid overwriting
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"responses/{base_filename}_{timestamp}.txt"
    else:
        filename = f"responses/{base_filename}.txt"
    
    # Remove existing file if not using timestamp
    if not save_timestamp and os.path.exists(filename):
        try:
            os.remove(filename)
            print(f"Đã xóa file phản hồi cũ: {filename}")
        except Exception as e:
            print(f"Cảnh báo: Không thể xóa file phản hồi cũ: {str(e)}")
    
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write("=== CHỦ ĐỀ ===\n")
            file.write(topic)
            file.write("\n\n=== GỐC: PHẢN HỒI GEMINI NGUYÊN BẢN ===\n\n")
            file.write(original_response)
            file.write("\n\n\n=== ĐÃ LÀM SẠCH: PHẢN HỒI SAU KHI XỬ LÝ ===\n\n")
            file.write(cleaned_response)
            file.write("\n\n=== THỜI GIAN ===\n")
            file.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            # Explicitly flush and close the file
            file.flush()
        
        # Double-check file exists and has content
        if os.path.exists(filename) and os.path.getsize(filename) > 0:
            print(f"Xác nhận: File phản hồi tồn tại và có kích thước {os.path.getsize(filename)} bytes")
        else:
            print(f"Cảnh báo: File phản hồi có thể chưa được tạo đúng cách")
        
        return filename
    
    except Exception as e:
        print(f"Lỗi khi lưu phản hồi vào file: {str(e)}")
        return None

def split_text_into_chunks(text, max_length=200):
    """Chia văn bản thành các phần nhỏ, cố gắng giữ nguyên câu"""
    # Nếu văn bản ngắn hơn max_length, trả về nguyên văn
    if len(text) <= max_length:
        return [text]
    
    # Chia theo câu
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # Nếu câu đơn lẻ dài hơn max_length, chia nhỏ câu
        if len(sentence) > max_length:
            # Chia theo dấu phẩy
            comma_parts = sentence.split(', ')
            for part in comma_parts:
                if len(current_chunk) + len(part) + 2 <= max_length:  # +2 cho dấu phẩy và khoảng trắng
                    current_chunk += part + ', '
                else:
                    if current_chunk:
                        chunks.append(current_chunk.rstrip(', '))
                    current_chunk = part + ', '
            # Đảm bảo không bỏ sót phần cuối
            if current_chunk:
                chunks.append(current_chunk.rstrip(', '))
                current_chunk = ""
        elif len(current_chunk) + len(sentence) + 1 <= max_length:  # +1 cho khoảng trắng
            current_chunk += sentence + ' '
        else:
            chunks.append(current_chunk.rstrip())
            current_chunk = sentence + ' '
    
    # Thêm phần còn lại nếu có
    if current_chunk:
        chunks.append(current_chunk.rstrip())
    
    return chunks

def text_to_speech_google(text, language='vi', save_timestamp=False):
    """Convert text to speech using Google Translate TTS API (không chính thức)"""
    if not text:
        print("Nội dung văn bản trống. Không thể tạo giọng nói.")
        return None
        
    # Ensure the text has a minimum length by adding spaces if needed
    text = text.strip()
    if len(text) < 10:
        print(f"Cảnh báo: Văn bản quá ngắn ({len(text)} ký tự), thêm nội dung đệm.")
        # Add padding text in Vietnamese to meet minimum requirements
        padding = "Đây là nội dung được tạo tự động bởi Gemini. "
        text = padding + text
    
    print(f"Độ dài văn bản để chuyển thành giọng nói: {len(text)} ký tự")
    
    # Create audio directory if it doesn't exist
    try:
        audio_dir = os.path.join(os.getcwd(), "audio")
        if not os.path.exists(audio_dir):
            os.makedirs(audio_dir)
            print(f"Đã tạo thư mục audio: {audio_dir}")
        else:
            print(f"Thư mục audio đã tồn tại: {audio_dir}")
    except Exception as e:
        print(f"Lỗi khi tạo thư mục audio: {str(e)}")
        # Try to create in the current directory as fallback
        audio_dir = "."
    
    # Define output filename
    base_filename = "gemini_latest_speech"
    
    if save_timestamp:
        # Add timestamp to filename to avoid overwriting
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(audio_dir, f"{base_filename}_{timestamp}.mp3")
    else:
        output_file = os.path.join(audio_dir, f"{base_filename}.mp3")
    
    # Remove existing file if not using timestamp and it exists
    if not save_timestamp and os.path.exists(output_file):
        try:
            os.remove(output_file)
            print(f"Đã xóa file âm thanh cũ: {output_file}")
        except Exception as e:
            print(f"Cảnh báo: Không thể xóa file âm thanh cũ: {str(e)}")
    
    # Add speech breaks to make the voice more natural
    processed_text = text
    # Add pauses after sentences to make speech more natural
    processed_text = re.sub(r'([.!?]) ', r'\1... ', processed_text)
    # Add slight pauses at commas
    processed_text = processed_text.replace(', ', ', ... ')
    # Add pauses at line breaks, but not for multiple consecutive line breaks
    processed_text = re.sub(r'(?<!\n)\n(?!\n)', '... ', processed_text)
    # Remove any unnecessary multiple pauses
    processed_text = re.sub(r'\.{3,}', '...', processed_text)
    
    # Detect language (default to Vietnamese)
    detected_language = language
    if any(ord(c) > 127 for c in text):
        # Contains non-ASCII chars, likely Vietnamese
        detected_language = 'vi'
        print("Đã phát hiện văn bản tiếng Việt")
    else:
        # Likely English
        detected_language = 'en'
        print("Sử dụng giọng tiếng Anh")
    
    try:
        # Process with Google Translate TTS API
        print(f"Đang chuyển đổi văn bản thành giọng nói với Google Translate TTS (ngôn ngữ: {detected_language})...")
        
        # Make sure the output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Create a temporary directory for chunks
        temp_dir = os.path.join(audio_dir, "temp_chunks")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
        
        # Split text into manageable chunks (Google Translate TTS has ~200 char limit)
        MAX_CHARS = 200
        
        chunks = split_text_into_chunks(processed_text, MAX_CHARS)
        print(f"Đã chia văn bản thành {len(chunks)} đoạn để xử lý.")
        
        chunk_files = []
        success = False
        
        # Process each chunk with Google Translate TTS
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
                
            print(f"Đang xử lý đoạn {i+1}/{len(chunks)} ({len(chunk)} ký tự)...")
            chunk_file = os.path.join(temp_dir, f"chunk_{i+1}.mp3")
            
            try:
                # URL không chính thức của Google Translate TTS
                url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl={detected_language}&q={urllib.parse.quote(chunk)}"
                
                # Thêm User-Agent để tránh bị chặn
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Referer': 'https://translate.google.com/'
                }
                
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    with open(chunk_file, 'wb') as f:
                        f.write(response.content)
                    
                    if os.path.exists(chunk_file) and os.path.getsize(chunk_file) > 0:
                        chunk_files.append(chunk_file)
                        print(f"  - Đã tạo đoạn {i+1}")
                    else:
                        print(f"  - Lỗi: File đoạn {i+1} không được tạo hoặc trống")
                else:
                    print(f"  - Lỗi khi gọi API: {response.status_code}")
                
                # Thêm độ trễ để tránh bị chặn
                time.sleep(0.5)
                
            except Exception as chunk_error:
                print(f"  - Lỗi khi xử lý đoạn {i+1}: {str(chunk_error)}")
                # Continue with other chunks
        
        if not chunk_files:
            print("Không thể tạo bất kỳ phần âm thanh nào. Thử phương pháp đơn giản hơn...")
            # Fallback to standard gTTS if available
            if GTTS_AVAILABLE:
                try:
                    print("Thử sử dụng gTTS làm phương án dự phòng...")
                    tts = gTTS(text="Xin chào. Không thể tạo âm thanh với Google Translate TTS. Đây là phương án dự phòng.", 
                              lang=detected_language, slow=False)
                    tts.save(output_file)
                    print(f"Đã tạo file âm thanh đơn giản: {output_file}")
                    success = True
                except Exception as simple_e:
                    print(f"Không thể tạo được file âm thanh: {str(simple_e)}")
                    return None
            else:
                print("Không thể tạo file âm thanh và gTTS không khả dụng.")
                return None
        else:
            # Combine all chunks into a single file
            print(f"Đang kết hợp {len(chunk_files)} đoạn thành file âm thanh hoàn chỉnh...")
            
            try:
                # Simple file concatenation
                with open(output_file, 'wb') as outfile:
                    for chunk_file in chunk_files:
                        if os.path.exists(chunk_file):
                            with open(chunk_file, 'rb') as infile:
                                outfile.write(infile.read())
                
                print(f"Đã tạo file âm thanh kết hợp: {output_file}")
                success = True
            except Exception as combine_error:
                print(f"Lỗi khi kết hợp các file: {str(combine_error)}")
                # If combining fails, try to copy at least the first chunk
                if chunk_files and os.path.exists(chunk_files[0]):
                    try:
                        import shutil
                        shutil.copy2(chunk_files[0], output_file)
                        print(f"Đã sao chép đoạn đầu tiên làm file âm thanh: {output_file}")
                        success = True
                    except Exception as copy_error:
                        print(f"Lỗi khi sao chép file: {str(copy_error)}")
                        return None
        
        # Clean up temporary files after processing
        try:
            if os.path.exists(temp_dir):
                for temp_file in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, temp_file))
                    except:
                        pass
                try:
                    os.rmdir(temp_dir)
                    print("Đã dọn dẹp các file tạm thời")
                except:
                    pass
        except:
            pass
        
        # Check if file was created successfully
        if success and os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            size = os.path.getsize(output_file)
            print(f"Xác nhận: File âm thanh tồn tại và có kích thước {size} bytes")
            return output_file
        else:
            print("Lỗi: File âm thanh không được tạo hoặc có kích thước bằng 0")
            return None
            
    except Exception as e:
        print(f"Lỗi khi tạo file âm thanh: {str(e)}")
        return None

def extract_content_section(cleaned_text):
    """Extract only the content section from the cleaned text"""
    if not cleaned_text:
        return ""
        
    # First try to find a properly formatted content section with brackets
    content_match = re.search(r'\[(content|nội dung)\](.*?)($|\[)', cleaned_text, re.DOTALL)
    if content_match:
        content = content_match.group(2).strip()
        # Remove introductory phrases from content section too
        content = re.sub(r'^(Tuyệt vời|Chắc chắn|Dưới đây|Đây là|Đây là nội dung)[^.]*\.', '', content)
        if content:
            return content
    
    # Fall back to looking for text that might be content without brackets
    # Try to find the title first
    title_match = re.search(r'\[(title|tiêu đề)\](.*?)($|\[)', cleaned_text, re.DOTALL)
    if title_match:
        # If we found a title, consider everything after it as content
        title_end = title_match.end()
        if title_end < len(cleaned_text):
            potential_content = cleaned_text[title_end:].strip()
            if potential_content:
                print("Đã tìm thấy tiêu đề, sử dụng nội dung phía sau tiêu đề làm nội dung chính.")
                return potential_content
    
    # Try to find clearly separated content even without proper tags
    # Look for common patterns like a title followed by content with a line break
    parts = cleaned_text.split('\n\n')
    if len(parts) >= 2:
        # First part might be title, use the rest as content
        potential_content = '\n\n'.join(parts[1:]).strip()
        if potential_content:
            print("Đã tìm thấy nội dung có cấu trúc rõ ràng ngay cả khi không có thẻ.")
            return potential_content
    
    # If we can't find proper formatting, return the entire text as content
    print("Không tìm thấy cấu trúc [nội dung] rõ ràng, sử dụng toàn bộ văn bản.")
    return cleaned_text  # Return the whole text if no content section found

def filter_speech_content(text):
    """Lọc các thành phần không cần thiết trong kịch bản trước khi chuyển đổi thành giọng nói"""
    if not text:
        return ""
    
    # Lưu văn bản gốc
    original_text = text
    
    # 1. Lọc bỏ các phần intro giới thiệu kịch bản
    intro_patterns = [
        r'^.*?(đây là kịch bản|kịch bản|bài viết).*?video.*?youtube.*?\.',
        r'^(Tuyệt vời|Chắc chắn|Được rồi|Dưới đây|Sau đây|Xin chào).*?(kịch bản|bài viết|nội dung).*?\.',
        r'^.*?kịch bản.*?(về chủ đề|với chủ đề|về).*?\.',
        r'^.*?đây là.*?(kịch bản|nội dung|bài viết).*?\.',
        # Thêm mẫu cụ thể để bắt dòng "Tuyệt vời! Đây là kịch bản chi tiết..."
        r'^Tuyệt vời\! Đây là kịch bản chi tiết.*?\.',
        r'^Tuyệt vời\! Đây là kịch bản.*?20 phút.*?\.',
        r'^Tuyệt vời\! Đây là kịch bản.*?chủ đề.*?\.',
        r'^Tuyệt vời\!.*?kịch bản.*?\.'
    ]
    
    # Tìm và loại bỏ mẫu intro đầu tiên tìm thấy
    filtered_text = text
    for pattern in intro_patterns:
        match = re.search(pattern, filtered_text, re.IGNORECASE)
        if match:
            intro_text = match.group(0)
            filtered_text = filtered_text.replace(intro_text, '', 1)
            print(f"Đã loại bỏ phần giới thiệu: '{intro_text[:50]}...'")
            break  # Chỉ loại bỏ mẫu đầu tiên tìm thấy
    
    # 2. Lọc các hướng dẫn diễn xuất (đặt trong ngoặc vuông, ngoặc tròn hoặc dấu *)
    acting_patterns = [
        r'\[.*?\]',  # Loại bỏ [mọi thứ trong ngoặc vuông]
        r'\(.*?\)',  # Loại bỏ (mọi thứ trong ngoặc tròn)
        r'\*.*?\*',  # Loại bỏ *mọi thứ giữa dấu sao*
    ]
    
    for pattern in acting_patterns:
        filtered_text = re.sub(pattern, '', filtered_text)
    
    # 3. Lọc bỏ định dạng markdown
    markdown_patterns = [
        r'\*\*',  # Loại bỏ ** (bold)
        r'\_\_',  # Loại bỏ __ (bold)
        r'\*',    # Loại bỏ * (italic)
        r'\_',    # Loại bỏ _ (italic)
        r'\~\~',  # Loại bỏ ~~ (strikethrough)
        r'\`',    # Loại bỏ ` (code)
    ]
    
    for pattern in markdown_patterns:
        filtered_text = filtered_text.replace(pattern, '')
    
    # 4. Lọc các lời kêu gọi hành động (CTA) thường có ở cuối
    cta_patterns = [
        r'Đừng quên.*?like.*?đăng ký.*?',
        r'Hãy để lại.*?bình luận.*?',
        r'Bấm đăng ký.*?',
        r'Bấm like.*?',
        r'Hãy đăng ký.*?',
        r'Theo dõi.*?kênh.*?',
        r'Cảm ơn.*?đã xem.*?',
    ]
    
    for pattern in cta_patterns:
        filtered_text = re.sub(pattern, '', filtered_text, flags=re.IGNORECASE)
    
    # 5. Loại bỏ các cụm từ thừa lặp lại
    redundant_phrases = [
        r'video đăng youtube',
        r'video youtube',
        r'kịch bản video',
        r'trong video này',
    ]
    
    for phrase in redundant_phrases:
        filtered_text = re.sub(phrase, '', filtered_text, flags=re.IGNORECASE)
    
    # 6. Dọn dẹp khoảng trắng thừa và các vấn đề định dạng
    filtered_text = re.sub(r'\n{3,}', '\n\n', filtered_text)  # Giảm nhiều dòng trống thành 2
    filtered_text = re.sub(r' {2,}', ' ', filtered_text)      # Giảm nhiều khoảng trắng thành 1
    filtered_text = filtered_text.strip()                     # Xóa khoảng trắng ở đầu và cuối
    
    # Kiểm tra nếu quá trình lọc đã loại bỏ quá nhiều nội dung
    if len(filtered_text) < len(original_text) * 0.7:
        print(f"Cảnh báo: Quá trình lọc đã giảm đáng kể nội dung (từ {len(original_text)} xuống {len(filtered_text)} ký tự)")
    
    return filtered_text

def remove_special_characters(text):
    """Loại bỏ hoặc thay thế các ký tự đặc biệt để giọng nói không đọc"""
    if not text:
        return ""
    
    # Lưu văn bản gốc
    original_text = text
    
    # 1. Thay thế các ký tự đặc biệt bằng khoảng trắng hoặc xóa
    replacements = {
        # Các ký tự đặc biệt thường gây vấn đề khi đọc
        '[': ' ',
        ']': ' ',
        '{': ' ',
        '}': ' ',
        '(': ' ',
        ')': ' ',
        '|': ' ',
        '/': ' ',
        '\\': ' ',
        '#': ' ',
        '@': ' ',
        '&': ' và ',
        '+': ' cộng ',
        '=': ' bằng ',
        '*': ' ',
        '_': ' ',
        '~': ' ',
        '<': ' ',
        '>': ' ',
        '^': ' ',
        '`': ' ',
        '•': ' ',
        '■': ' ',
        '●': ' ',
        '★': ' ',
        '☆': ' ',
        '♦': ' ',
        '♣': ' ',
        '♠': ' ',
        '♥': ' ',
        '→': ' ',
        '←': ' ',
        '↑': ' ',
        '↓': ' ',
    }
    
    # Thực hiện thay thế
    processed_text = text
    for char, replacement in replacements.items():
        processed_text = processed_text.replace(char, replacement)
    
    # 2. Xử lý các biểu tượng cảm xúc và emoji
    # Sử dụng regex để loại bỏ emoji
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F700-\U0001F77F"  # alchemical symbols
                               u"\U0001F780-\U0001F7FF"  # Geometric Shapes
                               u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
                               u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
                               u"\U0001FA00-\U0001FA6F"  # Chess Symbols
                               u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
                               u"\U00002702-\U000027B0"  # Dingbats
                               u"\U000024C2-\U0001F251" 
                               "]+", flags=re.UNICODE)
    processed_text = emoji_pattern.sub(r'', processed_text)
    
    # 3. Xử lý các ký hiệu toán học
    math_replacements = {
        '÷': ' chia cho ',
        '×': ' nhân ',
        '≤': ' nhỏ hơn hoặc bằng ',
        '≥': ' lớn hơn hoặc bằng ',
        '≠': ' khác ',
        '≈': ' xấp xỉ ',
        '∞': ' vô cùng ',
        '∑': ' tổng ',
        '∏': ' tích ',
        '√': ' căn bậc hai ',
        '∫': ' tích phân ',
        '∂': ' đạo hàm riêng ',
        '∇': ' nabla ',
        '∆': ' delta ',
        '∈': ' thuộc ',
        '∉': ' không thuộc ',
        '∩': ' giao ',
        '∪': ' hợp ',
        '⊂': ' tập con ',
        '⊃': ' tập cha ',
        '⊆': ' tập con hoặc bằng ',
        '⊇': ' tập cha hoặc bằng ',
    }
    
    for char, replacement in math_replacements.items():
        processed_text = processed_text.replace(char, replacement)
    
    # 4. Xử lý URL và đường dẫn web
    # Loại bỏ hoặc đơn giản hóa URL
    url_pattern = re.compile(r'https?://\S+|www\.\S+')
    processed_text = url_pattern.sub(' liên kết website ', processed_text)
    
    # 5. Xử lý dấu ngoặc và nội dung bên trong
    # Đã xử lý ở phần 1 bằng cách thay thế dấu ngoặc, nhưng có thể xử lý thêm nếu cần
    
    # 6. Xử lý nhiều dấu chấm câu lặp lại
    processed_text = re.sub(r'\.{2,}', ' ', processed_text)  # Thay thế ... bằng khoảng trắng
    processed_text = re.sub(r'\!{2,}', '!', processed_text)  # Thay thế !!! bằng !
    processed_text = re.sub(r'\?{2,}', '?', processed_text)  # Thay thế ??? bằng ?
    
    # 7. Xử lý các ký tự Unicode đặc biệt
    # Chuyển về dạng NFKD để tách Unicode đặc biệt
    import unicodedata
    processed_text = unicodedata.normalize('NFKD', processed_text)
    
    # 8. Loại bỏ các thẻ HTML và XML nếu có
    html_pattern = re.compile('<.*?>')
    processed_text = html_pattern.sub(' ', processed_text)
    
    # 9. Dọn dẹp khoảng trắng và dấu câu thừa
    processed_text = re.sub(r' +', ' ', processed_text)  # Thay thế nhiều khoảng trắng bằng 1 khoảng trắng
    processed_text = processed_text.strip()
    
    # 10. Kiểm tra xem sau khi xử lý còn lại bao nhiêu nội dung
    if len(processed_text) < len(original_text) * 0.5:
        print(f"Cảnh báo: Xử lý ký tự đặc biệt đã giảm đáng kể nội dung (từ {len(original_text)} xuống {len(processed_text)} ký tự)")
    
    return processed_text

def send_to_gemini(api_key, prompt, save_timestamp=False, use_content_only=False):
    # Format the prompt with the YouTube script template, emphasizing to only return spoken content
    formatted_prompt = f"""Tạo kịch bản chi tiết và đầy đủ cho video YouTube dài 20 phút với chủ đề: {prompt}.

Kịch bản phải thực sự dài, đầy đủ thông tin, và đủ nội dung để nói trong 20 phút. Kịch bản nên có độ dài ít nhất 2000-3000 từ.

Yêu cầu bắt buộc:
1. Sử dụng định dạng [tiêu đề] và [nội dung]
2. [nội dung] PHẢI dài và chi tiết, đủ để nói trong 20 phút
3. CHỈ bao gồm lời thoại của một người, KHÔNG có hướng dẫn quay phim, mô tả cảnh, chú thích hay ghi chú kỹ thuật
4. Nội dung PHẢI được triển khai đầy đủ, có phần giới thiệu, thân bài với nhiều điểm và ví dụ, và phần kết luận
5. Viết hoàn toàn bằng tiếng Việt, tập trung vào nội dung chất lượng cao

QUAN TRỌNG: ĐỪNG rút gọn hoặc tóm tắt. Kịch bản phải đủ dài cho video 20 phút."""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    data = {
        "contents": [{
            "parts": [{"text": formatted_prompt}]
        }],
        "generationConfig": {
            "temperature": 0.8,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 32768  # Tăng lên mức tối đa có thể để có nội dung dài hơn
        }
    }
    
    max_retries = 3  # Tăng số lần thử lại để đảm bảo nhận được nội dung đủ dài
    current_retry = 0
    
    while current_retry <= max_retries:
        try:
            print(f"Đang gửi yêu cầu đến Gemini API{' (lần thử lại)' if current_retry > 0 else ''}...")
            response = requests.post(url, headers=headers, json=data, timeout=60)  # Tăng timeout lên 60 giây
            response.raise_for_status()  # Raise exception for HTTP errors
            
            result = response.json()
            
            # Extract the response text from the result
            if 'candidates' in result and len(result['candidates']) > 0:
                if 'content' in result['candidates'][0] and 'parts' in result['candidates'][0]['content']:
                    parts = result['candidates'][0]['content']['parts']
                    if parts and 'text' in parts[0]:
                        # Store original response
                        original_response = parts[0]['text']
                        
                        # Kiểm tra độ dài nội dung - yêu cầu nội dung đủ dài cho video 20 phút
                        word_count = len(original_response.split())
                        print(f"Đã nhận phản hồi dài {len(original_response)} ký tự, khoảng {word_count} từ")
                        
                        # Kiểm tra nội dung ban đầu
                        if not original_response or len(original_response.strip()) < 10:
                            print(f"Cảnh báo: Phản hồi từ API quá ngắn hoặc trống: '{original_response}'")
                            if current_retry < max_retries:
                                print("Thử lại với prompt khác...")
                                current_retry += 1
                                continue
                        
                        # Kiểm tra nội dung có đủ dài cho video 20 phút không (ước tính khoảng 2000 từ)
                        if word_count < 1500 and current_retry < max_retries:
                            print(f"Cảnh báo: Nội dung quá ngắn cho video 20 phút ({word_count} từ). Thử lại yêu cầu nội dung dài hơn...")
                            current_retry += 1
                            # Điều chỉnh prompt để nhấn mạnh yêu cầu nội dung dài
                            formatted_prompt = f"""Tạo kịch bản rất chi tiết và dài cho video YouTube 20 phút về chủ đề: {prompt}.
                            
QUAN TRỌNG: Kịch bản phải THỰC SỰ dài, ít nhất 2500-3000 từ để đủ cho người nói trong 20 phút.

Yêu cầu:
- Sử dụng định dạng [tiêu đề] và [nội dung]
- Phải thật chi tiết, đầy đủ thông tin
- Viết hoàn toàn bằng tiếng Việt
- KHÔNG được tóm tắt hay rút gọn

Viết kịch bản đầy đủ mà người dẫn có thể đọc trong một video 20 phút."""
                            data["contents"][0]["parts"][0]["text"] = formatted_prompt
                            data["generationConfig"]["temperature"] = 0.9  # Tăng temperature để có nội dung đa dạng hơn
                            continue
                        
                        # Check if the response contains the expected sections
                        if "[tiêu đề]" not in original_response.lower() and "[nội dung]" not in original_response.lower():
                            print("Cảnh báo: Phản hồi không có cấu trúc đúng với thẻ [tiêu đề] và [nội dung]")
                            
                            if current_retry < max_retries:
                                print("Thử gửi yêu cầu lần nữa với hướng dẫn rõ ràng hơn...")
                                current_retry += 1
                                # Try with a clearer prompt
                                formatted_prompt = f"""Tạo kịch bản HOÀN CHỈNH VÀ DÀI cho video YouTube 20 phút về chủ đề: {prompt}.

PHẢI sử dụng CHÍNH XÁC định dạng sau:

[tiêu đề]
Tiêu đề của video

[nội dung]
Toàn bộ nội dung chi tiết ở đây, đủ dài cho 20 phút nói. Chỉ viết lời thoại, không thêm hướng dẫn. Viết hoàn toàn bằng tiếng Việt.

Lưu ý: Nội dung phải thực sự dài và chi tiết, ít nhất 2500 từ."""
                                data = {
                                    "contents": [{
                                        "parts": [{"text": formatted_prompt}]
                                    }],
                                    "generationConfig": {
                                        "temperature": 0.7,
                                        "topK": 40,
                                        "topP": 0.95,
                                        "maxOutputTokens": 32768
                                    }
                                }
                                continue  # Try again with the new prompt
                        
                        # Clean the response 
                        cleaned_response = clean_response(original_response)
                        
                        # Kiểm tra nội dung sau khi làm sạch
                        if not cleaned_response or len(cleaned_response.strip()) < 10:
                            print("Cảnh báo: Nội dung sau khi làm sạch quá ngắn hoặc trống rỗng, sử dụng nội dung gốc")
                            cleaned_response = original_response
                        
                        # Debug: check if cleaned response still has the content tag
                        if "[nội dung]" not in cleaned_response.lower() and use_content_only:
                            print("Cảnh báo: Thẻ [nội dung] có thể đã bị loại bỏ trong quá trình làm sạch")
                        
                        # Save both responses to file
                        saved_file = save_responses(original_response, cleaned_response, prompt, save_timestamp)
                        print(f"Đã lưu phản hồi vào file: {saved_file}")
                        
                        # Convert to speech using Google TTS
                        print("Đang chuyển đổi phản hồi thành giọng nói bằng Google TTS...")
                        
                        # Determine which text to convert to speech
                        final_speech_text = ""
                        
                        if use_content_only:
                            # Extract only the content section
                            speech_content = extract_content_section(cleaned_response)
                            if speech_content and len(speech_content.strip()) >= 10:
                                print("Chỉ chuyển đổi phần [nội dung] thành giọng nói...")
                                final_speech_text = speech_content
                            else:
                                print("Không tìm thấy phần [nội dung] hợp lệ, chuyển đổi toàn bộ phản hồi...")
                                final_speech_text = cleaned_response
                        else:
                            # Convert the entire cleaned response
                            final_speech_text = cleaned_response
                        
                        # Lọc các thành phần không cần đọc trong kịch bản trước khi chuyển đổi thành giọng nói
                        print("Đang lọc các thành phần không cần đọc (hướng dẫn diễn xuất, định dạng, v.v.)")
                        final_speech_text = filter_speech_content(final_speech_text)
                        
                        # Loại bỏ các ký tự đặc biệt để giọng nói không đọc
                        print("Đang xử lý và loại bỏ các ký tự đặc biệt...")
                        final_speech_text = remove_special_characters(final_speech_text)
                        
                        # Kiểm tra lần cuối trước khi chuyển đổi
                        if not final_speech_text or len(final_speech_text.strip()) < 10:
                            print("Cảnh báo nghiêm trọng: Nội dung cuối cùng cho chuyển đổi âm thanh trống hoặc quá ngắn")
                            # Thêm nội dung mặc định
                            default_text = f"Xin chào. Đây là kịch bản về chủ đề {prompt}. Rất tiếc, chúng tôi không thể tạo được nội dung đầy đủ. Vui lòng thử lại."
                            final_speech_text = default_text
                        
                        print(f"Nội dung cuối cùng để chuyển đổi âm thanh: {len(final_speech_text)} ký tự")
                        audio_file = text_to_speech_google(final_speech_text, language='vi', save_timestamp=save_timestamp)
                        
                        if audio_file:
                            print(f"Đã tạo file âm thanh: {audio_file}")
                        else:
                            print("Cảnh báo: Không thể tạo file âm thanh. Xem thông báo lỗi ở trên.")
                        
                        return cleaned_response
            
            # If we reach here, there was an issue with the response format
            if current_retry < max_retries:
                print("Phản hồi không hợp lệ. Thử lại...")
                current_retry += 1
                # Simplify the prompt for retry
                formatted_prompt = f"Viết kịch bản video YouTube về: {prompt}. Bắt đầu với [tiêu đề] và sau đó là [nội dung]. Viết bằng tiếng Việt."
                data = {
                    "contents": [{
                        "parts": [{"text": formatted_prompt}]
                    }],
                    "generationConfig": {
                        "temperature": 0.5,
                        "topK": 40,
                        "topP": 0.95,
                        "maxOutputTokens": 8192
                    }
                }
            else:
                # Give up after max retries
                break
        
        except requests.exceptions.RequestException as e:
            if current_retry < max_retries:
                print(f"Lỗi kết nối: {str(e)}. Thử lại sau 3 giây...")
                time.sleep(3)
                current_retry += 1
            else:
                return f"Lỗi khi gửi yêu cầu API: {str(e)}"
        except json.JSONDecodeError:
            if current_retry < max_retries:
                print("Lỗi phân tích JSON. Thử lại...")
                current_retry += 1
            else:
                return "Lỗi phân tích phản hồi JSON từ API."
        except Exception as e:
            if current_retry < max_retries:
                print(f"Lỗi không xác định: {str(e)}. Thử lại...")
                current_retry += 1
            else:
                return f"Lỗi không xác định: {str(e)}"
    
    # Fallback nếu không nhận được phản hồi hợp lệ
    fallback_response = f"Không thể nhận được phản hồi hợp lệ từ API sau nhiều lần thử cho chủ đề: {prompt}."
    
    # Tạo file âm thanh mặc định khi không nhận được phản hồi từ API
    print("Tạo âm thanh mặc định do không nhận được phản hồi hợp lệ...")
    default_text = f"Xin chào. Đây là thông báo. Chúng tôi không thể tạo kịch bản cho chủ đề {prompt} sau nhiều lần thử. Vui lòng thử lại với một chủ đề khác."
    text_to_speech_google(default_text, language='vi', save_timestamp=save_timestamp)
    
    return fallback_response

def main():
    # Default configuration file path
    config_file = "APIvsCURL.txt"
    
    # Extract API key from configuration file
    try:
        gemini_api_key = extract_api_key(config_file)
    except Exception as e:
        print(f"Lỗi khi đọc API key: {str(e)}")
        print("Vui lòng đảm bảo tệp APIvsCURL.txt tồn tại và chứa khóa Gemini API của bạn.")
        sys.exit(1)
    
    # Check if gtts is available
    if not GTTS_AVAILABLE:
        print("CẢNH BÁO: Thư viện gTTS chưa được cài đặt. Vui lòng cài đặt bằng lệnh: pip install gtts")
        print("Voice sẽ không được tạo cho đến khi bạn cài đặt gTTS.")
    
    print("Chào mừng đến với Trình tạo kịch bản YouTube bằng Gemini!")
    print("Nhập chủ đề và nhấn Enter để tạo kịch bản YouTube. Nhập 'exit' để thoát.")
    print("Kịch bản sẽ được định dạng với các phần [tiêu đề] và [nội dung].")
    print("Phiên bản nâng cấp: Đã tối ưu cho video 20 phút, không giới hạn ký tự")
    print("Phản hồi mới nhất sẽ được lưu vào file 'responses/gemini_latest_response.txt'.")
    
    # Default to not saving timestamp (overwrite files)
    save_with_timestamp = False
    use_content_only = False  # Set to False by default to read entire response
    
    if GTTS_AVAILABLE:
        print("Google Text-to-Speech đã được kích hoạt. Kịch bản sẽ được chuyển thành giọng nói.")
        print("File âm thanh sẽ được lưu vào thư mục 'audio/gemini_latest_speech.mp3'.")
        print("Hỗ trợ chuyển đổi văn bản dài không bị giới hạn ký tự.")
    
    print("-" * 50)
    print("Tùy chọn:")
    print("Nhập 'timestamp on' để lưu file với timestamp duy nhất")
    print("Nhập 'timestamp off' để ghi đè file cũ (mặc định)")
    print("Nhập 'content on' để chỉ đọc phần [nội dung]")
    print("Nhập 'content off' để đọc toàn bộ phản hồi (mặc định)")
    print("Nhập 'test' để kiểm tra chức năng tạo file âm thanh")
    print("-" * 50)
    
    while True:
        user_input = input("Chủ đề: ")
        
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("Tạm biệt!")
            break
        
        if user_input.lower() == 'timestamp on':
            save_with_timestamp = True
            print("Đã BẬT chế độ timestamp: Mỗi file sẽ được lưu với timestamp duy nhất.")
            continue
            
        if user_input.lower() == 'timestamp off':
            save_with_timestamp = False
            print("Đã TẮT chế độ timestamp: File mới sẽ ghi đè phiên bản trước.")
            continue
            
        if user_input.lower() == 'content on':
            use_content_only = True
            print("Đã BẬT chế độ chỉ đọc nội dung: Chỉ phần [nội dung] sẽ được chuyển thành giọng nói.")
            continue
            
        if user_input.lower() == 'content off':
            use_content_only = False
            print("Đã TẮT chế độ chỉ đọc nội dung: Toàn bộ phản hồi sẽ được chuyển thành giọng nói.")
            continue
        
        if user_input.lower() == 'test':
            print("Đang kiểm tra chức năng tạo file âm thanh...")
            test_text = "Xin chào! Đây là bài kiểm tra chuyển đổi văn bản thành giọng nói bằng Google Text-to-Speech. Nếu bạn có thể nghe thấy thông điệp này, có nghĩa là chức năng đang hoạt động bình thường."
            audio_file = text_to_speech_google(test_text, language='vi', save_timestamp=False)
            if audio_file:
                print(f"Đã tạo file âm thanh thành công: {audio_file}")
                print("Vui lòng mở file này để kiểm tra chất lượng giọng nói")
            else:
                print("Cảnh báo: Không thể tạo file âm thanh. Xem thông báo lỗi ở trên.")
            continue
        
        if user_input.strip():
            print("Đang tạo kịch bản YouTube...")
            response = send_to_gemini(gemini_api_key, user_input, save_with_timestamp, use_content_only)
            print("\n" + response)
            print("-" * 50)

if __name__ == "__main__":
    main() 