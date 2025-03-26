# Gemini YouTube Script Generator

This tool uses Gemini AI to create YouTube video scripts. It automatically generates 20-minute video scripts with formatted title and content sections in English.

## Requirements

- Python 3
- `requests` library (install with `pip install requests`)

## Configuration

The tool reads API keys from the `APIvsCURL.txt` file. Make sure this file contains API keys in the format:

```
API:YOUR_GEMINI_API_KEY
ELEVENLABS:YOUR_ELEVENLABS_API_KEY
```

If you don't have an ElevenLabs API key, the tool will automatically add a placeholder to the configuration file that you can update later.

## Usage

### On Windows:

1. Open PowerShell or Command Prompt
2. Navigate to the folder containing the scripts
3. Run the tool:

```
.\gemini-chat.ps1
```

Or directly with Python:

```
python gemini_chat.py
```

### On Linux/macOS:

1. Open Terminal
2. Navigate to the folder containing the scripts
3. Make scripts executable:

```
chmod +x gemini-chat.sh
```

4. Run the tool:

```
./gemini-chat.sh
```

Or directly with Python:

```
python3 gemini_chat.py
```

## How to Use

1. When prompted, enter a topic for your YouTube video
2. The tool will generate a complete script formatted with:
   - [title] - Title section
   - [content] - Content section containing only spoken dialogue (no scene descriptions or filming directions)
3. The script is designed for a 20-minute YouTube video sharing interesting knowledge
4. All of the following characters will be automatically removed from the text:
   - Asterisks (*)
   - Time codes (e.g., 7:30-8:00)
   - Time patterns (e.g., 7:30, 12:45)
   - Square brackets [] and their contents (except [title] and [content])
   - Parentheses () and their contents
5. Type 'exit', 'quit', or 'bye' to exit the tool
6. All responses are in English

## Response Storage Feature

This tool stores only the most recent chat:

1. Both versions of the response are saved:
   - **Original version** - Raw text as returned from the Gemini API
   - **Cleaned version** - Text after removing all unwanted formatting

2. Information is stored in a fixed file:
   ```
   responses/gemini_latest_response.txt
   ```

3. The file includes:
   - Requested topic
   - Original Gemini response
   - Cleaned response
   - Response creation time

Each time you generate a new script, the old file will be overwritten by the latest response.

## Text-to-Speech Feature

This tool integrates with ElevenLabs to convert scripts to speech:

1. **Automatic language detection**:
   - Automatically detects if the text is in Vietnamese and selects an appropriate voice
   - Uses English voice for non-Vietnamese text

2. **Converts only the content section to speech**:
   - The tool extracts the [content] section from the script to create the audio file
   - Skips the title and other sections

3. **Audio file storage**:
   - Audio file is always saved with the same fixed name:
   ```
   audio/gemini_latest_speech.mp3
   ```
   - Each time you generate a new script, the old audio file will be overwritten
   - File format: MP3

4. **Configuration**:
   - You need to add your ElevenLabs API key to the `APIvsCURL.txt` file to use this feature
   - If no ElevenLabs API key is provided, the text-to-speech feature will be disabled

5. **Multilingual support**:
   - Uses the eleven_multilingual_v2 model to support multiple languages
   - Automatically selects the appropriate voice based on text content 