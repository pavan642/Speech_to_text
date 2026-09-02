Using Model coedit-large for rewriting the text and correcting the grammer

Installed local LLM in this use case 

#. Summary
#
# This desktop application captures speech from a microphone, converts it to text, cleans up its grammar, and displays both versions side-by-side.
#
# **Core Functionality & Architecture**
#
# * **User Interface (`PyQt5`):** Displays a dual-panel text view (**Original Text** on the left, **Grammar Corrected Text** on the right), a status indicator, audio controls (**Mic ON / Mic OFF**), and utility action buttons (**Copy Original**, **Copy Corrected**, **Clear**, and **Close**).
# * **Audio Capture (`sounddevice` & `numpy`):** Captures single-channel PCM audio at 16 kHz during active recording and compiles the buffer frames into a flattened $1\text{D}$ array when **Mic OFF** is pressed.
# * **Transcription Engine (`faster-whisper`):** Processes the raw audio array using a quantized (`int8`) Whisper Base model on the CPU to extract a fast, raw text transcription.
# * **Grammar & Beautification (`transformers` & `Grammarly CoEdIT`):** Uses `grammarly/coedit-large` to polish the output. To prevent text truncation on long transcriptions, a regex function splits the transcript into sentence-level chunks ($\le 150$ characters), passes each chunk through the model with the prompt `"Fix grammatical errors in this text: "`, and reassembles the corrected output.
# * **Multithreading & Logging:** Executes AI operations asynchronously inside background threads (`ProcessingWorker`) to keep the desktop window responsive. Uses PyQt signals (`pyqtSignal`) for thread-safe UI updates and logs runtime steps directly to `sys.stdout`.

How to Run 

# libraries to install 
# pip3 install PyQt5 faster-whisper sounddevice numpy transformers torch
# to Run 
# 
# To run : python3 SpeechToText.py


