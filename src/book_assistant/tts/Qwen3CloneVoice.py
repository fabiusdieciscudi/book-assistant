#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: © 2026-present Fabius Dieciscudi
# SPDX-License-Identifier: MIT

from ..Commons import log, debug, single_channel, set_debug
from pathlib import Path
from qwen_asr import Qwen3ASRModel
from qwen_asr.inference.qwen3_asr import ASRTranscription
from typing import List
import argparse
import soundfile as sf
import torch
from Qwen3TTS import Qwen3TTS, CLONE_PROMPT


def extract_row(file, string):
    debug(f"extract_row({file}, {string})")
    with open(file, 'r', encoding='utf-8') as f:
        for line in f:
            if string in line:
                return line.rstrip('\n')
    return None


def transcribe_audio(audio_path: str) ->  List[ASRTranscription]:
    try:
        asr_model = Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-1.7B", dtype=torch.bfloat16, device_map="mps", local_files_only=True)
    except:
        debug(f"Loading model: Qwen/Qwen3-ASR-1.7B")
        asr_model = Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-1.7B", dtype=torch.bfloat16, device_map="mps", local_files_only=False)
        debug(">>>> done")

    return asr_model.transcribe(audio=audio_path, language="italian", return_time_stamps=False)

def test_voice(clone_prompt_file: str, text: str, output_wav: str):
    tts = Qwen3TTS(clone_prompt_file, "italian")
    chunk = tts.generate_single_chunk(text)
    sf.write(output_wav, single_channel(chunk), tts.sample_rate())


def clone_voce():
    set_debug(True)
    parser = argparse.ArgumentParser(description="BookAssistant")
    commands = ["clone", "test"]
    parser.add_argument("command", choices=commands, help=f"Command: {commands})")
    parser.add_argument("--csv", help="The CSV catalog of sample recordings.")
    parser.add_argument("--csv-ref-audio", help="The name of the sample recording to process (must be present in the CSV file).")
    parser.add_argument("--text", help="The text to render for the test file.")
    parser.add_argument("--voice-name", help="The name of the clone prompt file.")
    parser.add_argument("--output", help="The name of the test file to output.")

    args = parser.parse_args()
    clone_prompt_file = args.voice_name

    if args.command == "clone":
        log("Cloning voice...")
        csv = Path(args.csv)
        ref_audio = args.csv_ref_audio
        line = extract_row(csv, ref_audio).rstrip('\n').split('|')
        ref_text = line[2]
        log(f"ref audio: {ref_audio}, text: {ref_text}")
        ref_audio_file = str(csv.parent / ref_audio)
        if not ref_text:
            log("No reference text - will automatically transcribe")
            transcription = transcribe_audio(ref_audio_file)
            ref_text = " ".join(item.text for item in transcription).strip()
            debug(f"Transcription: {ref_text}")
        model = Qwen3TTS(CLONE_PROMPT, "italian")
        model.clone_voice(ref_audio_file, ref_text, clone_prompt_file)
        log("Generating test...")
        test_voice(clone_prompt_file, args.text, args.output)
    else:
        log(f"Generating {args.output}")
        test_voice(clone_prompt_file, args.text, args.output)

clone_voce()