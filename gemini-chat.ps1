# PowerShell script to run Gemini Chat

# Check if the Python script exists
if (-not (Test-Path -Path "gemini_chat.py")) {
    Write-Host "Error: gemini_chat.py not found"
    exit 1
}

# Check if Python is installed
try {
    $pythonVersion = python --version
    python gemini_chat.py
}
catch {
    try {
        $pythonVersion = python3 --version
        python3 gemini_chat.py
    }
    catch {
        Write-Host "Error: Python not found. Please install Python 3."
        exit 1
    }
} 