Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
