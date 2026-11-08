import tempfile
import unittest
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import wave
from pathlib import Path

from speech_extractor.audio import copy_wav_fragment
from speech_extractor.config import DEFAULT_WHISPER_MODEL, build_model_choices
from speech_extractor.exporter import export_project, sanitized_export_stem
from speech_extractor.project import ProjectError, create_project, list_projects, move_project_to_trash, open_project, snapshot_chunks, undo_last
from speech_extractor.utils import sanitize_component
from speech_extractor import transcribe as transcribe_module


class CoreTests(unittest.TestCase):

    def test_model_defaults_and_choice_order(self):
        self.assertEqual(DEFAULT_WHISPER_MODEL, "Systran/faster-whisper-large-v3")
        choices = build_model_choices([
            "custom/local-model",
            "openai/whisper-large-v3",
            "seastar105/whisper-medium-komixv2",
        ])
        self.assertNotIn("openai/whisper-large-v3", choices)
        # KomiX belongs at the end of built-in choices, not after cached custom models.
        self.assertEqual(choices[5], "seastar105/whisper-medium-komixv2")
        self.assertLess(choices.index("seastar105/whisper-medium-komixv2"), choices.index("custom/local-model"))
        self.assertEqual(choices.count("seastar105/whisper-medium-komixv2"), 1)
    def test_sanitize_component(self):
        self.assertEqual(sanitize_component('a/b\\c:*?"<>|'), "a_b_c_______")
        self.assertEqual(sanitize_component("CON"), "_CON")
        self.assertEqual(sanitize_component("name. "), "name")

    def test_wav_fragment_copies_exact_pcm_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "reference.wav"
            dst = root / "cut.wav"
            samples = bytes(range(256)) * 100
            with wave.open(str(src), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(samples)
            copy_wav_fragment(src, dst, 0.001, 0.003)
            with wave.open(str(dst), "rb") as wf:
                self.assertEqual(wf.getnframes(), 96)
                self.assertEqual(wf.readframes(96), samples[96:96 + 192])

    def test_project_create_and_discover_depth_two(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "Project"
            source = Path(td) / "source.mp4"
            source.write_bytes(b"dummy")
            project_dir, data = create_project(root, "Test Project", source,
                                               "faster-whisper defaults", "openai/whisper-large-v3", True)
            self.assertTrue((project_dir / "info.json").is_file())
            self.assertEqual(len(list_projects(root)), 1)
            nested = root / "nested" / "deeper"
            nested.mkdir(parents=True)
            (nested / "info.json").write_text('{"name":"Should not appear"}')
            self.assertEqual(len(list_projects(root)), 1)
            opened = open_project(project_dir)
            self.assertEqual(opened["name"], "Test Project")
            self.assertEqual(opened["source"], str(source.resolve()))

    def test_blank_project_name_uses_sanitized_source_stem(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source?name.mp4"
            source.write_bytes(b"dummy")
            _folder, data = create_project(root / "Project", "   ", source, None,
                                           "openai/whisper-large-v3", True)
            self.assertEqual(data["name"], "source_name")

    def test_blank_project_name_falls_back_to_uuid_if_source_stem_is_empty(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / " .wav"
            source.write_bytes(b"dummy")
            _folder, data = create_project(root / "Project", "", source, None,
                                           "openai/whisper-large-v3", True)
            self.assertRegex(data["name"], r"^[0-9a-f]{8}-[0-9a-f-]{27}$")

    def test_invalid_project_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.wav"
            source.write_bytes(b"dummy")
            with self.assertRaises(ProjectError):
                create_project(root / "Project", "Bad/Name", source, None,
                               "openai/whisper-large-v3", True)

    def test_custom_whisper_parameters_are_forwarded_to_faster_whisper(self):
        received = {}

        class FakeWhisperModel:
            def __init__(self, model_path, device, compute_type):
                pass

            def transcribe(self, reference_path, **kwargs):
                received.update(kwargs)
                segment = SimpleNamespace(start=0.0, end=1.0, text="test")
                info = SimpleNamespace(language="en", language_probability=1.0,
                                       duration=1.0, duration_after_vad=1.0)
                return iter([segment]), info

        fake_module = ModuleType("faster_whisper")
        fake_module.WhisperModel = FakeWhisperModel
        custom = {
            "beam_size": 5,
            "temperature": 0.5,
            "condition_on_previous_text": False,
            "compression_ratio_threshold": 2.4,
            "log_prob_threshold": -1.0,
            "no_speech_threshold": 0.6,
        }
        with patch.dict(sys.modules, {"faster_whisper": fake_module}), \
             patch.object(transcribe_module, "configure_windows_cuda_runtime", return_value=[]), \
             patch.object(transcribe_module, "detect_device", return_value=("cpu", "int8")), \
             patch.object(transcribe_module, "resolve_model", return_value="resolved-model"):
            chunks, _metadata = transcribe_module.transcribe_reference(
                Path("reference.wav"), "model-id", None,
                whisper_parameters=custom,
            )

        self.assertEqual(len(chunks), 1)
        for key, value in custom.items():
            self.assertEqual(received[key], value)
        self.assertTrue(received["vad_filter"])
        self.assertTrue(received["word_timestamps"])
        self.assertEqual(received["task"], "transcribe")

    def test_project_persists_custom_whisper_parameters(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.wav"
            source.write_bytes(b"dummy")
            params = {
                "beam_size": 5,
                "temperature": 0.5,
                "condition_on_previous_text": False,
                "compression_ratio_threshold": 2.4,
                "log_prob_threshold": -1.0,
                "no_speech_threshold": 0.6,
            }
            _folder, data = create_project(
                root / "Project", "Whisper settings", source, None,
                "seastar105/whisper-medium-komixv2", True,
                whisper_settings=params,
            )
            self.assertEqual(data["settings"]["whisper_parameters"], params)

    def test_project_whisper_parameters_default_to_library_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.wav"
            source.write_bytes(b"dummy")
            _folder, data = create_project(
                root / "Project", "Default Whisper settings", source, None,
                "Systran/faster-whisper-large-v3", True,
            )
            self.assertEqual(data["settings"]["whisper_parameters"], "faster-whisper defaults")

    def test_export_ignores_reviewed_and_writes_srt(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "project"
            project.mkdir()
            reference = project / "reference.wav"
            with wave.open(str(reference), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(b"\x00\x00" * 48000)
            out = root / "out"
            out.mkdir()
            data = {
                "name": "Demo",
                "speakers": {},
                "chunks": [
                    {"id": "1", "start": 0.0, "end": 0.5, "speaker": "", "corrected_text": "hello/world", "original_text": "hello", "reviewed": False, "status": True},
                    {"id": "2", "start": 0.5, "end": 0.75, "speaker": "", "corrected_text": "hello/world", "original_text": "world", "reviewed": True, "status": True},
                    {"id": "3", "start": 0.75, "end": 0.9, "speaker": "", "corrected_text": "inactive", "original_text": "inactive", "reviewed": True, "status": False},
                ],
            }
            export_project(data, project, out, numbered=False, make_zip=True)
            names = sorted(p.name for p in out.glob("*.wav"))
            self.assertEqual(names, ["hello_world.wav", "hello_world2.wav"])
            srt = (out / "ai_subtitle.srt").read_text(encoding="utf-8-sig")
            self.assertIn("hello/world", srt)
            self.assertEqual(srt.count(" --> "), 2)
            self.assertTrue((out / "Demo.zip").is_file())


    def test_numbered_export_width_uses_total_active_fragment_count(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            project = root / "project"
            project.mkdir()
            reference = project / "reference.wav"
            with wave.open(str(reference), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(b"\x00\x00" * 48000)

            # Nine active fragments use one digit; ten use two digits.
            for total, expected_first, expected_last in (
                (9, "1_part 0.wav", "9_part 8.wav"),
                (10, "01_part 0.wav", "10_part 9.wav"),
                (100, "001_part 0.wav", "100_part 99.wav"),
            ):
                out = root / f"out_{total}"
                out.mkdir()
                data = {
                    "name": "Numbering",
                    "speakers": {},
                    "chunks": [
                        {
                            "id": str(index),
                            "start": index * 0.005,
                            "end": (index + 1) * 0.005,
                            "speaker": "",
                            "corrected_text": f"part {index}",
                            "original_text": "",
                            "reviewed": False,
                            "status": True,
                        }
                        for index in range(total)
                    ],
                }
                export_project(data, project, out, numbered=True, make_zip=False)
                names = {path.name for path in out.glob("*.wav")}
                self.assertIn(expected_first, names)
                self.assertIn(expected_last, names)
                self.assertEqual(len(names), total)


    def test_project_trash_uses_existing_absolute_directory(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td) / "Project" / "test-project"
            project_dir.mkdir(parents=True)
            with patch("speech_extractor.project.send2trash.send2trash") as trash:
                move_project_to_trash(project_dir)
            trash.assert_called_once_with(str(project_dir.resolve()))

    def test_project_trash_rejects_non_directory(self):
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "not-a-project"
            file_path.write_text("x")
            with self.assertRaises(ProjectError):
                move_project_to_trash(file_path)

    def test_soft_delete_snapshot_can_be_undone(self):
        data = {"chunks": [{"id": "1", "status": True, "corrected_text": "false positive"}], "history": []}
        snapshot_chunks(data, "delete")
        data["chunks"][0]["status"] = False
        self.assertFalse(data["chunks"][0]["status"])
        self.assertTrue(undo_last(data))
        self.assertTrue(data["chunks"][0]["status"])

    def test_empty_name_and_truncation(self):
        self.assertEqual(sanitized_export_stem("///")[0], "___")
        self.assertEqual(sanitized_export_stem(" ")[0], "")
        stem, truncated = sanitized_export_stem("a" * 101)
        self.assertEqual(len(stem), 100)
        self.assertTrue(truncated)


if __name__ == "__main__":
    unittest.main()
