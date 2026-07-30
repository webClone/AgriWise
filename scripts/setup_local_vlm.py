"""
setup_local_vlm.py — Automatic Local LLM Setup Script
======================================================

Pulls Gemma 4 4B for Ollama, or downloads llama-server.exe
and quantized model file for standalone offline use.
"""
import os
import sys
import zipfile
import urllib.request
import json
import time

OLLAMA_URL = "http://localhost:11434"
LLAMA_CPP_ZIP_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b3000/llama-b3000-bin-win-avx2-x64.zip"
MODEL_GGUF_URL = "https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"

LOCAL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "local_llm")


def check_ollama_running() -> bool:
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False


def pull_ollama_model(model_name: str = "gemma-4-4b"):
    print(f"[*] Ollama detected. Pulling local model '{model_name}'...")
    url = f"{OLLAMA_URL}/api/pull"
    data = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("status") == "success":
                print(f"[+] Successfully pulled '{model_name}' to local Ollama registry.")
                return True
            else:
                print(f"[-] Pull response: {res_data}")
    except Exception as e:
        print(f"[-] Failed to pull model via Ollama API: {e}")
    return False


def download_with_progress(url: str, dest_path: str, filename: str):
    print(f"[*] Downloading {filename}...")
    
    def report(block_num, block_size, total_size):
        read_so_far = block_num * block_size
        if total_size > 0:
            percent = min(100, read_so_far * 100 / total_size)
            sys.stdout.write(f"\r  +- Progress: {percent:.1f}% ({read_so_far / (1024*1024):.1f}MB / {total_size / (1024*1024):.1f}MB)")
        else:
            sys.stdout.write(f"\r  +- Downloaded: {read_so_far / (1024*1024):.1f}MB")
        sys.stdout.flush()

    urllib.request.urlretrieve(url, dest_path, reporthook=report)
    print(f"\n[+] Saved to {dest_path}\n")


def get_latest_llama_cpp_url() -> str:
    print("[*] Querying GitHub for latest llama.cpp release...")
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if "bin-win-cpu-x64.zip" in name or "bin-win-avx2-x64.zip" in name:
                    url = asset.get("browser_download_url")
                    print(f"[+] Found latest release asset: {name}")
                    return url
    except Exception as e:
        print(f"[-] GitHub API error: {e}.")
    print("[*] Falling back to precompiled b3000 release...")
    return "https://github.com/ggml-org/llama.cpp/releases/download/b3000/llama-b3000-bin-win-avx2-x64.zip"


def setup_standalone():
    print("[*] Setting up standalone llama.cpp server for Windows...")
    os.makedirs(LOCAL_DIR, exist_ok=True)

    zip_path = os.path.join(LOCAL_DIR, "llama_cpp.zip")
    model_path = os.path.join(LOCAL_DIR, "gemma-4-4b-it-Q4_K_M.gguf")

    # 1. Download llama.cpp binary
    if not os.path.exists(os.path.join(LOCAL_DIR, "llama-server.exe")):
        download_url = get_latest_llama_cpp_url()
        download_with_progress(download_url, zip_path, "llama.cpp binaries")
        print("[*] Extracting llama.cpp zip...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Only extract necessary executables and DLLs to save space
            for file in zip_ref.namelist():
                if "llama-server.exe" in file or file.endswith(".dll"):
                    # Extract to flat directory
                    filename = os.path.basename(file)
                    if filename:
                        with open(os.path.join(LOCAL_DIR, filename), "wb") as f_out:
                            f_out.write(zip_ref.read(file))
        os.remove(zip_path)
        print("[+] Binary extraction complete.")

    # 2. Download Gemma 4 4B GGUF
    if not os.path.exists(model_path):
        download_with_progress(MODEL_GGUF_URL, model_path, "Gemma 4 4B-it Quantized GGUF (Q4_K_M)")

    # 3. Create local runner script
    bat_path = os.path.join(LOCAL_DIR, "run_local_llm.bat")
    with open(bat_path, "w") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("echo Starting Local Gemma 4 4B Server on port 8080...\n")
        f.write("llama-server.exe -m gemma-4-4b-it-Q4_K_M.gguf --port 8080 --host 127.0.0.1 --n-gpu-layers 0\n")
    
    print(f"[+] Standalone LLM runner set up at: {bat_path}")
    print("[!] You can launch the server by running the batch script above, then setting USE_LOCAL_LLM=true in your .env.")


def main():
    print("=" * 60)
    print("AgriBrain Local LLM Installer (Gemma 4 4B)")
    print("=" * 60)
    
    if check_ollama_running():
        success = pull_ollama_model("gemma-4-4b")
        if success:
            print("\n[+] Local LLM is fully set up through Ollama! Set USE_LOCAL_LLM=true in .env to use it.")
            return
        else:
            print("[-] Ollama pull failed. Falling back to standalone setup...")

    setup_standalone()


if __name__ == "__main__":
    main()
