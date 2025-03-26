#!/usr/bin/env python3
import os
import sys
import requests
import re

def extract_elevenlabs_api_key(file_path):
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            match = re.search(r'ELEVENLABS:([\w-]+)', content)
            if match:
                return match.group(1)
            else:
                print("ElevenLabs API key not found.")
                return None
    except FileNotFoundError:
        print(f"Error: Configuration file {file_path} not found.")
        return None

def test_elevenlabs(api_key):
    """Simple test of ElevenLabs API"""
    if not api_key:
        print("ElevenLabs API key not configured.")
        return False
    
    # Create audio directory if it doesn't exist
    if not os.path.exists('audio'):
        os.makedirs('audio')
    
    # Simple test text
    test_text = "This is a test of the ElevenLabs voice generation API."
    
    # Default English voice
    voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
    
    # Test output file
    output_file = "audio/test_voice.mp3"
    
    # API endpoint
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    # Headers
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    # Request body
    data = {
        "text": test_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    
    print(f"Making test request to ElevenLabs API...")
    print(f"API Key (first 4 chars): {api_key[:4]}...")
    print(f"Voice ID: {voice_id}")
    
    try:
        # Make the API request
        response = requests.post(url, json=data, headers=headers)
        
        # Print response details for debugging
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Save the audio file
            with open(output_file, 'wb') as f:
                f.write(response.content)
            
            # Check if file was created
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"Success! Test voice file created: {output_file}")
                print(f"File size: {os.path.getsize(output_file)} bytes")
                return True
            else:
                print(f"Error: File not created or is empty.")
                return False
        else:
            print(f"API Error: {response.status_code}")
            print(f"Response body: {response.text}")
            return False
    
    except Exception as e:
        print(f"Exception: {str(e)}")
        return False

if __name__ == "__main__":
    # Get API key
    config_file = "APIvsCURL.txt"
    api_key = extract_elevenlabs_api_key(config_file)
    
    if api_key:
        print(f"Found ElevenLabs API key in config file.")
        success = test_elevenlabs(api_key)
        if success:
            print("ElevenLabs API test successful! Voice file generated.")
        else:
            print("ElevenLabs API test failed. Check the output above for details.")
    else:
        print("No ElevenLabs API key found. Please add a valid key to your config file.") 